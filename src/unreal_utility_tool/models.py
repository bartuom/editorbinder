from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

CATEGORY_TRANSFORM = "Transform"
CATEGORY_SELECTION = "Selection"
CATEGORY_ORGANIZATION = "Organization"
CATEGORY_DEBUG = "Debug"
CATEGORY_CUSTOM = "Custom"
CATEGORIES = [CATEGORY_TRANSFORM, CATEGORY_SELECTION, CATEGORY_ORGANIZATION, CATEGORY_DEBUG, CATEGORY_CUSTOM]
CATEGORY_FALLBACKS = {
    "general": CATEGORY_CUSTOM,
}

WORKFLOW_PLACE_ARRANGE = "Place & Arrange"
WORKFLOW_SET_DRESSING = "Set Dressing"
WORKFLOW_SCENE_CLEANUP = "Scene Cleanup"
WORKFLOW_NAMING_ORGANIZATION = "Naming & Organization"
WORKFLOW_COLLISION_PHYSICS = "Collision & Physics"
WORKFLOW_MATERIALS = "Materials"
WORKFLOW_TEXTURES = "Textures"
WORKFLOW_INSTANCING = "Instancing"
WORKFLOW_IMPORT_DCC = "Import / DCC"
WORKFLOW_OPTIMIZATION = "Optimization"
WORKFLOW_REPORTS_HANDOFF = "Reports / Handoff"
WORKFLOW_CUSTOM = "Custom"
WORKFLOWS = [
    WORKFLOW_PLACE_ARRANGE,
    WORKFLOW_SET_DRESSING,
    WORKFLOW_SCENE_CLEANUP,
    WORKFLOW_NAMING_ORGANIZATION,
    WORKFLOW_COLLISION_PHYSICS,
    WORKFLOW_MATERIALS,
    WORKFLOW_TEXTURES,
    WORKFLOW_INSTANCING,
    WORKFLOW_IMPORT_DCC,
    WORKFLOW_OPTIMIZATION,
    WORKFLOW_REPORTS_HANDOFF,
]
ALL_WORKFLOWS = [*WORKFLOWS, WORKFLOW_CUSTOM]

ROLE_LEVEL_ARTIST = "Level Artist"
ROLE_ENVIRONMENT_ARTIST = "Environment Artist"
ROLE_TECH_ARTIST = "Tech Artist"
ROLE_MATERIAL_ARTIST = "Material Artist"
ROLE_PIPELINE_ARTIST = "Pipeline Artist"
ROLE_LEAD_QA = "Lead / QA"
ROLES = [
    ROLE_LEVEL_ARTIST,
    ROLE_ENVIRONMENT_ARTIST,
    ROLE_TECH_ARTIST,
    ROLE_MATERIAL_ARTIST,
    ROLE_PIPELINE_ARTIST,
    ROLE_LEAD_QA,
]

