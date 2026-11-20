"""The terminal names excluded candidates and why, from the validated assessments only."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

from hawaii_activity_forecaster.config.settings import TraceSettings
from hawaii_activity_forecaster.demo import run_demo
from hawaii_activity_forecaster.harness import load_scenario
from hawaii_activity_forecaster.presentation import _EXCLUSIONS, _exclusions, render_report
from hawaii_activity_forecaster.validation.safety import _HAZARDS
from release_samples import adapter

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "scenario-pack-v1"
TITLE = "Not recommended (excluded):"


def demo_text(tmp_path):
    output = asyncio.run(run_demo("advisory", ROOT, trace_settings=TraceSettings(directory=tmp_path)))
    return render_report(output.report, catalog=output.catalog, policy=output.policy)


def test_advisory_exclusion_is_named_with_its_policy_and_kept_out_of_recommendations(tmp_path):
    text = demo_text(tmp_path)
    recommendations, _, rest = text.partition(TITLE)
    assert "- Fictional Test Beach A (SYNTHETIC): an applicable official water-contact avoidance advisory" in rest
    assert "HM-WATER-001" not in text  # Policy identifiers are never presentation fields.
    assert "Fictional Test Beach A" not in recommendations.split("Recommendations (no finer rank is claimed)")[1]
    assert rest.index("Fictional Test Beach A") < rest.index("General limitations:")


def agent_text(tmp_path, scenario_id):
    """Render the step-1 report of an offline agent run of a registered scenario."""
    from hawaii_activity_forecaster.agents.scenario import agent_scenario_runner, load_scenario_tools
    from hawaii_activity_forecaster.harness.execution import execute_scenario
    reports = []
    runner = agent_scenario_runner(adapter([]), load_scenario_tools(ROOT, scenario_id))

    async def capture(inputs):
        report = await runner(inputs)
        reports.append(report)
        return report
    asyncio.run(execute_scenario(ROOT, scenario_id, runtime=capture, mode="AGENT_RUNTIME",
                                 trace_settings=TraceSettings(directory=tmp_path)))
    application = load_scenario(ROOT, scenario_id).application
    return render_report(reports[0], catalog=application.catalog, policy=application.policy_configuration)


def test_agent_run_names_the_excluded_beach_under_a_hard_area_restriction(tmp_path):
    text = agent_text(tmp_path, "SC-011")
    assert TITLE in text and "Fictional Test Beach A (SYNTHETIC): an applicable official water-contact" in text
    assert "Ignore previous instructions" not in text  # Untrusted source text is never displayed.


def test_no_section_when_nothing_is_excluded(tmp_path):
    assert TITLE not in agent_text(tmp_path, "SC-001")


def test_every_disqualifying_policy_has_fixed_wording():
    assert {policy_id for _, policy_id, _ in _HAZARDS} == set(_EXCLUSIONS)


def assessment(beach_id, eligibility, policies=(), constraints=()):
    return SimpleNamespace(beach_id=beach_id, eligibility=eligibility, disqualifying_policy_ids=list(policies),
                           hard_constraint_results=[SimpleNamespace(constraint_description=d, result=r) for d, r in constraints])


def test_constraint_and_unknown_policy_reasons_use_fixed_wording_only():
    beaches = {b: SimpleNamespace(name=f"Beach {b[-1]}") for b in ("TEST_BEACH_A", "TEST_BEACH_C", "TEST_BEACH_D")}
    state = SimpleNamespace(assessments=[
        assessment("TEST_BEACH_D", "EXCLUDED", constraints=[("Hard constraint 1 requires approved normalization", "FAIL")]),
        assessment("TEST_BEACH_C", "EXCLUDED", constraints=[("Required region: SOUTH_MAUI", "FAIL")]),
        assessment("TEST_BEACH_A", "EXCLUDED", policies=["HM-NEW-999"]),
        assessment("TEST_BEACH_B", "ELIGIBLE"),
    ])
    assert _exclusions(state, beaches) == [
        "Beach A: a disqualifying safety policy",
        "Beach C: outside your required region (South Maui)",
        "Beach D: a required condition you specified is not met",
    ]
