# Tool Packs

EditorBinder ships with a small Free Core seed in:

```text
data\tools.json
```

Additional tools can be shared as importable JSON files, Python files, text
marker blocks, ZIP files, or extracted folders.

EditorBinder can import either a ZIP directly or an extracted pack folder. If an
extracted folder contains a root `editorbinder-pack.json`, that root payload is
imported once and nested bundle ZIPs/manifests are ignored.

## Pack JSON

A pack ZIP can contain:

```text
editorbinder-pack.json
README.md
CHANGELOG.md
LICENSE.txt
```

`editorbinder-pack.json` uses the normal import shape:

```json
{
  "pack_id": "material_tools",
  "pack_name": "Material Tools",
  "version": "1.0.0",
  "min_app_version": "0.1.0",
  "recommended_import_policy": "skip",
  "target_roles": ["Technical Artist"],
  "workflow_pitch": "Material audit helpers for Unreal scenes.",
  "tools": [
    {
      "id": "material-audit-tool",
      "name": "Audit Materials",
      "description": "Checks material setup.",
      "category": "Material Tools",
      "tags": ["materials", "audit"],
      "workflows": ["Scene Audit"],
      "roles": ["Technical Artist"],
      "visibility": "primary",
      "code": "import unreal\nunreal.log('Tool code here')"
    }
  ]
}
```

The importer reads the `tools` array. Extra metadata is preserved in the file so
pack authors can describe compatibility, roles, workflows, and import guidance.

Tool `id` values are preserved during import. Updates and duplicate handling use
the stable `id` first, then fall back to the tool name for older exports.

## Bundle Folders

An extracted bundle folder can contain:

```text
editorbinder-pack.json
README.md
CHANGELOG.md
bundle-manifest.json
packs\
```

The root `editorbinder-pack.json` is the preferred bundle import because it can
contain each tool once. Nested ZIPs are useful when authors also want to provide
smaller packs.

## Dynamic Categories

`category` is intentionally open-ended. If a pack uses a category that is not in
the base app list, EditorBinder preserves it during import and shows it in the
category filter after the pack is installed.

`workflows` and `roles` are also open-ended for imported packs. Known values are
shown first in filters, and new values from imported packs are kept as custom
filter values.

The base app ships with these default categories:

```text
Transform
Selection
Organization
Debug
Custom
```

Pack categories should be short user-facing labels, for example:

```text
Material Tools
DCC Bridge
Lighting QA
Blueprint Cleanup
```

## Storage

Installed tools are saved into the user's working library:

```text
%APPDATA%\EditorBinder\tools.json
```

In portable mode they are saved next to the app:

```text
data\user_tools.json
```

The bundled Free Core seed remains unchanged during user imports:

```text
data\tools.json
```
