# Deployment

EditorBinder uses `pyproject.toml` as the release version source. The app
package version in `src\unreal_utility_tool\__init__.py` should match it before
a public release.

## Versioned Windows EXE

Build the Windows binary package with:

```bat
build_pyinstaller_onedir.bat
```

or directly:

```powershell
python tools\package_windows_release.py
```

The output is versioned from `pyproject.toml`:

```text
dist\EditorBinder-<version>-win-x64\
dist\EditorBinder-<version>-win-x64.zip
```

The folder contains `EditorBinder.exe`, the release seed at `data\tools.json`,
license files, the changelog, portable-mode helper, reset helper, shortcut
installer, and `release.json`.

`release.json` records the app version, package name, build timestamp, Python
version, PyInstaller version, git commit, and whether the worktree was dirty at
build time.

## Source ZIP

Build the source/BAT package with:

```bat
build_source_zip.bat
```

The output is:

```text
dist\EditorBinder-source-<version>.zip
```

## Release Checklist

1. Update `pyproject.toml` version.
2. Update `src\unreal_utility_tool\__init__.py` version to the same value.
3. Add a matching `CHANGELOG.md` entry.
4. Run the full test suite:
   `python -m unittest discover`
5. Build the source ZIP and Windows EXE ZIP.
6. Verify release artifacts:
   `python tools\verify_release_artifacts.py`
7. Smoke test `dist\EditorBinder-<version>-win-x64\EditorBinder.exe`.
8. Create a GitHub Release and attach the source/BAT ZIP plus Windows ZIP.