VISIBILITY_PRIMARY = "primary"
VISIBILITY_SECONDARY = "secondary"
VISIBILITY_HIDDEN = "hidden"
VISIBILITIES = [VISIBILITY_PRIMARY, VISIBILITY_SECONDARY, VISIBILITY_HIDDEN]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Tool:
    id: str
    name: str
    description: str
    tags: list[str]
    code: str
    created_at: str
    updated_at: str
    category: str = CATEGORY_CUSTOM
    workflows: list[str] = field(default_factory=lambda: [WORKFLOW_CUSTOM])
    roles: list[str] = field(default_factory=lambda: [ROLE_PIPELINE_ARTIST])
    visibility: str = VISIBILITY_PRIMARY

    @classmethod
    def create(
        cls,
        name: str,
        code: str,
        description: str = "",
        tags: list[str] | None = None,
        category: str = CATEGORY_CUSTOM,
        workflows: list[str] | str | None = None,
        roles: list[str] | str | None = None,
        visibility: str = VISIBILITY_PRIMARY,
    ) -> "Tool":
        now = utc_now_iso()
        normalized_tags = normalize_tags(tags or [])
        return cls(
            id=str(uuid4()),
            name=name.strip(),
            description=description.strip(),
            tags=normalized_tags,
            code=code,
            created_at=now,
            updated_at=now,
            category=normalize_category(category, normalized_tags),
            workflows=normalize_workflows(workflows),
            roles=normalize_roles(roles),
            visibility=normalize_visibility(visibility),
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Tool":
        required = ["id", "name", "description", "tags", "code", "created_at", "updated_at"]
        missing = [key for key in required if key not in raw]
        if missing:
            raise ValueError(f"Tool is missing required fields: {', '.join(missing)}")

        tags = normalize_tags(raw["tags"])
        return cls(
            id=str(raw["id"]),
            name=str(raw["name"]),
            description=str(raw["description"]),
            tags=tags,
            code=str(raw["code"]),
            created_at=str(raw["created_at"]),
            updated_at=str(raw["updated_at"]),
            category=normalize_category(raw.get("category", ""), tags),
            workflows=normalize_workflows(raw.get("workflows")),
            roles=normalize_roles(raw.get("roles")),
            visibility=normalize_visibility(raw.get("visibility")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "code": self.code,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "category": normalize_category(self.category, self.tags),
            "workflows": normalize_workflows(self.workflows),
            "roles": normalize_roles(self.roles),
            "visibility": normalize_visibility(self.visibility),
        }

    def with_updates(
        self,
        *,
        name: str,
        description: str,
        tags: list[str],
        code: str,
        category: str | None = None,
        workflows: list[str] | str | None = None,
        roles: list[str] | str | None = None,
        visibility: str | None = None,
    ) -> "Tool":
        normalized_tags = normalize_tags(tags)
        return Tool(
            id=self.id,
            name=name.strip(),
            description=description.strip(),
            tags=normalized_tags,
            code=code,
            created_at=self.created_at,
            updated_at=utc_now_iso(),
            category=normalize_category(self.category if category is None else category, normalized_tags),
            workflows=normalize_workflows(self.workflows if workflows is None else workflows),
            roles=normalize_roles(self.roles if roles is None else roles),
            visibility=normalize_visibility(self.visibility if visibility is None else visibility),
        )

    def duplicate(self) -> "Tool":
        return Tool.create(
            name=f"{self.name} Copy",
            description=self.description,
            tags=list(self.tags),
            code=self.code,
            category=self.category,
            workflows=list(self.workflows),
            roles=list(self.roles),
            visibility=self.visibility,
        )

    def matches(
        self,
        query: str,
        category: str | None = None,
        workflow: str | None = None,
        role: str | None = None,
    ) -> bool:
        if category and category != CATEGORY_CUSTOM and self.category != category:
            return False
        if category == CATEGORY_CUSTOM and self.category != CATEGORY_CUSTOM:
            return False
        if workflow and workflow not in self.workflows:
            return False
        if role and role not in self.roles:
            return False
        if not query.strip():
            return True

        needle = query.casefold().strip()
        haystack = " ".join(
            [
                self.name,
                self.description,
                self.category,
                " ".join(self.tags),
                " ".join(self.workflows),
                " ".join(self.roles),
                self.visibility,
            ]
        ).casefold()
        return needle in haystack


def normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = list(value)

    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        tag = str(item).strip().casefold()
        if tag and tag not in seen:
            normalized.append(tag)
            seen.add(tag)
    return normalized


def normalize_workflows(value: Any) -> list[str]:
    return _normalize_named_list(value, ALL_WORKFLOWS, [WORKFLOW_CUSTOM], allow_custom=True)


def normalize_roles(value: Any) -> list[str]:
    return _normalize_named_list(value, ROLES, [ROLE_PIPELINE_ARTIST], allow_custom=True)


def normalize_visibility(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    return raw if raw in VISIBILITIES else VISIBILITY_PRIMARY


def _normalize_named_list(
    value: Any,
    allowed: list[str],
    default: list[str],
    *,
    allow_custom: bool = False,
) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        raw_items = value.split(",")
    else:
        try:
            raw_items = list(value)
        except TypeError:
            raw_items = [value]

    by_name = {item.casefold(): item for item in allowed}
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        raw_text = str(raw_item).strip()
        key = raw_text.casefold()
        item = by_name.get(key)
        if item is None and allow_custom:
            item = _clean_custom_category(raw_text)
        if item and item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized or list(default)


def normalize_category(value: Any, tags: list[str] | None = None) -> str:
    raw = str(value or "").strip()
    if raw:
        by_name = {category.casefold(): category for category in CATEGORIES}
        key = raw.casefold()
        if key in by_name:
            return by_name[key]
        if key in CATEGORY_FALLBACKS:
            return CATEGORY_FALLBACKS[key]
        return _clean_custom_category(raw)

    tag_set = {tag.casefold() for tag in tags or []}
    if tag_set & {"transform", "placement", "collision"}:
        return CATEGORY_TRANSFORM
    if tag_set & {"selection", "select"}:
        return CATEGORY_SELECTION
    if tag_set & {"organization", "rename", "folder", "folders"}:
        return CATEGORY_ORGANIZATION
    if tag_set & {"debug", "logging", "log"}:
        return CATEGORY_DEBUG
    return CATEGORY_CUSTOM


def category_options(tools: list[Tool] | None = None, extra_categories: list[str] | None = None) -> list[str]:
    found = {
        normalize_category(category)
        for category in (extra_categories or [])
        if str(category or "").strip()
    }
    if tools:
        found.update(tool.category for tool in tools if tool.category.strip())

    ordered = list(CATEGORIES)
    extras = sorted(
        (category for category in found if category not in CATEGORIES),
        key=str.casefold,
    )
    return [*ordered, *extras]


def _clean_custom_category(value: str) -> str:
    cleaned = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    return cleaned[:80] if cleaned else CATEGORY_CUSTOM
