from __future__ import annotations

import html
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import http.server
import socketserver
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from .alerts.monitor import run as run_alert_monitor
from .build import build
from .pdf_import import analyze_edital_pdf, copy_attachment, import_selected_positions
from .repository import DATA_DIR, ROOT, load_dataset
from .search.orchestrator import SearchOrchestrator
from .services import (
    add_alert_source,
    save_organ,
    save_search_updates,
    set_alert_selection,
    update_alert_preferences,
)


BRAZIL_STATES = [
    ("Não informar", ""), ("Pernambuco", "PE"), ("Paraíba", "PB"), ("Alagoas", "AL"),
    ("Rio Grande do Norte", "RN"), ("Sergipe", "SE"), ("Ceará", "CE"),
    ("Maranhão", "MA"), ("Nacional", "BR"),
]


class RadarColabApp:
    """Single-screen Colab administration app.

    The notebook only bootstraps this class. All business rules remain in Python modules,
    which removes cell-order dependencies and allows the same logic to be tested.
    """

    def __init__(self, root: Path = ROOT) -> None:
        import ipywidgets as widgets
        from IPython.display import display

        self.widgets = widgets
        self.display = display
        self.root = Path(root)
        self.data_dir = self.root / "data"
        self.documents_dir = self.root / "documents"
        self.orchestrator = SearchOrchestrator()
        self.data: dict[str, Any] = {}
        self.search_report: dict[str, Any] | None = None
        self.pdf_analysis = None
        self.pdf_temp: Path | None = None
        self.server = None
        self.refresh()
        self._build_ui()

    def refresh(self) -> None:
        self.data = load_dataset(self.data_dir)
        self.organs = self.data["organs"]["organs"]
        self.contests = self.data["contests"]["contests"]
        self.positions = self.data["positions"]["positions"]
        self.updates = self.data["updates"]["updates"]

    def organ_by_id(self, organ_id: str) -> dict[str, Any] | None:
        return next((x for x in self.organs if x["id"] == organ_id), None)

    def contest_by_id(self, contest_id: str) -> dict[str, Any] | None:
        return next((x for x in self.contests if x["id"] == contest_id), None)

    def position_by_id(self, position_id: str) -> dict[str, Any] | None:
        return next((x for x in self.positions if x["id"] == position_id), None)

    def _organ_options(self, *, include_new: bool = False) -> list[tuple[str, str]]:
        options = [(f"{x['acronym']} — {x['name']}", x["id"]) for x in sorted(self.organs, key=lambda v: v["name"])]
        return (["+ Cadastrar novo órgão", "__new__"] if False else []) + options

    def _organ_dropdown_options(self, include_new: bool = False) -> list[tuple[str, str]]:
        options = self._organ_options()
        if include_new:
            return [("+ Cadastrar novo órgão", "__new__"), *options]
        return options

    def _build_ui(self) -> None:
        w = self.widgets
        self.header = w.HTML(
            """
            <div style='padding:18px 20px;border-radius:16px;background:#123d2d;color:white'>
              <h2 style='margin:0 0 7px'>Radar de Concursos — Painel único</h2>
              <div style='opacity:.88'>Escolha uma opção. Não é necessário executar outras células em ordem.</div>
            </div>
            """
        )
        self.mode = w.ToggleButtons(
            options=[
                ("1. Concurso na base", "base"),
                ("2. Buscar por órgão", "search"),
                ("3. Adicionar por PDF", "pdf"),
                ("4. Alertas e métricas", "alerts"),
                ("5. Gerar e exportar", "publish"),
            ],
            value="base",
            button_style="",
            layout=w.Layout(width="100%"),
        )
        self.main_output = w.VBox()
        self.mode.observe(self._switch_mode, names="value")
        self.base_panel = self._build_base_panel()
        self.search_panel = self._build_search_panel()
        self.pdf_panel = self._build_pdf_panel()
        self.alert_panel = self._build_alert_panel()
        self.publish_panel = self._build_publish_panel()
        self._switch_mode()

    def show(self) -> "RadarColabApp":
        self.display(self.header, self.mode, self.main_output)
        return self

    def _switch_mode(self, *_: object) -> None:
        mapping = {
            "base": self.base_panel,
            "search": self.search_panel,
            "pdf": self.pdf_panel,
            "alerts": self.alert_panel,
            "publish": self.publish_panel,
        }
        self.main_output.children = (mapping[self.mode.value],)
        if self.mode.value == "base":
            self._refresh_base_options()
        elif self.mode.value == "alerts":
            self._refresh_alert_options()
        elif self.mode.value == "pdf":
            self._refresh_pdf_organs()

    # ---------------- Base ----------------
    def _build_base_panel(self):
        w = self.widgets
        self.base_organ = w.Dropdown(description="Órgão", layout=w.Layout(width="98%"))
        self.base_show_all = w.Checkbox(description="Mostrar todos os concursos", value=False)
        self.base_contest = w.Dropdown(description="Concurso", layout=w.Layout(width="98%"))
        self.base_position = w.Dropdown(description="Cargo", layout=w.Layout(width="98%"))
        self.base_detail = w.HTML()
        self.base_organ.observe(self._base_organ_changed, names="value")
        self.base_show_all.observe(self._base_organ_changed, names="value")
        self.base_contest.observe(self._base_contest_changed, names="value")
        self.base_position.observe(self._base_position_changed, names="value")
        return w.VBox([
            w.HTML("<h3>Consultar concurso já cadastrado</h3><p>Órgão → concurso → todos os cargos do edital → detalhes.</p>"),
            self.base_organ, self.base_show_all, self.base_contest, self.base_position, self.base_detail,
        ])

    def _refresh_base_options(self) -> None:
        current = self.base_organ.value
        self.base_organ.options = self._organ_dropdown_options()
        if current and any(value == current for _, value in self.base_organ.options):
            self.base_organ.value = current
        elif self.base_organ.options:
            self.base_organ.value = self.base_organ.options[0][1]

    def _base_organ_changed(self, *_: object) -> None:
        oid = self.base_organ.value
        contests = sorted([x for x in self.contests if x["organ_id"] == oid], key=lambda x: (x["year"], x.get("publication_date", "")), reverse=True)
        if not self.base_show_all.value:
            contests = contests[:3]
        self.base_contest.options = [(f"{x['year']} — {x['title']} — {x['status']}", x["id"]) for x in contests]
        self.base_detail.value = "<p style='color:#65736c'>Selecione o concurso e o cargo.</p>"
        self._base_contest_changed()

    def _base_contest_changed(self, *_: object) -> None:
        cid = self.base_contest.value
        positions = sorted([x for x in self.positions if x["contest_id"] == cid], key=lambda x: (x["position"], x.get("specialty", "")))
        self.base_position.options = [
            (f"{x['position']}{' / '+x['specialty'] if x.get('specialty') else ''} — {x.get('immediate_vacancies')} vaga(s)", x["id"])
            for x in positions
        ]
        self._base_position_changed()

    def _base_position_changed(self, *_: object) -> None:
        position = self.position_by_id(self.base_position.value or "")
        if not position:
            self.base_detail.value = "<p>Nenhum cargo cadastrado.</p>"
            return
        contest = self.contest_by_id(position["contest_id"]) or {}
        organ = self.organ_by_id(contest.get("organ_id", "")) or {}
        vacancy = position.get("vacancy") or {}
        recent = [x for x in self.updates if x.get("organ_id") == organ.get("id")]
        recent.sort(key=lambda x: (x.get("published_at", ""), x.get("discovered_at", "")), reverse=True)
        update_html = "".join(
            f"<li><a href='{html.escape(x['url'])}' target='_blank'>{html.escape(x['title'])}</a> "
            f"<small>({html.escape(x.get('event_type','noticia'))})</small></li>" for x in recent[:5]
        ) or "<li>Nenhuma atualização automática salva.</li>"
        sources = [*(contest.get("sources") or []), *(position.get("sources") or [])]
        source_html = " ".join(f"<a href='{html.escape(x['url'])}' target='_blank'>{html.escape(x.get('label','Fonte'))}</a>" for x in sources) or "Nenhuma fonte."
        self.base_detail.value = f"""
        <div style='padding:16px;border:1px solid #dce5e0;border-radius:13px'>
          <h3>{html.escape(position['position'])}</h3>
          <p>{html.escape(position.get('specialty',''))}</p>
          <table style='width:100%;border-collapse:collapse'>
            <tr><td><b>Órgão</b></td><td>{html.escape(organ.get('acronym',''))}</td><td><b>Status</b></td><td>{html.escape(contest.get('status',''))}</td></tr>
            <tr><td><b>Vagas</b></td><td>{position.get('immediate_vacancies')}</td><td><b>Validade</b></td><td>{html.escape(contest.get('valid_until') or contest.get('validity_rule','Não localizada'))}</td></tr>
            <tr><td><b>Vacância</b></td><td>{vacancy.get('count') if vacancy.get('count') is not None else 'Não localizada'}</td><td><b>Referência</b></td><td>{html.escape(vacancy.get('reference_date',''))}</td></tr>
            <tr><td><b>Último chamado</b></td><td>{position.get('last_called_rank') or 'Não localizado'}</td><td><b>Nota</b></td><td>{position.get('last_called_score') if position.get('last_called_score') is not None else 'Não localizada'}</td></tr>
          </table>
          <p><b>Fontes:</b> {source_html}</p>
          <h4>Últimas atualizações encontradas para o órgão</h4><ul>{update_html}</ul>
        </div>"""

    # ---------------- Search ----------------
    def _build_search_panel(self):
        w = self.widgets
        organ_names = sorted({x["acronym"] for x in self.organs} | {x["name"] for x in self.organs})
        self.search_state = w.Dropdown(options=BRAZIL_STATES, description="Estado")
        self.search_organ_text = w.Combobox(options=organ_names, description="Órgão", placeholder="Ex.: UFPE", ensure_option=False, layout=w.Layout(width="98%"))
        self.search_days = w.IntSlider(value=90, min=7, max=365, step=7, description="Período", continuous_update=False, readout_format="d")
        self.search_official = w.Checkbox(description="Fontes oficiais cadastradas", value=True)
        self.search_gdelt = w.Checkbox(description="Notícias via GDELT", value=True)
        self.search_qd = w.Checkbox(description="Querido Diário municipal", value=True)
        self.search_button = w.Button(description="Buscar últimas informações", button_style="info", icon="search")
        self.search_results = w.SelectMultiple(options=[], description="Resultados", layout=w.Layout(width="99%", height="330px"))
        self.search_save = w.Button(description="Salvar atualizações selecionadas", button_style="success", disabled=True)
        self.search_pdf = w.Button(description="Analisar PDF selecionado", button_style="warning", disabled=True)
        self.search_output = w.Output()
        self.search_button.on_click(self._run_search)
        self.search_save.on_click(self._save_search_results)
        self.search_pdf.on_click(self._use_search_pdf)
        self.search_results.observe(self._search_selection_changed, names="value")
        return w.VBox([
            w.HTML("<h3>Buscar informações por estado e órgão</h3><p>A busca consulta fontes oficiais cadastradas, GDELT e, quando houver código IBGE municipal, Querido Diário. Resultados são classificados por edital, resultado, homologação, convocação, nomeação, vacância etc.</p>"),
            self.search_state, self.search_organ_text, self.search_days,
            w.HBox([self.search_official, self.search_gdelt, self.search_qd]), self.search_button,
            self.search_results, w.HBox([self.search_save, self.search_pdf]), self.search_output,
        ])

    def _resolve_search_organ(self) -> dict[str, Any]:
        value = (self.search_organ_text.value or "").strip()
        if not value:
            raise ValueError("Informe o órgão ou a sigla.")
        normalized = value.casefold()
        existing = next((x for x in self.organs if x["id"].casefold() == normalized or x["acronym"].casefold() == normalized or x["name"].casefold() == normalized), None)
        if existing:
            return existing
        # Temporary record for discovery. It is only saved when the user saves results or imports a PDF.
        return {
            "id": value.casefold().replace(" ", "-"), "name": value, "acronym": value.upper(),
            "career": "A definir", "sphere": "A definir", "scope": "regional",
            "state": self.search_state.value, "city": "", "alert_sources": [], "official_domains": [], "territory_id": "",
            "temporary": True,
        }

    def _run_search(self, _: object) -> None:
        with self.search_output:
            self.search_output.clear_output()
            try:
                organ = self._resolve_search_organ()
                enabled = set()
                if self.search_official.value: enabled.add("fontes_oficiais")
                if self.search_gdelt.value: enabled.add("gdelt")
                if self.search_qd.value: enabled.add("querido_diario")
                config = self.data["alerts"]
                report = self.orchestrator.search_organ(
                    organ,
                    keywords=config.get("keywords", []),
                    days=self.search_days.value,
                    max_results=config.get("max_results_per_provider", 50),
                    enabled_providers=enabled,
                )
                self.search_report = report.to_dict()
                options = []
                for index, item in enumerate(report.items):
                    official = "OFICIAL" if item.get("official") else "NOTÍCIA"
                    date_text = item.get("published_at") or "sem data"
                    label = f"{official} | {item.get('event_type','noticia').upper()} | {date_text} | {item['title']}"
                    options.append((label, index))
                self.search_results.options = options
                self.search_results.value = tuple(range(len(options))) if len(options) <= 20 else tuple(range(20))
                self.search_save.disabled = not options
                m = report.metrics
                print(f"Consulta: {report.query}")
                print(f"Provedores: {m['provider_successes']}/{m['provider_attempts']} com sucesso")
                print(f"Itens analisados: {m['items_scanned']} | relevantes: {m['relevant_items']} | oficiais: {m['official_items']} | erros: {m['errors']}")
                print(f"Duração: {m['duration_ms']/1000:.1f}s")
                if report.errors:
                    print("\nErros por fonte:")
                    for error in report.errors[:10]:
                        print(f"- {error.get('code')}: {error.get('source')} — {error.get('reason')}")
                if not options:
                    print("\nNenhuma atualização encontrada. Cadastre uma fonte oficial ou use a opção Adicionar por PDF.")
            except Exception as exc:
                print("ERRO NA BUSCA:", exc)

    def _search_selection_changed(self, *_: object) -> None:
        if not self.search_report or not self.search_results.value:
            self.search_pdf.disabled = True
            return
        selected = [self.search_report["items"][i] for i in self.search_results.value]
        self.search_pdf.disabled = not any(str(x.get("url", "")).casefold().split("?", 1)[0].endswith(".pdf") for x in selected)

    def _ensure_search_organ_saved(self) -> dict[str, Any]:
        organ = self._resolve_search_organ()
        if organ.get("temporary"):
            organ = save_organ(
                organ["name"], organ["acronym"],
                overrides={"state": self.search_state.value, "scope": "national" if self.search_state.value == "BR" else "regional"},
                data_dir=self.data_dir,
            )
            self.refresh()
        return organ

    def _save_search_results(self, _: object) -> None:
        with self.search_output:
            try:
                if not self.search_report or not self.search_results.value:
                    raise ValueError("Selecione ao menos um resultado.")
                organ = self._ensure_search_organ_saved()
                selected = []
                for index in self.search_results.value:
                    item = dict(self.search_report["items"][index])
                    item["organ_id"] = organ["id"]
                    selected.append(item)
                result = save_search_updates(selected, auto_apply=True, data_dir=self.data_dir)
                self.refresh()
                print(f"\nSalvos: {result['added_count']} | vinculados a concurso: {result['linked_count']} | mudanças de status: {len(result['status_changes'])}")
                for change in result["status_changes"]:
                    print(f"- {change['contest_id']}: {change['before']} → {change['after']}")
            except Exception as exc:
                print("ERRO AO SALVAR:", exc)

    def _use_search_pdf(self, _: object) -> None:
        with self.search_output:
            try:
                if not self.search_report:
                    raise ValueError("Faça uma busca primeiro.")
                selected = [self.search_report["items"][i] for i in self.search_results.value]
                item = next((x for x in selected if str(x.get("url", "")).casefold().split("?", 1)[0].endswith(".pdf")), None)
                if not item:
                    raise ValueError("Nenhum PDF selecionado.")
                target = Path("/content") / "edital-descoberto.pdf"
                request = Request(item["url"], headers={"User-Agent": "radar-concursos-ti/1.1"})
                with urlopen(request, timeout=45) as response:
                    target.write_bytes(response.read())
                organ = self._ensure_search_organ_saved()
                self._analyze_pdf_path(target, organ["id"])
                self.mode.value = "pdf"
                print("PDF baixado e encaminhado para a opção Adicionar por PDF.")
            except Exception as exc:
                print("ERRO AO BAIXAR PDF:", exc)

    # ---------------- PDF ----------------
    def _build_pdf_panel(self):
        w = self.widgets
        self.pdf_organ = w.Dropdown(description="Órgão", layout=w.Layout(width="98%"))
        self.pdf_new_name = w.Text(description="Novo nome", layout=w.Layout(width="98%"))
        self.pdf_new_acronym = w.Text(description="Nova sigla")
        self.pdf_new_state = w.Dropdown(options=BRAZIL_STATES, description="Estado")
        self.pdf_upload = w.FileUpload(accept=".pdf", multiple=False, description="Anexar PDF")
        self.pdf_url = w.Text(description="Ou URL PDF", placeholder="https://.../edital.pdf", layout=w.Layout(width="98%"))
        self.pdf_title = w.Text(description="Título", placeholder="Opcional", layout=w.Layout(width="98%"))
        self.pdf_analyze = w.Button(description="Analisar edital", button_style="info")
        self.pdf_positions = w.SelectMultiple(options=[], description="Cargos", layout=w.Layout(width="99%", height="370px"))
        self.pdf_import = w.Button(description="Importar cargos selecionados", button_style="success", disabled=True)
        self.pdf_output = w.Output()
        self.pdf_organ.observe(self._pdf_organ_changed, names="value")
        self.pdf_analyze.on_click(self._pdf_analyze_clicked)
        self.pdf_import.on_click(self._pdf_import_clicked)
        self._refresh_pdf_organs()
        return w.VBox([
            w.HTML("<h3>Adicionar concurso por edital PDF</h3><p>Selecione um órgão existente ou cadastre um novo. O sistema mostra todos os cargos reconhecidos e você escolhe quais importar.</p>"),
            self.pdf_organ, self.pdf_new_name, self.pdf_new_acronym, self.pdf_new_state,
            self.pdf_upload, self.pdf_url, self.pdf_title, self.pdf_analyze, self.pdf_positions, self.pdf_import, self.pdf_output,
        ])

    def _refresh_pdf_organs(self) -> None:
        current = getattr(self, "pdf_organ", None).value if getattr(self, "pdf_organ", None) else None
        if getattr(self, "pdf_organ", None):
            self.pdf_organ.options = self._organ_dropdown_options(include_new=True)
            if current and any(v == current for _, v in self.pdf_organ.options):
                self.pdf_organ.value = current
            else:
                self.pdf_organ.value = self.pdf_organ.options[0][1]
            self._pdf_organ_changed()

    def _pdf_organ_changed(self, *_: object) -> None:
        is_new = self.pdf_organ.value == "__new__"
        self.pdf_new_name.layout.display = "" if is_new else "none"
        self.pdf_new_acronym.layout.display = "" if is_new else "none"
        self.pdf_new_state.layout.display = "" if is_new else "none"

    def _get_pdf_organ_id(self) -> str:
        if self.pdf_organ.value != "__new__":
            return self.pdf_organ.value
        organ = save_organ(
            self.pdf_new_name.value,
            self.pdf_new_acronym.value,
            overrides={"state": self.pdf_new_state.value, "scope": "national" if self.pdf_new_state.value == "BR" else "regional"},
            data_dir=self.data_dir,
        )
        self.refresh(); self._refresh_pdf_organs(); self.pdf_organ.value = organ["id"]
        return organ["id"]

    @staticmethod
    def _uploaded_file(upload_widget) -> tuple[str, bytes]:
        value = upload_widget.value
        if not value:
            raise ValueError("Selecione um PDF ou informe a URL.")
        if isinstance(value, dict):
            name, item = next(iter(value.items()))
            content = item.get("content", b"") if isinstance(item, dict) else item
            return name, bytes(content)
        item = value[0]
        return item.get("name", "edital.pdf"), bytes(item["content"])

    def _pdf_analyze_clicked(self, _: object) -> None:
        with self.pdf_output:
            self.pdf_output.clear_output()
            try:
                organ_id = self._get_pdf_organ_id()
                if self.pdf_url.value.strip():
                    target = Path("/content") / "edital-url.pdf"
                    request = Request(self.pdf_url.value.strip(), headers={"User-Agent": "radar-concursos-ti/1.1"})
                    with urlopen(request, timeout=45) as response:
                        target.write_bytes(response.read())
                else:
                    name, content = self._uploaded_file(self.pdf_upload)
                    target = Path("/content") / Path(name).name
                    target.write_bytes(content)
                self._analyze_pdf_path(target, organ_id)
            except Exception as exc:
                self.pdf_import.disabled = True
                print("ERRO AO ANALISAR:", exc)

    def _analyze_pdf_path(self, path: Path, organ_id: str) -> None:
        analysis = analyze_edital_pdf(path)
        self.pdf_analysis = analysis; self.pdf_temp = path; self.pdf_organ.value = organ_id
        options = []
        for row in analysis.positions:
            label = f"{row['position_code']} — {row['position']}"
            if row.get("specialty"):
                label += f" / {row['specialty']}"
            label += f" — {row['immediate_vacancies']} vaga(s) — {row.get('lotation') or 'lotação geral'}"
            options.append((label, str(row["position_code"])))
        self.pdf_positions.options = options
        self.pdf_positions.value = tuple(value for _, value in options)
        self.pdf_import.disabled = False
        with self.pdf_output:
            print(f"Motor: {analysis.extraction_engine} | cargos reconhecidos: {len(options)}")
            for key, value in analysis.metadata.items():
                if value not in ("", None):
                    print(f"- {key}: {value}")

    def _pdf_import_clicked(self, _: object) -> None:
        with self.pdf_output:
            try:
                if self.pdf_analysis is None or self.pdf_temp is None:
                    raise ValueError("Analise um edital primeiro.")
                if not self.pdf_positions.value:
                    raise ValueError("Selecione ao menos um cargo.")
                organ_id = self._get_pdf_organ_id()
                target = copy_attachment(self.pdf_temp, self.documents_dir, prefix=organ_id, category="editais")
                relative = target.relative_to(self.root).as_posix()
                contest, positions = import_selected_positions(
                    self.pdf_analysis,
                    organ_id=organ_id,
                    selected_codes=list(self.pdf_positions.value),
                    attachment_relative_url=relative,
                    contest_title=self.pdf_title.value.strip() or None,
                    data_dir=self.data_dir,
                )
                self.refresh()
                print(f"Importado: {contest['title']} | {len(positions)} cargo(s).")
                print("Vacância, último chamado e nota permanecem separados e devem ser apurados por fontes próprias.")
            except Exception as exc:
                print("ERRO AO IMPORTAR:", exc)

    # ---------------- Alerts ----------------
    def _build_alert_panel(self):
        w = self.widgets
        self.alert_organs = w.SelectMultiple(description="Órgãos", layout=w.Layout(width="98%", height="220px"))
        self.alert_official = w.Checkbox(description="Fontes oficiais", value=True)
        self.alert_gdelt = w.Checkbox(description="GDELT", value=True)
        self.alert_qd = w.Checkbox(description="Querido Diário", value=True)
        self.alert_days = w.IntSlider(value=90, min=7, max=365, step=7, description="Período")
        self.alert_daily_metrics = w.Checkbox(description="Enviar resumo diário de métricas", value=True)
        self.alert_keywords = w.Textarea(description="Palavras", layout=w.Layout(width="98%", height="120px"))
        self.alert_save = w.Button(description="Salvar configuração", button_style="success")
        self.alert_run = w.Button(description="Executar teste agora", button_style="info")
        self.alert_output = w.Output()
        self.alert_save.on_click(self._save_alerts)
        self.alert_run.on_click(self._test_alerts)
        return w.VBox([
            w.HTML("<h3>Alertas automáticos e métricas</h3><p>Escolha os órgãos. O GitHub Actions fará buscas periódicas, enviará novidades ao Telegram e um resumo diário de métricas. Token e Chat ID ficam nos Secrets do GitHub.</p>"),
            self.alert_organs, w.HBox([self.alert_official, self.alert_gdelt, self.alert_qd]),
            self.alert_days, self.alert_daily_metrics, self.alert_keywords,
            w.HBox([self.alert_save, self.alert_run]), self.alert_output,
        ])

    def _refresh_alert_options(self) -> None:
        config = self.data["alerts"]
        self.alert_organs.options = self._organ_dropdown_options()
        available = {v for _, v in self.alert_organs.options}
        self.alert_organs.value = tuple(x for x in config.get("monitored_organs", []) if x in available)
        providers = config.get("providers", {})
        self.alert_official.value = providers.get("fontes_oficiais", True)
        self.alert_gdelt.value = providers.get("gdelt", True)
        self.alert_qd.value = providers.get("querido_diario", True)
        self.alert_days.value = int(config.get("search_days", 90))
        self.alert_daily_metrics.value = bool(config.get("daily_metrics", True))
        self.alert_keywords.value = "\n".join(config.get("keywords", []))

    def _save_alerts(self, _: object) -> None:
        with self.alert_output:
            self.alert_output.clear_output()
            try:
                config = update_alert_preferences(
                    organ_ids=list(self.alert_organs.value),
                    keywords=self.alert_keywords.value.splitlines(),
                    providers={"fontes_oficiais": self.alert_official.value, "gdelt": self.alert_gdelt.value, "querido_diario": self.alert_qd.value},
                    search_days=self.alert_days.value,
                    daily_metrics=self.alert_daily_metrics.value,
                    data_dir=self.data_dir,
                )
                self.refresh()
                print("Configuração salva.")
                print(f"Órgãos: {len(config['monitored_organs'])} | período: {config['search_days']} dias | métricas diárias: {config['daily_metrics']}")
            except Exception as exc:
                print("ERRO:", exc)

    def _test_alerts(self, _: object) -> None:
        with self.alert_output:
            self.alert_output.clear_output()
            try:
                report = run_alert_monitor(dry_run=True, send_metrics=True, data_dir=self.data_dir)
                print("\nCódigo:", report["code"])
                print("Métricas:", report["metrics"])
            except Exception as exc:
                print("ERRO NO TESTE:", exc)

    # ---------------- Publish ----------------
    def _build_publish_panel(self):
        w = self.widgets
        self.publish_test = w.Button(description="Testar e gerar portal", button_style="success")
        self.publish_preview = w.Button(description="Visualizar portal", button_style="info")
        self.publish_export = w.Button(description="Exportar ZIP", button_style="warning")
        self.publish_output = w.Output()
        self.publish_test.on_click(self._test_and_build)
        self.publish_preview.on_click(self._preview)
        self.publish_export.on_click(self._export)
        return w.VBox([
            w.HTML("<h3>Gerar, visualizar e exportar</h3><p>Os testes e o build são independentes das demais opções. O ZIP não inclui .git, caches ou a pasta dist.</p>"),
            w.HBox([self.publish_test, self.publish_preview, self.publish_export]), self.publish_output,
        ])

    def _test_and_build(self, _: object) -> None:
        with self.publish_output:
            self.publish_output.clear_output()
            try:
                env = dict(os.environ); env["PYTHONPATH"] = str(self.root / "src")
                subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=self.root, env=env, check=True)
                payload = build()
                print(f"Portal gerado: {len(payload['organs'])} órgãos, {len(payload['contests'])} concursos, {len(payload['positions'])} cargos, {len(payload['updates'])} atualizações.")
            except Exception as exc:
                print("ERRO:", exc)

    def _preview(self, _: object) -> None:
        with self.publish_output:
            try:
                build()
                from google.colab import output
                port = 8000
                os.chdir(self.root / "dist")
                if self.server:
                    self.server.shutdown()
                class ReuseTCPServer(socketserver.TCPServer):
                    allow_reuse_address = True
                self.server = ReuseTCPServer(("", port), http.server.SimpleHTTPRequestHandler)
                threading.Thread(target=self.server.serve_forever, daemon=True).start()
                output.serve_kernel_port_as_iframe(port, height=900)
                os.chdir(self.root)
            except Exception as exc:
                print("ERRO NA VISUALIZAÇÃO:", exc)

    def _export(self, _: object) -> None:
        with self.publish_output:
            try:
                from google.colab import files
                export = Path("/content/radar-concursos-ti-atualizado.zip")
                with tempfile.TemporaryDirectory() as tmp:
                    target = Path(tmp) / "radar-concursos-ti"
                    shutil.copytree(
                        self.root, target,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache", ".DS_Store", "dist", "alert_last_run.json"),
                    )
                    shutil.make_archive(str(export.with_suffix("")), "zip", root_dir=target)
                print("ZIP gerado:", export)
                files.download(str(export))
            except Exception as exc:
                print("ERRO NA EXPORTAÇÃO:", exc)


def launch(root: str | Path = ROOT) -> RadarColabApp:
    return RadarColabApp(Path(root)).show()
