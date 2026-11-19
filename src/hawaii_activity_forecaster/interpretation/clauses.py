"""Conservative supported-clause checks, not a general language interpreter.

The independent checks below verify authored proposals. Uncovered language asks
for clarification rather than accepting a model's unsupported interpretation.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import re

from hawaii_activity_forecaster.catalog import HST, resolve_location, location_match
from hawaii_activity_forecaster.models import TimeRange
from .contracts import ContextLocation, Origin
from .profile import RequestRuleProfile

_ACTIVITIES = {
    "swim": "SWIMMING", "swimming": "SWIMMING", "snorkel": "SNORKELING", "snorkeling": "SNORKELING",
    "sup": "SUP", "paddleboard": "SUP", "stand-up paddleboarding": "SUP", "stand up paddleboarding": "SUP",
}
_DATE = r"\b(?:today|tomorrow|\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b"
_ISO = r"\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d(?:\.\d{1,6})?)?(?:Z|[+-]\d\d:\d\d)"
_CLOCK = r"(?P<h{}>\d{{1,2}})(?::(?P<m{}>\d{{2}}))?\s*(?P<a{}>[ap]\.?m\.?)?"
_RANGE = re.compile(r"(?<![\d:\w-])(?:from\s+)?" + _CLOCK.format(1, 1, 1) + r"\s*(?:to|[–-])\s*" + _CLOCK.format(2, 2, 2) + r"(?![\d:\w])", re.I)
_FILLER = frozenset("where what about try should can could would may i we me us you my our go want like to the a an please actually let let's look instead and or on for is am i'm im from at hst hawaii time request fictional demo recommend somewhere location locations beach beaches thanks thank with now it be do that have of".split())


@dataclass
class Meaning:
    changes: dict = field(default_factory=dict)
    origins: dict = field(default_factory=dict)
    consumed: list = field(default_factory=list)
    questions: list = field(default_factory=list)
    limitations: list = field(default_factory=list)
    uncertain: set = field(default_factory=set)
    removals: list = field(default_factory=list)
    starting: list = field(default_factory=list)
    starting_changed: bool = False
    unresolved: list = field(default_factory=list)

    def put(self, name, value, span, *, assumed=False, default_rule=None):
        self.changes[name] = value
        self.origins[(name, None)] = Origin(name, None, "DEFAULT" if assumed else "USER", span, assumed, default_rule)
        self.consumed.append(span)

    def question(self, text):
        if text not in self.questions:
            self.questions.append(text)


def _overlaps(span, used):
    return any(span[0] < end and span[1] > start for start, end in used)


def _negative(text, start):
    prefix = re.split(r"[.;!?]|\b(?:but|instead)\b", text[:start], flags=re.I)[-1]
    return bool(re.search(r"\b(?:not|never|no|don['’]t|won['’]t|cannot|can['’]t)\b", prefix, re.I))


def _date_value(text, clock):
    key = text.casefold()
    if key in {"today", "tomorrow"}:
        return clock.astimezone(HST).date() + timedelta(days=key == "tomorrow")
    if re.fullmatch(r"\d{4}-\d\d-\d\d", text):
        return date.fromisoformat(text)
    # The approved English rule profile must not depend on the host's locale.
    month, day, year = text.replace(",", "").split()
    months = "january february march april may june july august september october november december".split()
    return date(int(year), months.index(month.casefold()) + 1, int(day))


def _clock_pair(match):
    parts = match.groupdict()
    first, second = parts["a1"], parts["a2"]
    # An explicit final meridiem also governs a simple ascending same-period pair.
    if first is None and second and int(parts["h1"]) <= int(parts["h2"]):
        first = second
    if second is None and first and int(parts["h1"]) <= int(parts["h2"]):
        second = first
    result = []
    for number, suffix in ((1, first), (2, second)):
        hour, minute = int(parts[f"h{number}"]), int(parts[f"m{number}"] or 0)
        if minute > 59:
            raise ValueError("invalid minute")
        if suffix:
            if not 1 <= hour <= 12:
                raise ValueError("invalid meridiem hour")
            hour = hour % 12 + (12 if suffix.casefold().startswith("p") else 0)
        elif not (parts["m1"] is not None and parts["m2"] is not None and 0 <= hour <= 23):
            raise ValueError("ambiguous meridiem")
        result.append((hour, minute))
    return result


def analyze(context, prior):
    text, result = context.original_request, Meaning()
    base = prior.model_dump() if prior is not None else {}
    lists = {name: list(base.get(name, [])) for name in ("hard_constraints", "soft_preferences")}

    for match in re.finditer(r"\b(?:clear|remove)(?:\s+the)?\s+(?P<what>experience(?: level)?|requested date|time window)\b", text, re.I):
        name = "experience_level" if match["what"].casefold().startswith("experience") else (
            "target_date" if match["what"].casefold() == "requested date" else "target_time_window")
        result.put(name, None, match.span())

    # Process explicit removals against prior indices, never against new additions.
    removal_pattern = r"\b(?:remove|drop)\s+(?:the\s+|that\s+)?(?P<what>[^,;.!?]+?)(?=\s+and\s+|[,;.!?]|$)"
    removed = {name: set() for name in lists}
    for match in re.finditer(removal_pattern, text, re.I):
        if _overlaps(match.span(), result.consumed):
            continue
        what = match["what"].strip().casefold()
        targets = []
        if what in {"restriction", "constraint"}:
            targets = [("hard_constraints", n) for n in range(len(lists["hard_constraints"]))]
        elif what in {"preference", "calm water preference", "calm-water preference"}:
            targets = [("soft_preferences", n) for n, item in enumerate(lists["soft_preferences"])
                       if what == "preference" or item.get("kind") == "CALM_WATER"]
            if what == "preference" and base.get("preferred_area"):
                targets.append(("preferred_area", None))
        elif what.endswith(" restriction"):
            label = what.removesuffix(" restriction")
            known = resolve_location(context.catalog, label)
            targets = [("hard_constraints", n) for n, item in enumerate(lists["hard_constraints"])
                       if item.get("kind") == "LOCATION_RESTRICTION" and (item.get("scope"), item.get("value")) in known]
        if len(targets) != 1:
            result.question("Which existing constraint or preference should be removed?")
        else:
            name, index = targets[0]
            if index is None:
                result.put(name, None, match.span())
            else:
                removed[name].add(index)
                result.removals.append((name, index, match.span()))
        result.consumed.append(match.span())
    for name in lists:
        if removed[name]:
            lists[name] = [item for n, item in enumerate(lists[name]) if n not in removed[name]]
            result.changes[name] = lists[name]

    def add(name, item, span, unresolved=False):
        if item not in lists[name]:
            lists[name].append(item)
        index = lists[name].index(item)
        result.changes[name] = lists[name]
        result.origins[(name, index)] = Origin(name, index, "USER", span)
        result.consumed.append(span)
        if unresolved:
            result.unresolved.append((name, index, span))

    activity_hits = []
    for match in re.finditer(r"\b(?:stand[- ]up paddleboarding|swimming|snorkeling|swim|snorkel|paddleboard|sup|surfing|kayaking|scuba|boating|paddling)\b", text, re.I):
        if _overlaps(match.span(), result.consumed):
            continue
        value = _ACTIVITIES.get(match[0].casefold())
        if not _negative(text, match.start()):
            activity_hits.append((value, match.span()))
        result.consumed.append(match.span())
    if activity_hits:
        choices = {value for value, _ in activity_hits}
        if None in choices or len(choices) != 1:
            result.uncertain.add("activity")
            result.question("Choose one supported activity: swimming, snorkeling or SUP.")
        else:
            result.put("activity", activity_hits[0][0], activity_hits[0][1])
    for match in re.finditer(r"\b(?:beginner|intermediate|advanced)\b", text, re.I):
        if _negative(text, match.start()):
            result.question("Please clarify the stated experience level.")
            result.uncertain.add("experience_level")
        elif "experience_level" in result.changes and result.changes["experience_level"] != match[0].upper():
            result.question("Please clarify the stated experience level.")
            result.uncertain.add("experience_level")
        else:
            result.put("experience_level", match[0].upper(), match.span())
        result.consumed.append(match.span())

    # Parse offset-aware ISO intervals first so their two dates are not mistaken
    # for conflicting standalone dates or their clock fragments for local ranges.
    iso = list(re.finditer(r"(?P<start>" + _ISO + r")\s*(?:/|to)\s*(?P<end>" + _ISO + r")", text, re.I))
    window = None
    if iso:
        for match in iso:
            result.consumed.append(match.span())
        try:
            if len(iso) != 1:
                raise ValueError("multiple intervals")
            window = TimeRange(start=datetime.fromisoformat(iso[0]["start"].replace("Z", "+00:00").replace("z", "+00:00")).astimezone(HST),
                               end=datetime.fromisoformat(iso[0]["end"].replace("Z", "+00:00").replace("z", "+00:00")).astimezone(HST))
            result.put("target_time_window", window, iso[0].span())
            result.put("target_date", window.start.date(), iso[0].span())
        except ValueError:
            result.question("Please provide one valid offset-aware time interval.")
            result.uncertain.update({"target_date", "target_time_window"})
    dates = []
    for match in re.finditer(_DATE, text, re.I):
        if _overlaps(match.span(), [m.span() for m in iso]):
            continue
        result.consumed.append(match.span())
        try:
            dates.append((_date_value(match[0], context.reference_time), match.span()))
        except ValueError:
            result.question("Please provide a valid calendar date.")
            result.uncertain.add("target_date")
    if dates:
        if len({d for d, _ in dates}) != 1 or (window and window.start.date() != dates[0][0]):
            result.question("Please clarify the conflicting requested dates.")
            result.uncertain.update({"target_date", "target_time_window"})
        else:
            result.put("target_date", dates[0][0], dates[0][1])
    day = result.changes.get("target_date", base.get("target_date"))
    dayparts = list(re.finditer(r"\b(?:morning|afternoon|evening|tonight|night)\b", text, re.I))
    ranges = [m for m in _RANGE.finditer(text) if not _overlaps(m.span(), [m.span() for m in iso])
              and not _overlaps(m.span(), [span for _, span in dates])]
    for match in dayparts:
        result.consumed.append(match.span())
    if ranges:
        for match in ranges:
            result.consumed.append(match.span())
        try:
            if len(ranges) != 1 or day is None:
                raise ValueError("date or interval ambiguous")
            start, end = _clock_pair(ranges[0])
            window = TimeRange(start=datetime(day.year, day.month, day.day, *start, tzinfo=HST),
                               end=datetime(day.year, day.month, day.day, *end, tzinfo=HST))
            result.put("target_time_window", window, ranges[0].span())
        except ValueError:
            result.question("Please provide a date and an unambiguous start/end time.")
            result.uncertain.add("target_time_window")
    elif dayparts and not iso:
        try:
            if len(dayparts) != 1 or day is None:
                raise ValueError("daypart ambiguous")
            window = RequestRuleProfile().daypart_window(dayparts[0][0].casefold(), day)
            result.put("target_time_window", window, dayparts[0].span(), assumed=True,
                       default_rule=dayparts[0][0].casefold())
        except ValueError:
            result.question("Please provide a date and explicit hours for this time period.")
            result.uncertain.add("target_time_window")
    elif dates and not iso and prior is not None and prior.target_time_window is not None and day is not None:
        previous = prior.target_time_window
        offset = previous.end.astimezone(HST).date() - previous.start.astimezone(HST).date()
        window = TimeRange(start=datetime.combine(day, previous.start.astimezone(HST).timetz()),
                           end=datetime.combine(day + offset, previous.end.astimezone(HST).timetz()))
        result.changes["target_time_window"] = window
        # Preserve inherited hour precision when only the calendar date changes.
        result.origins[("target_time_window", None)] = Origin("target_time_window", None, "INHERITED", inherited_from=context.inherited.investigation_id,
            assumed="target_time_window" in context.inherited.assumed_fields,
            default_rule=next((o.default_rule for o in context.inherited.origins if o.field == "target_time_window"), None))

    for match in re.finditer(r"\b(?:anywhere is fine|no area preference|clear (?:the )?area preference)\b", text, re.I):
        result.put("preferred_area", None, match.span())
    for match in re.finditer(r"\b(?:prefer|ideally)(?:\s+some)?\s+calm[ -]water\b", text, re.I):
        if _negative(text, match.start()):
            result.question("Please clarify the environmental preference change.")
        else:
            add("soft_preferences", {"kind": "CALM_WATER"}, match.span())
    # Preserve a complete unresolved mandatory clause before looking for an
    # embedded preposition such as "in waves" inside "I won't go in waves".
    for match in re.finditer(r"\b(?:I\s+)?(?:won['’]t|will not|must|cannot|can['’]t|avoid|do not|don['’]t)\b[^,;.!?]*", text, re.I):
        if not _overlaps(match.span(), result.consumed) and not re.match(r"must\s+stay\s+in\b", match[0], re.I):
            add("hard_constraints", {"kind": "UNINTERPRETED", "text": match[0]}, match.span(), unresolved=True)
            result.question("Please clarify the mandatory condition; no approved interpretation can establish it.")
    # Location phrases end at punctuation, a time phrase or an explicit connector.
    location_pattern = (r"\b(?P<prefix>staying\s+in|must\s+stay\s+in|prefer\s+near|near|prefer|ideally|only|in|at)\s+"
                        r"(?P<target>.+?)(?=\s+(?:tomorrow|today|morning|afternoon|from\s+\d|and|instead)\b|[,;.!?]|$)")
    for match in re.finditer(location_pattern, text, re.I):
        if _overlaps(match.span(), result.consumed):
            continue
        prefix = " ".join(match["prefix"].casefold().split())
        soft = prefix in {"near", "prefer", "prefer near", "ideally"}
        scopes = ("REGION", "LOCALITY") if soft or prefix == "in" else ("BEACH",) if prefix == "at" else ("REGION", "LOCALITY", "BEACH")
        choices = resolve_location(context.catalog, match["target"].strip(), scopes)
        if _negative(text, match.start()):
            choices = ()
        if prefix == "staying in":
            result.starting_changed = True
            if len(choices) == 1:
                result.starting.append(ContextLocation(*choices[0], match.span()))
            else:
                result.limitations.append("Starting location is not uniquely resolved in the catalog.")
            result.consumed.append(match.span())
        elif len(choices) == 1:
            scope, value = choices[0]
            if soft:
                if "preferred_area" in result.changes and result.changes["preferred_area"] not in {None, value}:
                    result.question("Please clarify which area preference should replace the previous one.")
                    result.uncertain.add("preferred_area")
                else:
                    result.put("preferred_area", value, match.span())
            else:
                add("hard_constraints", {"kind": "LOCATION_RESTRICTION", "scope": scope, "value": value}, match.span())
        else:
            name = "soft_preferences" if soft else "hard_constraints"
            add(name, {"kind": "UNINTERPRETED", "text": match[0]}, match.span(), unresolved=True)
            if soft:
                result.limitations.append("An uninterpreted soft preference cannot be claimed as satisfied; no nearby relationship is inferred.")
                if prefix in {"near", "prefer near"} and base.get("preferred_area"):
                    result.put("preferred_area", None, match.span())
            else:
                result.question("Please provide a unique supported location for the mandatory restriction.")

    for match in re.finditer(r"\b(?:prefer|ideally)\b[^,;.!?]*", text, re.I):
        if not _overlaps(match.span(), result.consumed):
            add("soft_preferences", {"kind": "UNINTERPRETED", "text": match[0]}, match.span(), unresolved=True)
            result.limitations.append("An uninterpreted soft preference cannot be claimed as satisfied.")

    # Account for unmatched words instead of allowing a valid keyword quote to
    # silently erase unsupported or contradictory clauses.
    leftovers = [m[0].casefold().replace("’", "'") for m in re.finditer(r"[^\W\d_]+(?:['’][^\W\d_]+)?", text)
                 if not _overlaps(m.span(), result.consumed)]
    if any(word not in _FILLER for word in leftovers):
        result.question("Please restate the unrecognized request details using explicit activity, date, hours and catalog locations.")
    if re.search(r"\b(?:PST|PDT|EST|EDT|CST|UTC)\b", text, re.I) and not iso:
        result.question("Please give Hawaii hours or an explicit ISO interval with offsets.")
    for name in result.uncertain:
        result.changes.pop(name, None)
        result.origins.pop((name, None), None)
    active_hard = result.changes.get("hard_constraints", base.get("hard_constraints", []))
    locations = [item for item in active_hard if item.get("kind") == "LOCATION_RESTRICTION"]
    if locations and not any(all(location_match(item, b) for item in locations) for b in context.catalog.root):
        result.question("Please clarify the mutually incompatible mandatory locations.")
    return result
