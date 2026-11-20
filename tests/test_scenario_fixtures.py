"""SC-004/SC-010 authoring and preflight checks, not execution/evaluator passes.

Expected case facts below are independently taken from acceptance §§18/20.
No application result is generated or compared with its own policy output here.
"""

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from hawaii_activity_forecaster.fixtures import FixtureLoadError, load_fixture_inputs
from hawaii_activity_forecaster.harness import load_scenario

V1 = Path(__file__).resolve().parents[1] / 'fixtures'
PACKAGE = V1 / 'scenario-pack-v1'
START = '2026-11-17T08:00:00-10:00'
END = '2026-11-17T11:00:00-10:00'
SUPPORTED = {'TEST_BEACH_A', 'TEST_BEACH_B', 'TEST_BEACH_C', 'TEST_BEACH_D'}


@pytest.fixture(scope='module', params=['SC-001', 'SC-002', 'SC-003', 'SC-004', 'SC-005', 'SC-006', 'SC-007', 'SC-008', 'SC-009', 'SC-010', 'SC-011'])
def scenario(request):
    return request.param, load_scenario(PACKAGE, request.param)


def checks(bundle, target, field=None, operator=None, **selector):
    """Find definitions in the independent plan, without evaluating observations."""
    return [a for a in bundle.evaluator.expected_results.assertions
            if a.target == target and (field is None or a.field == field)
            and (operator is None or a.operator == operator)
            and all(a.selector.get(key) == value for key, value in selector.items())]


def finding_map(bundle):
    return {(source, f.finding_id): f for source, response in bundle.driver.source_responses.items() for f in response.findings}


def test_v2_package_registers_only_the_authored_cases():
    manifest = json.loads((PACKAGE / 'manifest.json').read_text())
    assert {item['scenario_id'] for item in manifest['scenarios']} == {'SC-001', 'SC-002', 'SC-003', 'SC-004', 'SC-005', 'SC-006', 'SC-007', 'SC-008', 'SC-009', 'SC-010', 'SC-011', 'SC-012'}
    assert manifest['fixture_format_version'] == '2.0.0'
    assert manifest['fixture_package_version'] == '1.6.0'
    assert manifest['synthetic'] is True
    assert manifest['reference_time'] == '2026-11-16T09:00:00-10:00'


def test_v1_catalog_is_copied_exactly_and_v1_loader_remains_unchanged():
    path = 'catalogs/synthetic-maui-v1.json'
    assert (PACKAGE / path).read_bytes() == (V1 / path).read_bytes()
    assert len(load_fixture_inputs(V1).catalog.root) == 5
    with pytest.raises(FixtureLoadError):
        load_fixture_inputs(PACKAGE)


def test_definition_is_active_but_execution_remains_explicitly_blocked(scenario):
    sid, bundle = scenario
    assert bundle.definition.scenario_id == sid
    assert bundle.definition.test_status == 'ACTIVE'
    assert bundle.execution_readiness.outcome == 'BLOCKED'
    assert 'genuine model-driven run' in bundle.execution_readiness.reason
    assert '--agent' in bundle.execution_readiness.reason
    assert bundle.driver.script.requests[0].user_request == bundle.application.user_request
    assert bundle.driver.script.requests[0].reference_time == bundle.application.reference_time
    assert bundle.application.reference_time.isoformat() == '2026-11-16T09:00:00-10:00'


def test_requests_match_the_approved_scenarios():
    assert load_scenario(PACKAGE, 'SC-004').application.user_request == 'Where should I snorkel tomorrow morning near Kihei?'
    assert load_scenario(PACKAGE, 'SC-010').application.user_request == 'Where should I snorkel tomorrow morning?'


