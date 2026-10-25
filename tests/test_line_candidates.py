"""A/B proposals preserve the accepted builder order and source meaning."""

from __future__ import annotations

from hashlib import sha256
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from autocad_assistance.services import line_candidates


SOURCE = (
    b"Point,X,Y,Z,Code,Comments\n"
    b"P1,0,0,1,k1,first\n"
    b"P2,100,0,2,k1,second\n"
    b"P3,1,0,3,k1,third\n"
    b"P4,2,0,4,k1,fourth\n"
    b"B1,10,10,5,fonar,block\n"
)
MAPPING = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4, "Comments": 5}
SETTINGS = {"coordinateSystem": "local", "horizontalUnit": "m", "verticalUnit": "m",
            "scaleFactor": "500", "renderSettings": {"mapping": MAPPING}}


class FakeStore:
    def __init__(self, raw=SOURCE):
        self.raw = raw
        encoded = json.dumps(SETTINGS, sort_keys=True)
        self.revision = SimpleNamespace(
            revision_id="revision", project_id="project", source_format="csv",
            source_sha256=sha256(raw).hexdigest(),
            settings_sha256=sha256(encoded.encode()).hexdigest(),
            settings_json=encoded, algorithm_version="geoai-dxf-v1",
        )

    def assert_project_owner(self, owner_id, project_id):
        if (owner_id, project_id) != ("owner", "project"):
            raise AssertionError("Unexpected owner or project")

    def assert_revision_owner(self, owner_id, revision_id):
        if (owner_id, revision_id) != ("owner", "revision"):
            raise AssertionError("Unexpected owner or revision")
        return self.revision

    def read_source_for(self, owner_id, project_id, revision_id):
        self.assert_project_owner(owner_id, project_id)
        self.assert_revision_owner(owner_id, revision_id)
        return self.raw


class LineCandidateTests(unittest.TestCase):
    def test_zigzag_proposals_match_legacy_order_without_mutating_source(self):
        store = FakeStore()
        first = line_candidates.build_line_candidates(store, "owner", "project", "revision")
        second = line_candidates.build_line_candidates(store, "owner", "project", "revision")
        self.assertEqual(first, second)
        self.assertEqual(store.raw, SOURCE)
        self.assertEqual(first["sourceSha256"], sha256(SOURCE).hexdigest())
        self.assertEqual(first["generatorVersion"], "geoai-dxf-v1")
        self.assertEqual(first["groupCount"], 1)
        group = first["groups"][0]
        self.assertEqual(group["groupCode"], "k1")
        self.assertEqual(group["status"], "proposals")
        self.assertFalse(group["sameOrder"])
        a, b = group["candidates"]
        self.assertEqual(a["pointIds"], ["P1", "P2", "P3", "P4"])
        self.assertEqual(b["pointIds"], ["P1", "P3", "P4", "P2"])
        self.assertEqual(a["rowIndexes"], [1, 2, 3, 4])
        self.assertEqual(b["rowIndexes"], [1, 3, 4, 2])
        self.assertEqual(a["vertices"][1]["xyz"], ["100", "0", "2"])
        self.assertEqual(a["length2D"], 200)
        self.assertEqual(b["length2D"], 100)
        self.assertEqual(b["reorderedPositions"], 3)
        self.assertEqual(group["reasons"], ["REVIEW_REQUIRED"])

    def test_tie_is_stable_and_ambiguous_ids_abstain(self):
        tie = (b"Point,X,Y,Z,Code,Comments\nP1,0,0,1,k1,\nP2,1,0,1,k1,\nP3,-1,0,1,k1,\n")
        result = line_candidates.build_line_candidates(FakeStore(tie), "owner", "project", "revision")
        self.assertEqual(result["groups"][0]["candidates"][1]["pointIds"], ["P1", "P2", "P3"])
        duplicate = (b"Point,X,Y,Z,Code,Comments\nP1,0,0,1,k1,\nP1,1,0,1,k1,\n")
        result = line_candidates.build_line_candidates(FakeStore(duplicate), "owner", "project", "revision")
        self.assertEqual(result["groups"][0]["status"], "needs_review")
        self.assertEqual(result["groups"][0]["reasons"], ["DUPLICATE_POINT_ID"])
        self.assertEqual(result["groups"][0]["candidates"], [])
        empty = (b"Point,X,Y,Z,Code,Comments\n,0,0,1,k1,\nP2,1,0,1,k1,\n")
        result = line_candidates.build_line_candidates(FakeStore(empty), "owner", "project", "revision")
        self.assertEqual(result["groups"][0]["reasons"], ["EMPTY_POINT_ID"])

    def test_bounds_and_invalid_mapping(self):
        with patch.object(line_candidates, "MAX_GROUP_POINTS", 3):
            with self.assertRaises(line_candidates.LineCandidateLimitError):
                line_candidates.build_line_candidates(FakeStore(), "owner", "project", "revision")
        with patch.object(line_candidates, "MAX_TOTAL_POINTS", 3):
            with self.assertRaises(line_candidates.LineCandidateLimitError):
                line_candidates.build_line_candidates(FakeStore(), "owner", "project", "revision")
        with patch.object(line_candidates, "MAX_GROUPS", 0):
            with self.assertRaises(line_candidates.LineCandidateLimitError):
                line_candidates.build_line_candidates(FakeStore(), "owner", "project", "revision")
        store = FakeStore()
        store.revision.settings_json = "{}"
        with self.assertRaises(line_candidates.LineCandidateInvalidError):
            line_candidates.build_line_candidates(store, "owner", "project", "revision")
        extreme = (b"Point,X,Y,Z,Code,Comments\nP1,1e308,0,1,k1,\nP2,-1e308,0,1,k1,\n")
        with self.assertRaises(line_candidates.LineCandidateInvalidError):
            line_candidates.build_line_candidates(FakeStore(extreme), "owner", "project", "revision")


if __name__ == "__main__":
    unittest.main()
