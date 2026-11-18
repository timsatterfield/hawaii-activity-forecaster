"""Synthetic structural acceptance checks for M1.1-B (requirements 03/04).

These small payloads exercise contracts; they are not the scenario fixture system
or proof of environmental safety, provenance verification, or agent behavior.
"""

from copy import deepcopy
import pytest
from pydantic import ValidationError

from hawaii_activity_forecaster import models as m
from hawaii_activity_forecaster.models.enums import TraceEventType

NOW = '2026-11-16T09:00:00-10:00'
LATER = '2026-11-16T09:01:00-10:00'
WINDOW = {'start': '2026-11-17T08:00:00-10:00', 'end': '2026-11-17T11:00:00-10:00'}
SOURCE = dict(source_id='SYNTH_CATALOG', publisher='Fictional test catalog',
              url='https://example.invalid/catalog', accessed_at='2026-11-16',
              supports_fields=['latitude', 'longitude', 'supported_activities'])
BEACH = dict(beach_id='TEST_BEACH_A', name='Fictional Beach A', region='SOUTH_MAUI',
             locality='Synthetic locality', latitude='20.0', longitude='-156.0',
             supported_activities=['SNORKELING'], lifeguard_status='UNKNOWN',
             sources=[SOURCE], last_verified='2026-11-16', catalog_status='VERIFIED')
MEASUREMENT = dict(measurement_type='SURF_HEIGHT', value={'min': 1, 'max': 2},
                   unit='ft', measurement_convention='FACE')
ADVISORY = dict(advisory_id='advisory-1', issuer='Synthetic issuer', advisory_type='Synthetic advisory',
                affected_area='Synthetic region', source_reference='https://example.invalid/advisory')
FINDING = dict(finding_id='finding-1', investigation_id='investigation-1', agent_type='OCEAN',
               source_id='NWS_MARINE', source_reference='https://example.invalid/marine',
               finding_type='FORECAST', coverage_type='REGIONAL', coverage_id='synthetic-zone',
               coverage_description='Fictional reporting region', retrieved_at=NOW,
               valid_from=WINDOW['start'], valid_until=WINDOW['end'],
               measurements=[MEASUREMENT], retrieval_status='SUCCESS', validation_status='PENDING')
CONSTRAINT = dict(constraint_id='constraint-1', constraint_description='Synthetic restriction',
                  result='PASS', explanation='Synthetic check completed')
PREFERENCE = dict(preference_id='preference-1', preference_description='Synthetic preference',
                  alignment='MATCH', explanation='Synthetic match')
POLICY = dict(policy_id='synthetic-policy', result='PASS', supporting_finding_ids=['finding-1'],
              explanation='Hypothetical policy result for structural testing')
ASSESSMENT = dict(
    assessment_id='assessment-1', investigation_id='investigation-1', beach_id='TEST_BEACH_A',
    activity='SNORKELING', target_time_window=WINDOW, evaluated_at=NOW,
    eligibility='NEEDS_INVESTIGATION', environmental_suitability='UNDETERMINED',
    evidence_quality='INSUFFICIENT', supporting_finding_ids=[], conflicting_finding_ids=[],
    rejected_finding_ids=[], evidence_limitations=['Mandatory checks pending'],
    assessment_basis='Synthetic incomplete assessment', hard_constraint_results=[CONSTRAINT],
    preference_results=[PREFERENCE], geographic_preference_match='NOT_SPECIFIED',
    policy_results=[POLICY], disqualifying_policy_ids=[], unresolved_policy_ids=['pending-policy'],
    safety_limitations=[], decision_reasons=['More evidence required'],
    recommended_next_actions=['REQUEST_OCEAN_EVIDENCE'], remaining_questions=['Advisory status?'],
    assessment_version='1',
)
NORMALIZED = dict(original_request='Synthetic snorkeling request', activity='SNORKELING',
                  target_time_window=WINDOW, hard_constraints=[], soft_preferences=[],
                  clarification_needed=False, clarification_questions=[])
