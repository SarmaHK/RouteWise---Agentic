"""Route-planning endpoint (Workstream A; A3 orchestration, A5 multi-step tool loop).

``POST /api/route/plan`` is the reserved primary endpoint (docs/API_CONTRACTS.md §2). The
pipeline is: A2 extraction → clarification gate → agent orchestration → candidate evaluation →
decision → ``PlanResponse`` (A3 brief §12). The **request contract is unchanged from A2**; the
response carries a decision (status ``COMPLETED``, a recommendation, alternatives, and the full
agent-action trace) whenever the request can be planned.

**A5** keeps this exact endpoint and contract but lets the agent perform a *bounded, model-driven*
sequence of tool calls before deciding (A5 brief §2/§7/§23). The only response-schema change is
**additive**: a tool call in ``agent_actions[]`` may now carry ``error_code`` when it failed
(API_CONTRACTS §4/§9). The trace may therefore contain more than one tool call, in a model-selected
order — never a hard-coded sequence. If the planner exceeds ``MAX_AGENT_ITERATIONS`` the agent stops
safely and returns its observed actions with **no** fabricated recommendation (A5 brief §8).

Honesty (A3 brief §7/§17; AGENT_SPEC §15–§16): route figures come from a deterministic MOCK
candidate provider and every result is labelled ``data_source="mock"``. Extraction and tool
selection use real Qwen when ``MODEL_STUDIO_API_KEY`` is set, else the deterministic mocks (A2/A5).
If the request needs clarification, the agent **stops before deciding** and returns status
``UNDERSTANDING`` (A2 behaviour preserved). Malformed model output is rejected safely as a 502.

**A9** adds no endpoint and changes no field meaning (brief §16); it makes the request *correlatable*
and the failure modes *distinguishable*:

* every call mints a lightweight ``request_id``, echoes it in the ``X-Request-Id`` response header
  and the (additive, optional) ``request_id`` response field, and passes it to the agent so the
  logs, the actions and the body all refer to one execution (brief §10);
* structured ``event=…`` logs mark the request received, extraction failure and the response sent —
  never the raw text, never a credential (brief §9);
* an unreachable live AI service is now a retryable **503** (the slot API_CONTRACTS §5 already
  reserved), distinct from a malformed model answer (502) and an internal bug (500) (brief §7).
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Response

from app.agent.orchestrator import RouteAgent, get_agent
from app.logging_config import REQUEST_ID_HEADER, format_event, new_request_id
from app.schemas.route import PlanRequest, PlanResponse
from app.services.ai.base import AIServiceUnavailableError
from app.services.ai.extraction import (
    MalformedExtractionError,
    TravelRequestExtractor,
    get_extractor,
)

logger = logging.getLogger("routewise.api")

router = APIRouter(tags=["route"])


@router.post(
    "/plan",
    response_model=PlanResponse,
    summary="Plan a route with the agent (A5 multi-step tool loop; mock candidates, deterministic decision)",
)
def plan_route(
    request: PlanRequest,
    response: Response,
    extractor: TravelRequestExtractor = Depends(get_extractor),
    agent: RouteAgent = Depends(get_agent),
) -> PlanResponse:
    """Understand the request (A2), then let the agent decide a route (A3).

    Missing hard constraints are surfaced honestly through the TravelRequest clarification fields,
    and the agent stops before deciding rather than fabricating a route (A3 brief §6/§12). All
    route data is mock and labelled as such; no live transit/booking data is claimed. A9 adds the
    per-request identifier and the 503 mapping; nothing else about the behaviour changes.
    """
    started = time.perf_counter()
    request_id = new_request_id()
    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        format_event(
            "request.received",
            request_id=request_id,
            mode="text" if request.raw_text else "structured",
        )
    )

    hints = request.model_dump(exclude={"raw_text"}, exclude_none=True)
    raw_text = request.raw_text or ""

    try:
        travel_request = extractor.extract(raw_text, hints)
    except MalformedExtractionError as exc:
        # Model output was malformed/invalid — reject safely, don't fabricate a request.
        logger.warning(
            format_event("extraction.failed", request_id=request_id, reason="malformed_output")
        )
        raise HTTPException(
            status_code=502,
            detail="Travel-request extraction failed: the model returned invalid output.",
        ) from exc
    except AIServiceUnavailableError as exc:
        # A9 (§7/§14): the configured live service was unreachable. Retryable (503), distinct from
        # a malformed answer (502); the error message never claims the model succeeded.
        logger.warning(
            format_event("extraction.failed", request_id=request_id, reason="service_unavailable")
        )
        raise HTTPException(
            status_code=503,
            detail="The AI extraction service could not be reached; please retry shortly.",
        ) from exc

    try:
        # The agent owns the state machine, tool calls, decision, and action trace (A3 brief §12).
        context = agent.run(travel_request, request_id=request_id)
    except AIServiceUnavailableError as exc:
        logger.warning(
            format_event("planning.failed", request_id=request_id, reason="service_unavailable")
        )
        raise HTTPException(
            status_code=503,
            detail="The AI planning service could not be reached; please retry shortly.",
        ) from exc

    logger.info(
        format_event(
            "plan.responded",
            request_id=request_id,
            status=context.state,
            recommendation=(context.recommendation.id if context.recommendation else None),
            actions=len(context.actions),
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
    )
    return PlanResponse(
        status=context.state,
        request=context.request,
        recommendation=context.recommendation,
        legs=context.legs,
        alternatives=context.alternatives,
        agent_actions=context.actions,
        reasoning=context.reasoning,
        request_id=request_id,
    )
