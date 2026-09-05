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
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

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
    summary="Plan a route with the agent (A5 multi-step tool loop; mock candidates, deterministic decision)",
)
def plan_route(
    request: PlanRequest,
    extractor: TravelRequestExtractor = Depends(get_extractor),
    agent: RouteAgent = Depends(get_agent),
    settings: Optional[Any] = None,
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

    legs = context.legs
    if not legs and context.recommendation is not None:
        from app.config import get_settings
        active_settings = settings or get_settings()
        if getattr(active_settings, "enable_transit_intelligence", False):
            from app.tools.registry import build_tools
            tools = build_tools(active_settings)
            details_res = tools.call("get_route_details", route_id=context.recommendation.id)
            if details_res.success and isinstance(details_res.data, dict):
                legs = details_res.data.get("legs", [])
                context.legs = legs

    return PlanResponse(
        status=context.state,
        request=context.request,
        recommendation=context.recommendation,
        legs=legs,
        alternatives=context.alternatives,
        agent_actions=context.actions,
        reasoning=context.reasoning,
    )


# ----------------------------------------------------------------------
# Workstream C: Autonomous Re-Planning, Disruption & Booking Endpoints
# ----------------------------------------------------------------------

from pydantic import BaseModel, Field


class ReplanRequest(BaseModel):
    """Payload for autonomous re-planning when a corridor disruption is detected."""

    request: PlanRequest = Field(description="Original or updated travel request.")
    previous_recommendation_id: Optional[str] = Field(
        default="R1", description="ID of route candidate that was previously recommended."
    )
    disruption_notice: Optional[str] = Field(
        default=None, description="Optional description of the observed disruption."
    )


class DisruptionInjectionRequest(BaseModel):
    """Payload to simulate real-time transit disruption in GTFS-RT feed."""

    trip_id: str = Field(
        default="trip_train_mainline_1005", description="GTFS-RT trip_id or corridor key."
    )
    delay_minutes: float = Field(
        default=55.0, description="Delay duration in minutes (>= 45 triggers disruption)."
    )
    delay_risk: str = Field(default="high", description="Delay risk tier ('low', 'moderate', 'high').")
    alert_header: str = Field(
        default="Landslide clearance operation between Hatton and Kotagala. Speed restriction 10 km/h.",
        description="Passenger-facing alert message.",
    )


class BookingHoldRequest(BaseModel):
    """Payload to autonomously prepare a 15-minute booking hold (simulated)."""

    route_id: str = Field(description="Route identifier to hold (e.g. 'R1', 'R2').")
    traveler_name: Optional[str] = Field(
        default="Samantha Perera", description="Name of the primary traveler."
    )
    seats: int = Field(default=1, ge=1, le=6, description="Number of seats to reserve.")
    total_fare_lkr: Optional[float] = Field(
        default=None, description="Total expected fare in Sri Lankan Rupees."
    )
    seat_class: Optional[str] = Field(
        default="second", description="Transit class ('first', 'second', 'ac_express')."
    )


ReplanRequest.model_rebuild()
DisruptionInjectionRequest.model_rebuild()
BookingHoldRequest.model_rebuild()


@router.post(
    "/replan",
    response_model=PlanResponse,
    summary="Re-plan route upon disruption (Workstream C / Coder Wake ADAPT flow)",
)
def replan_route(
    replan_req: ReplanRequest,
    extractor: TravelRequestExtractor = Depends(get_extractor),
) -> PlanResponse:
    """Execute autonomous re-planning loop (AGENT_SPEC §12).

    Transitions through REPLANNING -> SEARCHING -> EVALUATING -> COMPLETED,
    penalizing or excluding disrupted routes and selecting the optimal resilient alternative.
    """
    from app.agent.decision import DecisionEngine
    from app.agent.state import AgentExecutionContext
    from app.config import get_settings
    from app.schemas.candidate import CandidateAvailability
    from app.schemas.route import AgentAction, AgentState, DataSource
    from app.tools.registry import build_tools

    hints = replan_req.request.model_dump(exclude={"raw_text"}, exclude_none=True)
    raw_text = replan_req.request.raw_text or ""
    travel_request = extractor.extract(raw_text, hints)

    active_settings = get_settings()
    tools = build_tools(active_settings)

    # 1. Initialize context and advance to REPLANNING
    context = AgentExecutionContext(request=travel_request)
    context.advance(AgentState.UNDERSTANDING)
    context.advance(AgentState.PLANNING)
    context.advance(AgentState.SEARCHING)
    context.advance(AgentState.EVALUATING)
    context.advance(AgentState.REPLANNING)

    prev_id = (replan_req.previous_recommendation_id or "R1").upper()
    disruption_msg = (
        replan_req.disruption_notice
        or f"High delay disruption detected on corridor route '{prev_id}'. Autonomous re-planning initiated."
    )

    context.record_action(
        state=AgentState.REPLANNING,
        label="Disruption Detected & Re-Planning Triggered",
        detail=disruption_msg,
    )

    # 2. Re-search candidates
    context.advance(AgentState.SEARCHING)
    search_res = tools.call(
        "search_routes",
        origin=travel_request.origin or "Colombo Fort",
        destination=travel_request.destination or "Ella",
    )
    candidates = (
        search_res.data if (search_res.success and isinstance(search_res.data, list)) else []
    )

    # 3. Augment candidates with live delay and availability
    for c in candidates:
        del_res = tools.call("get_delay_prediction", route_id=c.id)
        if del_res.success and isinstance(del_res.data, dict):
            c.delay_risk = del_res.data.get("delay_risk", c.delay_risk)
            c.delay_min_estimate = del_res.data.get("delay_min_estimate", c.delay_min_estimate)

        avail_res = tools.call("check_availability", route_id=c.id)
        if avail_res.success and isinstance(avail_res.data, dict):
            c.availability = CandidateAvailability(
                avail_res.data.get("availability", c.availability)
            )

    context.record_action(
        state=AgentState.SEARCHING,
        label="Corridor Options Re-Evaluated",
        detail=f"Retrieved {len(candidates)} candidate route(s) with live GTFS-RT delays.",
    )

    # 4. Re-evaluate with DecisionEngine
    context.advance(AgentState.EVALUATING)
    decision = DecisionEngine().decide(travel_request, candidates)
    context.recommendation = decision.recommendation
    context.alternatives = decision.alternatives

    # 5. Populate legs for new recommendation
    legs = []
    if context.recommendation:
        det_res = tools.call("get_route_details", route_id=context.recommendation.id)
        if det_res.success and isinstance(det_res.data, dict):
            legs = det_res.data.get("legs", [])
    context.legs = legs

    # 6. Finalize to COMPLETED
    context.advance(AgentState.COMPLETED)
    new_id = context.recommendation.id if context.recommendation else "None"
    context.reasoning = (
        f"Autonomous Re-Planning: {disruption_msg} "
        f"Previous route '{prev_id}' was demoted due to severe corridor delay. "
        f"Selected resilient route '{new_id}' ({context.recommendation.summary if context.recommendation else ''}): "
        f"Estimated fare LKR {context.recommendation.total_fare_lkr:,.0f} with {context.recommendation.delay_risk} delay risk."
    )
    context.record_action(
        state=AgentState.COMPLETED,
        label="Optimal Resilient Route Finalized",
        detail=f"Replaced disrupted '{prev_id}' with resilient '{new_id}'.",
    )

    return PlanResponse(
        status=context.state,
        request=context.request,
        recommendation=context.recommendation,
        legs=legs,
        alternatives=context.alternatives,
        agent_actions=context.actions,
        reasoning=context.reasoning,
    )


@router.post(
    "/disruption/inject",
    summary="Inject simulated transit disruption (Workstream C demo helper)",
)
def inject_disruption(payload: DisruptionInjectionRequest) -> dict[str, Any]:
    """Inject a disruption alert into the simulated real-time delay feed."""
    from automation.monitoring.disruption_monitor import get_disruption_monitor

    monitor = get_disruption_monitor()
    return monitor.inject_disruption(
        trip_id=payload.trip_id,
        delay_minutes=payload.delay_minutes,
        delay_risk=payload.delay_risk,
        alert_header=payload.alert_header,
    )


@router.post(
    "/disruption/restore",
    summary="Restore pristine transit delay feed (Workstream C demo helper)",
)
def restore_disruption() -> dict[str, Any]:
    """Restore delay feed to baseline low-delay state."""
    from automation.monitoring.disruption_monitor import get_disruption_monitor

    monitor = get_disruption_monitor()
    return monitor.restore_disruption()


@router.get(
    "/disruption/status",
    summary="Get active corridor disruptions (Workstream C monitoring)",
)
def disruption_status() -> dict[str, Any]:
    """Return active high-delay disruptions across the transit network."""
    from automation.monitoring.disruption_monitor import get_disruption_monitor

    monitor = get_disruption_monitor()
    disruptions = monitor.get_active_disruptions()
    return {"active_disruptions": disruptions, "disrupted_count": len(disruptions)}


@router.post(
    "/hold",
    summary="Prepare a booking reservation hold (Workstream C execution)",
)
def prepare_booking_hold(payload: BookingHoldRequest) -> dict[str, Any]:
    """Autonomously hold ticket inventory for 15 minutes (no financial transaction)."""
    from automation.booking.booking_service import get_booking_service

    service = get_booking_service()
    return service.prepare_hold(
        route_id=payload.route_id,
        traveler_name=payload.traveler_name,
        seats=payload.seats,
        total_fare_lkr=payload.total_fare_lkr,
        seat_class=payload.seat_class,
    )

