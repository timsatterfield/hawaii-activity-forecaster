"""Independent proposal checks and origin-preserving normalized follow-up merge."""

from dataclasses import asdict, replace
from datetime import date, datetime
from hashlib import sha256
import json
from typing import Literal

from hawaii_activity_forecaster.catalog import HST, known_location, location_descriptor, resolve_location
from hawaii_activity_forecaster.models import BeachCatalog, NormalizedRequest, TimeRange
from hawaii_activity_forecaster.models.common import ContractModel, PositiveInt, Text, Timestamp
from .clauses import analyze
from .contracts import (
    PROFILE_ID, InterpretationProposal, InterpreterInput,
    RequestContext, RequestValidationError, ValidatedRequest,
)


class _Scope(ContractModel):
    original_request: Text
    reference_time: Timestamp
    session_id: Text
    investigation_id: Text
    request_revision: PositiveInt
    prior_status: Literal["COMPLETED", "ABSTAINED", "FAILED"] | None
    rule_profile: Literal[PROFILE_ID]


def _json(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError("Unsupported audit value")


def digest(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json).encode()).hexdigest()


def checked_context(context: RequestContext) -> RequestContext:
    try:
        scope = _Scope.model_validate({key: getattr(context, key) for key in _Scope.model_fields})
        catalog = BeachCatalog.model_validate(context.catalog.model_dump())
        prior = context.inherited
        if prior is None:
            if scope.request_revision != 1 or scope.prior_status is not None:
                raise ValueError("Initial context mismatch")
        elif (scope.prior_status is None or prior.session_id != scope.session_id
              or prior.request_revision + 1 != scope.request_revision or prior.investigation_id == scope.investigation_id
              or (prior.request.clarification_needed and scope.prior_status != "FAILED")):
            raise ValueError("Post-terminal context mismatch")
        return replace(context, **scope.model_dump(), catalog=catalog)
    except (ValueError, TypeError, AttributeError):
        raise RequestValidationError("Invalid request-validation context.") from None


def context_digest(context: RequestContext) -> str:
    prior = context.inherited
    return digest({**{key: getattr(context, key) for key in _Scope.model_fields}, "catalog": context.catalog,
                   "inherited": None if prior is None else {
                       "session": prior.session_id, "investigation": prior.investigation_id, "revision": prior.request_revision,
                       "context_digest": prior.context_digest, "request": prior.request,
                       "origins": [asdict(o) for o in prior.origins], "limitations": prior.limitations,
                       "starting_locations": [asdict(v) for v in prior.starting_locations],
                   }})


def _descriptor(item, name, prior):
    if item in prior:
        return  # Existing opaque entries may be retained, never upgraded.
    if item.get("kind") == "LOCATION_RESTRICTION" and name == "hard_constraints" and location_descriptor(item):
        return
    if item == {"kind": "CALM_WATER"} and name == "soft_preferences":
        return
    if set(item) == {"kind", "text"} and item["kind"] == "UNINTERPRETED" and isinstance(item["text"], str) and item["text"].strip():
        return
    raise RequestValidationError("Invalid request descriptor.")


def _canonical(name, value, base, context):
    candidate = NormalizedRequest.model_validate(base | {name: value})
    value = getattr(candidate, name)
    if name == "target_time_window" and value is not None:
        value = TimeRange(start=value.start.astimezone(HST), end=value.end.astimezone(HST))
    if name == "preferred_area" and value is not None:
        choices = resolve_location(context.catalog, value, ("REGION", "LOCALITY"))
        if len(choices) != 1:
            raise RequestValidationError("Proposed area is not uniquely resolved.")
        value = choices[0][1]
    if name in {"hard_constraints", "soft_preferences"}:
        for item in value:
            _descriptor(item, name, base[name])
            if item.get("kind") == "LOCATION_RESTRICTION" and not known_location(item, context.catalog):
                raise RequestValidationError("Proposed location is not in the catalog.")
    return value


def _covers(span, target):
    return span.start <= target[0] and span.end >= target[1]


def validate_request(proposal, context: RequestContext) -> ValidatedRequest:
    """Validate authored interpretation output; perform no calls, events or state writes."""
    try:
        return _validate(proposal, checked_context(context))
    except (ValueError, TypeError, AttributeError, KeyError, IndexError):
        raise RequestValidationError("Request proposal or its supporting context could not be validated.") from None