EVIDENCE_REQUEST = dict(request_id='request-1', agent_type='OCEAN', candidate_beach_ids=['TEST_BEACH_A'],
                        target_time_window=WINDOW, request_status='PENDING')
ISSUE = dict(issue_id='issue-1', issue_type='MISSING', finding_ids=[],
             affected_beach_ids=['TEST_BEACH_A'], description='Synthetic advisory gap', resolved=False)
STATE = dict(
    **NORMALIZED, investigation_id='investigation-1', session_id='session-1', schema_version='0.1',
    created_at=NOW, updated_at=NOW, status='INVESTIGATING', request_revision=1,
    candidate_beach_ids=['TEST_BEACH_A'], assessments=[ASSESSMENT], investigated_beach_ids=[],
    remaining_candidate_ids=['TEST_BEACH_A'], weather_findings=[], ocean_findings=[FINDING],
    pending_evidence_requests=[EVIDENCE_REQUEST], unresolved_evidence_issues=[ISSUE],
    iteration_count=0, max_iterations=5, tool_call_count=0, max_tool_calls=12,
    retry_count=0, max_retries=1, remaining_actions=[], active_errors=[], recovery_actions=[],
    fallback_attempted=False,
)
RECOMMENDATION = dict(
    recommendation_id='recommendation-1', beach_id='TEST_BEACH_A', assessment_id='assessment-1',
    display_name='Fictional Beach A', environmental_suitability='FAVORABLE',
    evidence_quality='SUFFICIENT', recommended_time_window=WINDOW, supporting_finding_ids=['finding-1'],
    advisory_references=[], recommendation_reason='Synthetic structural example only',
    environmental_summary='Hypothetical evidence', preference_alignment=[], warnings=[], limitations=[],
    source_references=['NWS_MARINE'],
)
RESULT = dict(
    result_id='result-1', investigation_id='investigation-1', request_revision=1, schema_version='0.1',
    generated_at=NOW, activity='SNORKELING', target_time_window=WINDOW, outcome='NO_RECOMMENDATION',
    summary='Synthetic abstention', recommendations=[], general_warnings=[], general_limitations=[],
    no_recommendation_reason='INSUFFICIENT_EVIDENCE', explanation='Synthetic mandatory evidence gap',
)
EVENT = dict(event_id='event-1', trace_id='trace-1', sequence_number=1, timestamp=NOW,
             event_type='INVESTIGATION_STARTED', actor='ORCHESTRATOR', request_revision=1, details={})
TRACE = dict(trace_id='trace-1', investigation_id='investigation-1', schema_version='0.1',
             started_at=NOW, configuration_version='synthetic-1', policy_version='synthetic-1', events=[EVENT])
REQUIREMENT = dict(requirement_id='requirement-1', evidence_type='synthetic-advisory-check', priority='REQUIRED')
GAP = dict(gap_id='gap-1', gap_type='MISSING', related_finding_ids=[], description='Synthetic advisory gap')
ERROR = dict(error_id='error-1', error_code='SOURCE_TIMEOUT', message='Synthetic timeout', retryable=True)
REQUEST = dict(request_id='request-1', investigation_id='investigation-1', request_revision=1,
               schema_version='0.1', agent_type='OCEAN', candidate_beach_ids=['TEST_BEACH_A'],
               target_time_window=WINDOW, requested_evidence=[REQUIREMENT], known_evidence_gaps=[],
               issued_at=NOW, attempt_number=1)
RESPONSE = dict(response_id='response-1', request_id='request-1', investigation_id='investigation-1',
                request_revision=1, schema_version='0.1', agent_type='OCEAN', attempt_number=1,
                status='SUCCESS', findings=[FINDING], unresolved_gaps=[], errors=[],
                started_at=NOW, completed_at=LATER)
