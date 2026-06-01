# Contributing

Thanks for helping improve EditorBinder.

## Development Setup

EditorBinder has no runtime third-party dependencies. Use Python 3.10 or newer
on Windows.

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover
```

## Pull Requests

- Keep changes focused and avoid unrelated formatting churn.
- Add or update tests for parser, importer, storage, packaging, or UI behavior
  when those areas change.
- Keep bundled tools in `data/tools.json` small, general-purpose, and safe to
  review before running in Unreal Engine.
- Do not commit local runtime files such as `data/user_tools.json`,
  `data/settings.json`, build outputs, unreviewed screenshots, or secrets.
- Run `python -m unittest discover` before opening a pull request.
- Public hygiene tests must stay green: the public tree must not contain
  private pack source, commercial workflow files, restrictive license terms, or
  secret tokens.

## Tool Contributions

Imported or bundled tools should be paste-ready Unreal Python Console scripts.
They should include clear names, practical descriptions, and safe defaults.
Mutating Unreal scene tools should use `unreal.ScopedEditorTransaction` where
the Unreal API supports undo.
