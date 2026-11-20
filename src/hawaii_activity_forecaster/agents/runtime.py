"""Three-role model planning around the existing trusted synthetic dispatcher.

Only small, explicitly configured ToolAction allowlists enter this layer. Neither
behavior scripts, response templates, policy premises nor evaluator inputs are
model context. The model proposes work; existing contracts/validators authorize it.
"""

import json
from uuid import uuid4

from hawaii_activity_forecaster.model_runtime.contracts import (
    CoordinatorInput, InvocationIdentity, SpecialistInput,
)
from hawaii_activity_forecaster.models import NormalizedRequest, SpecialistInvestigationRequest
from hawaii_activity_forecaster.tools import ToolAction, ToolPlanError


def _identity(state):
    return InvocationIdentity(session_id=state.session_id, investigation_id=state.investigation_id,
                              request_revision=state.request_revision)


class AgentRuntime:
    """One investigation's Coordinator and Weather/Ocean planners, not a new role."""

    def __init__(self, adapter, options):
        self.adapter, self._options = adapter, options
        self._delegated = set()

    def _choices(self, role, candidates, window):
        result = tuple(ToolAction.model_validate(a.model_dump()) for a in self._options(role, tuple(candidates), window))
        if len({a.action_id for a in result}) != len(result):
            raise ToolPlanError("Duplicate configured tool option")
        return result

    async def plan(self, inputs):
        state, counts = inputs.state, inputs.budgets
        identity = _identity(state)
        legal = []
        for role in ("WEATHER", "OCEAN"):
            if role in self._delegated:
                continue
            choices = self._choices(role, inputs.investigation_candidate_ids, state.target_time_window)
            categories = sorted({str(c) for a in choices for c in a.requested_evidence})
            if choices:
                legal.append(dict(agent_type=role, candidate_ids=list(inputs.investigation_candidate_ids),
                                  evidence_categories=categories, gap_ids=[]))
        # The final model decision observes canonical assessments. Stop permissions
        # come from trusted state, never a model's claim that evidence is adequate.
        eligible = any(a.eligibility == "ELIGIBLE" for a in state.assessments)
        reasons = (["SUFFICIENT_EVIDENCE"] if eligible else []) + (["NO_LEGAL_ACTION"] if not legal else [])
        context = CoordinatorInput.model_validate_json(json.dumps(dict(identity=identity.model_dump(),
            request={k: v for k, v in state.model_dump(mode="json").items() if k in NormalizedRequest.model_fields},
            candidate_ids=list(inputs.investigation_candidate_ids),
            assessments=[dict(beach_id=a.beach_id, eligibility=a.eligibility,
                evidence_quality=a.evidence_quality, environmental_suitability=a.environmental_suitability)
                for a in state.assessments if a.beach_id in inputs.investigation_candidate_ids],
            observations=[], legal_tasks=legal, evidence_refs=[f.finding_id for f in state.weather_findings + state.ocean_findings],
            allowed_stop_reasons=reasons, remaining_model_calls=12-counts.model_calls-counts.reserved_model_calls,
            remaining_tool_calls=12-counts.tool_calls-counts.reserved_tool_calls,
            remaining_iterations=6-counts.iterations)))
        decision = await inputs.models.invoke("coordinator_plan", context)
        if decision.action == "CONCLUDE":
            return ()
        result = []
        for task in decision.tasks:
            self._delegated.add(task.agent_type)
            result.append(SpecialistInvestigationRequest(
                request_id=str(uuid4()), investigation_id=state.investigation_id,
                request_revision=state.request_revision, schema_version=state.schema_version,
                agent_type=task.agent_type, candidate_beach_ids=task.candidate_ids,
                target_time_window=state.target_time_window, requested_evidence=[dict(
                    requirement_id=str(uuid4()), evidence_type=c,
                    priority="OPTIONAL" if c == "UNDERWATER_VISIBILITY" else "REQUIRED") for c in task.evidence_categories],
                known_evidence_gaps=[], issued_at=state.updated_at, attempt_number=1))
        return tuple(result)

    async def tools(self, request, models, counts):
        choices = self._choices(request.agent_type, request.candidate_beach_ids, request.target_time_window)
        lookup = {a.action_id: a for a in choices}
        identity = models.identity
        context = SpecialistInput(identity=identity, request=request, gap_ids=[],
            legal_option_ids=list(lookup), observations=[],
            remaining_tool_calls=12-counts.tool_calls-counts.reserved_tool_calls)
        operation = "weather_investigation" if request.agent_type == "WEATHER" else "ocean_investigation"
        proposal = await models.invoke(operation, context)
        actions, originals = [], set()
        for index, step in enumerate(proposal.steps):
            option = lookup[step.option_id]
            expected = ("RETRY_IF_RETRYABLE_FAILURE" if option.retry_of else
                        "FALLBACK_IF_REQUIRED_GAP_UNRESOLVED" if option.fallback_of else "ALWAYS")
            if step.condition != expected:
                raise ToolPlanError("Recovery cannot be relabeled as a new original")
            if step.origin_step is not None:
                origin_option = lookup[proposal.steps[step.origin_step].option_id]
                origin_id = origin_option.retry_of or origin_option.action_id
                if origin_id != (option.retry_of or option.fallback_of):
                    raise ToolPlanError("Recovery does not reference its configured original")
            key = (option.source_id, tuple(sorted(option.candidate_beach_ids)),
                   tuple(sorted(option.requested_evidence)), json.dumps(option.geographic_scope, sort_keys=True))
            origin = actions[step.origin_step].action_id if step.origin_step is not None else None
            if step.condition == "ALWAYS":
                if key in originals:
                    raise ToolPlanError("A query cannot be a second original")
                originals.add(key)
            actions.append(ToolAction(**{**option.model_dump(), "action_id": f"{request.request_id}-{index}",
                "retry_of": origin if step.condition == "RETRY_IF_RETRYABLE_FAILURE" else None,
                "fallback_of": origin if step.condition == "FALLBACK_IF_REQUIRED_GAP_UNRESOLVED" else None}))
        return tuple(actions)