TOOL_REQUEST = dict(tool_call_id='call-1', investigation_id='investigation-1', source_id='NWS_MARINE',
                    agent_type='OCEAN', requested_evidence=['synthetic-surf'], target_time_window=WINDOW,
                    geographic_scope={'zone': 'synthetic-zone'}, issued_at=NOW)
TOOL_RESPONSE = dict(tool_call_id='call-1', source_id='NWS_MARINE', retrieval_status='SUCCESS',
                     retrieved_at=NOW, findings=[FINDING], missing_evidence=[], errors=[], duration_ms=1)

SAMPLES = [
    (m.TimeRange, WINDOW), (m.NumberRange, {'min': 1, 'max': 2}),
    (m.SourceReference, SOURCE), (m.BeachRecord, BEACH), (m.BeachCatalog, [BEACH]),
    (m.Measurement, MEASUREMENT), (m.AdvisoryReference, ADVISORY),
    (m.EnvironmentalFinding, FINDING), (m.ConstraintResult, CONSTRAINT),
    (m.PreferenceResult, PREFERENCE), (m.PolicyResult, POLICY),
    (m.CandidateAssessment, ASSESSMENT), (m.NormalizedRequest, NORMALIZED),
    (m.EvidenceRequest, EVIDENCE_REQUEST), (m.EvidenceIssue, ISSUE), (m.InvestigationState, STATE),
    (m.Recommendation, RECOMMENDATION), (m.RecommendationResult, RESULT),
    (m.TraceEvent, EVENT), (m.InvestigationTrace, TRACE), (m.EvidenceRequirement, REQUIREMENT),
    (m.EvidenceGap, GAP), (m.SpecialistError, ERROR), (m.SpecialistInvestigationRequest, REQUEST),
    (m.SpecialistInvestigationResponse, RESPONSE), (m.EnvironmentalToolRequest, TOOL_REQUEST),
    (m.EnvironmentalToolResponse, TOOL_RESPONSE),
]


@pytest.mark.parametrize('model,payload', SAMPLES, ids=[model.__name__ for model, _ in SAMPLES])
def test_contract_json_round_trip(model, payload):
    """FX-OD-001..006: explicit synthetic fields survive JSON serialization."""
    record = model.model_validate(deepcopy(payload))
    assert model.model_validate_json(record.model_dump_json(exclude_none=True)) == record
    assert model.model_json_schema()


@pytest.mark.parametrize('model,payload', [(model, data) for model, data in SAMPLES if isinstance(data, dict)],
                         ids=[model.__name__ for model, data in SAMPLES if isinstance(data, dict)])
def test_unknown_fields_are_rejected(model, payload):
    """SRS-006/DS-007: unexpected authority fields cannot silently disappear."""
    with pytest.raises(ValidationError):
        model.model_validate(dict(payload, invented_authority=True))


@pytest.mark.parametrize('model,payload,key', [
    (m.BeachRecord, BEACH, 'beach_id'), (m.EnvironmentalFinding, FINDING, 'source_id'),
    (m.CandidateAssessment, ASSESSMENT, 'evidence_quality'),
    (m.InvestigationState, STATE, 'request_revision'), (m.RecommendationResult, RESULT, 'outcome'),
    (m.TraceEvent, EVENT, 'details'), (m.SpecialistInvestigationRequest, REQUEST, 'attempt_number'),
    (m.SpecialistInvestigationResponse, RESPONSE, 'errors'),
    (m.EnvironmentalToolRequest, TOOL_REQUEST, 'geographic_scope'),
    (m.EnvironmentalToolResponse, TOOL_RESPONSE, 'duration_ms'),
])
@pytest.mark.parametrize('missing', [True, False], ids=['omitted', 'null'])
def test_required_fields_cannot_be_missing_or_null(model, payload, key, missing):
    """03 §1.3 / TC-009: required values must be present and cannot be null."""
    data = deepcopy(payload)
    if missing:
        del data[key]
    else:
        data[key] = None
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize('timestamp', ['2026-11-17T08:00:00', '0', 0, True])
def test_timestamps_require_explicit_timezone_and_iso_format(timestamp):
    with pytest.raises(ValidationError):
        m.TimeRange.model_validate(dict(WINDOW, start=timestamp))


