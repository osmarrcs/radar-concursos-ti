import json
import tempfile
import unittest
from pathlib import Path

from radar_concursos.search.orchestrator import SearchReport
from radar_concursos.sync import sync_organs


class FakeOrchestrator:
    def search_organ(self, organ, **kwargs):
        item = {
            "organ_id": organ["id"],
            "title": f"{organ['acronym']} publica Edital nº 3/2026",
            "url": f"https://{organ['official_domains'][0]}/concurso/edital-3-2026.pdf",
            "event_type": "edital",
            "provider": "fontes_oficiais",
            "source_label": "Fonte oficial",
            "published_at": "2026-08-03",
            "summary": "Concurso público",
            "official": True,
            "confidence": "alta",
            "discovered_at": "2026-08-03T12:00:00+00:00",
        }
        return SearchReport(
            organ_id=organ["id"],
            query=organ["acronym"],
            items=[item],
            metrics={
                "provider_attempts": 1,
                "provider_successes": 1,
                "provider_failures": 0,
                "items_scanned": 1,
                "relevant_items": 1,
                "official_items": 1,
                "errors": 0,
            },
            errors=[],
            searched_at="2026-08-03T12:00:00+00:00",
        )


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        organs = {
            "metadata": {"schema_version": "4.0"},
            "organs": [{
                "id": "tjpe", "name": "Tribunal de Justiça de Pernambuco", "acronym": "TJPE",
                "career": "Tribunais", "sphere": "Estadual", "scope": "regional",
                "state": "PE", "city": "Recife", "alert_sources": [],
                "official_domains": ["tjpe.jus.br"], "territory_id": "",
            }],
        }
        (self.data / "organs.json").write_text(json.dumps(organs), encoding="utf-8")
        (self.data / "contests.json").write_text(json.dumps({"metadata": {}, "contests": []}), encoding="utf-8")
        (self.data / "positions.json").write_text(json.dumps({"metadata": {}, "positions": []}), encoding="utf-8")
        (self.data / "updates.json").write_text(json.dumps({"metadata": {}, "updates": []}), encoding="utf-8")
        (self.data / "alert_config.json").write_text(json.dumps({
            "metadata": {}, "monitored_organs": [], "search_days": 90,
            "daily_metrics": True, "notify_errors": True, "notify_open_edicts": True,
        }), encoding="utf-8")
        (self.data / "discovered_contests.json").write_text(json.dumps({"metadata": {}, "discoveries": []}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_sync_persists_new_update_and_discovery(self):
        report = sync_organs(data_dir=self.data, orchestrator=FakeOrchestrator())
        self.assertEqual(report["metrics"]["updates_added"], 1)
        self.assertEqual(report["metrics"]["discoveries_added"], 1)
        updates = json.loads((self.data / "updates.json").read_text())["updates"]
        discoveries = json.loads((self.data / "discovered_contests.json").read_text())["discoveries"]
        self.assertEqual(len(updates), 1)
        self.assertEqual(len(discoveries), 1)
        self.assertEqual(discoveries[0]["organ_id"], "tjpe")

    def test_second_sync_does_not_duplicate(self):
        sync_organs(data_dir=self.data, orchestrator=FakeOrchestrator())
        report = sync_organs(data_dir=self.data, orchestrator=FakeOrchestrator())
        self.assertEqual(report["metrics"]["updates_added"], 0)
        discoveries = json.loads((self.data / "discovered_contests.json").read_text())["discoveries"]
        self.assertEqual(len(discoveries), 1)


if __name__ == "__main__":
    unittest.main()
