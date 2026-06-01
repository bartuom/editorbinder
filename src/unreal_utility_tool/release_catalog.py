from __future__ import annotations


APP_NAME = "EditorBinder"
PACK_JSON_NAME = "editorbinder-pack.json"

FREE_CORE_TOOL_IDS = (
    "preset-scene-cleanup-audit-report",
    "preset-distribute-selected-actors-in-grid",
    "preset-organize-selected-actors-by-static-mesh",
    "preset-find-broken-or-suspicious-actors",
    "preset-transform-selected-actors",
    "preset-randomize-selected-transform",
    "preset-snap-selected-actors-to-ground",
    "preset-move-selected-actors-to-folder",
    "preset-rename-selected-actors-pattern",
    "preset-replace-text-in-selected-labels",
    "preset-set-selected-collision-profile",
    "preset-select-same-static-mesh",
    "preset-set-selected-actors-mobility",
    "preset-flatten-selected-actors-to-same-z",
    "preset-reset-bad-scale-on-selected-actors",
    "preset-select-actors-by-label-text",
    "preset-select-actors-by-class-name",
    "preset-report-selected-actors-summary",
)
FREE_CORE_COUNT = len(FREE_CORE_TOOL_IDS)
