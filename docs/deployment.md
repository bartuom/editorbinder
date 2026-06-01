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
dist\EditorBinder-<version>-win-x64.exe
```

The folder contains `EditorBinder.exe`, the release seed at `data\tools.json`,
license files, the changelog, portable-mode helper, reset helper, shortcut
installer, and `release.json`.

The standalone `.exe` is the primary end-user download. It bundles the runtime
seed, icon, license, and changelog into one file and stores user data in
`%APPDATA%\EditorBinder` unless the user imports/exports tools manually.

`release.json` records the app version, package name, build timestamp, Python
version, PyInstaller version, git commit, and whether the worktree was dirty at
build time.

## Source ZIP

Build the source/BAT package with:

```bat
build_source_zip.bat
```

or directly:

```powershell
python tools\package_source_release.py
```

The output is:

```text
dist\EditorBinder-source-<version>.zip
```

The source/BAT ZIP is a user-facing package. It should include the app source,
Free Core seed, docs, icon, license files, and BAT launch/reset helpers. It
should not include tests, build outputs, private pack source, or local runtime
files such as `data\user_tools.json` and `data\settings.json`.

## Artifact Verification

Run:

```powershell
python tools\verify_release_artifacts.py
```

The verification step checks the source/BAT ZIP and Windows package for the
expected public contents, including:

- MIT license files,
- `data\tools.json` with the Free Core seed,
- no `preset_packs` directory,
- no commercial workflow files,
- no local runtime files.

For a manual release smoke test, download the ZIPs from the GitHub Release into
a clean temporary folder, extract them, and check:

1. `EditorBinder.exe` exists in the Windows package.
2. `data\tools.json` contains the expected Free Core seed.
3. `EditorBinder.exe` starts and stays open.
4. `EditorBinder-<version>-win-x64.exe` exists and starts.
5. The source/BAT ZIP contains `run_app.bat`.
6. No private or paid-pack artifacts are present.

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
8. Smoke test `dist\EditorBinder-<version>-win-x64.exe`.
9. Create a GitHub Release and attach the standalone EXE, Windows ZIP, and
   source/BAT ZIP.
10. Confirm GitHub Actions is green on `main`.
