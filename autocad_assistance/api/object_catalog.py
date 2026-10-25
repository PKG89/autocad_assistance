"""Read-only authenticated view of the reviewed object-code snapshot."""

from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from autocad_assistance.services.object_catalog import load_snapshot, lookup


def create_object_catalog_router() -> APIRouter:
    snapshot = load_snapshot()
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

    return router