@pytest.mark.parametrize('window', [dict(WINDOW, end=WINDOW['start']), dict(WINDOW, end=NOW)])
def test_time_ranges_require_positive_duration(window):
    with pytest.raises(ValidationError):
        m.TimeRange.model_validate(window)


def test_ranges_compare_instants_in_different_offsets():
    with pytest.raises(ValidationError):
        m.TimeRange(start='2026-11-17T08:00:00-10:00', end='2026-11-17T10:00:00Z')


@pytest.mark.parametrize('updates', [dict(latitude=91), dict(longitude=-181), dict(region='EAST_MAUI'),
                                      dict(supported_activities=['SURFING'])])
def test_beach_validation_bc_002_003_004(updates):
    with pytest.raises(ValidationError):
        m.BeachRecord.model_validate(dict(BEACH, **updates))


def test_catalog_rejects_duplicate_beach_ids_bc_001():
    with pytest.raises(ValidationError):
        m.BeachCatalog.model_validate([BEACH, BEACH])


@pytest.mark.parametrize('value', [True, None, float('nan'), float('inf'), {'min': 3, 'max': 1}])
def test_measurement_value_integrity(value):
    with pytest.raises(ValidationError):
        m.Measurement.model_validate(dict(MEASUREMENT, value=value))


def test_numeric_measurements_require_units():
    with pytest.raises(ValidationError):
        m.Measurement(measurement_type='WIND_SPEED', value=8)


def test_measurements_preserve_reported_values_and_conventions():
    record = m.Measurement.model_validate(MEASUREMENT)
    assert record.value.min == 1
    assert record.value.max == 2
    assert record.unit == 'ft'
    assert record.measurement_convention == 'FACE'
    qualitative = m.Measurement(measurement_type='WATER_VISIBILITY', value='Synthetic marginal report')
    assert qualitative.value == 'Synthetic marginal report'
    assert qualitative.unit is None


@pytest.mark.parametrize('updates', [dict(source_id='UNAUTHORIZED'), dict(source_reference=None),
                                      dict(coverage_type='BEACH'), dict(valid_until=NOW)])
def test_finding_structural_integrity_ef_001_002_004_012(updates):
    with pytest.raises(ValidationError):
        m.EnvironmentalFinding.model_validate(dict(FINDING, **updates))


@pytest.mark.parametrize('status', ['PENDING', 'ACCEPTED', 'LIMITED', 'REJECTED'])
def test_retrieval_does_not_determine_validation_ef_011(status):
    assert m.EnvironmentalFinding.model_validate(dict(FINDING, validation_status=status)).validation_status == status


def test_missing_observation_timestamp_remains_representable_for_later_rejection():
    record = m.EnvironmentalFinding.model_validate(dict(FINDING, finding_type='OBSERVATION'))
    assert record.observed_at is None
    assert record.validation_status == 'PENDING'


@pytest.mark.parametrize('status', ['ERROR', 'UNAVAILABLE'])
def test_failed_retrieval_cannot_supply_measurements_ef_010(status):
    with pytest.raises(ValidationError):
        m.EnvironmentalFinding.model_validate(dict(FINDING, retrieval_status=status))


def eligible_assessment():
    return dict(ASSESSMENT, eligibility='ELIGIBLE', environmental_suitability='FAVORABLE',
                evidence_quality='SUFFICIENT', unresolved_policy_ids=[])


