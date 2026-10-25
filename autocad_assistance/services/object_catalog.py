"""Versioned snapshot of committed object-code evidence, parsed without execution."""

from __future__ import annotations

import ast
import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
from typing import Any


CATALOG_VERSION = "object-code-v1"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PACKAGE_ROOT / "config.py"
SINO_PATH = PACKAGE_ROOT / "templates" / "SinoKOD.txt"
SNAPSHOT_PATH = PACKAGE_ROOT / "templates" / "object-catalog-v1.json"
SINO_FIELDS = ("Тип", "Код", "Описание", "Группа", "Цвет", "Стиль", "Размер")


class CatalogSourceError(ValueError):
    """A committed source no longer has the reviewed static structure."""


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as exc:
        raise CatalogSourceError("Catalog source contains a nonliteral rule") from exc


def _dict(node: ast.AST) -> dict[str, ast.AST]:
    if not isinstance(node, ast.Dict):
        raise CatalogSourceError("Catalog source dictionary is missing")
    result = {}
    for key, value in zip(node.keys, node.values):
        name = _literal(key)
        if not isinstance(name, str) or name in result:
            raise CatalogSourceError("Catalog source has duplicate or nontext keys")
        result[name] = value
    return result


def _assignment(tree: ast.Module, name: str) -> ast.AST:
    values = [stmt.value for stmt in tree.body if isinstance(stmt, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == name
                      for target in stmt.targets)]
    if len(values) != 1:
        raise CatalogSourceError(f"Catalog source assignment {name} is absent or repeated")
    return values[0]


def _string_set(node: ast.AST) -> list[str]:
    value = _literal(node)
    if not isinstance(value, (set, frozenset, tuple, list)) or not all(
        isinstance(item, str) and 0 < len(item) <= 128 for item in value
    ):
        raise CatalogSourceError("Catalog source code set is invalid")
    return sorted(set(value))


def _selected_literal(source: dict[str, ast.AST], names: tuple[str, ...]) -> dict:
    output = {}
    for name in names:
        if name in source:
            value = _literal(source[name])
            if isinstance(value, set):
                value = sorted(value)
            if isinstance(value, dict):
                value = {str(key): item for key, item in sorted(value.items())}
            output[name] = value
    return output


def _config_evidence(text: str) -> dict:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise CatalogSourceError("Catalog config syntax is invalid") from exc
    prefixes = _string_set(_assignment(tree, "polyline_prefixes"))
    layers = _literal(_assignment(tree, "polyline_layer_mapping"))
    if not isinstance(layers, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in layers.items()
    ):
        raise CatalogSourceError("Catalog line layers are invalid")
    controller = _dict(_assignment(tree, "sm_controller_config"))
    mapping = _dict(controller["block_mapping"])
    blocks = []
    for label, node in mapping.items():
        parts = _dict(node)
        name = _literal(parts["name"])
        if not isinstance(name, str) or not name:
            raise CatalogSourceError("Catalog block name is invalid")
        blocks.append({"label": label, "blockName": name,
                       "aliases": _string_set(parts["code"]), "sourceLine": node.lineno})
    special = {}
    for name, keys in {
        "vl_support": ("codes", "bracing_codes", "blocks", "distance_threshold"),
        "tower_config": ("codes", "prefixes", "group_size", "min_points",
                         "block_name", "layer", "right_angle_tolerance",
                         "max_span", "base_width", "base_height",
                         "zscale", "min_scale"),
    }.items():
        node = controller.get(name)
        if node is not None:
            special[name] = _selected_literal(_dict(node), keys)
    return {"blockMappings": blocks,
            "linePrefixes": prefixes,
            "lineLayerOverrides": dict(sorted(layers.items())),
            "specialRules": special}


def _sino_rows(text: str) -> list[dict]:
    reader = csv.DictReader(StringIO(text))
    if tuple(reader.fieldnames or ()) != SINO_FIELDS:
        raise CatalogSourceError("SinoKOD columns changed")
    rows = []
    for line, row in enumerate(reader, start=2):
        if None in row or any(row.get(field) is None for field in SINO_FIELDS):
            raise CatalogSourceError("SinoKOD row shape is invalid")
        if not row["Код"].strip() or len(row["Код"]) > 128:
            raise CatalogSourceError("SinoKOD code is invalid")
        rows.append({"sourceLine": line, "type": row["Тип"], "code": row["Код"],
                     "description": row["Описание"], "group": row["Группа"],
                     "color": row["Цвет"], "style": row["Стиль"], "size": row["Размер"]})
    if not rows:
        raise CatalogSourceError("SinoKOD has no entries")
    return rows


