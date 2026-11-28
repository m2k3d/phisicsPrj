"""Validate the working clearances and export-independent scene contract."""

import argparse
import itertools
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


CHANNELS = ((-110, .15), (0, .20), (110, .25))
MAX_PLUCK = 23
TOP, END = 435, 135
SLOPE = MAX_PLUCK * math.pi / (TOP - END)
BREAK = MAX_PLUCK / SLOPE
# A conservative bound for the first-mode disk and for a string pulled
# between endpoints with its grip at Z = 260..310 mm.
SLABS = (
    (END, END + BREAK, SLOPE, -SLOPE * END),
    (END + BREAK, TOP - BREAK, 0, MAX_PLUCK),
    (TOP - BREAK, TOP, -SLOPE, SLOPE * TOP),
)
AXES = [(math.cos(math.radians(i)), math.sin(math.radians(i))) for i in range(0, 360, 5)]
GROUPS = ("05_INSTRUMENTS", "09_PICKUPS", "10_CABLING")


def xyz(obj):
    return obj.matrix_world.translation * 1000


def geometry(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.data
    mesh.calc_loop_triangles()
    return ([(evaluated.matrix_world @ v.co) * 1000 for v in mesh.vertices],
            [tuple(triangle.vertices) for triangle in mesh.loop_triangles])


def extents(vertices):
    return [(min(v[i] for v in vertices), max(v[i] for v in vertices)) for i in range(3)]


def overlap(a, b, tol=.04):
    return all(min(x2, y2) - max(x1, y1) > tol for (x1, x2), (y1, y2) in zip(a, b))


def clip(points, height, above):
    if not points:
        return []
    result = []
    previous = points[-1]
    for current in points:
        prev_inside = previous.z >= height if above else previous.z <= height
        inside = current.z >= height if above else current.z <= height
        if inside != prev_inside:
            result.append(previous.lerp(current, (height - previous.z) / (current.z - previous.z)))
        if inside:
            result.append(current)
        previous = current
    return result


def planar_margin(points, string_x, slope, intercept, wire_radius):
    relative = [(p.x - string_x, p.y, slope * p.z + intercept + wire_radius) for p in points]
    # For any unit vector n the support plane n·(p-w) = R(z) contains the
    # complete disk at that height on its inner side. R is linear within each
    # slab. A positive minimum at the clipped vertices certifies the whole face,
    # including motion at angles between the directions used to find the plane.
    return max(min(nx * x + ny * y - radius for x, y, radius in relative) for nx, ny in AXES)


def certify_wire(vertices, triangles, box, string_x, wire_radius):
    z_min, z_max = box[2]
    limits = []
    for bottom, top, slope, intercept in SLABS:
        if z_max < bottom or z_min > top:
            continue
        max_radius = max(slope * min(z_max, top), slope * max(z_min, bottom)) + intercept + wire_radius
        coarse = max(box[0][0] - string_x, string_x - box[0][1], box[1][0], -box[1][1]) - max_radius
        if coarse > 9:
            limits.append(coarse)
            continue
        for ids in triangles:
            points = [vertices[i] for i in ids]
            if all(v.z < bottom for v in points) or all(v.z > top for v in points):
                continue
            section = clip(clip(points, bottom, True), top, False)
            if section:
                limits.append(planar_margin(section, string_x, slope, intercept, wire_radius))
    return min(limits, default=float("inf"))


def check_cable_routes(objects):
    prefixes = ("CABLE_PU_", "CABLE_PREAMP_", "CABLE_COAX_", "CABLE_SCOPE_")
    jackets = [o for o in objects if o.type == "MESH" and o.name.startswith(prefixes)
               and "_FANOUT_" not in o.name and not o.name.endswith("_ID")]
    shells = [objects[name] for name in (
        "BENCH_HPL_TOP", "SCOPE_FRONT_BEZEL", "SCOPE_SHELL", "SCOPE_REAR_COVER",
        "PREAMP_DIECAST_BODY", "PREAMP_LID", "FRAME_POST_01", "FRAME_BASE_PLATE_01",
        "STOPWATCH_CRADLE_BASE", "PICKUP_RAIL_20X20",
    )]
    shells.extend(o for o in objects if "_ACRYLIC_" in o.name or o.name.startswith("CABLE_POST_CLIP_"))
    records = {}
    for obj in jackets + shells:
        pts, tris = geometry(obj)
        records[obj.name] = (extents(pts), BVHTree.FromPolygons(pts, tris, all_triangles=True))
    for a, b in itertools.chain(itertools.product(jackets, shells), itertools.combinations(jackets, 2)):
        ab, at = records[a.name]
        bb, bt = records[b.name]
        if overlap(ab, bb):
            assert not at.overlap(bt), f"Cable jacket intersection: {a.name} / {b.name}"
    return len(jackets)


def verify():
    scene = bpy.context.scene
    objects = scene.objects
    assert scene.name == "STANDING_WAVE_LAB_V3_1"
    assert scene.unit_settings.system == "METRIC" and scene.unit_settings.scale_length == 1
    assert "METER_DISPLAY" not in objects and "INSTRUMENT_BODY" not in objects
    assert len([o for o in scene.objects if o.type == "CAMERA"]) == 9
    assert len(set(obj.name for obj in objects)) == len(objects)
    assert all(obj.scale[:] == (1.0, 1.0, 1.0) for obj in objects)
    bpy.context.view_layer.update()
    assert xyz(objects["LAB_ROOT"]).length < .001
    for i, (x, _) in enumerate(CHANNELS, 1):
        tag = f"{i:02}"
        for suffix, z in (("TOP", TOP), ("MID", 285), ("END", END), ("HOOK_SEAT", 115)):
            assert (xyz(objects[f"STR_{tag}_{suffix}"]) - Vector((x, 0, z))).length < .001
        assert (xyz(objects[f"PICKUP_{tag}"]) - Vector((x + 6.5, 8.2, 410))).length < .002
        assert abs(math.degrees(objects[f"PICKUP_{tag}"].rotation_euler.x) - 14) < .001
        assert objects[f"CABLE_COAX_CH_{tag}"]["path"] == f"PREAMP OUT {i} → OSC CH{i}"
        for side in ("HI", "LO"):
            assert f"PREAMP_IN_{tag}_{side}" in objects and f"PU_{tag}_{side}" in objects
        assert objects[f"COAX_{tag}_SCOPE_PLUG"].parent == objects[f"OSC_CH_{tag}_BNC"]
        assert objects[f"COAX_{tag}_AMP_PLUG"].parent == objects[f"PREAMP_OUT_{tag}_BNC"]
    assert not any(o.name.startswith("COAX") for o in objects["OSC_CH_04_BNC"].children_recursive)
    display = objects["OSCILLOSCOPE_DISPLAY"]
    surface = objects["OSCILLOSCOPE_DISPLAY_SURFACE"]
    assert surface.parent == display and len(surface.data.uv_layers) == 1
    orientation = display.matrix_world.to_quaternion()
    assert (orientation @ Vector((0, 0, 1)) - Vector((0, -1, 0))).length < 1e-6
    assert (orientation @ Vector((0, 1, 0)) - Vector((0, 0, 1))).length < 1e-6
    assert objects["STOPWATCH_DISPLAY"].parent == objects["DIGITAL_STOPWATCH"]
    assert all(obj.name not in bpy.data.collections["05_INSTRUMENTS"].objects
               for obj in bpy.data.collections["08_STUDIO"].objects if obj.name.startswith("DEMO_SCOPE_"))

    margins = {}
    group_clear = {}
    for group in GROUPS:
        nearest = float("inf")
        for obj in bpy.data.collections[group].objects:
            if obj.type != "MESH":
                continue
            vertices, triangles = geometry(obj)
            box = extents(vertices)
            # Keep the grip and the forward access to the hanging weight clear.
            for x, radius in CHANNELS:
                assert not overlap(box, ((x - 35, x + 35), (-250, 30), (257, 315))), obj.name
                assert not overlap(box, ((x - 26, x + 26), (-65, 25), (0, 135))), obj.name
                margin = certify_wire(vertices, triangles, box, x, radius)
                assert margin > .04, f"{obj.name} / string {x}: {margin:.4f} mm"
                if margin < nearest:
                    nearest = margin
                    margins[group] = obj.name
            # The front access to all three recesses in the rack.
            assert not overlap(box, ((217, 407), (-250, 21), (0, 135))), obj.name
            if box[2][0] < -.04:
                assert obj.name in {"CABLE_SCOPE_USB_POWER", "CABLE_PREAMP_DC_POWER"}, obj.name
                for v in vertices:
                    if -2 < v.z < -.04:
                        assert math.hypot(v.x + 312, v.y - 252) < 4.1 + .04, (obj.name, v)
        group_clear[group] = round(nearest, 3)

    # A more direct dimensional check for the closest acrylic face to the board.
    z_board = min(v.z for v in geometry(objects["TOP_BOARD"])[0])
    acrylic = [o for o in bpy.data.collections["09_PICKUPS"].objects if "_ACRYLIC_" in o.name]
    z_case = max(v.z for o in acrylic for v in geometry(o)[0])
    assert z_board - z_case > .8
    for i in range(1, 4):
        tag = f"{i:02}"
        head = objects[f"PICKUP_{tag}"]
        inverse = head.matrix_world.inverted()
        local = [(inverse @ (v / 1000)) * 1000 for o in acrylic if o.parent == head for v in geometry(o)[0]]
        assert all(abs(hi - lo - d) < .01 for (lo, hi), d in zip(extents(local), (80, 25, 35)))
    scope_profile = extents(geometry(objects["SCOPE_FRONT_BEZEL"])[0])
    scope_rear = extents(geometry(objects["SCOPE_REAR_COVER"])[0])
    assert abs(scope_profile[0][1] - scope_profile[0][0] - 265.35) < .01
    assert abs(scope_profile[2][1] - 161.75) < .01
    assert abs(scope_rear[1][1] - scope_profile[1][0] - 77.38) < .01
    routed_jackets = check_cable_routes(objects)
    result = {
        "objects": len(objects),
        "cameras": [o.name for o in scene.objects if o.type == "CAMERA"],
        "lower_bound_mm_for_any_horizontal_azimuth": group_clear,
        "closest_meshes": margins,
        "acrylic_to_board_mm": round(z_board - z_case, 3),
        "working_length_mm": TOP - END,
        "checked_cable_jackets": routed_jackets,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def inventory(path):
    scene = bpy.context.scene
    types = {"MESH": "Меш", "EMPTY": "Пустышка", "CAMERA": "Камера", "LIGHT": "Свет"}
    text = ["# Объекты лабораторной установки V3.1", "",
            f"Поимённый перечень сцены Blender. Всего {len(scene.objects)} объектов.", ""]
    for group in sorted(scene.collection.children, key=lambda c: c.name):
        objects = sorted(group.objects, key=lambda obj: obj.name)
        text.extend([f"## {group.name} ({len(objects)})", "",
                     "| Имя | Тип | Родитель |", "|---|---|---|"])
        for obj in objects:
            parent = f"`{obj.parent.name}`" if obj.parent else "—"
            text.append(f"| `{obj.name}` | {types[obj.type]} | {parent} |")
        text.append("")
    path.write_text("\n".join(text), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    verify()
    if args.inventory:
        inventory(args.inventory)
