import unittest

from radar_concursos.catalog import career_options, open_contests, organ_options
from radar_concursos.repository import load_dataset
from radar_concursos.research import research_selected_positions
from radar_concursos.search.models import ProviderMetrics
from radar_concursos.search.orchestrator import SearchReport


class EmptyOrchestrator:
    def search_organ(self, organ, **kwargs):
        return SearchReport(
            organ_id=organ["id"], query=organ["acronym"], items=[],
            metrics={
                "duration_ms": 1, "providers_enabled": 1, "provider_attempts": 1,
                "provider_successes": 1, "provider_failures": 0, "items_scanned": 0,
                "relevant_items": 0, "official_items": 0, "errors": 0, "providers": [],
            }, errors=[], searched_at="2026-08-03T00:00:00+00:00",
        )


class HierarchyOpenResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_dataset()

    def test_national_police_career_contains_pf_and_abin(self):
        careers = career_options(self.data, scope_mode="national")
        self.assertIn("Carreiras Policiais e Inteligência", careers)
        ids = {x["id"] for x in organ_options(self.data, scope_mode="national", career="Carreiras Policiais e Inteligência")}
        self.assertTrue({"pf", "prf", "abin"}.issubset(ids))

    def test_states_filter_career_then_organ(self):
        ids = {x["id"] for x in organ_options(self.data, scope_mode="states", state="PE", career="Tribunais")}
        self.assertIn("tjpe", ids)
        self.assertNotIn("dataprev", ids)

    def test_ufpe_is_open_edital(self):
        ids = {row["contest"]["id"] for row in open_contests(self.data, scope_mode="states", state="PE")}
        self.assertIn("ufpe-concurso-tae-ufpe-2026-edital-no-12-2026-2026", ids)

    def test_metric_research_limits_two_positions(self):
        contest = next(x for x in self.data["contests"]["contests"] if x["id"].startswith("ufpe-concurso"))
        organ = next(x for x in self.data["organs"]["organs"] if x["id"] == "ufpe")
        positions = [x for x in self.data["positions"]["positions"] if x["contest_id"] == contest["id"]][:3]
        with self.assertRaises(ValueError):
            research_selected_positions(organ, contest, positions, orchestrator=EmptyOrchestrator())

    def test_metric_research_returns_three_core_fields(self):
        contest = next(x for x in self.data["contests"]["contests"] if x["id"].startswith("ufpe-concurso"))
        organ = next(x for x in self.data["organs"]["organs"] if x["id"] == "ufpe")
        position = next(x for x in self.data["positions"]["positions"] if x["contest_id"] == contest["id"])
        result = research_selected_positions(organ, contest, [position], orchestrator=EmptyOrchestrator())[0]
        self.assertTrue(hasattr(result, "vacancy"))
        self.assertTrue(hasattr(result, "last_called_name"))
        self.assertTrue(hasattr(result, "last_called_score"))


if __name__ == "__main__":
    unittest.main()
