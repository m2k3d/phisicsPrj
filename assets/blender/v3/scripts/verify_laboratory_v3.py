"""Verify geometry and optionally round-trip the Blender export contract to GLB."""

import argparse
import json
import struct
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree


CHANNELS = (-110, 0, 110)
MASSES = (100, 200, 300)
COLLECTIONS = (
    "01_BENCH", "02_FRAME", "03_STRING_HARDWARE", "04_RACK",
    "05_INSTRUMENTS", "06_ATTACHMENTS", "07_WEIGHTS", "08_STUDIO",
)


def xyz(obj):
    return obj.matrix_world.translation * 1000


def near(actual, expected, epsilon=0.04):
    distance = abs(actual - expected) if isinstance(actual, (int, float)) else (actual - Vector(expected)).length
    assert distance <= epsilon, f"{actual!s} differs from {expected!s} by {distance:.6f}"


def evaluated_geometry(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    vertices = [evaluated.matrix_world @ v.co for v in evaluated.data.vertices]
    polygons = [p.vertices[:] for p in evaluated.data.polygons]
    return vertices, polygons


def tree(obj):
    return BVHTree.FromPolygons(*evaluated_geometry(obj))


def hit(bvh, point, direction, length):
    location, _, _, _ = bvh.ray_cast(Vector(point) / 1000, Vector(direction), length / 1000)
    return location * 1000 if location is not None else None


def bounds(obj):
    vertices, _ = evaluated_geometry(obj)
    return [Vector([op(v[axis] for v in vertices) * 1000 for axis in range(3)]) for op in (min, max)]


def z_range(obj, lower, upper, epsilon=0.04):
    minimum, maximum = bounds(obj)
    near(minimum.z, lower, epsilon)
    near(maximum.z, upper, epsilon)


def check_contact(a, b, epsilon_mm=0.04):
    # Sample both meshes. Coincident seam/bearing faces are deliberate.
    geometries = [evaluated_geometry(obj) for obj in (a, b)]
    margin = epsilon_mm / 1000
    boxes = [[(min(v[axis] for v in verts), max(v[axis] for v in verts)) for axis in range(3)]
             for verts, _ in geometries]
    if any(min(a_hi, b_hi) - max(a_lo, b_lo) <= margin
           for (a_lo, a_hi), (b_lo, b_hi) in zip(*boxes)):
        return
    trees = [BVHTree.FromPolygons(*geometry) for geometry in geometries]
    directions = [Vector(d).normalized() for d in ((1, 0.317, 0.147), (0.19, -1, 0.27), (0.41, 0.2, 1))]

    def inside(point, surface):
        votes = 0
        for direction in directions:
            crossings = 0
            origin = point
            while True:
                location, _, _, _ = surface.ray_cast(origin, direction)
                if location is None:
                    break
                crossings += 1
                origin = location + direction * 1e-7
            votes += crossings % 2
        return votes > 1

    for i in (0, 1):
        worst = 0
        for point in geometries[i][0]:
            if any(not lo + margin < value < hi - margin for value, (lo, hi) in zip(point, boxes[1 - i])):
                continue
            surface = trees[1 - i]
            _, _, _, depth = surface.find_nearest(point)
            if depth is not None and depth > margin and inside(point, surface):
                worst = max(worst, depth)
        assert worst <= margin, f"{a.name} / {b.name} overlap by {worst * 1000:.4f} mm"


def check_geometry():
    scene = bpy.context.scene
    objects = scene.objects
    assert scene.name == "STANDING_WAVE_LAB_V3"
    assert scene.unit_settings.system == "METRIC"
    near(scene.unit_settings.scale_length, 1, 1e-6)
    assert {c.name for c in scene.collection.children} == set(COLLECTIONS)
    assert all(obj.scale[:] == (1.0, 1.0, 1.0) for obj in objects)
    assert not any(obj.name.startswith("Tool_") for obj in objects)
    bpy.context.view_layer.update()
    near(xyz(objects["LAB_ROOT"]), (0, 0, 0))
    bench = objects["BENCH_HPL_TOP"]
    for vector, expected in zip(bounds(bench), ((-450, -250, -1), (450, 310, 0))):
        near(vector, expected)
    z_range(objects["BENCH_BIRCH_CORE"], -29, -1)
    bench_tree = tree(bench)
    plywood_tree = tree(objects["BENCH_BIRCH_CORE"])
    z_range(objects["BENCH_FOOT_L_FRONT"], -740, -730)
    board = objects["TOP_BOARD"]
    for vector, expected in zip(bounds(board), ((-210, -35, 435), (210, 105, 451))):
        near(vector, expected)
    board_tree = tree(board)
    tray = tree(objects["RACK_MOLDED_BODY"])
    near(xyz(objects["RACK_SLOT_300"]).x - xyz(objects["RACK_SLOT_200"]).x, 62)
    near(xyz(objects["RACK_SLOT_200"]).x - xyz(objects["RACK_SLOT_100"]).x, 62)
    near(xyz(objects["INSTRUMENT_BODY"]), (-310, 20, 0))
    for key, z in (("METER", 83), ("STOPWATCH", 43)):
        display = objects[key + "_DISPLAY"]
        near(xyz(display), (-310, -23, z))
        orientation = display.matrix_world.to_quaternion()
        near(orientation @ Vector((0, 0, 1)), (0, -1, 0))
        near(orientation @ Vector((0, 1, 0)), (0, 0, 1))
        near(bounds(objects[key + "_LENS"])[0].y, -23)

    for index, x in enumerate((-180, 180), 1):
        tag = f"{index:02}"
        z_range(objects["FRAME_BASE_PLATE_" + tag], 0, 6)
        z_range(objects["FRAME_POST_" + tag], 6, 468)
        z_range(objects["FRAME_CONSOLE_ARM_" + tag], 426, 435)
        near(bounds(objects["FRAME_CONSOLE_ARM_" + tag])[0].y, 30)
        check_contact(board, objects["FRAME_CONSOLE_ARM_" + tag])
        for i in (1, 2):
            z_range(objects[f"FRAME_GUSSET_{tag}_{i}"], 359, 426, 0.3)
        z_range(objects["BENCH_BACKING_PLATE_" + tag], -36, -30)
        for dx in (-30, 30):
            for y in (120, 190):
                assert hit(bench_tree, (x + dx, y, 1), (0, 0, -1), 2) is None
                assert hit(plywood_tree, (x + dx, y, 1), (0, 0, -1), 31) is None
        for y in (60, 90):
            assert hit(board_tree, (x, y, 434), (0, 0, 1), 18) is None, "Board screw bore missing"

    solid_parts = [
        (obj.name, bounds(obj)) for family in COLLECTIONS[:5]
        for obj in bpy.data.collections[family].objects if obj.type == "MESH"
    ]
    seats = []
    slot_widths = []
    hook_gapes = []
    for index, x in enumerate(CHANNELS, 1):
        tag = f"{index:02}"
        top, mid, end, seat = (objects[f"STR_{tag}_{suffix}"] for suffix in ("TOP", "MID", "END", "HOOK_SEAT"))
        for obj, height in zip((top, mid, end, seat), (435, 285, 135, 115)):
            near(xyz(obj), (x, 0, height))
        near((xyz(top) - xyz(end)).length, 300)
        # A 46 mm wide zone around the midpoint is open to the front.
        for name, (lower, upper) in solid_parts:
            inside_grip = (lower.x < x + 23 and upper.x > x - 23 and
                           lower.y < 10 and upper.y > -250 and
                           lower.z < 310 and upper.z > 260)
            assert not inside_grip, f"{name} in the pluck zone of channel {tag}"
        wire = objects[f"DEMO_WIRE_{tag}"]
        z_range(wire, 135, 435)
        low, high = bounds(wire)
        near(high.x - low.x, (0.3, 0.4, 0.5)[index - 1], 0.002)
        positive = hit(board_tree, (x, -15, 442), (1, 0, 0), 5)
        negative = hit(board_tree, (x, -15, 442), (-1, 0, 0), 5)
        slot_widths.append(round(positive.x - negative.x, 3))
        near(slot_widths[-1], 3.2, 0.01)
        assert hit(board_tree, (x, -30, 434), (0, 0, 1), 20) is None, "Front entry blocked"
        assert hit(board_tree, (x, 0, 434), (0, 0, 1), 18) is None, "Seat blocks shank"
        insert = objects[f"SLOT_INSERT_{tag}"]
        insert_tree = tree(insert)
        head = objects[f"CAP_HEAD_{tag}"]
        shank = objects[f"CAP_SHANK_{tag}"]
        sleeve = objects[f"HOOK_CRIMP_{tag}"]
        hook_wire = objects[f"HOOK_WIRE_{tag}"]
        check_contact(board, insert)
        check_contact(board, shank)
        check_contact(insert, head)
        check_contact(head, shank)
        check_contact(sleeve, hook_wire)
        for dx in (-4, 4):
            near(hit(board_tree, (x + dx, 0, 454), (0, 0, -1), 5).z, 449.4)
            near(hit(insert_tree, (x + dx, 0, 454), (0, 0, -1), 5).z, 451)
            near(hit(tree(head), (x + dx, 0, 450), (0, 0, 1), 5).z, 451)
        z_range(shank, 435, 452.15)
        z_range(sleeve, 128, 135)
        hook = tree(hook_wire)
        near(hit(hook, (x, 0, 117), (0, 0, -1), 5).z, 115, 0.015)
        points = evaluated_geometry(objects[f"HOOK_WIRE_{tag}"])[0]
        rings = [[vertex * 1000 for vertex in points[i:i + 16]] for i in range(0, len(points), 16)]
        entry, tip = rings[:18], rings[-1]
        gap = min((a - b).length for ring in entry for a in ring for b in tip)
        assert gap > 2.1 + 0.5
        hook_gapes.append(round(gap, 3))
        seats.append(seat)

    clearances, mass_dimensions = {}, {}
    for mass in MASSES:
        weight = objects[f"WEIGHT_{mass}"]
        assert weight.parent is None and all(abs(angle) < 1e-7 for angle in weight.rotation_euler)
        near(weight["solid_mass_estimate_g"], mass, 0.02)
        body = objects[f"WEIGHT_BODY_{mass}"]
        eye = objects[f"WEIGHT_EYE_{mass}"]
        slot = objects[f"RACK_SLOT_{mass}"]
        original = weight.location.copy()
        try:
            weight.location = slot.matrix_world.translation
            bpy.context.view_layer.update()
            minimum, maximum = bounds(body)
            near(minimum.z, 12)
            near(maximum.x - minimum.x, 34)
            near(maximum.y - minimum.y, 34)
            near(hit(tray, (xyz(slot).x, -30, 25), (0, 0, -1), 20).z, 12)
            inner = hit(tray, (xyz(slot).x, -30, 15), (1, 0, 0), 25)
            near(inner.x - xyz(slot).x, 20, 0.05)
            check_contact(body, objects["RACK_MOLDED_BODY"])
            check_contact(eye, body)
            mass_dimensions[mass] = {
                "height_mm": round(maximum.z - minimum.z, 3),
                "rack_pivot_z_mm": round(xyz(slot).z, 3),
                "mass_g": weight["solid_mass_estimate_g"],
            }
            for i, seat in enumerate(seats, 1):
                p = xyz(seat)
                weight.location = seat.matrix_world.translation
                bpy.context.view_layer.update()
                lowest, highest = bounds(body)
                assert lowest.z > 50 and highest.z < p.z
                # Cast through the open eye at the world pivot and test contact from both sides.
                contact = hit(tree(eye), (p.x, p.y, p.z - 1), (0, 0, 1), 3)
                near(contact, p, 0.015)
                check_contact(eye, objects[f"HOOK_WIRE_{i:02}"])
                assert lowest.x > p.x - 18 and highest.x < p.x + 18
                assert lowest.y > -18 and highest.y < 18
                # The outer dimensions of the assembly stay in its own channel
                # and in front of the nearest support (Y = +30 mm).
                near(p.y, 0)
                assert highest.y < 30
                clearances[(i, mass)] = lowest.z
        finally:
            weight.location = original
            bpy.context.view_layer.update()
    assert all(abs(x) + 23 < 375 for x in CHANNELS)
    assert -175 < 0 < 235  # Vertical line of the load stays inside the foot polygon.
    clear_grip = 110 - 2 * 23 - (0.4 + 0.5) / 2
    through_contact = {
        "scene_objects": len(objects),
        "collections": {c: len(bpy.data.collections[c].objects) for c in COLLECTIONS},
        "slot_width_mm": slot_widths,
        "hook_opening_mm_approx": hook_gapes,
        "eye_wire_mm": 2.1,
        "hanging_clearance_mm": {f"{i:02}_{m}": round(z, 3) for (i, m), z in clearances.items()},
        "wire_to_wire_mm_at_pluck_envelope": round(clear_grip, 3),
        "weights": mass_dimensions,
    }
    return through_contact


def glb_json(path):
    data = path.read_bytes()
    magic, version, length, chunk_length, kind = struct.unpack_from("<4sIII4s", data)
    assert (magic, version, length, kind) == (b"glTF", 2, len(data), b"JSON")
    return json.loads(data[20:20 + chunk_length])


def export_preview(directory, collections, name, selected_root_poses=False):
    bpy.ops.object.select_all(action="DESELECT")
    weights = [bpy.data.objects[f"WEIGHT_{mass}"] for mass in MASSES]
    original = [obj.location.copy() for obj in weights]
    for collection_name in collections:
        for obj in bpy.data.collections[collection_name].objects:
            obj.select_set(True)
    path = directory / (name + ".glb")
    try:
        if selected_root_poses:
            for obj in weights:
                obj.location.zero()
            bpy.context.view_layer.update()
        bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True,
                                  export_yup=True, export_apply=True, export_extras=True,
                                  export_animations=False, export_cameras=False, export_lights=False)
    finally:
        for obj, location in zip(weights, original):
            obj.location = location
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.update()
    return glb_json(path), path.stat().st_size


