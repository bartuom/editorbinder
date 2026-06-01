# Tool: Move Selected Actors Up
# Param: z_offset | float | 100.0 | Z Offset | step=10

import unreal

offset = float({{z_offset}})
selected = unreal.EditorLevelLibrary.get_selected_level_actors()

for actor in selected:
    location = actor.get_actor_location()
    actor.set_actor_location(
        unreal.Vector(location.x, location.y, location.z + offset),
        False,
        True,
    )
