"""Offline unit tests: no provider tokens or external datasets are required."""
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import researcher


class LiteratureTest(unittest.TestCase):
    def test_normalize_and_abstract(self):
        raw = {
            "id": "https://openalex.org/W123",
            "title": "Spatial validation",
            "doi": "https://doi.org/10.1000/test",
            "publication_year": 2024,
            "authorships": [{"author": {"display_name": "Test Author"}}],
            "abstract_inverted_index": {"Spatial": [0], "validation": [1], "works": [2]},
        }
        paper = researcher.normalize(raw)
        self.assertEqual(paper["abstract"], "Spatial validation works")
        self.assertEqual(paper["doi"], "https://doi.org/10.1000/test")
        self.assertEqual(paper["authors"], ["Test Author"])

    def test_suspicious_url_is_not_accepted(self):
        self.assertEqual(researcher.clean_https("https://doi.org.evil.test/10.1/123", "doi.org"), "")
        self.assertEqual(researcher.clean_https("javascript:alert(1)", "doi.org"), "")

    def test_allowlist_rejects_hallucinated_dois(self):
        papers = [{"doi": "https://doi.org/10.1000/test"}]
        self.assertEqual(researcher.check_ai_citations("Cited [R1] DOI 10.1000/test", papers), [])
        self.assertTrue(researcher.check_ai_citations("[R2] claims DOI 10.8888/fake", papers))

    def test_find_literature_does_not_invent_sources(self):
        raw = {"results": [{
            "id": "https://openalex.org/W123", "title": "Evidence", "doi": None,
            "abstract_inverted_index": {"Evidence": [0]}, "authorships": [],
        }]}
        with patch.object(researcher, "get_json", return_value=raw) as mocked:
            found, fallback = researcher.find_literature("spatial flood prediction", "geoai", 5)
        self.assertEqual(len(found), 1)
        self.assertFalse(fallback)
        self.assertEqual(found[0]["id"], "https://openalex.org/W123")
        self.assertEqual(mocked.call_count, 1)

    def test_draft_never_claims_unrun_experiments(self):
        text = researcher.base_draft("Spatial flood modelling", "geoai", [])
        self.assertIn("Chưa thực hiện thí nghiệm", text)
        self.assertIn("NOT PEER REVIEWED", text)


@unittest.skipUnless(all(importlib.util.find_spec(x) for x in ("pandas", "numpy", "sklearn")),
                     "Optional numerical dependencies not installed")
class SpatialBenchmarkTest(unittest.TestCase):
    def test_spatial_holdout_runs_on_actual_local_csv(self):
        from experiments.spatial_benchmark import run
        with tempfile.TemporaryDirectory() as tmp:
            csvfile = Path(tmp) / "user_data.csv"
            with csvfile.open("w", encoding="utf-8", newline="") as file:
                out = csv.writer(file)
                out.writerow(["lat", "lon", "rainfall", "elevation", "flood_depth"])
                for block in range(8):
                    for row in range(5):
                        out.writerow([
                            10.0 + block * 0.4 + row * 0.01,
                            105.0 + block * 0.3 + row * 0.01,
                            100 + block * 5 + row,
                            2 + block,
                            0.4 * block + row * 0.05,
                        ])
            result = run(str(csvfile), "flood_depth", ["rainfall", "elevation"],
                         "lat", "lon", 0.25, 4, 42)
            self.assertEqual(result["rows_used"], 40)
            self.assertEqual(result["cv_folds"], 4)
            self.assertEqual(len(result["folds"]), 4)
            self.assertIn("random_forest", result["summary"])


if __name__ == "__main__":
    unittest.main()
