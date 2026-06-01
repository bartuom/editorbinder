"""Export selected Blender objects to EditorBinder DCC layout CSV.

Usage:
1. Open this script in Blender's Text Editor.
2. Set CSV_PATH and options below.
3. Select objects or set EXPORT_SELECTED_ONLY = False.
4. Run Script.

Optional object custom properties:
- unreal_asset_path: full Unreal StaticMesh asset path, e.g. /Game/Props/SM_Rock.SM_Rock
- eb_uid: stable UID for roundtrip updates
"""

import csv
import math
import os
import re

import bpy


CSV_PATH = "//editorbinder_dcc_layout.csv"
EXPORT_SELECTED_ONLY = True
COLLECTION_NAME = ""
RAW_UNREAL_SPACE = False
SOURCE_LABEL = "blender_export"
UNREAL_UNIT_SCALE = 100.0

FIELDNAMES = [
    "uid",
    "asset_path",
    "mesh_name",
    "x",
    "y",
    "z",
    "pitch",
    "yaw",
    "roll",
    "sx",
    "sy",
    "sz",
    "collection",
    "actor_label",
    "source",
]


def clean_text(value):
    return str(value or "").strip()


def safe_uid(value):
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", clean_text(value))
    return text.strip("_") or "object"


def selected_objects():
    if EXPORT_SELECTED_ONLY:
        return [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    if COLLECTION_NAME:
        collection = bpy.data.collections.get(COLLECTION_NAME)
        if collection is None:
            raise ValueError(f"Collection not found: {COLLECTION_NAME}")
        return [obj for obj in collection.objects if obj.type == "MESH"]
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def object_collection(obj):
    if obj.users_collection:
        return obj.users_collection[0].name
    return ""


def object_uid(obj):
    return safe_uid(obj.get("eb_uid") or obj.name)


def object_asset_path(obj):
    return clean_text(obj.get("unreal_asset_path", ""))


def object_mesh_name(obj):
    asset_path = object_asset_path(obj)
    if asset_path:
        tail = asset_path.rsplit("/", 1)[-1]
        return tail.split(".", 1)[0]
    return clean_text(obj.data.name)


def convert_location(location):
    if RAW_UNREAL_SPACE:
        return location.x, location.y, location.z
    return (
        location.y * UNREAL_UNIT_SCALE,
        location.x * UNREAL_UNIT_SCALE,
        location.z * UNREAL_UNIT_SCALE,
    )


def convert_rotation(euler):
    if RAW_UNREAL_SPACE:
        return (
            math.degrees(euler.x),
            math.degrees(euler.z),
            math.degrees(euler.y),
        )
    return (
        math.degrees(euler.x),
        math.degrees(euler.z),
        math.degrees(euler.y),
    )


def object_row(obj):
    matrix = obj.matrix_world
    location = matrix.to_translation()
    rotation = matrix.to_euler("XYZ")
    scale = matrix.to_scale()
    x, y, z = convert_location(location)
    pitch, yaw, roll = convert_rotation(rotation)
    return {
        "uid": object_uid(obj),
        "asset_path": object_asset_path(obj),
        "mesh_name": object_mesh_name(obj),
        "x": f"{x:.6f}",
        "y": f"{y:.6f}",
        "z": f"{z:.6f}",
        "pitch": f"{pitch:.6f}",
        "yaw": f"{yaw:.6f}",
        "roll": f"{roll:.6f}",
        "sx": f"{scale.x:.6f}",
        "sy": f"{scale.y:.6f}",
        "sz": f"{scale.z:.6f}",
        "collection": object_collection(obj),
        "actor_label": obj.name,
        "source": SOURCE_LABEL,
    }


def main():
    path = bpy.path.abspath(CSV_PATH)
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    rows = [object_row(obj) for obj in selected_objects()]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"EditorBinder DCC CSV exported: {path}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
