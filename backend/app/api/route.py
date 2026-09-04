"""Route-planning endpoint (A1 FOUNDATION STUB).

``POST /api/route/plan`` is the reserved primary endpoint (docs/API_CONTRACTS.md §2). The real
planning/decision engine is built in A2–A9. In A1 this handler returns an HONEST foundation
stub — status ``IDLE``, no fabricated route — that proves the frontend → backend → (agent
foundation) pipe works. It deliberately does NOT call Qwen or any tool/decision logic.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.route import (
    AgentAction,
    AgentState,
    DataSource,
    PlanRequest,
    PlanResponse,
)

router = APIRouter(tags=["route"])


@router.post(
    "/plan", response_model=PlanResponse, summary="Plan a trip (A1 foundation stub)"
)
def plan_route(request: PlanRequest) -> PlanResponse:
    """Validate the request and return an honest A1 foundation response.

    No travel-planning logic is implemented in A1 (docs/PROJECT.md §14 → A9 Final API). The
    request is echoed back so the UI can confirm the contract shape end-to-end.
    """
    now = datetime.now(timezone.utc)
    stub_action = AgentAction(
        seq=1,
        state=AgentState.IDLE,
        label="A1 foundation reached",
        detail=(
            "Frontend <-> backend <-> agent-foundation connectivity confirmed. Route "
            "planning, tool calling, and scoring are implemented in later phases (A2-A9); "
            "this response is an honest foundation stub, not a real plan."
        ),
        status="done",
        timestamp=now,
        data_source=DataSource.mock,
    )
    return PlanResponse(
        status=AgentState.IDLE,
        request=request,
        recommendation=None,
        legs=[],
        alternatives=[],
        agent_actions=[stub_action],
    )
