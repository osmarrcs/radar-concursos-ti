import unittest

from radar_concursos.discovery import candidate_from_item, merge_discoveries


class DiscoveryTests(unittest.TestCase):
    def test_creates_candidate_from_official_edital(self):
        item = {
            "organ_id": "tjpe",
            "title": "Edital nº 7 do concurso TJPE 2026",
            "url": "https://www.tjpe.jus.br/edital-7-2026.pdf",
            "event_type": "edital",
            "provider": "fontes_oficiais",
            "source_label": "TJPE",
            "official": True,
            "confidence": "alta",
        }
        candidate = candidate_from_item(item)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["organ_id"], "tjpe")
        self.assertEqual(candidate["year"], 2026)
        self.assertEqual(candidate["edital_number"], "7")
        self.assertEqual(candidate["status"], "Edital publicado")
        self.assertFalse(candidate["structured"])

    def test_merge_does_not_duplicate_same_candidate(self):
        item = {
            "organ_id": "tjpe",
            "title": "Edital nº 7 do concurso TJPE 2026",
            "url": "https://www.tjpe.jus.br/edital-7-2026.pdf?utm_source=x",
            "event_type": "edital",
            "provider": "fontes_oficiais",
            "source_label": "TJPE",
            "official": True,
        }
        rows, added, changed = merge_discoveries([], [item, item])
        self.assertEqual(len(rows), 1)
        self.assertEqual(added, 1)
        self.assertGreaterEqual(changed, 0)


if __name__ == "__main__":
    unittest.main()
