"""Synthetic tool component inputs, with no evaluator/oracle projection."""

from hawaii_activity_forecaster.harness.contracts import DriverInputs
from hawaii_activity_forecaster.models import EnvironmentalToolResponse
from hawaii_activity_forecaster.tools.synthetic import ToolAction
from specialist_samples import BEACH, NOW, WINDOW, finding


def template(role="WEATHER", status="SUCCESS", source=None):
    source = source or ("NWS_WEATHER" if role == "WEATHER" else "NWS_MARINE")
    return EnvironmentalToolResponse(
        tool_call_id="template-call", source_id=source, retrieval_status=status, retrieved_at=NOW,
        findings=[finding(role, source_id=source)] if status in {"SUCCESS", "PARTIAL"} else [],
        missing_evidence=["Synthetic incomplete category"] if status in {"PARTIAL", "UNAVAILABLE"} else [],
        errors=[dict(error_id="template-error", error_code="SOURCE_UNAVAILABLE", message="Synthetic outage",
                     source_id=source, tool_call_id="template-call", retryable=True)] if status == "ERROR" else [],
        duration_ms=0,
    )


def action(action_id="main", source="NWS_WEATHER", categories=("WIND_CONDITIONS",), zone="SYNTHETIC_ZONE", **updates):
    return ToolAction(action_id=action_id, source_id=source, candidate_beach_ids=[BEACH],
                      requested_evidence=categories, geographic_scope={"zone": zone}, **updates)


def operation(op_id="main", source="NWS_WEATHER", role="WEATHER", categories=("WIND_CONDITIONS",),
              zone="SYNTHETIC_ZONE", behaviors=("SUCCESS",), durations=None):
    attempts = []
    for index, behavior in enumerate(behaviors):
        attempt = dict(attempt=index + 1, behavior=behavior,
                       simulated_duration_ms=(durations[index] if durations else 11000 if behavior == "TIMEOUT" else 1))
        if behavior == "MALFORMED":
            attempt.update(raw_response_path="malformed/tool.json", invalid_fields=["/findings"])
        elif behavior != "TIMEOUT":
            attempt["response_fixture_id"] = f"{source}-{('SUCCESS' if behavior == 'DUPLICATE' else behavior)}"
        if behavior == "DUPLICATE":
            attempt["delivery_count"] = 3
        attempts.append(attempt)
    return dict(operation_id=op_id, request_step=1, agent_type=role, source_id=source,
                candidate_beach_ids=[BEACH], requested_evidence=list(categories), target_time_window=WINDOW,
                geographic_scope={"zone": zone}, attempts=attempts)


def inputs(*operations):
    operations = operations or (operation(),)
    sources = {}
    for op in operations:
        for attempt in op["attempts"]:
            fixture = attempt.get("response_fixture_id")
            if fixture:
                status = "SUCCESS" if attempt["behavior"] == "DUPLICATE" else attempt["behavior"]
                sources[fixture] = template(op["agent_type"], status, op["source_id"])
    malformed = template().model_dump(mode="json") | {"findings": "deliberately invalid"}
    return DriverInputs.model_validate(dict(
        script=dict(harness_contract_version="1.0.0", requests=[dict(request_step=1, user_request="Synthetic request", reference_time=NOW)],
                    operations=operations), source_responses=sources, malformed_responses={"malformed/tool.json": malformed},
    ))
