from __future__ import annotations

import html
import http.server
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from .alerts.monitor import run as run_alert_monitor
from .build import build
from .catalog import (
    career_options,
    latest_contests,
    open_contests,
    organ_options,
    positions_for_contest,
    search_catalog,
)
from .pdf_import import analyze_edital_pdf, copy_attachment, import_selected_positions
from .repository import ROOT, load_dataset
from .research import research_selected_positions
from .search.orchestrator import SearchOrchestrator
from .services import save_organ, save_search_updates, update_alert_preferences

BRAZIL_STATES = [
    ("Todos", ""), ("Pernambuco", "PE"), ("Paraíba", "PB"), ("Alagoas", "AL"),
    ("Rio Grande do Norte", "RN"), ("Sergipe", "SE"), ("Ceará", "CE"),
    ("Maranhão", "MA"),
]


def _fmt(value: Any, fallback: str = "Não localizado") -> str:
    return fallback if value in (None, "") else html.escape(str(value))


def _links(items: list[dict[str, Any]]) -> str:
    valid = [item for item in items if item.get("url")]
    if not valid:
        return "<span style='color:#65736c'>Nenhum link encontrado.</span>"
    return " ".join(
        f"<a href='{html.escape(str(item['url']))}' target='_blank'>{html.escape(str(item.get('label') or item.get('title') or 'Fonte'))}</a>"
        for item in valid
    )