def test_source_inputs_are_synthetic_pending_and_explicitly_timed(scenario):
    _, bundle = scenario
    for response in bundle.driver.source_responses.values():
        assert response.source_reference.startswith('https://example.invalid/')
        assert response.retrieved_at == bundle.application.reference_time
        for finding in response.findings:
            assert finding.validation_status == 'PENDING'
            assert finding.source_reference.startswith('https://example.invalid/')
            declared_stale = {rule.finding_id for rule in bundle.application.policy_configuration.evidence_rules
                              if rule.temporal_rule == 'DECLARED_REPORT_WINDOW'}
            if finding.finding_id in declared_stale:  # SC-007: explicitly declared past report windows.
                assert finding.finding_type == 'REPORT' and finding.valid_until.isoformat() < START
            else:
                assert finding.valid_from.isoformat() == START
                assert finding.valid_until.isoformat() == END
            assert finding.issued_at <= finding.retrieved_at
            assert finding.coverage_type in {'REGIONAL', 'BEACH'}


def test_premise_support_resolves_without_relabeling_scope(scenario):
    _, bundle = scenario
    findings = finding_map(bundle)
    for premise in bundle.application.policy_configuration.premises:
        assert premise.time_window.start.isoformat() == START
        assert premise.time_window.end.isoformat() == END
        assert premise.rationale.startswith('SYNTHETIC')
        for ref in premise.finding_refs:
            record = findings[(ref.source_fixture_id, ref.finding_id)]
            assert record.beach_id is None or record.beach_id == premise.beach_id
            assert record.valid_from <= premise.time_window.start < premise.time_window.end <= record.valid_until
        for ref in premise.catalog_field_refs:
            assert ref.beach_id == premise.beach_id


def test_positive_sc004_checks_are_explicit_for_both_beaches():
    bundle = load_scenario(PACKAGE, 'SC-004')
    expected = {
        'OFFICIAL_ADVISORY_CHECK_COMPLETE': True, 'WATER_CONTACT_ADVISORY_CHECK_COMPLETE': True,
        'DISQUALIFYING_SURF_PRESENT': False, 'DANGEROUS_CURRENT_PRESENT': False,
        'DISQUALIFYING_WEATHER_PRESENT': False, 'DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT': False,
        'MATERIAL_SAFETY_CONFLICT_PRESENT': False, 'ACTIVITY_SUPPORTING_CONDITIONS_PRESENT': True,
    }
    for beach in ('TEST_BEACH_A', 'TEST_BEACH_B'):
        facts = {p.fact_type: p.value for p in bundle.application.policy_configuration.premises if p.beach_id == beach}
        assert facts == dict(expected, WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT=(beach == 'TEST_BEACH_A'))


def test_sc004_advisory_and_complete_negative_check_are_distinct_inputs():
    bundle = load_scenario(PACKAGE, 'SC-004')
    a = bundle.driver.source_responses['sc-004-water-a'].findings[0]
    b = bundle.driver.source_responses['sc-004-water-b'].findings[0]
    assert a.beach_id == 'TEST_BEACH_A'
    assert a.advisories[0].advisory_id == 'SC-004_WATER_CONTACT_AVOIDANCE_A'
    assert a.advisories[0].affected_area == 'TEST_BEACH_A'
    assert a.advisories[0].effective_from.isoformat() == START
    assert a.advisories[0].effective_until.isoformat() == END
    assert b.beach_id == 'TEST_BEACH_B'
    assert b.advisories == []
    assert any('complete water-contact advisory check' in text for text in b.descriptive_findings)
    assert any('does not establish safe water quality' in text for text in b.descriptive_findings)
    # An empty list is never the sole premise for claiming a completed check.
    for beach in ['TEST_BEACH_A', 'TEST_BEACH_B']:
        assert any(p.beach_id == beach and p.fact_type == 'WATER_CONTACT_ADVISORY_CHECK_COMPLETE' and p.value is True
                   and p.finding_refs for p in bundle.application.policy_configuration.premises)


def test_sc004_declares_mandatory_evidence_and_explicit_visibility_gap():
    bundle = load_scenario(PACKAGE, 'SC-004')
    required = {'OFFICIAL_ADVISORIES', 'SURF_WAVE_CONDITIONS', 'CURRENTS_PERSISTENT_HAZARDS', 'WATER_QUALITY_ADVISORY_CHECK'}
    for beach in ['TEST_BEACH_A', 'TEST_BEACH_B']:
        categories = {r.category for r in bundle.application.policy_configuration.evidence_rules if beach in r.beach_ids}
        assert required <= categories
    missing = bundle.driver.source_responses['sc-004-visibility-unavailable']
    assert missing.retrieval_status == 'UNAVAILABLE'
    assert missing.findings == []
    assert missing.missing_evidence == ['UNDERWATER_VISIBILITY']


