import unittest

from radar_concursos.catalog import latest_contests, organ_options, positions_for_contest, search_catalog
from radar_concursos.repository import load_dataset


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_dataset()

    def test_organ_selection_is_independent_from_contest(self):
        organs = organ_options(self.data)
        self.assertTrue(any(item["id"] == "ifpe" for item in organs))
        self.assertTrue(any(item["id"] == "ufpe" for item in organs))

    def test_latest_contests_returns_three_by_default_when_requested(self):
        contests = latest_contests(self.data, "ifpe", limit=3)
        self.assertEqual(len(contests), 3)
        years = [item["year"] for item in contests]
        self.assertEqual(years, sorted(years, reverse=True))

    def test_all_contests_can_be_requested(self):
        all_items = latest_contests(self.data, "ifpe", limit=None)
        limited = latest_contests(self.data, "ifpe", limit=3)
        self.assertGreaterEqual(len(all_items), len(limited))

    def test_positions_are_loaded_after_contest(self):
        contest = latest_contests(self.data, "ufpe", limit=1)[0]
        positions = positions_for_contest(self.data, contest["id"])
        self.assertGreaterEqual(len(positions), 1)

    def test_general_catalog_search_does_not_require_organ(self):
        results = search_catalog(self.data, query="UFPE redes")
        self.assertTrue(results)
        self.assertTrue(all(row["organ"]["id"] == "ufpe" for row in results))
        self.assertTrue(any("redes" in (row["position"].get("specialty", "").casefold()) for row in results))

    def test_general_catalog_search_filters_state(self):
        results = search_catalog(self.data, query="tecnologia", state="PE")
        self.assertTrue(results)
        self.assertTrue(all(row["organ"].get("state") == "PE" for row in results))


if __name__ == "__main__":
    unittest.main()