@pytest.mark.parametrize('updates', [dict(evidence_quality='LIMITED'), dict(evidence_quality='INSUFFICIENT'),
    dict(environmental_suitability='UNFAVORABLE'), dict(environmental_suitability='UNDETERMINED'),
    dict(unresolved_policy_ids=['unknown-policy']),
    dict(hard_constraint_results=[dict(CONSTRAINT, result='UNKNOWN')]),
    dict(hard_constraint_results=[dict(CONSTRAINT, result='FAIL')]),
    dict(disqualifying_policy_ids=['synthetic-policy'])])
def test_eligible_assessment_rejects_contradictions_ca_004_to_016(updates):
    with pytest.raises(ValidationError):
        m.CandidateAssessment.model_validate(dict(eligible_assessment(), **updates))


def test_failed_constraint_requires_excluded_ca_006():
    data = dict(ASSESSMENT, hard_constraint_results=[dict(CONSTRAINT, result='FAIL')])
    with pytest.raises(ValidationError):
        m.CandidateAssessment.model_validate(data)
    assert m.CandidateAssessment.model_validate(dict(data, eligibility='EXCLUDED')).eligibility == 'EXCLUDED'


def test_rejected_finding_cannot_support_assessment_ca_010():
    with pytest.raises(ValidationError):
        m.CandidateAssessment.model_validate(dict(ASSESSMENT, supporting_finding_ids=['finding-1'],
                                                 rejected_finding_ids=['finding-1']))


@pytest.mark.parametrize('status,outcome', [('COMPLETED', 'RECOMMENDATIONS'),
                                           ('ABSTAINED', 'NO_RECOMMENDATION'), ('FAILED', 'ERROR')])
def test_state_terminal_outcome_mapping(status, outcome):
    data = dict(STATE, status=status, outcome=outcome, result_id='result-1', completion_reason='Synthetic completion')
    assert m.InvestigationState.model_validate(data).outcome == outcome
    with pytest.raises(ValidationError):
        m.InvestigationState.model_validate(dict(data, outcome='ERROR' if outcome != 'ERROR' else 'RECOMMENDATIONS'))


@pytest.mark.parametrize('updates', [dict(request_revision=0), dict(iteration_count=-1),
    dict(tool_call_count=True), dict(fallback_attempted='false'), dict(updated_at='2026-11-15T09:00:00Z'),
    dict(status='CANCELLED'), dict(status='COMPLETED'), dict(outcome='ERROR'),
    dict(ocean_findings=[dict(FINDING, agent_type='WEATHER')]),
    dict(assessments=[dict(ASSESSMENT, investigation_id='another-investigation')])])
def test_state_rejects_invalid_snapshot(updates):
    with pytest.raises(ValidationError):
        m.InvestigationState.model_validate(dict(STATE, **updates))


def test_retry_count_is_not_misinterpreted_as_per_invocation_budget():
    assert m.InvestigationState.model_validate(dict(STATE, retry_count=2, max_retries=1)).retry_count == 2


@pytest.mark.parametrize('count', [1, 2, 3])
def test_recommendation_count_rr_003(count):
    entries = [dict(RECOMMENDATION, recommendation_id=f'rec-{i}', beach_id=f'TEST_BEACH_{i}') for i in range(count)]
    assert len(m.RecommendationResult.model_validate(dict(RESULT, outcome='RECOMMENDATIONS', recommendations=entries)).recommendations) == count


@pytest.mark.parametrize('count', [0, 4])
def test_invalid_recommendation_count_rr_003(count):
    with pytest.raises(ValidationError):
        m.RecommendationResult.model_validate(dict(RESULT, outcome='RECOMMENDATIONS', recommendations=[RECOMMENDATION] * count))


@pytest.mark.parametrize('outcome', ['NO_RECOMMENDATION', 'ERROR'])
def test_nonrecommendation_outcomes_cannot_include_recommendations_rr_004(outcome):
    with pytest.raises(ValidationError):
        m.RecommendationResult.model_validate(dict(RESULT, outcome=outcome, recommendations=[RECOMMENDATION]))


