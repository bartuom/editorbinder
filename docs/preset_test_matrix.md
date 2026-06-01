# Free Core Test Matrix

Status date: 2026-05-31.

This matrix tracks the 15-tool Free Core seed shipped in `data\tools.json`.

Legend: `PASS` verified, `TODO` not verified yet, `N/A` not applicable.

| Tool | No Selection | One Actor | Multiple Actors | Undo | Output Log | UE Version |
| --- | --- | --- | --- | --- | --- | --- |
| Scene Cleanup Audit Report | TODO | TODO | TODO | N/A | TODO | TODO |
| Distribute Selected Actors In Grid | TODO | TODO | TODO | TODO | TODO | TODO |
| Organize Selected Actors By Static Mesh | TODO | TODO | TODO | TODO | TODO | TODO |
| Find Broken Or Suspicious Actors | TODO | TODO | TODO | N/A | TODO | TODO |
| Transform Selected Actors | PASS | TODO | PASS | TODO | PASS | UE 5.4 |
| Randomize Selected Transform | PASS | TODO | PASS | TODO | PASS | UE 5.4 |
| Snap Selected Actors To Ground | PASS | PASS | TODO | TODO | PASS | TODO |
| Move Selected Actors To Folder | PASS | TODO | PASS | TODO | PASS | UE 5.4 |
| Rename Selected Actors Pattern | PASS | TODO | PASS | TODO | PASS | UE 5.4 |
| Replace Text In Selected Actor Labels | PASS | TODO | PASS | TODO | PASS | UE 5.4 |
| Set Selected Collision Profile | PASS | TODO | PASS | TODO | PASS | UE 5.4 |
| Select Same Static Mesh As Selected | PASS | TODO | PASS | N/A | PASS | UE 5.4 |
| Set Selected Actors Mobility | PASS | TODO | PASS | TODO | PASS | UE 5.4 |
| Flatten Selected Actors To Same Z | TODO | TODO | TODO | TODO | TODO | TODO |
| Reset Bad Scale On Selected Actors | TODO | TODO | TODO | TODO | TODO | TODO |

Fresh release QA should cover:

- Empty selection warnings for every tool.
- Selected `StaticMeshActor` and multi-selection behavior for every tool.
- Undo for every tool that changes level data.
- Output Log summary with changed/found/skipped counts.
- UE 5.4 baseline and a separate UE 5.6 pass before claiming 5.6 support.