def mesh_stats(gltf):
    triangles = 0
    primitives = 0
    for node in gltf["nodes"]:
        if "mesh" not in node:
            continue
        for primitive in gltf["meshes"][node["mesh"]]["primitives"]:
            assert primitive.get("mode", 4) == 4
            count = gltf["accessors"][primitive["indices"]]["count"]
            triangles += count // 3
            primitives += 1
    return triangles, primitives


def check_export():
    with TemporaryDirectory(prefix="lab_v3_glb_") as directory:
        apparatus, apparatus_bytes = export_preview(Path(directory), COLLECTIONS[:6], "apparatus")
        weights, weights_bytes = export_preview(Path(directory), COLLECTIONS[6:7], "weights",
                                               selected_root_poses=True)
    nodes = {node["name"]: node for node in apparatus["nodes"]}
    assert len(nodes) == len(apparatus["nodes"])
    for prefix in ("DEMO_", "STUDIO_", "LIGHT_", "WEIGHT_BODY_"):
        assert not any(name.startswith(prefix) for name in nodes)
    for i, x in enumerate(CHANNELS, 1):
        for suffix, y in (("TOP", 435), ("MID", 285), ("END", 135), ("HOOK_SEAT", 115)):
            node = nodes[f"STR_{i:02}_{suffix}"]
            near(Vector(node["translation"]), (x / 1000, y / 1000, 0), 5e-7)
        for family in ("CAP", "HOOK"):
            assert f"{family}_{i:02}" in nodes
    for key, height in (("METER", 83), ("STOPWATCH", 43)):
        node = nodes[f"{key}_DISPLAY"]
        near(Vector(node["translation"]), (-0.310, height / 1000, 0.023), 5e-7)
        rotation = Quaternion((node["rotation"][3], *node["rotation"][:3]))
        near(rotation @ Vector((0, 1, 0)), (0, 0, 1), 5e-7)
        near(rotation @ Vector((0, 0, -1)), (0, 1, 0), 5e-7)
    for mass in MASSES:
        anchor = bpy.data.objects[f"RACK_SLOT_{mass}"]
        vector = anchor.location
        near(Vector(nodes[anchor.name]["translation"]), (vector.x, vector.z, -vector.y), 5e-7)
    weight_nodes = {node["name"]: node for node in weights["nodes"]}
    assert {weights["nodes"][i]["name"] for i in weights["scenes"][weights["scene"]]["nodes"]} == {
        f"WEIGHT_{mass}" for mass in MASSES
    }
    for mass in MASSES:
        near(Vector(weight_nodes[f"WEIGHT_{mass}"].get("translation", (0, 0, 0))), (0, 0, 0), 5e-7)
        assert f"WEIGHT_BODY_{mass}" in weight_nodes
    a_tri, a_primitives = mesh_stats(apparatus)
    w_tri, w_primitives = mesh_stats(weights)
    return {
        "apparatus": {"bytes": apparatus_bytes, "triangles": a_tri, "mesh_primitives": a_primitives},
        "weights": {"bytes": weights_bytes, "triangles": w_tri, "mesh_primitives": w_primitives},
    }


def verify(with_glb=False):
    result = check_geometry()
    if with_glb:
        result["temporary_glb"] = check_export()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def write_inventory(path):
    types = {"MESH": "Меш", "EMPTY": "Пустышка", "CAMERA": "Камера", "LIGHT": "Свет"}
    lines = ["# Объекты предварительной установки V3", "",
             "Перечень объектов активной сцены. Родители указаны по именам объектов.", ""]
    for name in COLLECTIONS:
        objects = sorted(bpy.data.collections[name].objects, key=lambda obj: obj.name)
        lines += [f"## {name} ({len(objects)})", "",
                  "| Объект | Тип | Родитель |", "|---|---|---|"]
        for obj in objects:
            parent = f"`{obj.parent.name}`" if obj.parent else "—"
            lines.append(f"| `{obj.name}` | {types[obj.type]} | {parent} |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", action="store_true")
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    verify(args.glb)
    if args.inventory:
        write_inventory(args.inventory)
