"""Conservative, read-only interpretation of one documented field-code profile."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata


PROFILE_VERSION = "drawcode-explicit-v1"
PROFILE_PATH = Path(__file__).resolve().parents[1] / "templates" / "field-code-profile-drawcode-v1.json"
PROFILE_SHA256 = "18cc41fd4711b77ee19cbc58fe96d14f68dfb35e2087095ccdd25483b91396e6"
TOKEN = re.compile(r"[^ \t]+")


class FieldCodeError(ValueError):
    """Profile or input violates the frozen 029A contract."""


def load_profile() -> dict:
    raw = PROFILE_PATH.read_bytes()
    if len(raw) > 8192 or sha256(raw).hexdigest() != PROFILE_SHA256:
        raise FieldCodeError("Field-code profile checksum or size is invalid")
    try:
        profile = json.loads(raw)
        if profile["profileVersion"] != PROFILE_VERSION or profile["catalogVersion"] != "object-code-v1":
            raise FieldCodeError("Unsupported field-code profile")
        if not isinstance(profile["pointCodes"], list) or not isinstance(profile["lineStyleCandidates"], list):
            raise FieldCodeError("Field-code profile shape is invalid")
        if profile["lineActionCandidates"] != {"1": "start", "0": "end"}:
            raise FieldCodeError("Field-code action markers changed")
    except (ValueError, KeyError, TypeError) as exc:
        raise FieldCodeError("Field-code profile is invalid") from exc
    return profile


def parse_code(profile: dict, raw_code: str) -> dict:
    """Report documented candidates; never choose geometry or rewrite raw data."""
    if not isinstance(raw_code, str) or len(raw_code) > 128:
        raise FieldCodeError("Field code must be text of at most 128 characters")
    if any(unicodedata.category(char).startswith("C") and char not in " \t"
           for char in raw_code):
        raise FieldCodeError("Field code contains a control character")
    spans = list(TOKEN.finditer(raw_code))
    if len(spans) > 32:
        raise FieldCodeError("Field code contains more than 32 tokens")
    point_codes = set(profile["pointCodes"])
    style_codes = set(profile["lineStyleCandidates"])
    actions = profile["lineActionCandidates"]
    tokens = []
    diagnostics = []
    for span in spans:
        value = span.group()
        candidates = []
        if value in point_codes:
            candidates.append({"role": "point-symbol-candidate", "code": value,
                               "assetStatus": "unverified"})
        if value in actions:
            candidates.append({"role": "line-action-candidate", "action": actions[value]})
        if value in style_codes:
            candidates.append({"role": "line-style-candidate", "code": value})
        token = {"raw": value, "start": span.start(), "end": span.end(),
                 "candidates": candidates}
        tokens.append(token)
        if not candidates:
            diagnostics.append({"code": "UNKNOWN_TOKEN", "tokenIndex": len(tokens) - 1,
                                "message": "Token is not defined by this profile"})
        elif len(candidates) > 1:
            diagnostics.append({"code": "AMBIGUOUS_TOKEN", "tokenIndex": len(tokens) - 1,
                                "message": "Token has multiple documented roles"})
    if not tokens:
        diagnostics.append({"code": "EMPTY_CODE", "tokenIndex": None,
                            "message": "Field code has no tokens"})
    return {"profileVersion": profile["profileVersion"],
            "profileSha256": PROFILE_SHA256, "rawCode": raw_code,
            "tokens": tokens, "diagnostics": diagnostics}
