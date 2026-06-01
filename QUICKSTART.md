# EditorBinder Quickstart

EditorBinder is a standalone clipboard library for Unreal Engine Python Console
tools. It does not install into Unreal Engine and it does not run scripts
automatically.

## 1. Open The App

For the source/BAT release, run:

```text
run_app.bat
```

For the Windows EXE release, run:

```text
EditorBinder.exe
```

## 2. Copy A Tool

1. Pick a tool from the library.
2. Adjust any visible parameters.
3. Click `Copy`.
4. Open Unreal Engine's Python Console.
5. Paste and run the copied code.

Review scripts before running them in a production project. Test new workflows
on a copy of a level first.

## 3. Import A Tool Pack

1. Open `Add Tool`.
2. Choose `Import Files`.
3. Select a `.json`, `.txt`, `.py`, pack ZIP, `editorbinder-pack.json`, or an
   extracted pack folder.
4. Keep `Skip duplicates` selected when importing more than one pack.
5. Click `Save Imported`.

EditorBinder imports the root `editorbinder-pack.json` when an extracted folder
contains one, so bundle folders can provide a single combined payload.

Small import examples are included in:

```text
docs\examples\
```

## 4. Create A Tool With AI

1. Open `Add Tool`.
2. Describe the tool.
3. Click `Copy Prompt`.
4. Paste the prompt into ChatGPT, Gemini, or another AI chat app.
5. Paste the returned answer into EditorBinder.
6. Review and save the parsed tool.

No AI API key is required for the default copy/paste workflow.

More details and marker-format examples are in:

```text
docs\ai_workflow.md
```

## 5. Where Tools Are Stored

Source and portable runs:

```text
data\user_tools.json
```

Installed frozen builds:

```text
%APPDATA%\EditorBinder\tools.json
```

The bundled Free Core seed is:

```text
data\tools.json
```
