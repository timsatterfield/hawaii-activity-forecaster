"""Small deterministic contract examples, never safety or scenario oracles."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from hawaii_activity_forecaster.fixtures import load_fixture_inputs
from hawaii_activity_forecaster.models import (
    EnvironmentalFinding, InvestigationState, NormalizedRequest,
    SpecialistInvestigationRequest, SpecialistInvestigationResponse,
)

NOW = datetime(2026, 11, 18, 19, tzinfo=timezone.utc)
WINDOW = {"start": NOW + timedelta(days=1), "end": NOW + timedelta(days=1, hours=2)}
BEACH = "TEST_BEACH_A"


def catalog():
    return load_fixture_inputs(Path(__file__).resolve().parents[1] / "fixtures").catalog


def normalized():
    return NormalizedRequest(
        original_request="Fictional swimming request", activity="SWIMMING", target_time_window=WINDOW,
        hard_constraints=[{"constraint": "synthetic"}], soft_preferences=[],
        clarification_needed=False, clarification_questions=[],
    )


def state():
    return InvestigationState(
        **normalized().model_dump(), investigation_id="investigation-1", session_id="session-1",
        schema_version="0.1", created_at=NOW, updated_at=NOW, status="INVESTIGATING", request_revision=1,
        candidate_beach_ids=[BEACH], assessments=[], investigated_beach_ids=[],
        remaining_candidate_ids=[BEACH], weather_findings=[], ocean_findings=[],
        pending_evidence_requests=[], unresolved_evidence_issues=[], iteration_count=1,
        max_iterations=5, tool_call_count=0, max_tool_calls=12, retry_count=0, max_retries=1,
        remaining_actions=[], active_errors=[], recovery_actions=[], fallback_attempted=False,
    )


def request(role="WEATHER", **updates):
    data = dict(
        request_id=f"{role}-request", investigation_id="investigation-1", request_revision=1,
        schema_version="0.1", agent_type=role, candidate_beach_ids=[BEACH], target_time_window=WINDOW,
        requested_evidence=[{"requirement_id": "required-1", "evidence_type": "WIND_CONDITIONS" if role == "WEATHER"
                             else "SURF_WAVE_CONDITIONS", "priority": "REQUIRED"}],
        known_evidence_gaps=[], issued_at=NOW, attempt_number=1,
    )
    return SpecialistInvestigationRequest.model_validate({**data, **updates})


def finding(role="WEATHER", **updates):
    return EnvironmentalFinding.model_validate(dict(
        finding_id=f"{role}-finding", investigation_id="investigation-1", agent_type=role,
        source_id="NWS_WEATHER" if role == "WEATHER" else "NWS_MARINE",
        source_reference="https://example.invalid/synthetic", finding_type="FORECAST", coverage_type="REGIONAL",
        coverage_id="FICTIONAL_AREA", coverage_description="Fictional region, not direct beach measurements",
        retrieved_at=NOW, issued_at=NOW, valid_from=WINDOW["start"], valid_until=WINDOW["end"],
        descriptive_findings=["Synthetic evidence; no environmental recommendation"],
        retrieval_status="SUCCESS", validation_status="PENDING",
    ) | updates)


def response(origin=None, **updates):
    origin = origin or request()
    evidence = finding(origin.agent_type, investigation_id=origin.investigation_id)
    return SpecialistInvestigationResponse.model_validate(dict(
        response_id=f"{origin.request_id}-response", request_id=origin.request_id,
        investigation_id=origin.investigation_id, request_revision=origin.request_revision,
        schema_version=origin.schema_version, agent_type=origin.agent_type, attempt_number=origin.attempt_number,
        status="SUCCESS", findings=[evidence], unresolved_gaps=[], errors=[],
        started_at=origin.issued_at, completed_at=origin.issued_at,
    ) | updates)