def test_other_sc004_supported_beaches_have_explicit_gaps_not_favorable_defaults():
    bundle = load_scenario(PACKAGE, 'SC-004')
    required = {'OFFICIAL_ADVISORIES', 'SURF_WAVE_CONDITIONS', 'CURRENTS_PERSISTENT_HAZARDS',
                'WATER_QUALITY_ADVISORY_CHECK', 'WIND_CONDITIONS', 'UNDERWATER_VISIBILITY'}
    for beach in ['TEST_BEACH_C', 'TEST_BEACH_D']:
        gaps = {cat for op in bundle.driver.script.operations if beach in op.candidate_beach_ids
                and all(a.behavior == 'UNAVAILABLE' for a in op.attempts) for cat in op.requested_evidence}
        assert gaps == required
        assert not any(p.beach_id == beach for p in bundle.application.policy_configuration.premises)
    e = next(b for b in bundle.application.catalog.root if b.beach_id == 'TEST_BEACH_E')
    assert 'SNORKELING' not in e.supported_activities


def test_marine_values_are_not_thresholds_or_current_measurements():
    bundle = load_scenario(PACKAGE, 'SC-004')
    marine = bundle.driver.source_responses['sc-004-marine'].findings[0]
    surf, swell = marine.measurements
    assert (surf.measurement_type, surf.value.min, surf.value.max, surf.unit, surf.measurement_convention) == ('SURF_HEIGHT', 1, 2, 'ft', 'FACE')
    assert (swell.measurement_type, swell.value, swell.unit) == ('SWELL_HEIGHT', 3, 'ft')
    assert any('not direct current-speed measurements' in text for text in marine.descriptive_findings)
    assert marine.coverage_type == 'REGIONAL'


def test_sc010_missing_marine_conditions_are_not_false_hazard_or_favorable_premises():
    bundle = load_scenario(PACKAGE, 'SC-010')
    prohibited = {'DISQUALIFYING_SURF_PRESENT', 'DANGEROUS_CURRENT_PRESENT',
                  'ACTIVITY_SUPPORTING_CONDITIONS_PRESENT', 'MATERIAL_SAFETY_CONFLICT_PRESENT'}
    assert not any(p.fact_type in prohibited for p in bundle.application.policy_configuration.premises)
    assert not any(r.category in {'SURF_WAVE_CONDITIONS', 'CURRENTS_PERSISTENT_HAZARDS'}
                   for r in bundle.application.policy_configuration.evidence_rules)
    for beach in SUPPORTED:
        known = {p.fact_type: p.value for p in bundle.application.policy_configuration.premises if p.beach_id == beach}
        assert known == {'OFFICIAL_ADVISORY_CHECK_COMPLETE': True, 'WATER_CONTACT_ADVISORY_CHECK_COMPLETE': True,
                         'WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT': False, 'DISQUALIFYING_WEATHER_PRESENT': False,
                         'DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT': False}


@pytest.mark.parametrize('fixture,provider,categories', [
    ('sc-010-marine-error', 'NWS_MARINE', {'SURF_WAVE_CONDITIONS', 'CURRENTS_PERSISTENT_HAZARDS'}),
    ('sc-010-fallback-surf', 'HWT_SURF', {'SURF_WAVE_CONDITIONS'}),
    ('sc-010-fallback-currents', 'SNORKEL_STORE', {'CURRENTS_PERSISTENT_HAZARDS'}),
])
def test_sc010_primary_and_alternate_paths_have_structured_failures(fixture, provider, categories):
    bundle = load_scenario(PACKAGE, 'SC-010')
    response = bundle.driver.source_responses[fixture]
    assert response.retrieval_status == 'ERROR'
    assert response.source_id == provider
    assert response.findings == []
    assert set(response.missing_evidence) == categories
    assert response.errors[0]['error_code'] == 'SOURCE_UNAVAILABLE'
    assert response.errors[0]['tool_call_id'] == response.tool_call_id
    assert response.errors[0]['source_id'] == provider


