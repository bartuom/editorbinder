# Changelog

All notable user-facing changes for EditorBinder are documented here.

## 0.1.3 - 2026-11-22

### Improved

- Expanded Unreal Python linting to recognize additional mutating Actor/component operations and unreal.log_error().
- Hardened tool-library and settings persistence with UTF-8 BOM tolerance, strict decoding, atomic replacement, fsync, and failed-write cleanup.
- Hardened tool-pack ZIP import by rejecting absolute, drive-qualified, and parent-traversal member paths.
- Made dialog timers trackable and cancellable during teardown, and moved AI-generation result handoff onto a thread-safe queue consumed by the UI thread.
- Hardened monitor and work-area geometry validation.
- Updated the documented preset test matrix to the current 21-tool Free Core catalog.

### Validation

- 215 automated tests passed locally.
- Ruff and Python bytecode compilation passed.
- GitHub Actions Windows CI passed on Python 3.10, 3.11, and 3.12.
- The release workflow builds and verifies the versioned Windows EXE, portable ZIP, and source ZIP from a clean Windows runner.

### Notes

- The bundled Free Core remains at 21 tools. This release focuses on application reliability, import safety, and authoring workflows rather than adding new bundled scripts.
- EditorBinder copies scripts to the clipboard for review and execution in Unreal Editor. It does not execute them directly in Unreal.
- The Windows executable is unsigned, so Microsoft Defender SmartScreen may show an Unknown publisher warning.

## 0.1.2 - 2026-11-22

### Added

- Expanded the bundled 18-tool Free Core into a 21-tool Free Core catalog:
  - Select Actors By Material, with material-name and asset-path matching.
  - Batch Update Actor Tags, with add, remove, replace, and undo support.
  - Audit Missing Material Slots on selected actors, with optional selection of affected actors.
- Added focused Ruff static checks to the GitHub Actions CI matrix.

### Improved

- Hardened AI provider URL validation, including HTTPS enforcement and local-loopback HTTP support.
- Preserved query parameters in AI endpoint URLs, redacted provider secrets from errors, and rejected truncated model responses.
- Improved AI marker parsing for incomplete code fences and multiple response sections.
- Improved numeric parameter scrubbing while preserving normal text selection and keyboard shortcuts.
- Improved window recovery across monitor changes and cancelled delayed UI callbacks when dialogs close.
- Improved code-editor highlighting for multiline docstrings and token priority.
- Improved the Unreal Python tool linter with syntax-aware mutation, transaction, logging, and HitResult checks.
- Improved onedir packaging to avoid a redundant standalone EXE build and forward command-line arguments.

### Fixed

- Restricted parameter substitution to top-level assignments and rejected non-finite numeric values.
- Fixed keyboard interaction regressions in compact tool rows.
- Fixed generated egg-info/dist-info metadata leaking into source ZIP packages.
- Fixed release-catalog registration and coverage for the three new Free Core tools.

### Validation

- 191 automated tests passed on Python 3.10, 3.11, and 3.12 in local and release validation.
- Ruff static checks passed.
- Windows PyInstaller onedir and standalone packaging verified locally.
- Source ZIP and wheel build/install smoke tests passed.

## 0.1.1 - 2026-06-01

### Added

- Expanded the default 18-tool Free Core release seed with:
  - Select Actors By Label Text
  - Select Actors By Class Name
  - Report Selected Actors Summary
- Added a visual walkthrough GIF and `docs\walkthrough.md`.
- Added import examples under `docs\examples\`.
- Added `docs\ai_workflow.md` for marker-format AI-assisted tool creation.
- Added a standalone Windows EXE release asset for the default download path.
- Added `docs\downloads.md` to clarify EXE, portable ZIP, and source ZIP usage.
- Expanded release packaging and artifact verification docs.

## 0.1.0 - 2026-05-29

Initial open-source Free Core release.

### Added

- Lightweight Windows desktop app for storing and copying paste-ready Unreal
  Engine Python Console scripts.
- Tool library with search, category filter, favorites, recent tools, keyboard
  shortcuts, and compact responsive layout.
- Parameter UI for script placeholders using `# Param:` comments.
- Supported parameter types: `str`, `text`, `path`, `int`, `float`, `bool`, and
  `enum`.
- Inline parameter validation, remembered parameter values, reset parameters,
  and copy-ready rendered code.
- AI-assisted Add Tool flow with copyable prompt, marker-based paste/import
  parser, preview diagnostics, and Paste And Save from clipboard.
- Import support for `.json`, `.txt`, `.py`, `.zip`, clipboard text, and folders.
- Export support for single tools and the full tool library.
- Library backup and restore workflow with safety backups.
- About EditorBinder dialog with version, author/copyright, Epic disclaimer,
  support-info copy, and quick links to the license, changelog, and data folder.
- Default 15-tool Free Core release seed:
  - Scene Cleanup Audit Report
  - Distribute Selected Actors In Grid
  - Organize Selected Actors By Static Mesh
  - Find Broken Or Suspicious Actors
  - Transform Selected Actors
  - Randomize Selected Transform
  - Snap Selected Actors To Ground
  - Move Selected Actors To Folder
  - Rename Selected Actors Pattern
  - Replace Text In Selected Actor Labels
  - Set Selected Collision Profile
  - Select Same Static Mesh As Selected
  - Set Selected Actors Mobility
  - Flatten Selected Actors To Same Z
  - Reset Bad Scale On Selected Actors
- Source/portable storage separation:
  - `data/tools.json` is the clean release seed.
  - `data/user_tools.json` is the editable local source/portable library.
  - installed frozen builds use `%APPDATA%\EditorBinder\tools.json`.
- Windows BAT workflow:
  - `run_app.bat`
  - `install_shortcuts.bat`
  - `reset_window.bat`
  - `enable_portable_mode.bat`
- App icon, Start Menu/Desktop shortcut helper, multi-monitor dialog placement,
  always-on-top toggle, and drag-scroll list behavior.

### Notes

- EditorBinder does not execute scripts directly in Unreal Engine. It copies
  Python code to the clipboard so the user can paste and run it in Unreal
  Python Console.
- Runtime dependencies are limited to the Python standard library and
  `tkinter`; no third-party Python packages are required to run the app.
- The bundled Free Core tools should be reviewed in a copy of a level before
  use in production scenes.