def test_abstention_and_error_require_explanations():
    with pytest.raises(ValidationError):
        m.RecommendationResult.model_validate(dict(RESULT, explanation=None))
    with pytest.raises(ValidationError):
        m.RecommendationResult.model_validate(dict(RESULT, outcome='ERROR'))
    assert m.RecommendationResult.model_validate(dict(RESULT, outcome='ERROR', error_code='SYNTHETIC',
        error_summary='Synthetic operational error', recoverable=False)).recoverable is False


@pytest.mark.parametrize('updates', [dict(evidence_quality='LIMITED'), dict(environmental_suitability='UNFAVORABLE'), dict(rank=True)])
def test_recommendation_allowed_dimensions_rr_006_007(updates):
    with pytest.raises(ValidationError):
        m.Recommendation.model_validate(dict(RECOMMENDATION, **updates))


def test_unknown_trace_event_is_rejected_tr_evt_001():
    with pytest.raises(ValidationError):
        m.TraceEvent.model_validate(dict(EVENT, event_type='INVENTED_EVENT'))


def test_trace_event_enum_matches_authoritative_vocabulary():
    # Independent inventory from 03 §7.4; deliberately excludes routing/status labels.
    assert {e.value for e in TraceEventType} == set('''REQUEST_RECEIVED REQUEST_NORMALIZED REQUEST_REVISED
        CLARIFICATION_REQUESTED INVESTIGATION_STARTED INVESTIGATION_COMPLETED INVESTIGATION_ABSTAINED
        INVESTIGATION_FAILED AGENT_STARTED AGENT_COMPLETED AGENT_FAILED TOOL_CALLED TOOL_COMPLETED
        TOOL_FAILED RETRY_INITIATED FALLBACK_INITIATED CONTRACT_VALIDATED EVIDENCE_RECEIVED EVIDENCE_VALIDATED
        EVIDENCE_REJECTED EVIDENCE_CONFLICT_DETECTED CANDIDATE_ASSESSED POLICY_EVALUATED CANDIDATE_EXCLUDED
        CANDIDATE_ELIGIBLE INVESTIGATION_LIMIT_REACHED RESULT_VALIDATED'''.split())


@pytest.mark.parametrize('event', [EVENT, dict(EVENT, event_id='event-2'),
    dict(EVENT, event_id='event-2', sequence_number=2, trace_id='wrong-trace')])
def test_duplicate_or_mismatched_trace_events_rejected_it_002(event):
    with pytest.raises(ValidationError):
        m.InvestigationTrace.model_validate(dict(TRACE, events=[EVENT, event]))


def test_trace_preserves_parallel_completion_order_and_partial_records():
    events = [EVENT, dict(EVENT, event_id='event-2', sequence_number=2, actor='OCEAN', event_type='AGENT_COMPLETED'),
              dict(EVENT, event_id='event-3', sequence_number=3, actor='WEATHER', event_type='AGENT_COMPLETED')]
    trace = m.InvestigationTrace.model_validate(dict(TRACE, events=events))
    assert trace.completed_at is None
    assert trace.final_status is None
    assert [e.actor for e in trace.events] == ['ORCHESTRATOR', 'OCEAN', 'WEATHER']


@pytest.mark.parametrize('updates', [dict(attempt_number=0), dict(request_revision=True),
    dict(deadline_at='2026-11-15T09:00:00Z'), dict(agent_type='SAFETY')])
def test_invalid_specialist_request(updates):
    with pytest.raises(ValidationError):
        m.SpecialistInvestigationRequest.model_validate(dict(REQUEST, **updates))


@pytest.mark.parametrize('updates', [dict(status='ERROR'), dict(status='PARTIAL'),
    dict(completed_at='2026-11-15T09:00:00Z'), dict(findings=[FINDING, FINDING]),
    dict(findings=[dict(FINDING, investigation_id='wrong')]), dict(agent_type='WEATHER')])