def test_sc010_operation_alternatives_can_exercise_a_budget_boundary_without_prescribing_order():
    bundle = load_scenario(PACKAGE, 'SC-010')
    ops = bundle.driver.script.operations
    assert sum(len(op.attempts) for op in ops) > 12  # Availability is not dispatch authorization.
    originals = [op for op in ops if op.source_id == 'NWS_MARINE']
    assert {tuple(op.candidate_beach_ids) for op in originals} == {
        ('TEST_BEACH_A', 'TEST_BEACH_B', 'TEST_BEACH_C', 'TEST_BEACH_D'),
        ('TEST_BEACH_A',), ('TEST_BEACH_B',), ('TEST_BEACH_C',), ('TEST_BEACH_D',)}
    assert len({json.dumps(op.geographic_scope, sort_keys=True) for op in originals}) == len(originals)
    for op in originals:
        assert [attempt.attempt for attempt in op.attempts] == [1, 2]
        assert all(attempt.behavior == 'ERROR' for attempt in op.attempts)
    for op in ops:
        assert len(op.attempts) <= 2


def test_sc004_independent_plan_requires_b_and_disallows_empty_or_padded_results():
    bundle = load_scenario(PACKAGE, 'SC-004')
    assert any(a.expected == 1 for a in checks(bundle, 'recommendation', operator='COUNT_EQUALS'))
    assert checks(bundle, 'recommendation', operator='EXISTS', beach_id='TEST_BEACH_B')
    for letter in 'ACDE':
        assert checks(bundle, 'recommendation', operator='ABSENT', beach_id=f'TEST_BEACH_{letter}')
    assert any(a.expected == 'EXCLUDED' for a in checks(bundle, 'candidate_assessment', '/eligibility', 'EQUALS', beach_id='TEST_BEACH_A'))
    assert any(a.expected == 'ELIGIBLE' for a in checks(bundle, 'candidate_assessment', '/eligibility', 'EQUALS', beach_id='TEST_BEACH_B'))
    assert any(a.expected == 'RECOMMENDATIONS' for a in checks(bundle, 'recommendation_result', '/outcome', 'EQUALS'))
    assert any(a.expected == 'HM-WATER-001' for a in checks(bundle, 'candidate_assessment', '/disqualifying_policy_ids', 'INCLUDES', beach_id='TEST_BEACH_A'))


def test_sc010_plan_preserves_unknown_assessments_and_abstention_for_supported_candidates():
    bundle = load_scenario(PACKAGE, 'SC-010')
    for beach in SUPPORTED:
        for field, value in [('/eligibility', 'NEEDS_INVESTIGATION'), ('/evidence_quality', 'INSUFFICIENT'),
                             ('/environmental_suitability', 'UNDETERMINED')]:
            assert any(a.expected == value for a in checks(bundle, 'candidate_assessment', field, 'EQUALS', beach_id=beach))
    assert any(a.expected == 'NO_RECOMMENDATION' for a in checks(bundle, 'recommendation_result', '/outcome', 'EQUALS'))
    assert any(a.expected == 'ABSTAINED' for a in checks(bundle, 'investigation_state', '/status', 'EQUALS'))
    assert any(a.expected == 0 for a in checks(bundle, 'recommendation', operator='COUNT_EQUALS'))
    assert checks(bundle, 'recommendation_result', '/explanation', 'NOT_EQUALS')
    # Successful optional weather/water retrieval is not forced when ocean gaps already preclude eligibility.
    assert not checks(bundle, 'environmental_finding', '/validation_status', 'EQUALS')


