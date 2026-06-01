# AI-Assisted Tool Creation

EditorBinder does not call an AI service by default. The default workflow is
copy/paste only:

1. Open `Add Tool`.
2. Describe the Unreal Engine Python Console workflow you want.
3. Click `Copy Prompt For AI`.
4. Paste the prompt into ChatGPT, Gemini, or another chat assistant.
5. Paste the assistant response back into EditorBinder.
6. Review the parsed name, notes, parameters, and Python code before saving.

Always review generated scripts before running them in a production project.
Test new scripts in a copy of a level first.

## Expected Response Format

EditorBinder parses marker-format responses:

```text
<<<UUT_NAME>>>
Select Point Lights
<<<UUT_NOTES>>>
Selects point light actors in the current level.
<<<UUT_CODE>>>
import unreal

actors = unreal.EditorLevelLibrary.get_all_level_actors()
for actor in actors:
    actor.set_actor_selection_state(actor.get_class().get_name() == "PointLight")
<<<UUT_END>>>
```

The marker order should stay:

```text
UUT_NAME
UUT_NOTES
UUT_CODE
UUT_END
```

## Parameters

Generated code can expose editable UI parameters with `# Param:` comments:

```python
# Param: folder_path | path | Environment/Props | Folder Path
# Param: select_after_move | bool | True | Select After Move
```

Supported types are:

```text
str
text
path
int
float
bool
enum
```

For numeric and enum controls, optional metadata can be added after the label:

```python
# Param: amount | int | 5 | Count | min=1 | max=100 | step=1
# Param: mode | enum | selected | Mode | options=selected,all
```

EditorBinder replaces `{{parameter_name}}` placeholders before copying the
script to the clipboard.

## Fixing A Generated Tool

If a generated script fails validation or needs adjustment:

1. Save or select the tool.
2. Open the tool menu.
3. Choose `Copy Fix Prompt`.
4. Paste that prompt into the same chat assistant.
5. Paste the corrected marker-format response back into `Add Tool`.

Good fix prompts include the error, current code, and expected marker format so
the assistant can return a complete corrected tool instead of a partial snippet.