def test_invalid_specialist_response_srs_002_004_008_009(updates):
    with pytest.raises(ValidationError):
        m.SpecialistInvestigationResponse.model_validate(dict(RESPONSE, **updates))


def test_partial_and_failed_responses_preserve_gaps_and_errors():
    response = m.SpecialistInvestigationResponse.model_validate(dict(RESPONSE, status='PARTIAL', unresolved_gaps=[GAP]))
    assert response.unresolved_gaps[0].gap_id == 'gap-1'
    assert response.findings[0].validation_status == 'PENDING'
    response = m.SpecialistInvestigationResponse.model_validate(dict(RESPONSE, status='ERROR', findings=[], errors=[ERROR]))
    assert response.errors[0].retryable is True


@pytest.mark.parametrize('updates', [dict(duration_ms=-1), dict(duration_ms=True),
                                      dict(source_id='UNAUTHORIZED'), dict(source_id='NWS_WEATHER')])
def test_tool_response_integrity(updates):
    with pytest.raises(ValidationError):
        m.EnvironmentalToolResponse.model_validate(dict(TOOL_RESPONSE, **updates))


@pytest.mark.parametrize('value', ['2026-11-16T00:00:00Z', '20261116', 0, True])
def test_calendar_dates_use_explicit_calendar_format(value):
    with pytest.raises(ValidationError):
        m.SourceReference.model_validate(dict(SOURCE, accessed_at=value))


def test_valid_eligible_snapshot_does_not_invent_policy_or_evidence():
    assessment = m.CandidateAssessment.model_validate(eligible_assessment())
    assert assessment.eligibility == 'ELIGIBLE'
    assert assessment.supporting_finding_ids == []
    # The future external validator must resolve evidence; the schema creates none.


def test_clarification_blocks_completed_recommendation_state():
    with pytest.raises(ValidationError):
        m.InvestigationState.model_validate(dict(STATE, status='COMPLETED', outcome='RECOMMENDATIONS',
            result_id='result-1', completion_reason='Synthetic completion', clarification_needed=True))


def test_advisory_dates_cannot_be_reversed():
    with pytest.raises(ValidationError):
        m.AdvisoryReference.model_validate(dict(ADVISORY, effective_from=LATER, effective_until=NOW))


def test_trace_terminal_event_must_agree_with_supplied_status():
    event = dict(EVENT, event_type='INVESTIGATION_ABSTAINED')
    assert m.InvestigationTrace.model_validate(dict(TRACE, final_status='ABSTAINED',
        completed_at=LATER, events=[event])).final_status == 'ABSTAINED'
    with pytest.raises(ValidationError):
        m.InvestigationTrace.model_validate(dict(TRACE, final_status='COMPLETED', events=[event]))


def test_unknown_nested_generic_shapes_are_not_silently_coerced():
    with pytest.raises(ValidationError):
        m.EnvironmentalToolRequest.model_validate(dict(TOOL_REQUEST, geographic_scope='Synthetic zone'))
    with pytest.raises(ValidationError):
        m.TraceEvent.model_validate(dict(EVENT, details=['not', 'an', 'object']))


def test_original_finding_provenance_survives_snapshot_serialization():
    finding = dict(FINDING, investigation_id='prior-investigation')
    state = m.InvestigationState.model_validate(dict(STATE, ocean_findings=[finding]))
    assert state.ocean_findings[0].investigation_id == 'prior-investigation'
    # This preserves the data; it does not authorize cross-investigation evidence reuse.


def test_models_do_not_create_required_lists_or_defaults_for_evidence():
    with pytest.raises(ValidationError):
        m.CandidateAssessment.model_validate({k: v for k, v in ASSESSMENT.items() if k != 'supporting_finding_ids'})
    with pytest.raises(ValidationError):
        m.EnvironmentalFinding.model_validate({k: v for k, v in FINDING.items() if k != 'validation_status'})
