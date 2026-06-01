from __future__ import annotations


TOOL_TYPE_TRANSFORM = "Transform / Move Actors"
TOOL_TYPE_TRACE = "Line Trace / HitResult"
TOOL_TYPE_SELECTION = "Selection"
TOOL_TYPE_ORGANIZATION = "Organization / Rename"
TOOL_TYPE_DEBUG = "Debug / Report"
TOOL_TYPE_CUSTOM = "Custom"

TOOL_TYPES = [
    TOOL_TYPE_TRANSFORM,
    TOOL_TYPE_TRACE,
    TOOL_TYPE_SELECTION,
    TOOL_TYPE_ORGANIZATION,
    TOOL_TYPE_DEBUG,
    TOOL_TYPE_CUSTOM,
]


SELECTED_ACTORS_HELPER = """selected_actors_helper:
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
selected_actors = [actor for actor in actor_subsystem.get_selected_level_actors() if actor is not None]
if not selected_actors:
    unreal.log_warning("No actors are selected.")
"""


ACTOR_LABEL_HELPER = """actor_label_helper:
def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()
"""


SAFE_MOVE_ACTOR_HELPER = """safe_move_actor_helper:
def nearly_same_location(a, b, tolerance=0.1):
    return abs(a.x - b.x) <= tolerance and abs(a.y - b.y) <= tolerance and abs(a.z - b.z) <= tolerance

def move_actor_to_location(actor, target_location, debug_log=False):
    old_location = actor.get_actor_location()
    actor.modify()
    actor.set_actor_location(target_location, False, False)
    new_location = actor.get_actor_location()
    moved_ok = nearly_same_location(new_location, target_location)
    if debug_log:
        unreal.log(f"Move debug: {actor_label(actor)} old={old_location} target={target_location} new={new_location} moved_ok={moved_ok}")
    return moved_ok, new_location
"""


HIT_RESULT_TO_TUPLE_HELPER = """hit_result_to_tuple_helper:
def hit_tuple(hit_result):
    try:
        return hit_result.to_tuple()
    except Exception:
        return None

def hit_tuple_value(hit_result, property_name):
    values = hit_tuple(hit_result)
    if values is None:
        return None
    indices = {
        "blocking_hit": 0,
        "location": 4,
        "impact_point": 5,
        "hit_actor": 9,
        "hit_component": 10,
    }
    index = indices.get(property_name)
    if index is None or index >= len(values):
        return None
    return values[index]

def hit_value(hit_result, property_name):
    value = hit_tuple_value(hit_result, property_name)
    if value is not None:
        return value
    try:
        return getattr(hit_result, property_name)
    except Exception:
        return hit_result.get_editor_property(property_name)

def hit_location(hit_result):
    for property_name in ("impact_point", "location"):
        try:
            value = hit_value(hit_result, property_name)
            if value is not None:
                return value
        except Exception:
            pass
    return None

def hit_blocks(hit_result):
    value = hit_tuple_value(hit_result, "blocking_hit")
    if value is not None:
        return bool(value)
    try:
        return bool(hit_value(hit_result, "blocking_hit"))
    except Exception:
        return hit_location(hit_result) is not None
"""


LINE_TRACE_DEBUG_HELPER = """line_trace_debug_helper:
def extract_hit_result(raw_hit, debug_log=False):
    if raw_hit is None:
        return None
    if isinstance(raw_hit, (list, tuple)):
        did_hit = bool(raw_hit[0]) if raw_hit else False
        hit_result = raw_hit[1] if len(raw_hit) > 1 else None
    else:
        hit_result = raw_hit
        did_hit = hit_blocks(hit_result)
    if debug_log:
        tuple_values = hit_tuple(hit_result) if hit_result is not None else None
        unreal.log(f"Trace debug: raw_type={type(raw_hit)} did_hit={did_hit} tuple_len={len(tuple_values) if tuple_values is not None else 'none'} location={hit_location(hit_result) if hit_result is not None else None}")
    if did_hit and hit_result is not None and hit_location(hit_result) is not None:
        return hit_result
    return None
"""


COUNT_AND_LOG_HELPER = """count_and_log_helper:
# Track changed_count, skipped_count, missed_count, failed_count.
# Always finish with unreal.log() reporting those counts.
"""