def _candidates(code: str, blocks: list[dict]) -> list[dict]:
    normalized = code.strip().lower()
    return [{"label": block["label"], "blockName": block["blockName"],
             "sourceLine": block["sourceLine"]}
            for block in blocks if normalized in {alias.lower() for alias in block["aliases"]}]


def _classify(code: str, config: dict) -> tuple[str, list[dict]]:
    matches = _candidates(code, config["blockMappings"])
    support = {item.lower() for item in config["specialRules"].get("vl_support", {}).get("codes", [])}
    if code.strip().lower() in support:
        return "dynamic_support", matches
    tower = config["specialRules"].get("tower_config", {})
    tower_codes = {item.lower() for item in tower.get("codes", [])}
    tower_prefixes = {item.lower() for item in tower.get("prefixes", [])}
    normalized = code.strip().lower()
    if normalized in tower_codes or any(normalized.startswith(prefix) for prefix in tower_prefixes):
        return "dynamic_tower", matches
    if len(matches) > 1:
        return "ambiguous", matches
    return ("mapped" if matches else "unmapped"), matches


def build_snapshot(config_text: str, sino_text: str) -> dict:
    """Build a deterministic source snapshot from data-only AST fields."""
    if len(config_text) > 1024 * 1024 or len(sino_text) > 1024 * 1024:
        raise CatalogSourceError("Catalog source exceeds 1 MiB")
    config = _config_evidence(config_text)
    rows = _sino_rows(sino_text)
    entries = []
    for row in rows:
        status, candidates = _classify(row["code"], config)
        entries.append({**row, "status": status, "blockCandidates": candidates})
    core = {
        "catalogVersion": CATALOG_VERSION,
        "sources": {
            "config.py": sha256(config_text.encode("utf-8")).hexdigest(),
            "SinoKOD.txt": sha256(sino_text.encode("utf-8")).hexdigest(),
        },
        "entries": entries,
        **config,
    }
    core["contentSha256"] = sha256(_canonical(core).encode("utf-8")).hexdigest()
    return core


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def snapshot_bytes(snapshot: dict) -> bytes:
    return (json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def build_current_snapshot() -> dict:
    return build_snapshot(CONFIG_PATH.read_text(encoding="utf-8"),
                          SINO_PATH.read_text(encoding="utf-8-sig"))


def load_snapshot() -> dict:
    raw = SNAPSHOT_PATH.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise CatalogSourceError("Catalog snapshot exceeds 2 MiB")
    try:
        snapshot = json.loads(raw)
        digest = snapshot.pop("contentSha256")
        if sha256(_canonical(snapshot).encode("utf-8")).hexdigest() != digest:
            raise CatalogSourceError("Catalog snapshot checksum is invalid")
        snapshot["contentSha256"] = digest
        if snapshot["catalogVersion"] != CATALOG_VERSION:
            raise CatalogSourceError("Unsupported catalog version")
    except (ValueError, KeyError, TypeError) as exc:
        raise CatalogSourceError("Catalog snapshot is invalid") from exc
    return snapshot


def lookup(snapshot: dict, code: str) -> dict:
    if not isinstance(code, str) or not 0 < len(code) <= 128:
        raise CatalogSourceError("Catalog lookup code is invalid")
    matching = [item for item in snapshot["entries"] if item["code"] == code]
    status, candidates = _classify(code, snapshot)
    normalized = code.strip().lower()
    match = re.fullmatch(r"(?P<prefix>[a-zA-Z]+)\d+", normalized)
    prefix = match.group("prefix") if match and match.group("prefix") in {
        item.lower() for item in snapshot["linePrefixes"]
    } else None
    return {
        "catalogVersion": snapshot["catalogVersion"], "code": code,
        "matchingEntries": matching, "status": status,
        "blockCandidates": candidates,
        "lineRule": {"prefix": prefix,
                     "layer": snapshot["lineLayerOverrides"].get(prefix, "Polylines")}
                    if prefix else None,
    }
