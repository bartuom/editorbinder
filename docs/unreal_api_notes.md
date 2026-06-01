# Unreal Python API Notes

Local notes for EditorBinder prompts and presets. These are practical
rules for paste-ready snippets used in Unreal Engine Python Console.

## General

- Code must run from one paste into Python Console.
- Import `unreal` explicitly.
- Use `unreal.log()` for success messages and `unreal.log_warning()` for user-fixable problems.
- Log how many actors, components, or assets were changed.
- Handle empty selection before doing work.
- For scene changes, wrap edits in `unreal.ScopedEditorTransaction`.
- Avoid invented API. If unsure, use simple Unreal Python calls that are known to exist.

## Actors

- Get editor actor access with:

```python
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
selected_actors = list(actor_subsystem.get_selected_level_actors())
level_actors = list(actor_subsystem.get_all_level_actors())
```

- Do not use `actor.is_pending_kill()`. Unreal Python Actor does not expose it.
- Do not assume `actor.is_valid()` exists.
- Do not assume `actor.get_root_component()` exists. Prefer
  `actor.get_editor_property("root_component")` as a fallback.
- Basic filtering should use checks like `if actor is not None`.
- For actor labels, use `actor.get_actor_label()` and `actor.set_actor_label()`.
- For Outliner folders, use `actor.set_folder_path()`.
- For transforms, prefer actor methods such as `get_actor_location()`, `set_actor_location()`,
  `get_actor_rotation()`, `set_actor_rotation()`, `get_actor_scale3d()`, and
  `set_actor_scale3d()`.
- `unreal.SystemLibrary.line_trace_single()` can return a direct `HitResult` in
  Unreal 5.4 instead of an indexable tuple. Handle both forms before reading
  `blocking_hit` or `impact_point`.

## Components

- Do not assume `actor.get_components_by_class()` exists in Unreal Python.
- Prefer `actor.get_components_by_class(unreal.ActorComponent)` only after it has been
  verified in the target Unreal version, or use a safer preset pattern already tested in
  this repository.
- Check component type with `isinstance(component, unreal.PrimitiveComponent)` or a known
  Unreal component class when available.
- For collision profile changes, use `component.set_collision_profile_name(profile_name)`.
- For mobility changes, check whether the component has the `mobility` editor property before
  setting it.

## Parameters

- Put editable values at the top as `# Param:` lines.
- Use placeholders like `{{name}}` in assignments near the top:

```python
# Param: folder_path | path | Props/Rocks | Folder Path
folder_path = {{folder_path}}
```

- Supported parameter types in the app are `str`, `text`, `path`, `int`, `float`, `bool`,
  and `enum`.
- Use `enum` with `options=` for short controlled choices.

## AI Prompt Rules

- Return only EditorBinder marker format.
- Do not include Markdown explanations outside markers.
- Keep marker lines exactly:

```text
<<<UUT_NAME>>>
<<<UUT_NOTES>>>
<<<UUT_CODE>>>
<<<UUT_END>>>
```

- Do not put marker strings inside generated Python code.