TYPE_SNIPPETS = {
    TOOL_TYPE_TRANSFORM: [SELECTED_ACTORS_HELPER, ACTOR_LABEL_HELPER, SAFE_MOVE_ACTOR_HELPER, COUNT_AND_LOG_HELPER],
    TOOL_TYPE_TRACE: [
        SELECTED_ACTORS_HELPER,
        ACTOR_LABEL_HELPER,
        HIT_RESULT_TO_TUPLE_HELPER,
        LINE_TRACE_DEBUG_HELPER,
        SAFE_MOVE_ACTOR_HELPER,
        COUNT_AND_LOG_HELPER,
    ],
    TOOL_TYPE_SELECTION: [ACTOR_LABEL_HELPER, COUNT_AND_LOG_HELPER],
    TOOL_TYPE_ORGANIZATION: [SELECTED_ACTORS_HELPER, ACTOR_LABEL_HELPER, COUNT_AND_LOG_HELPER],
    TOOL_TYPE_DEBUG: [ACTOR_LABEL_HELPER, COUNT_AND_LOG_HELPER],
    TOOL_TYPE_CUSTOM: [ACTOR_LABEL_HELPER, COUNT_AND_LOG_HELPER],
}


TYPE_REQUIREMENTS = {
    TOOL_TYPE_TRANSFORM: (
        "For actor movement, log old/target/new locations in debug mode and verify that the location changed.",
        "Use move_actor_to_location() or equivalent old/target/new validation.",
    ),
    TOOL_TYPE_TRACE: (
        "For HitResult, always support hit_result.to_tuple(); do not rely only on hit.location or hit.impact_point.",
        "Include '# Param: debug_log | bool | False | Debug Log'.",
        "Log raw trace type, blocking_hit, location/impact_point, target, and new actor location when debug_log is true.",
    ),
    TOOL_TYPE_SELECTION: (
        "Selection tools must log scanned and selected counts.",
        "Use actor_subsystem.set_selected_level_actors(matches) for editor selection.",
    ),
    TOOL_TYPE_ORGANIZATION: (
        "Organization tools must log changed and skipped counts.",
        "Use actor labels and folder paths through Unreal Python editor APIs.",
    ),
    TOOL_TYPE_DEBUG: (
        "Debug/report tools must avoid changing scene data unless explicitly requested.",
        "Log enough information for the user to copy into a fix prompt.",
    ),
    TOOL_TYPE_CUSTOM: (
        "Include clear diagnostics and final counts.",
    ),
}


def tool_type_names() -> list[str]:
    return list(TOOL_TYPES)


def normalize_tool_type(value: str) -> str:
    normalized = str(value or "").strip().casefold()
    for tool_type in TOOL_TYPES:
        if tool_type.casefold() == normalized:
            return tool_type
    return TOOL_TYPE_CUSTOM


def infer_tool_type(tool_request: str) -> str:
    text = str(tool_request or "").casefold()
    if any(word in text for word in ("trace", "hitresult", "hit result", "ray", "snap", "ground", "floor")):
        return TOOL_TYPE_TRACE
    if any(word in text for word in ("move", "offset", "transform", "rotate", "scale", "align", "array", "duplicate")):
        return TOOL_TYPE_TRANSFORM
    if any(word in text for word in ("select", "find", "filter", "same mesh")):
        return TOOL_TYPE_SELECTION
    if any(word in text for word in ("rename", "folder", "organize", "label", "prefix", "suffix")):
        return TOOL_TYPE_ORGANIZATION
    if any(word in text for word in ("debug", "report", "log", "audit", "count", "csv")):
        return TOOL_TYPE_DEBUG
    return TOOL_TYPE_CUSTOM


def snippets_for_tool_type(tool_type: str) -> list[str]:
    return list(TYPE_SNIPPETS.get(normalize_tool_type(tool_type), TYPE_SNIPPETS[TOOL_TYPE_CUSTOM]))


def requirements_for_tool_type(tool_type: str) -> tuple[str, ...]:
    return TYPE_REQUIREMENTS.get(normalize_tool_type(tool_type), TYPE_REQUIREMENTS[TOOL_TYPE_CUSTOM])
