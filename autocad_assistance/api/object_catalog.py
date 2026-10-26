"""Read-only authenticated view of the reviewed object-code snapshot."""

from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from autocad_assistance.services.object_catalog import load_snapshot, lookup
from autocad_assistance.services.field_code_profile import (
    PROFILE_SHA256, PROFILE_VERSION, FieldCodeError, load_profile, parse_code,
)


class ParseCodeRequest(BaseModel):
    model_config = {"extra": "forbid"}
    profileVersion: str
    rawCode: str


def create_object_catalog_router() -> APIRouter:
    snapshot = load_snapshot()
    profile = load_profile()
    router = APIRouter(prefix="/api/v1/object-catalog", tags=["object-catalog"])
    status_counts = dict(sorted(Counter(entry["status"] for entry in snapshot["entries"]).items()))

    @router.get("")
    async def catalog_page(
        page: Annotated[int, Query(ge=1)] = 1,
        pageSize: Annotated[int, Query(ge=1, le=50)] = 20,
    ):
        entries = snapshot["entries"]
        start = (page - 1) * pageSize
        return JSONResponse(content={
            "catalogVersion": snapshot["catalogVersion"],
            "contentSha256": snapshot["contentSha256"],
            "sources": snapshot["sources"],
            "linePrefixes": snapshot["linePrefixes"],
            "lineLayerOverrides": snapshot["lineLayerOverrides"],
            "specialRules": snapshot["specialRules"],
            "statusCounts": status_counts,
            "data": entries[start:start + pageSize],
            "pagination": {"page": page, "pageSize": pageSize,
                           "totalItems": len(entries),
                           "hasMore": start + pageSize < len(entries)},
        }, headers={"Cache-Control": "no-store"})

    @router.get("/lookup/{code}")
    async def catalog_lookup(code: str):
        if not 0 < len(code) <= 128:
            return JSONResponse(status_code=422, content={"error": {
                "code": "CODE_INVALID", "message": "Object code is invalid",
            }}, headers={"Cache-Control": "no-store"})
        return JSONResponse(content=lookup(snapshot, code),
                            headers={"Cache-Control": "no-store"})

    @router.get("/profiles/{profile_version}")
    async def profile_read(profile_version: str):
        if profile_version != PROFILE_VERSION:
            return JSONResponse(status_code=404, content={"error": {
                "code": "PROFILE_NOT_FOUND", "message": "Field-code profile not found",
            }}, headers={"Cache-Control": "no-store"})
        return JSONResponse(content={**profile, "profileSha256": PROFILE_SHA256},
                            headers={"Cache-Control": "no-store"})

    @router.post("/parse")
    async def profile_parse(request: ParseCodeRequest):
        if request.profileVersion != PROFILE_VERSION:
            return JSONResponse(status_code=422, content={"error": {
                "code": "PROFILE_UNSUPPORTED", "message": "Unsupported field-code profile",
            }}, headers={"Cache-Control": "no-store"})
        try:
            result = parse_code(profile, request.rawCode)
        except FieldCodeError as exc:
            return JSONResponse(status_code=422, content={"error": {
                "code": "CODE_INVALID", "message": str(exc),
            }}, headers={"Cache-Control": "no-store"})
        return JSONResponse(content=result, headers={"Cache-Control": "no-store"})

    return router
