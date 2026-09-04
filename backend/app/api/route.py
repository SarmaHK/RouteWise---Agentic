"""Route-planning endpoint (Workstream A, Phase A3 — Agent Orchestration & Decision).

``POST /api/route/plan`` is the reserved primary endpoint (docs/API_CONTRACTS.md §2). The A3
pipeline is: A2 extraction → clarification gate → agent orchestration → candidate evaluation →
decision → ``PlanResponse`` (A3 brief §12). The **request contract is unchanged from A2**; the
response now carries a decision (status ``COMPLETED``, a recommendation, alternatives, and the
full agent-action trace) whenever the request can be planned.

Honesty (A3 brief §7/§17; AGENT_SPEC §15–§16): route figures come from a deterministic MOCK
candidate provider and every result is labelled ``data_source="mock"``. Extraction still uses real
Qwen when ``MODEL_STUDIO_API_KEY`` is set, else the deterministic mock extractor (A2). If the
request needs clarification, the agent **stops before deciding** and returns status
``UNDERSTANDING`` (A2 behaviour preserved). Malformed model output is rejected safely as a 502.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.agent.orchestrator import RouteAgent, get_agent
from app.schemas.route import PlanRequest, PlanResponse
from app.services.ai.extraction import (
    MalformedExtractionError,
    TravelRequestExtractor,
    get_extractor,
)

router = APIRouter(tags=["route"])


@router.post(
    "/plan",
    response_model=PlanResponse,
    summary="Plan a route with the A3 agent (mock candidates, deterministic decision)",
)
def plan_route(
    request: PlanRequest,
    extractor: TravelRequestExtractor = Depends(get_extractor),
    agent: RouteAgent = Depends(get_agent),
) -> PlanResponse:
    """Understand the request (A2), then let the agent decide a route (A3).

    Missing hard constraints are surfaced honestly through the TravelRequest clarification fields,
    and the agent stops before deciding rather than fabricating a route (A3 brief §6/§12). All
    route data is mock and labelled as such; no live transit/booking data is claimed.
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

    # The agent owns the state machine, tool calls, decision, and action trace (A3 brief §12).
    context = agent.run(travel_request)
    return PlanResponse(
        status=context.state,
        request=context.request,
        recommendation=context.recommendation,
        legs=context.legs,
        alternatives=context.alternatives,
        agent_actions=context.actions,
        reasoning=context.reasoning,
    )
