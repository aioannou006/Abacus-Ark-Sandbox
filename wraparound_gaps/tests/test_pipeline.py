"""Unit + end-to-end tests. Run with:  python3 -m unittest discover tests"""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import CONFIG
from pipeline.step2_ofsted import _pick_data_url, load_ofsted_rows
from pipeline.step3_websweep import find_signals
from pipeline.util import (name_tokens, norm_postcode, norm_street,
                           postcode_district, resolve_column)


class TestNormalisation(unittest.TestCase):
    def test_postcode(self):
        self.assertEqual(norm_postcode(" sw18 2pq "), "SW182PQ")
        self.assertEqual(postcode_district("SW18 2PQ"), "SW18")
        self.assertEqual(postcode_district("KT1 2BB"), "KT1")
        self.assertEqual(postcode_district(""), "")
        self.assertEqual(postcode_district("BAD"), "")

    def test_street(self):
        self.assertEqual(norm_street("12 Cedar Rd."), norm_street("12 Cedar Road"))
        self.assertEqual(norm_street("1 High St"), "1 high street")

    def test_name_tokens(self):
        self.assertEqual(name_tokens("Riverside Primary School"), {"riverside"})
        self.assertTrue(
            name_tokens("Oakfield Junior and Infant School")
            <= name_tokens("Oakfield Kids Club"))
        # Distinctive tokens must NOT match an unrelated provider.
        self.assertFalse(
            name_tokens("Greenway Primary School")
            <= name_tokens("Oakfield Kids Club"))

    def test_resolve_column(self):
        fields = ["URN", "LA (code)", "EstablishmentName"]
        self.assertEqual(resolve_column(fields, "LA (code)"), "LA (code)")
        self.assertEqual(resolve_column(fields, "la code", "LA (code)"), "LA (code)")
        self.assertIsNone(resolve_column(fields, "Nonexistent"))


class TestSignals(unittest.TestCase):
    def test_afterschool_beats_breakfast(self):
        kind, term, _ = find_signals(
            "we run a breakfast club and an after school club", CONFIG)
        self.assertEqual(kind, "afterschool")

    def test_breakfast_only(self):
        kind, term, _ = find_signals("we run a breakfast club daily", CONFIG)
        self.assertEqual((kind, term), ("breakfast", "breakfast club"))

    def test_brand(self):
        kind, term, _ = find_signals("provision run by fit for sport", CONFIG)
        self.assertEqual((kind, term), ("afterschool", "fit for sport"))

    def test_no_signal(self):
        self.assertEqual(find_signals("welcome to our school", CONFIG)[0], "")


_ODS_CONTENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
 <office:body><office:spreadsheet>
  <table:table table:name="Notes">
   <table:table-row><table:table-cell><text:p>About this release</text:p>
   </table:table-cell></table:table-row>
  </table:table>
  <table:table table:name="Data">
   <table:table-row><table:table-cell table:number-columns-repeated="3">
    <text:p>Childcare providers as at 31 December 2025</text:p>
   </table:table-cell></table:table-row>
   <table:table-row>
    <table:table-cell><text:p>Provider name</text:p></table:table-cell>
    <table:table-cell><text:p>Provider type</text:p></table:table-cell>
    <table:table-cell><text:p>Postcode</text:p></table:table-cell>
   </table:table-row>
   <table:table-row>
    <table:table-cell><text:p>Riverside After School Club</text:p></table:table-cell>
    <table:table-cell><text:p>Childcare on non-domestic premises</text:p></table:table-cell>
    <table:table-cell><text:p>SW18 2PQ</text:p></table:table-cell>
    <table:table-cell table:number-columns-repeated="1000"/>
   </table:table-row>
  </table:table>
 </office:spreadsheet></office:body>
