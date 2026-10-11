"""Admin data quality + crosswalk review routes (Phase 5)."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import require_admin
from api.services.data_quality_pass import DataQualityPass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/data-quality", tags=["admin-data-quality"])


@router.get("/summary")
async def get_data_quality_summary(
    begin_year: int = Query(2020, ge=1990, le=2100),
    end_year: Optional[int] = Query(None, ge=1990, le=2100),
    _admin: dict = Depends(require_admin),
):
    """Crosswalk stats, Inside Spin drift, rankings snapshots, Fargo coverage."""
    try:
        return DataQualityPass().run(begin_year=begin_year, end_year=end_year, apply_aliases=False)
    except Exception as exc:
        logger.exception("data quality summary failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/crosswalk/review")
async def list_crosswalk_review_rows(
    limit: int = Query(200, ge=1, le=500),
    _admin: dict = Depends(require_admin),
):
    """Fuzzy crosswalk matches (date+name / llm) pending review, lowest score first."""
    try:
        return {"rows": DataQualityPass().crosswalk_review_rows(limit=limit)}
    except Exception as exc:
        logger.exception("crosswalk review list failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/crosswalk/{row_id:int}/confirm")
async def confirm_crosswalk_row(
    row_id: int,
    _admin: dict = Depends(require_admin),
):
    """Approve a fuzzy crosswalk match (method -> 'confirmed')."""
    result = DataQualityPass().confirm_crosswalk_row(row_id)
    if not result.get("ok"):
        if result.get("reason") == "conflict":
            raise HTTPException(
                status_code=409,
                detail="Another event of the same source already maps this tournament; reject one instead",
            )
        raise HTTPException(status_code=404, detail="Row not found or not reviewable")
    return {"id": row_id, "status": "confirmed"}


@router.delete("/crosswalk/{row_id:int}")
async def reject_crosswalk_row(
    row_id: int,
    _admin: dict = Depends(require_admin),
):
    """Reject a fuzzy crosswalk match (row deleted; re-ingest treats event as new).

    Response includes the linked tournament's current results count so the operator
    can check for gap-filled rows that may belong to the rejected source event.
    """
    result = DataQualityPass().reject_crosswalk_row(row_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Row not found or not reviewable")
    return {
        "id": row_id,
        "status": "rejected",
        "tournament_id": result.get("tournament_id"),
        "local_results_count": result.get("local_results_count", 0),
    }


@router.post("/crosswalk/purge-same-source-duplicates")
async def purge_same_source_duplicates(
    _admin: dict = Depends(require_admin),
):
    """Delete fuzzy rows that violate the 1:1 per-source mapping (provably wrong). Super admin only."""
    if _admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin required")
    try:
        return DataQualityPass().purge_same_source_fuzzy_duplicates()
    except Exception as exc:
        logger.exception("crosswalk purge failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/seed-aliases")
async def seed_name_aliases(
    _admin: dict = Depends(require_admin),
):
    """Seed player_name_aliases from latest multi-source ranking snapshots."""
    if _admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin required")
    systems = [
        "WPA_Men", "WPA_Women", "WPBA_Women",
        "InsideSpin_9Ball", "InsideSpin_Women", "InsideSpin_Overall",
        "Competitors_Pool_9Ball", "DigitalPool_WPAWorldMen",
    ]
    try:
        report = DataQualityPass().run(apply_aliases=True, alias_systems=systems)
        return report.get("alias_seed") or report
    except Exception as exc:
        logger.exception("alias seed failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