@pytest.mark.parametrize('sid,events', [
    ('SC-004', {'EVIDENCE_RECEIVED', 'POLICY_EVALUATED', 'CANDIDATE_EXCLUDED', 'CANDIDATE_ELIGIBLE', 'INVESTIGATION_COMPLETED'}),
    ('SC-010', {'TOOL_FAILED', 'FALLBACK_INITIATED', 'INVESTIGATION_LIMIT_REACHED', 'INVESTIGATION_ABSTAINED'}),
])
def test_required_trace_events_have_explicit_expectations(sid, events):
    bundle = load_scenario(PACKAGE, sid)
    planned = {a.selector.get('event_type') for a in checks(bundle, 'trace_event', operator='EXISTS')}
    assert events <= planned
    assert checks(bundle, 'trace_event', operator='ABSENT', event_type='INVESTIGATION_FAILED')


def test_sc010_recovery_failures_are_correlated_not_just_named_events():
    bundle = load_scenario(PACKAGE, 'SC-010')
    for operation in ['sc-010-fallback-surf', 'sc-010-fallback-currents']:
        ref = {'operation_id': operation, 'attempt': 1}
        assert any(a.selector.get('related_call_ref') == ref
                   for a in checks(bundle, 'trace_event', operator='EXISTS', event_type='TOOL_FAILED'))
        assert any(a.selector.get('related_call_ref') == ref and a.expected == 'SOURCE_UNAVAILABLE'
                   for a in checks(bundle, 'trace_event', '/details/error_code', 'EQUALS'))


def test_mandatory_plan_coverage_and_observed_counter_links_are_explicit(scenario):
    _, bundle = scenario
    plan = bundle.evaluator.expected_results.assertions
    # Mandatory coverage is ACTIVE. Optional rows are ACTIVE (reported separately) or BLOCKED with a reason.
    assert all(a.test_status == 'ACTIVE' for a in plan if a.mandatory)
    assert all(a.test_status == 'ACTIVE' or (a.test_status == 'BLOCKED' and a.blocking_reason)
               for a in plan if not a.mandatory)
    assert len({a.assertion_id for a in plan}) == len(plan)
    coverage = {rid for a in plan for rid in a.requirement_ids}
    assert set(bundle.definition.requirement_ids) <= coverage
    assert {a.target for a in plan} == {'investigation_state', 'candidate_assessment', 'environmental_finding',
        'recommendation_result', 'recommendation', 'trace_event', 'harness_execution'}
    assert any(a.expected == 12 for a in checks(bundle, 'trace_event', operator='COUNT_AT_MOST', event_type='TOOL_CALLED'))
    assert checks(bundle, 'harness_execution', '/tool_invocation_count', 'SAME_AS')
    assert checks(bundle, 'trace_event', '/details/total_tool_calls', 'SAME_AS')


def test_evaluator_paths_and_values_do_not_enter_application_or_driver(scenario):
    sid, bundle = scenario
    expected_path = f'scenarios/{sid}/expected.json'
    for value in [bundle.application.model_dump_json(), bundle.driver.model_dump_json()]:
        assert expected_path not in value
        assert 'assertion_id' not in value
        assert 'expected_results' not in value
        assert 'artifact_digests' not in value
    assert bundle.evaluator.artifact_digests[expected_path] == hashlib.sha256((PACKAGE / expected_path).read_bytes()).hexdigest()
    for premise in bundle.application.policy_configuration.premises:
        assert {'eligibility', 'evidence_quality', 'environmental_suitability', 'policy_result'}.isdisjoint(premise.model_dump())


def test_mutating_oracle_does_not_change_case_inputs(tmp_path):
    root = Path(shutil.copytree(PACKAGE, tmp_path / 'package'))
    before = load_scenario(root, 'SC-004')
    file = root / 'scenarios/SC-004/expected.json'
    raw = json.loads(file.read_text())
    assertion = next(a for a in raw['assertions'] if a['target'] == 'candidate_assessment' and a.get('field') == '/eligibility')
    assertion['expected'] = 'NEEDS_INVESTIGATION'  # Deliberately wrong, but structurally valid oracle.
    file.write_text(json.dumps(raw))
    after = load_scenario(root, 'SC-004')
    assert before.application == after.application
    assert before.driver == after.driver
    assert before.evaluator != after.evaluator