</office:document-content>"""


class TestOfstedLoader(unittest.TestCase):
    def test_pick_data_url_prefers_csv_then_most_recent(self):
        ods = "https://assets.example/a/Childcare_data.ods"
        csv_other = "https://assets.example/b/Childcare_summary.csv"
        csv_recent = ("https://assets.example/c/Childcare_most_recent_"
                      "inspections_data.csv")
        self.assertEqual(_pick_data_url([ods, csv_other, csv_recent]),
                         csv_recent)
        self.assertEqual(_pick_data_url([ods, csv_other]), csv_other)
        self.assertEqual(_pick_data_url([ods]), ods)

    def test_load_csv_with_title_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.csv"
            path.write_text(
                "Latest inspections of all registered providers as at "
                "31 December 2025 (published by 31 December 2025),\n"
                "Provider name,Provider type,Postcode\n"
                "Riverside After School Club,"
                "Childcare on non-domestic premises,SW18 2PQ\n",
                encoding="utf-8")
            rows = load_ofsted_rows(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Provider name"],
                         "Riverside After School Club")

    def test_load_ods(self):
        import zipfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.ods"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("mimetype",
                           "application/vnd.oasis.opendocument.spreadsheet")
                z.writestr("content.xml", _ODS_CONTENT_XML)
            rows = load_ofsted_rows(path)
        # Title row and Notes sheet skipped; header found by content.
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Provider name"],
                         "Riverside After School Club")
        self.assertEqual(rows[0]["Postcode"], "SW18 2PQ")


def _read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestEndToEnd(unittest.TestCase):
    """Full fixture run: every classification path lands where expected."""

    @classmethod
    def setUpClass(cls):
        import run_pipeline

        cls.tmp = tempfile.TemporaryDirectory()
        rc = run_pipeline.main(["--fixtures", "--output-root", cls.tmp.name])
        assert rc == 0
        runs = list(Path(cls.tmp.name).iterdir())
        assert len(runs) == 1
        cls.out = runs[0]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_universe(self):
        universe = _read(self.out / "schools_universe.csv")
        # 15 fixture rows -> 10 in scope (dup, closed, nursery, secondary,
        # out-of-borough all filtered).
        self.assertEqual(len(universe), 10)
        self.assertEqual(len({r["urn"] for r in universe}), 10)
        names = {r["name"] for r in universe}
        for excluded in ("Old Closed School", "Little Ducks Nursery",
                         "Broadwater Secondary Academy",
                         "Out Of Scope Primary School"):
            self.assertNotIn(excluded, names)

    def test_ofsted_matches(self):
        matches = {r["urn"]: r for r in _read(self.out / "ofsted_matches.csv")}
        self.assertEqual(matches["100001"]["ofsted_match"], "exact")
        self.assertEqual(matches["100003"]["ofsted_match"], "name")
        self.assertEqual(matches["100013"]["ofsted_match"], "fuzzy")
        # Childminder at the same postcode must not create a second match
        # type; resigned and out-of-scope providers must not match at all.
        self.assertEqual(matches["100005"]["ofsted_match"], "none")
        self.assertEqual(matches["100004"]["ofsted_match"], "none")

    def test_buckets(self):
        confirmed = {r["urn"]: r for r in
                     _read(self.out / "confirmed_provision.csv")}
        gaps = {r["urn"]: r for r in _read(self.out / "probable_gaps.csv")}
        manual = {r["urn"]: r for r in _read(self.out / "manual_check.csv")}

        self.assertEqual(set(confirmed), {"100001", "100002", "100003",
                                          "100008", "100013", "100014"})
        self.assertEqual(set(gaps), {"100004", "100005"})
        self.assertEqual(set(manual), {"100006", "100007"})

        self.assertEqual(gaps["100004"]["classification"], "PROBABLE_GAP")
        self.assertEqual(gaps["100005"]["classification"], "PARTIAL_PROVISION")
        # FIS upgrade carries its source URL.
        self.assertEqual(confirmed["100008"]["fis_checked"], "hit")
        self.assertIn("fis.example/lambeth", confirmed["100008"]["fis_url"])

    def test_evidence_is_auditable(self):
        sweep = {r["urn"]: r for r in
                 _read(self.out / "website_evidence.csv")}
        for urn in ("100001", "100002", "100014"):
            self.assertEqual(sweep[urn]["website_class"], "CONFIRMED_CLUB")
            self.assertTrue(sweep[urn]["evidence_term"])
            self.assertTrue(sweep[urn]["evidence_url"])
        self.assertEqual(sweep["100005"]["website_class"], "BREAKFAST_ONLY")
        self.assertEqual(sweep["100004"]["website_class"], "NO_EVIDENCE")
        self.assertEqual(sweep["100013"]["website_class"], "UNVERIFIABLE")
        self.assertIn("JS-only", sweep["100013"]["fetch_note"])

    def test_report(self):
        text = (self.out / "summary.md").read_text(encoding="utf-8")
        self.assertIn("Greenway Primary School", text)
        self.assertIn("Known limitations", text)
        self.assertIn("phone", text)


if __name__ == "__main__":
    unittest.main()