def _validate(proposal, context):
    proposal = InterpretationProposal.model_validate(proposal.model_dump() if isinstance(proposal, InterpretationProposal) else proposal)
    spans = [*proposal.source_spans, *proposal.removed_entries, *proposal.unresolved_spans]
    if any(span.end > len(context.original_request) for span in spans):
        raise RequestValidationError("Source span is outside the utterance.")
    keys = [(s.field, s.entry_index, s.start, s.end) for s in proposal.source_spans]
    if len(keys) != len(set(keys)):
        raise RequestValidationError("Duplicate source spans")
    prior = context.inherited.request if context.inherited else None
    base = (prior.model_dump() if prior is not None else NormalizedRequest(
        original_request=context.original_request, hard_constraints=[], soft_preferences=[],
        clarification_needed=False, clarification_questions=[],
    ).model_dump()) | {"original_request": context.original_request, "clarification_needed": False, "clarification_questions": []}
    meaning = analyze(context, prior)
    proposed = {name: _canonical(name, value, base, context) for name, value in proposal.changed_values.items()}
    expected_removed = {(name, index, span[0], span[1]) for name, index, span in meaning.removals}
    actual_removed = [(s.field, s.previous_index, s.start, s.end) for s in proposal.removed_entries]
    if len(actual_removed) != len(set(actual_removed)) or set(actual_removed) != expected_removed:
        raise RequestValidationError("Removal is not supported by the current utterance.")
    auto = {name for name, _, span in meaning.unresolved if any(_covers(s, span) for s in proposal.unresolved_spans)}
    for name, value in proposed.items():
        if name in meaning.uncertain:
            continue  # Preserve uncertainty; never let a model select one disputed interpretation.
        if name not in meaning.changes or value != meaning.changes[name]:
            raise RequestValidationError("Proposed change is not supported by its clause.")
    for name in meaning.changes:
        dependent = meaning.origins.get((name, None))
        if name not in proposed and name not in auto and not (dependent and dependent.source == "INHERITED"):
            raise RequestValidationError("Proposal omitted a supported change.")
    for (name, index), origin in meaning.origins.items():
        if origin.span is None:
            continue
        matching = [s for s in proposal.source_spans if s.field == name and s.entry_index in (None, index) and _covers(s, origin.span)]
        unresolved = (name in auto and any(n == name and i == index for n, i, _ in meaning.unresolved))
        if not matching and not unresolved:
            raise RequestValidationError("A changed value lacks its relevant source span.")
    for span in proposal.source_spans:
        if span.field not in proposed or not any(name == span.field and span.entry_index in (None, index)
                and origin.span is not None and _covers(span, origin.span) for (name, index), origin in meaning.origins.items()):
            # List removals are supported by the exact removed_entries references.
            if not any(name == span.field and _covers(span, area) for name, _, area in meaning.removals):
                raise RequestValidationError("Source span does not support this field.")
    data = base | meaning.changes
    for name in meaning.uncertain:
        data[name] = base[name]
    if data["activity"] is None:
        meaning.question("Which supported activity do you want: swimming, snorkeling or SUP?")
    if data["target_date"] is None or data["target_time_window"] is None:
        meaning.question("What date and time interval should be investigated?")
    window = data["target_time_window"]
    if window is not None:
        window = TimeRange.model_validate(window)
        data["target_time_window"] = window
        if data["target_date"] is not None and window.start.astimezone(HST).date() != data["target_date"]:
            meaning.question("Please make the requested date and Hawaii time window consistent.")
        if window.start < context.reference_time:
            meaning.question("The requested interval has already started; please give a current or future interval.")
    if any(not known_location(item, context.catalog) for item in data["hard_constraints"]):
        meaning.question("A retained mandatory condition requires clarification or an approved interpretation.")
    if any(item.get("kind") in {"CALM_WATER", "UNINTERPRETED"} for item in data["soft_preferences"]):
        meaning.limitations.append("Soft preference alignment remains UNKNOWN until independently established; it is not a suitability claim.")
    data.update(clarification_needed=bool(meaning.questions), clarification_questions=meaning.questions)
    request = NormalizedRequest.model_validate(data)
    origins = []
    if context.inherited:
        removed = {(name, index) for name, index, _ in meaning.removals}
        for origin in context.inherited.origins:
            if origin.entry_index is None:
                if (origin.field, None) in meaning.origins:
                    continue
                index = None
            else:
                if (origin.field, origin.entry_index) in removed:
                    continue
                index = origin.entry_index - sum(n == origin.field and i < origin.entry_index for n, i in removed)
                if (origin.field, index) in meaning.origins:
                    continue
            origins.append(replace(origin, entry_index=index, source="INHERITED", span=None,
                                   inherited_from=context.inherited.investigation_id))
    origins.extend(meaning.origins.values())
    starting = tuple(meaning.starting)
    if context.inherited and not meaning.starting_changed:
        starting = tuple(replace(item, span=None, inherited_from=context.inherited.investigation_id)
                         for item in context.inherited.starting_locations)
    return ValidatedRequest(context.session_id, context.investigation_id, context.request_revision, context_digest(context),
                            tuple(sorted(origins, key=lambda o: (o.field, -1 if o.entry_index is None else o.entry_index))),
                            tuple(sorted(meaning.changes)), tuple(dict.fromkeys(meaning.limitations)),
                            starting, request.model_dump_json().encode(), proposal.model_dump_json().encode())


def verify_request(receipt: ValidatedRequest, context: RequestContext) -> ValidatedRequest:
    try:
        canonical = validate_request(InterpretationProposal.model_validate_json(receipt._proposal), context)
        if receipt != canonical:
            raise ValueError("Receipt mismatch")
        return canonical
    except (ValueError, TypeError, AttributeError):
        raise RequestValidationError("Request receipt is stale or inconsistent.") from None


def interpret_request(context: RequestContext, interpreter) -> ValidatedRequest:
    """Invoke an authored synchronous proposal callback with isolated input data.

    This seam performs no SDK/tool dispatch and records no model usage. A live
    adapter and its shared-budget admission remain a separately authorized step.
    """
    context = checked_context(context)
    inherited = context.inherited
    inputs = InterpreterInput(context.original_request, context.reference_time, context.session_id,
        context.investigation_id, context.request_revision, context.rule_profile,
        tuple((b.beach_id, b.name, tuple(b.aliases or ()), b.region.value, b.locality) for b in context.catalog.root),
        inherited.origins if inherited else (), inherited._request if inherited else None)
    try:
        proposal = interpreter(inputs)
    except Exception:
        raise RequestValidationError("Synthetic interpreter did not return a proposal.") from None
    return validate_request(proposal, context)