class RadarColabApp:
    """Painel único do Colab; todas as regras permanecem em módulos testáveis."""

    def __init__(self, root: Path = ROOT) -> None:
        import ipywidgets as widgets
        from IPython.display import display

        self.widgets = widgets
        self.display = display
        self.root = Path(root)
        self.data_dir = self.root / "data"
        self.documents_dir = self.root / "documents"
        self.orchestrator = SearchOrchestrator()
        self.server = None
        self.search_report: dict[str, Any] | None = None
        self.pdf_analysis = None
        self.pdf_temp: Path | None = None
        self.pdf_duplicate_id = ""
        self.refresh()
        self._build_ui()

    def refresh(self) -> None:
        self.data = load_dataset(self.data_dir)
        self.organs = self.data["organs"]["organs"]
        self.contests = self.data["contests"]["contests"]
        self.positions = self.data["positions"]["positions"]
        self.updates = self.data["updates"]["updates"]

    def organ_by_id(self, oid: str) -> dict[str, Any] | None:
        return next((x for x in self.organs if x["id"] == oid), None)

    def contest_by_id(self, cid: str) -> dict[str, Any] | None:
        return next((x for x in self.contests if x["id"] == cid), None)

    def position_by_id(self, pid: str) -> dict[str, Any] | None:
        return next((x for x in self.positions if x["id"] == pid), None)

    def _build_ui(self) -> None:
        w = self.widgets
        self.header = w.HTML("""
        <div style='padding:18px 20px;border-radius:16px;background:#123d2d;color:white'>
          <h2 style='margin:0 0 7px'>Radar de Concursos — painel administrativo</h2>
          <div style='opacity:.9'>O fluxo principal começa por âmbito, carreira e órgão. O PDF é apenas uma alternativa quando o concurso ainda não existe na base.</div>
        </div>""")
        self.mode = w.ToggleButtons(
            options=[
                ("1. Histórico por órgão", "history"),
                ("2. Editais em aberto", "open"),
                ("3. Pesquisa automática", "search"),
                ("4. Adicionar PDF faltante", "pdf"),
                ("5. Alertas", "alerts"),
                ("6. Gerar/Publicar", "publish"),
            ],
            value="history", layout=w.Layout(width="100%"),
        )
        self.main = w.VBox()
        self.history_panel = self._build_history_panel()
        self.open_panel = self._build_open_panel()
        self.search_panel = self._build_search_panel()
        self.pdf_panel = self._build_pdf_panel()
        self.alert_panel = self._build_alert_panel()
        self.publish_panel = self._build_publish_panel()
        self.mode.observe(self._switch_mode, names="value")
        self._switch_mode()

    def show(self):
        self.display(self.header, self.mode, self.main)
        return self

    def _switch_mode(self, *_: object) -> None:
        mapping = {
            "history": self.history_panel, "open": self.open_panel, "search": self.search_panel,
            "pdf": self.pdf_panel, "alerts": self.alert_panel, "publish": self.publish_panel,
        }
        self.main.children = (mapping[self.mode.value],)
        self.refresh()
        if self.mode.value == "history":
            self._history_refresh_hierarchy()
        elif self.mode.value == "open":
            self._open_refresh_hierarchy()
        elif self.mode.value == "search":
            self._search_refresh_hierarchy()
        elif self.mode.value == "pdf":
            self._pdf_refresh_organs()
        elif self.mode.value == "alerts":
            self._alerts_refresh()

    # ---------- shared hierarchy ----------
    def _toggle_state(self, scope_widget, state_widget) -> None:
        state_widget.layout.display = "" if scope_widget.value == "states" else "none"
        if scope_widget.value == "national":
            state_widget.value = ""

    # ---------- history ----------
    def _build_history_panel(self):
        w = self.widgets
        self.h_scope = w.ToggleButtons(options=[("Nacional", "national"), ("Estados", "states")], value="national", description="Âmbito")
        self.h_state = w.Dropdown(options=BRAZIL_STATES, description="Estado")
        self.h_career = w.Dropdown(description="Carreira", layout=w.Layout(width="98%"))
        self.h_organ = w.Dropdown(description="Órgão", layout=w.Layout(width="98%"))
        self.h_summary = w.HTML()
        self.h_auto_search = w.Checkbox(description="Buscar automaticamente quando houver menos de 3 concursos", value=True)
        self.h_remote_button = w.Button(description="Atualizar histórico e publicações", button_style="info", icon="refresh")
        self.h_remote_results = w.SelectMultiple(description="Achados online", layout=w.Layout(width="99%", height="230px"))
        self.h_remote_save = w.Button(description="Salvar achados selecionados", button_style="success", disabled=True)
        self.h_remote_output = w.Output()
        self.h_remote_items: list[dict[str, Any]] = []
        self.h_all = w.ToggleButton(description="Ver todos os concursos", value=False, icon="list")
        self.h_contest = w.Select(description="Concursos", layout=w.Layout(width="99%", height="200px"))
        self.h_position = w.Select(description="Cargos", layout=w.Layout(width="99%", height="250px"))
        self.h_detail = w.HTML()
        self.h_query = w.Text(description="Busca geral", placeholder="Órgão, edital, ano, cargo, especialidade, lotação...", layout=w.Layout(width="98%"))
        self.h_query_button = w.Button(description="Pesquisar em toda a base", button_style="info", icon="search")
        self.h_query_results = w.Select(description="Resultados", layout=w.Layout(width="99%", height="250px"))
        self.h_query_open = w.Button(description="Abrir resultado", button_style="success", disabled=True)
        self.h_query_info = w.HTML()
        self.h_rows: list[dict[str, Any]] = []

        for widget in (self.h_scope, self.h_state):
            widget.observe(self._history_refresh_hierarchy, names="value")
        self.h_career.observe(self._history_refresh_organs, names="value")
        self.h_organ.observe(self._history_organ_changed, names="value")
        self.h_all.observe(self._history_organ_changed, names="value")
        self.h_contest.observe(self._history_contest_changed, names="value")
        self.h_position.observe(self._history_position_changed, names="value")
        self.h_remote_button.on_click(self._history_remote_search)
        self.h_remote_results.observe(lambda *_: setattr(self.h_remote_save, "disabled", not bool(self.h_remote_results.value)), names="value")
        self.h_remote_save.on_click(self._history_remote_save)
        self.h_query_button.on_click(self._history_general_search)
        self.h_query_results.observe(lambda *_: setattr(self.h_query_open, "disabled", self.h_query_results.value in (None, -1)), names="value")
        self.h_query_open.on_click(self._history_open_result)

        return w.VBox([
            w.HTML("<h3>Histórico: âmbito → carreira → órgão → concurso → cargo</h3><p>No âmbito nacional, escolha a carreira, por exemplo <b>Carreiras Policiais e Inteligência</b>, e depois PF, PRF ou ABIN. Em Estados, escolha primeiro o estado. Por padrão aparecem os três concursos mais recentes.</p>"),
            self.h_scope, self.h_state, self.h_career, self.h_organ, self.h_summary,
            self.h_auto_search, self.h_remote_button, self.h_remote_results, self.h_remote_save, self.h_remote_output,
            self.h_all, self.h_contest, self.h_position, self.h_detail,
            w.HTML("<hr><h3>Busca geral na base</h3><p>Esta pesquisa não exige selecionar órgão e funciona sem internet.</p>"),
            self.h_query, self.h_query_button, self.h_query_results, self.h_query_open, self.h_query_info,
        ])

    def _history_refresh_hierarchy(self, *_: object) -> None:
        self.refresh(); self._toggle_state(self.h_scope, self.h_state)
        careers = career_options(self.data, scope_mode=self.h_scope.value, state=self.h_state.value or "")
        current = self.h_career.value
        self.h_career.options = [("Selecione uma carreira...", ""), *[(x, x) for x in careers]]
        self.h_career.value = current if current in careers else ""
        self._history_refresh_organs()

    def _history_refresh_organs(self, *_: object) -> None:
        current = self.h_organ.value or ""
        items = organ_options(self.data, scope_mode=self.h_scope.value, state=self.h_state.value or "", career=self.h_career.value or "")
        options = [("Selecione um órgão...", ""), *[(f"{x['acronym']} — {x['name']}", x["id"]) for x in items]]
        self.h_organ.options = options
        values = {v for _, v in options}
        self.h_organ.value = current if current in values else ""
        if not self.h_organ.value:
            self.h_contest.options = [("Selecione um órgão primeiro", "")]
            self.h_position.options = [("Selecione um concurso primeiro", "")]
            self.h_summary.value = "<p style='color:#65736c'>Selecione a carreira e o órgão.</p>"
            self.h_detail.value = ""

    def _history_organ_changed(self, *_: object) -> None:
        oid = self.h_organ.value or ""
        if not oid:
            return
        organ = self.organ_by_id(oid) or {}
        all_items = latest_contests(self.data, oid, limit=None)
        shown = all_items if self.h_all.value else all_items[:3]
        self.h_contest.options = [("Selecione um concurso...", ""), *[
            (f"{c.get('year')} — {c.get('title')} | {c.get('status')} | {c.get('valid_until') or c.get('validity_rule') or 'validade não localizada'}", c["id"])
            for c in shown
        ]]
        self.h_contest.value = ""; self.h_position.options = [("Selecione um concurso primeiro", "")]
        mode = "todos" if self.h_all.value else "até os 3 mais recentes"
        shortage = max(0, 3 - len(all_items))
        warning = f"<br><b>Faltam {shortage} concurso(s) para completar o histórico mínimo.</b> A busca automática será executada." if shortage else ""
        self.h_summary.value = f"<div style='padding:12px;background:#f4f8f6;border-radius:10px'><b>{html.escape(organ.get('acronym',''))} — {html.escape(organ.get('name',''))}</b><br>{len(all_items)} concurso(s) estruturado(s) na base; exibindo {mode}.{warning}</div>"
        self.h_detail.value = "<p style='color:#65736c'>Selecione um concurso.</p>"
        self.h_remote_items = []
        self.h_remote_results.options = []
        self.h_remote_save.disabled = True
        if shortage and self.h_auto_search.value:
            self._history_remote_search(None)

    def _history_remote_search(self, _: object | None) -> None:
        oid = self.h_organ.value or ""
        with self.h_remote_output:
            self.h_remote_output.clear_output()
            if not oid:
                print("Selecione um órgão antes da busca online.")
                return
            organ = self.organ_by_id(oid) or {}
            try:
                report = self.orchestrator.search_organ(
                    organ,
                    keywords=["concurso", "edital", "resultado final", "homologação", "convocação", "nomeação", "validade"],
                    days=3650,
                    max_results=120,
                    enabled_providers={"fontes_oficiais", "gdelt", "querido_diario"},
                )
                self.h_remote_items = report.items
                self.h_remote_results.options = [
                    (f"{'OFICIAL' if item.get('official') else 'NOTÍCIA'} | {item.get('event_type')} | {item.get('title')}", index)
                    for index, item in enumerate(self.h_remote_items)
                ]
                self.h_remote_results.value = ()
                self.h_remote_save.disabled = True
                metrics = report.metrics
                print(f"Órgão: {organ.get('acronym')} | achados relevantes: {len(self.h_remote_items)} | oficiais: {metrics.get('official_items', 0)} | erros: {metrics.get('errors', 0)}")
                print("Selecione os links úteis e salve. Editais em PDF podem ser encaminhados para a aba 'Adicionar PDF faltante'.")
                for error in report.errors[:10]:
                    print("ERRO:", error)
            except Exception as exc:
                print("ERRO NA BUSCA DO HISTÓRICO:", exc)

    def _history_remote_save(self, _: object) -> None:
        with self.h_remote_output:
            selected = [self.h_remote_items[index] for index in self.h_remote_results.value]
            if not selected:
                print("Selecione ao menos um achado.")
                return
            result = save_search_updates(selected, auto_apply=False, data_dir=self.data_dir)
            self.refresh()
            print(f"Achados novos salvos: {result['added_count']}. Eles passam a aparecer como evidências e atualizações do órgão.")

    def _history_contest_changed(self, *_: object) -> None:
        cid = self.h_contest.value or ""
        if not cid:
            return
        rows = positions_for_contest(self.data, cid)
        self.h_position.options = [("Selecione um cargo/especialidade...", ""), *[
            (f"{x.get('position')}{' / '+x.get('specialty','') if x.get('specialty') else ''} — {_fmt(x.get('immediate_vacancies'))} vaga(s)", x["id"])
            for x in rows
        ]]
        self.h_position.value = ""
        self.h_detail.value = f"<p style='color:#65736c'>{len(rows)} cargo(s) cadastrado(s). Todos são exibidos, sem filtro por TI.</p>"

    def _detail_html(self, position: dict[str, Any]) -> str:
        contest = self.contest_by_id(position["contest_id"]) or {}
        organ = self.organ_by_id(contest.get("organ_id", "")) or {}
        vacancy = position.get("vacancy") or {}
        sources = [*(contest.get("sources") or []), *(position.get("sources") or []), *(vacancy.get("sources") or [])]
        updates = [x for x in self.updates if x.get("organ_id") == organ.get("id")]
        updates.sort(key=lambda x: (x.get("published_at", ""), x.get("discovered_at", "")), reverse=True)
        update_links = _links([{"label": x.get("title"), "url": x.get("url")} for x in updates[:6]])
        return f"""
        <div style='padding:16px;border:1px solid #dce5e0;border-radius:13px'>
          <h3>{html.escape(position.get('position',''))}</h3><p>{html.escape(position.get('specialty',''))}</p>
          <table style='width:100%;border-collapse:collapse'>
            <tr><td><b>Órgão</b></td><td>{html.escape(organ.get('acronym',''))}</td><td><b>Concurso</b></td><td>{html.escape(contest.get('title',''))}</td></tr>
            <tr><td><b>Status</b></td><td>{html.escape(contest.get('status',''))}</td><td><b>Validade</b></td><td>{html.escape(contest.get('valid_until') or contest.get('validity_rule') or 'Não localizada')}</td></tr>
            <tr><td><b>Vagas</b></td><td>{_fmt(position.get('immediate_vacancies'))}</td><td><b>Vacância</b></td><td>{_fmt(vacancy.get('count'))}</td></tr>
            <tr><td><b>Último convocado</b></td><td>{_fmt(position.get('last_called_name'))}</td><td><b>Classificação</b></td><td>{_fmt(position.get('last_called_rank'))}</td></tr>
            <tr><td><b>Nota</b></td><td>{_fmt(position.get('last_called_score'))}</td><td><b>Nomeados</b></td><td>{_fmt(position.get('total_appointed'))}</td></tr>
          </table>
          <p><b>Fontes:</b> {_links(sources)}</p><p><b>Atualizações automáticas:</b> {update_links}</p>
        </div>"""

    def _history_position_changed(self, *_: object) -> None:
        position = self.position_by_id(self.h_position.value or "")
        if position:
            self.h_detail.value = self._detail_html(position)

    def _history_general_search(self, _: object) -> None:
        self.h_rows = search_catalog(self.data, query=self.h_query.value, limit=500)
        self.h_query_results.options = [("Selecione um resultado...", -1), *[
            (f"{r['organ'].get('acronym')} | {r['contest'].get('year')} | {r['position'].get('position')}{' / '+r['position'].get('specialty','') if r['position'].get('specialty') else ''}", i)
            for i, r in enumerate(self.h_rows)
        ]]
        self.h_query_results.value = -1
        self.h_query_info.value = f"<p><b>{len(self.h_rows)}</b> resultado(s) na base local.</p>"

    def _history_open_result(self, _: object) -> None:
        idx = self.h_query_results.value
        if idx is None or idx < 0:
            return
        row = self.h_rows[idx]
        organ, contest, position = row["organ"], row["contest"], row["position"]
        self.h_scope.value = "national" if organ.get("scope") == "national" else "states"
        if self.h_scope.value == "states": self.h_state.value = organ.get("state") or ""
        self._history_refresh_hierarchy(); self.h_career.value = organ.get("career") or ""; self._history_refresh_organs()
        self.h_organ.value = organ["id"]
        latest_ids = {x["id"] for x in latest_contests(self.data, organ["id"], limit=3)}
        self.h_all.value = contest["id"] not in latest_ids; self._history_organ_changed()
        self.h_contest.value = contest["id"]; self._history_contest_changed(); self.h_position.value = position["id"]

    # ---------- open contests ----------
    def _build_open_panel(self):
        w = self.widgets
        self.o_scope = w.ToggleButtons(options=[("Nacional", "national"), ("Estados", "states")], value="states", description="Âmbito")
        self.o_state = w.Dropdown(options=BRAZIL_STATES, description="Estado", value="PE")
        self.o_career = w.Dropdown(description="Carreira", layout=w.Layout(width="98%"))
        self.o_organ = w.Dropdown(description="Órgão", layout=w.Layout(width="98%"))
        self.o_discover = w.Button(description="Buscar editais abertos agora", button_style="info", icon="search")
        self.o_candidates = w.SelectMultiple(description="Achados online", layout=w.Layout(width="99%", height="220px"))
        self.o_candidates_save = w.Button(description="Salvar achados selecionados", button_style="success", disabled=True)
        self.o_candidates_pdf = w.Button(description="Usar PDF selecionado", button_style="warning", disabled=True)
        self.o_discovery_output = w.Output()
        self.o_candidate_items: list[dict[str, Any]] = []
        self.o_contest = w.Select(description="Editais abertos", layout=w.Layout(width="99%", height="220px"))
        self.o_positions = w.SelectMultiple(description="Escolha até 2", layout=w.Layout(width="99%", height="280px"))
        self.o_days = w.IntSlider(value=730, min=30, max=1825, step=30, description="Busca (dias)")
        self.o_official = w.Checkbox(description="Fontes oficiais", value=True)
        self.o_gdelt = w.Checkbox(description="GDELT", value=True)
        self.o_qd = w.Checkbox(description="Querido Diário", value=True)
        self.o_save = w.Checkbox(description="Salvar links encontrados em Atualizações", value=True)
        self.o_research = w.Button(description="Pesquisar vacância, chamadas e notas", button_style="info", icon="search")
        self.o_info = w.HTML()
        self.o_output = w.Output()
        for x in (self.o_scope, self.o_state): x.observe(self._open_refresh_hierarchy, names="value")
        self.o_career.observe(self._open_refresh_organs, names="value")
        self.o_organ.observe(self._open_refresh_contests, names="value")
        self.o_contest.observe(self._open_contest_changed, names="value")
        self.o_positions.observe(self._open_limit_positions, names="value")
        self.o_discover.on_click(self._open_discover)
        self.o_candidates.observe(self._open_candidate_selection, names="value")
        self.o_candidates_save.on_click(self._open_save_candidates)
        self.o_candidates_pdf.on_click(self._open_use_pdf)
        self.o_research.on_click(self._open_run_research)
        return w.VBox([
            w.HTML("<h3>Concursos com edital em aberto</h3><p>Escolha um edital por vez. O sistema apresenta <b>todos os cargos</b>; você pode comparar no máximo <b>dois cargos/especialidades</b>. A pesquisa automática procura evidências de vacância, último convocado/classificação e nota.</p>"),
            self.o_scope, self.o_state, self.o_career, self.o_organ,
            self.o_discover, self.o_candidates, w.HBox([self.o_candidates_save, self.o_candidates_pdf]), self.o_discovery_output,
            self.o_contest, self.o_positions, self.o_info, self.o_days, w.HBox([self.o_official, self.o_gdelt, self.o_qd]), self.o_save,
            self.o_research, self.o_output,
        ])

    def _open_discover(self, _: object) -> None:
        with self.o_discovery_output:
            self.o_discovery_output.clear_output()
            try:
                organs = organ_options(self.data, scope_mode=self.o_scope.value, state=self.o_state.value or "", career=self.o_career.value or "")
                if self.o_organ.value:
                    organs = [organ for organ in organs if organ["id"] == self.o_organ.value]
                if not organs:
                    raise ValueError("Nenhum órgão corresponde aos filtros.")
                report = self.orchestrator.search_organs(
                    organs[:20],
                    keywords=["edital", "concurso público", "inscrições abertas", "retificação"],
                    days=365,
                    max_results=200,
                    enabled_providers={"fontes_oficiais", "gdelt", "querido_diario"},
                    query_label="Editais em aberto",
                )
                accepted = {"edital", "retificacao", "inscricao"}
                self.o_candidate_items = [item for item in report.items if item.get("event_type") in accepted]
                self.o_candidates.options = [
                    (f"{'OFICIAL' if item.get('official') else 'NOTÍCIA'} | {item.get('event_type')} | {item.get('title')}", index)
                    for index, item in enumerate(self.o_candidate_items)
                ]
                self.o_candidates.value = ()
                self._open_candidate_selection()
                metrics = report.metrics
                print(f"Órgãos consultados: {metrics.get('organs_searched', len(organs))} | editais/inscrições candidatos: {len(self.o_candidate_items)} | oficiais: {metrics.get('official_items', 0)} | erros: {metrics.get('errors', 0)}")
                if not self.o_candidate_items:
                    print("Nenhum edital aberto foi localizado pelos provedores atuais. Veja os erros e confirme as fontes oficiais cadastradas.")
                for error in report.errors[:10]:
                    print("ERRO:", error)
            except Exception as exc:
                print("ERRO NA DESCOBERTA DE EDITAIS:", exc)

    def _open_candidate_selection(self, *_: object) -> None:
        selected = tuple(self.o_candidates.value or ())
        self.o_candidates_save.disabled = not bool(selected)
        is_single_pdf = False
        if len(selected) == 1:
            url = str(self.o_candidate_items[selected[0]].get("url") or "").lower()
            is_single_pdf = ".pdf" in url
        self.o_candidates_pdf.disabled = not is_single_pdf

    def _open_save_candidates(self, _: object) -> None:
        with self.o_discovery_output:
            selected = [self.o_candidate_items[index] for index in self.o_candidates.value]
            result = save_search_updates(selected, auto_apply=False, data_dir=self.data_dir)
            self.refresh()
            print(f"Achados novos salvos: {result['added_count']}.")

    def _open_use_pdf(self, _: object) -> None:
        selected = tuple(self.o_candidates.value or ())
        if len(selected) != 1:
            return
        item = self.o_candidate_items[selected[0]]
        self.mode.value = "pdf"
        self._pdf_refresh_organs()
        organ_id = item.get("organ_id") or ""
        valid = {value for _, value in self.p_organ.options}
        if organ_id in valid:
            self.p_organ.value = organ_id
        self.p_url.value = str(item.get("url") or "")
        with self.p_output:
            self.p_output.clear_output()
            print("PDF descoberto automaticamente. Confirme o órgão e clique em 'Analisar edital'.")

    def _open_refresh_hierarchy(self, *_: object) -> None:
        self.refresh(); self._toggle_state(self.o_scope, self.o_state)
        careers = career_options(self.data, scope_mode=self.o_scope.value, state=self.o_state.value or "")
        self.o_career.options = [("Todas as carreiras", ""), *[(x, x) for x in careers]]
        if self.o_career.value not in careers: self.o_career.value = ""
        self._open_refresh_organs()

    def _open_refresh_organs(self, *_: object) -> None:
        items = organ_options(self.data, scope_mode=self.o_scope.value, state=self.o_state.value or "", career=self.o_career.value or "")
        self.o_organ.options = [("Todos os órgãos", ""), *[(f"{x['acronym']} — {x['name']}", x["id"]) for x in items]]
        self.o_organ.value = ""; self._open_refresh_contests()

    def _open_refresh_contests(self, *_: object) -> None:
        rows = open_contests(self.data, scope_mode=self.o_scope.value, state=self.o_state.value or "", career=self.o_career.value or "", organ_id=self.o_organ.value or "")
        self.o_contest.options = [("Selecione um edital aberto...", ""), *[
            (f"{r['organ'].get('acronym')} | {r['contest'].get('year')} — {r['contest'].get('title')} | {r['contest'].get('status')}", r["contest"]["id"])
            for r in rows
        ]]
        self.o_contest.value = ""; self.o_positions.options = []
        self.o_info.value = f"<p><b>{len(rows)}</b> edital(is) aberto(s) na base para os filtros atuais.</p>"

    def _open_contest_changed(self, *_: object) -> None:
        cid = self.o_contest.value or ""
        rows = positions_for_contest(self.data, cid) if cid else []
        self.o_positions.options = [
            (f"{x.get('position')}{' / '+x.get('specialty','') if x.get('specialty') else ''} — {_fmt(x.get('immediate_vacancies'))} vaga(s)", x["id"])
            for x in rows
        ]
        self.o_positions.value = ()
        self.o_info.value = f"<p>{len(rows)} cargo(s) no edital. Selecione um ou dois.</p>"

    def _open_limit_positions(self, change: dict[str, Any]) -> None:
        values = tuple(change.get("new") or ())
        if len(values) > 2:
            self.o_positions.value = values[:2]
            self.o_info.value = "<p style='color:#9b4b3f'><b>Limite:</b> selecione no máximo dois cargos por edital.</p>"

    def _open_run_research(self, _: object) -> None:
        with self.o_output:
            self.o_output.clear_output()
            try:
                contest = self.contest_by_id(self.o_contest.value or "")
                if not contest: raise ValueError("Selecione um edital aberto.")
                selected = [self.position_by_id(pid) for pid in self.o_positions.value]
                selected = [x for x in selected if x]
                organ = self.organ_by_id(contest["organ_id"]) or {}
                enabled = set()
                if self.o_official.value: enabled.add("fontes_oficiais")
                if self.o_gdelt.value: enabled.add("gdelt")
                if self.o_qd.value: enabled.add("querido_diario")
                results = research_selected_positions(organ, contest, selected, orchestrator=self.orchestrator, days=self.o_days.value, enabled_providers=enabled)
                all_evidence: list[dict[str, Any]] = []
                for result in results:
                    print("\n" + "=" * 80)
                    print(result.position_label)
                    print("Vacância:", result.vacancy if result.vacancy is not None else "não localizada")
                    print("Último convocado:", result.last_called_name or "não localizado")
                    print("Classificação:", result.last_called_rank if result.last_called_rank is not None else "não localizada")
                    print("Nota:", result.last_called_score if result.last_called_score is not None else "não localizada")
                    print("Código:", result.status_code, "—", result.status_reason)
                    for group, items in result.evidence.items():
                        if items:
                            print(f"\n{group.upper()}:")
                            for item in items:
                                print("-", item.get("title"), "\n ", item.get("url"))
                                all_evidence.append(item)
                    print("Métricas da busca:", result.search_metrics)
                if self.o_save.value and all_evidence:
                    saved = save_search_updates(all_evidence, auto_apply=False, data_dir=self.data_dir)
                    self.refresh(); print(f"\nLinks novos salvos: {saved['added_count']}")
            except Exception as exc:
                print("ERRO:", exc)

    # ---------- automatic search ----------
    def _build_search_panel(self):
        w = self.widgets
        self.s_scope = w.ToggleButtons(options=[("Todos", ""), ("Nacional", "national"), ("Estados", "states")], value="", description="Âmbito")
        self.s_state = w.Dropdown(options=BRAZIL_STATES, description="Estado")
        self.s_career = w.Dropdown(description="Carreira", layout=w.Layout(width="98%"))
        self.s_organ = w.Dropdown(description="Órgão", layout=w.Layout(width="98%"))
        self.s_query = w.Text(description="Termo", placeholder="Ex.: edital, técnico judiciário, segurança, convocação...", layout=w.Layout(width="98%"))
        self.s_days = w.IntSlider(value=180, min=7, max=1825, step=7, description="Período")
        self.s_limit = w.IntSlider(value=10, min=1, max=50, description="Máx. órgãos")
        self.s_official = w.Checkbox(description="Fontes oficiais", value=True)
        self.s_gdelt = w.Checkbox(description="GDELT", value=True)
        self.s_qd = w.Checkbox(description="Querido Diário", value=True)
        self.s_button = w.Button(description="Pesquisar automaticamente", button_style="info", icon="search")
        self.s_results = w.SelectMultiple(description="Resultados", layout=w.Layout(width="99%", height="350px"))
        self.s_save = w.Button(description="Salvar resultados selecionados", button_style="success", disabled=True)
        self.s_metrics = w.HTML(); self.s_output = w.Output(); self.s_items: list[dict[str, Any]] = []
        for x in (self.s_scope, self.s_state): x.observe(self._search_refresh_hierarchy, names="value")
        self.s_career.observe(self._search_refresh_organs, names="value")
        self.s_button.on_click(self._search_run); self.s_results.observe(self._search_selection, names="value"); self.s_save.on_click(self._search_save)
        return w.VBox([
            w.HTML("<h3>Pesquisa automática geral</h3><p>Procure um órgão específico, uma carreira inteira ou vários órgãos cadastrados. Esta é a função principal para localizar editais, resultados, convocações, nomeações e vacância; o PDF é apenas complemento.</p>"),
            self.s_scope, self.s_state, self.s_career, self.s_organ, self.s_query, self.s_days, self.s_limit,
            w.HBox([self.s_official, self.s_gdelt, self.s_qd]), self.s_button, self.s_metrics,
            self.s_results, self.s_save, self.s_output,
        ])

    def _search_refresh_hierarchy(self, *_: object) -> None:
        self.refresh(); self.s_state.layout.display = "" if self.s_scope.value in ("", "states") else "none"
        if self.s_scope.value == "national": self.s_state.value = ""
        careers = career_options(self.data, scope_mode=self.s_scope.value, state=self.s_state.value or "")
        self.s_career.options = [("Todas as carreiras", ""), *[(x, x) for x in careers]]
        if self.s_career.value not in careers: self.s_career.value = ""
        self._search_refresh_organs()

    def _search_refresh_organs(self, *_: object) -> None:
        items = organ_options(self.data, scope_mode=self.s_scope.value, state=self.s_state.value or "", career=self.s_career.value or "")
        self.s_organ.options = [("Todos os órgãos filtrados", ""), *[(f"{x['acronym']} — {x['name']}", x["id"]) for x in items]]
        self.s_organ.value = ""

    def _search_run(self, _: object) -> None:
        with self.s_output:
            self.s_output.clear_output()
            try:
                items = organ_options(self.data, scope_mode=self.s_scope.value, state=self.s_state.value or "", career=self.s_career.value or "")
                if self.s_organ.value:
                    items = [x for x in items if x["id"] == self.s_organ.value]
                items = items[: self.s_limit.value]
                if not items: raise ValueError("Nenhum órgão corresponde aos filtros.")
                enabled = set()
                if self.s_official.value: enabled.add("fontes_oficiais")
                if self.s_gdelt.value: enabled.add("gdelt")
                if self.s_qd.value: enabled.add("querido_diario")
                keywords = [self.s_query.value.strip()] if self.s_query.value.strip() else ["concurso edital resultado convocação nomeação vacância"]
                report = self.orchestrator.search_organs(items, keywords=keywords, days=self.s_days.value, max_results=200, enabled_providers=enabled, query_label="Pesquisa geral")
                self.s_items = report.items
                self.s_results.options = [(f"{'OFICIAL' if x.get('official') else 'NOTÍCIA'} | {x.get('event_type')} | {x.get('title')}", i) for i, x in enumerate(self.s_items)]
                self.s_results.value = (); self.s_save.disabled = True
                m = report.metrics
                self.s_metrics.value = f"<div style='padding:12px;background:#f4f8f6;border-radius:10px'><b>Órgãos:</b> {m.get('organs_searched', len(items))} | <b>Itens analisados:</b> {m.get('items_scanned',0)} | <b>Relevantes:</b> {m.get('relevant_items',0)} | <b>Oficiais:</b> {m.get('official_items',0)} | <b>Erros:</b> {m.get('errors',0)} | <b>Duração:</b> {m.get('duration_ms',0)/1000:.1f}s</div>"
                for error in report.errors[:10]: print("ERRO:", error)
            except Exception as exc:
                print("ERRO NA PESQUISA:", exc)

    def _search_selection(self, *_: object) -> None:
        self.s_save.disabled = not bool(self.s_results.value)

    def _search_save(self, _: object) -> None:
        with self.s_output:
            selected = [self.s_items[i] for i in self.s_results.value]
            result = save_search_updates(selected, data_dir=self.data_dir)
            self.refresh(); print(f"Resultados novos salvos: {result['added_count']} | vinculados: {result['linked_count']}")

    # ---------- PDF fallback ----------
    def _build_pdf_panel(self):
        w = self.widgets
        self.p_organ = w.Dropdown(description="Órgão", layout=w.Layout(width="98%"))
        self.p_new_name = w.Text(description="Novo órgão", placeholder="Nome completo", layout=w.Layout(width="98%"))
        self.p_new_acronym = w.Text(description="Sigla", layout=w.Layout(width="50%"))
        self.p_new_state = w.Dropdown(options=[("Nacional", "BR"), *BRAZIL_STATES[1:]], description="Estado")
        self.p_upload = w.FileUpload(accept=".pdf", multiple=False, description="Selecionar PDF")
        self.p_url = w.Text(description="URL PDF", layout=w.Layout(width="98%"))
        self.p_title = w.Text(description="Título opcional", layout=w.Layout(width="98%"))
        self.p_force = w.Checkbox(description="Atualizar mesmo se o edital já existir", value=False)
        self.p_analyze = w.Button(description="Analisar edital", button_style="info")
        self.p_positions = w.SelectMultiple(description="Cargos", layout=w.Layout(width="99%", height="350px"))
        self.p_import = w.Button(description="Importar cargos selecionados", button_style="success", disabled=True)
        self.p_output = w.Output()
        self.p_analyze.on_click(self._pdf_analyze); self.p_import.on_click(self._pdf_import)
        return w.VBox([
            w.HTML("<h3>Adicionar por PDF — somente quando faltar na base</h3><p>Antes, use <b>Pesquisa automática</b>. Esta opção serve para anexar um edital que não foi encontrado ou para corrigir uma importação incompleta.</p>"),
            self.p_organ, self.p_new_name, w.HBox([self.p_new_acronym, self.p_new_state]), self.p_upload, self.p_url, self.p_title, self.p_force,
            self.p_analyze, self.p_positions, self.p_import, self.p_output,
        ])

    def _pdf_refresh_organs(self) -> None:
        self.p_organ.options = [("+ Cadastrar novo órgão", "__new__"), *[(f"{x['acronym']} — {x['name']}", x["id"]) for x in sorted(self.organs, key=lambda x: x["name"])]]
        self.p_organ.value = self.p_organ.options[1][1] if len(self.p_organ.options) > 1 else "__new__"

    @staticmethod
    def _uploaded_file(widget) -> tuple[str, bytes]:
        value = widget.value
        if not value: raise ValueError("Selecione um PDF ou informe uma URL.")
        if isinstance(value, dict):
            name, item = next(iter(value.items())); content = item.get("content", b"") if isinstance(item, dict) else item
            return name, bytes(content)
        item = value[0]; return item.get("name", "edital.pdf"), bytes(item["content"])

    def _pdf_organ_id(self) -> str:
        if self.p_organ.value != "__new__": return self.p_organ.value
        organ = save_organ(self.p_new_name.value, self.p_new_acronym.value, overrides={"state": self.p_new_state.value, "scope": "national" if self.p_new_state.value == "BR" else "regional"}, data_dir=self.data_dir)
        self.refresh(); self._pdf_refresh_organs(); self.p_organ.value = organ["id"]; return organ["id"]

    def _pdf_analyze(self, _: object) -> None:
        with self.p_output:
            self.p_output.clear_output(); self.p_import.disabled = True
            try:
                oid = self._pdf_organ_id()
                if self.p_url.value.strip():
                    target = Path("/content/edital-url.pdf")
                    with urlopen(Request(self.p_url.value.strip(), headers={"User-Agent": "radar-concursos-ti/1.3"}), timeout=60) as response: target.write_bytes(response.read())
                else:
                    name, content = self._uploaded_file(self.p_upload); target = Path("/content") / Path(name).name; target.write_bytes(content)
                analysis = analyze_edital_pdf(target); self.pdf_analysis = analysis; self.pdf_temp = target
                year = analysis.metadata.get("year"); number = str(analysis.metadata.get("edital_number") or "")
                duplicate = next((c for c in self.contests if c.get("organ_id") == oid and c.get("year") == year and (not number or str(c.get("edital_number") or "") == number)), None)
                self.pdf_duplicate_id = duplicate["id"] if duplicate else ""
                if duplicate and not self.p_force.value:
                    print(f"ATENÇÃO: o edital parece já existir: {duplicate['title']}. Marque 'Atualizar mesmo...' apenas se deseja corrigir/completar.")
                options = []
                for row in analysis.positions:
                    label = f"{row['position_code']} — {row['position']}{' / '+row.get('specialty','') if row.get('specialty') else ''} — {row['immediate_vacancies']} vaga(s)"
                    options.append((label, str(row["position_code"])))
                self.p_positions.options = options; self.p_positions.value = tuple(v for _, v in options)
                self.p_import.disabled = bool(duplicate and not self.p_force.value)
                print(f"Cargos reconhecidos: {len(options)} | motor: {analysis.extraction_engine}")
                for k, v in analysis.metadata.items():
                    if v not in (None, ""): print(f"- {k}: {v}")
            except Exception as exc:
                print("ERRO AO ANALISAR:", exc)

    def _pdf_import(self, _: object) -> None:
        with self.p_output:
            try:
                if not self.pdf_analysis or not self.pdf_temp: raise ValueError("Analise um edital primeiro.")
                if not self.p_positions.value: raise ValueError("Selecione ao menos um cargo.")
                oid = self._pdf_organ_id(); target = copy_attachment(self.pdf_temp, self.documents_dir, prefix=oid, category="editais")
                contest, positions = import_selected_positions(self.pdf_analysis, organ_id=oid, selected_codes=list(self.p_positions.value), attachment_relative_url=target.relative_to(self.root).as_posix(), contest_title=self.p_title.value.strip() or None, data_dir=self.data_dir)
                self.refresh(); print(f"Importado/atualizado: {contest['title']} | {len(positions)} cargo(s).")
            except Exception as exc:
                print("ERRO AO IMPORTAR:", exc)

    # ---------- alerts ----------
    def _build_alert_panel(self):
        w = self.widgets
        self.a_organs = w.SelectMultiple(description="Órgãos", layout=w.Layout(width="98%", height="260px"))
        self.a_official = w.Checkbox(description="Fontes oficiais", value=True); self.a_gdelt = w.Checkbox(description="GDELT", value=True); self.a_qd = w.Checkbox(description="Querido Diário", value=True)
        self.a_days = w.IntSlider(value=90, min=7, max=1825, step=7, description="Período")
        self.a_daily = w.Checkbox(description="Resumo diário das métricas", value=True)
        self.a_errors = w.Checkbox(description="Alertar erros de pesquisa", value=True)
        self.a_open = w.Checkbox(description="Destacar novos editais abertos", value=True)
        self.a_keywords = w.Textarea(description="Palavras", layout=w.Layout(width="98%", height="120px"))
        self.a_save = w.Button(description="Salvar alertas", button_style="success"); self.a_test = w.Button(description="Testar agora", button_style="info")
        self.a_output = w.Output(); self.a_save.on_click(self._alerts_save); self.a_test.on_click(self._alerts_test)
        return w.VBox([
            w.HTML("<h3>Alertas e métricas automáticas</h3><p>Selecione os órgãos. O GitHub Actions roda a cada seis horas sem depender do Colab e envia novidades e métricas ao Telegram.</p>"),
            self.a_organs, w.HBox([self.a_official, self.a_gdelt, self.a_qd]), self.a_days,
            w.HBox([self.a_daily, self.a_errors, self.a_open]), self.a_keywords, w.HBox([self.a_save, self.a_test]), self.a_output,
        ])

    def _alerts_refresh(self) -> None:
        cfg = self.data["alerts"]
        self.a_organs.options = [(f"{x['acronym']} — {x['name']}", x["id"]) for x in sorted(self.organs, key=lambda x: x["name"])]
        valid = {v for _, v in self.a_organs.options}; self.a_organs.value = tuple(x for x in cfg.get("monitored_organs", []) if x in valid)
        p = cfg.get("providers", {}); self.a_official.value = p.get("fontes_oficiais", True); self.a_gdelt.value = p.get("gdelt", True); self.a_qd.value = p.get("querido_diario", True)
        self.a_days.value = int(cfg.get("search_days", 90)); self.a_daily.value = bool(cfg.get("daily_metrics", True)); self.a_errors.value = bool(cfg.get("notify_errors", True)); self.a_open.value = bool(cfg.get("notify_open_edicts", True)); self.a_keywords.value = "\n".join(cfg.get("keywords", []))

    def _alerts_save(self, _: object) -> None:
        with self.a_output:
            self.a_output.clear_output()
            try:
                cfg = update_alert_preferences(organ_ids=list(self.a_organs.value), keywords=self.a_keywords.value.splitlines(), providers={"fontes_oficiais": self.a_official.value, "gdelt": self.a_gdelt.value, "querido_diario": self.a_qd.value}, search_days=self.a_days.value, daily_metrics=self.a_daily.value, notify_errors=self.a_errors.value, notify_open_edicts=self.a_open.value, data_dir=self.data_dir)
                self.refresh(); print(f"Configuração salva para {len(cfg['monitored_organs'])} órgão(s).")
            except Exception as exc: print("ERRO:", exc)

    def _alerts_test(self, _: object) -> None:
        with self.a_output:
            self.a_output.clear_output()
            try:
                report = run_alert_monitor(dry_run=True, send_metrics=True, data_dir=self.data_dir)
                print("Código:", report["code"]); print("Métricas:", report["metrics"])
            except Exception as exc: print("ERRO:", exc)

    # ---------- publish ----------
    def _build_publish_panel(self):
        w = self.widgets
        self.pub_test = w.Button(description="Testar e gerar portal", button_style="success")
        self.pub_preview = w.Button(description="Visualizar portal", button_style="info")
        self.pub_export = w.Button(description="Exportar ZIP", button_style="warning")
        self.pub_output = w.Output(); self.pub_test.on_click(self._test_build); self.pub_preview.on_click(self._preview); self.pub_export.on_click(self._export)
        return w.VBox([w.HTML("<h3>Gerar, visualizar e exportar</h3><p>Depois de exportar, extraia o ZIP e envie o conteúdo ao repositório. O GitHub Actions publica o site automaticamente.</p>"), w.HBox([self.pub_test, self.pub_preview, self.pub_export]), self.pub_output])

    def _test_build(self, _: object) -> None:
        with self.pub_output:
            self.pub_output.clear_output()
            try:
                env = dict(os.environ); env["PYTHONPATH"] = str(self.root / "src")
                subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=self.root, env=env, check=True)
                payload = build(); print(f"Portal gerado: {len(payload['organs'])} órgãos, {len(payload['contests'])} concursos, {len(payload['positions'])} cargos.")
            except Exception as exc: print("ERRO:", exc)

    def _preview(self, _: object) -> None:
        with self.pub_output:
            try:
                build(); from google.colab import output
                port = 8000
                if self.server: self.server.shutdown()
                handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(*args, directory=str(self.root / "dist"), **kwargs)
                class Reuse(socketserver.TCPServer): allow_reuse_address = True
                self.server = Reuse(("", port), handler); threading.Thread(target=self.server.serve_forever, daemon=True).start()
                output.serve_kernel_port_as_iframe(port, height=900)
            except Exception as exc: print("ERRO:", exc)

    def _export(self, _: object) -> None:
        with self.pub_output:
            try:
                from google.colab import files
                output_path = Path("/content/radar-concursos-ti-atualizado.zip")
                with tempfile.TemporaryDirectory() as tmp:
                    target = Path(tmp) / "radar-concursos-ti"
                    shutil.copytree(self.root, target, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache", ".DS_Store", "dist", "alert_last_run.json"))
                    shutil.make_archive(str(output_path.with_suffix("")), "zip", root_dir=target)
                print("ZIP gerado:", output_path); files.download(str(output_path))
            except Exception as exc: print("ERRO:", exc)


def launch(root: str | Path = ROOT):
    return RadarColabApp(Path(root)).show()
