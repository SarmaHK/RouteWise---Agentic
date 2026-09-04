"""Route-planning endpoint (Workstream A, Phase A2 — Request Understanding).

``POST /api/route/plan`` is the reserved primary endpoint (docs/API_CONTRACTS.md §2). In A2 it
UNDERSTANDS the request only: it runs natural-language extraction into a validated
``TravelRequest`` and returns status ``UNDERSTANDING``. It deliberately does NOT plan a route,
call tools, or score alternatives — those arrive in A3+ (A2 brief §7).

Extraction uses the existing AI abstraction: real Qwen when ``MODEL_STUDIO_API_KEY`` is set,
otherwise a deterministic mock clearly labelled ``extraction_source="mock"`` (A2 brief §5).
Malformed model output is rejected safely as a 502, never silently accepted.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.route import (
    AgentAction,
    AgentState,
    DataSource,
    PlanRequest,
    PlanResponse,
)
from app.services.ai.extraction import (
    MalformedExtractionError,
    TravelRequestExtractor,
    get_extractor,
)

router = APIRouter(tags=["route"])


@router.post(
    "/plan",
    response_model=PlanResponse,
    summary="Understand a travel request (A2 — no route planning yet)",
)
def plan_route(
    request: PlanRequest,
    extractor: TravelRequestExtractor = Depends(get_extractor),
) -> PlanResponse:
    """Extract a validated ``TravelRequest`` from the request. No route is planned in A2.

    The natural-language ``raw_text`` (plus any explicit structured fields as hints) is
    understood into a ``TravelRequest``. Missing hard constraints are surfaced honestly via
    the TravelRequest clarification fields rather than fabricated (A2 brief §6).
    """
    hints = request.model_dump(exclude={"raw_text"}, exclude_none=True)
    raw_text = request.raw_text or ""

    try:
        travel_request = extractor.extract(raw_text, hints)
    except MalformedExtractionError as exc:
        # Model output was malformed/invalid — reject safely, don't fabricate a request.
        raise HTTPException(
            status_code=502,
            detail="Travel-request extraction failed: the model returned invalid output.",
        ) from exc

    is_mock = travel_request.extraction_source is not None and (
        travel_request.extraction_source.value == "mock"
    )
    if travel_request.clarification_required:
        detail = (
            "Understood the request but a required detail is missing: "
            + ", ".join(travel_request.missing_fields)
            + ". No route planned (A2 is understanding only)."
        )
    else:
        understood = [
            f"{k}={v}"
            for k, v in travel_request.model_dump(
                include={
                    "origin",
                    "destination",
                    "budget",
                    "currency",
                    "luggage",
                    "walking_preference",
                },
                exclude_none=True,
            ).items()
        ]
        detail = (
            "Understood the travel request: "
            + (", ".join(understood) if understood else "(no explicit constraints)")
            + ". Route planning, tool calling, and scoring arrive in later phases (A3+)."
        )

    action = AgentAction(
        seq=1,
        state=AgentState.UNDERSTANDING,
        label="Understood travel request",
        detail=detail,
        status="done",
        timestamp=datetime.now(timezone.utc),
        data_source=DataSource.mock if is_mock else DataSource.live,
    )
    return PlanResponse(
        status=AgentState.UNDERSTANDING,
        request=travel_request,
        recommendation=None,
        legs=[],
        alternatives=[],
        agent_actions=[action],
    )
