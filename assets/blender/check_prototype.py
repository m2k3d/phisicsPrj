"""Verify the assembled variant A geometry and the temporary GLB export contract."""

import argparse
import json
import math
import struct
import sys
import tempfile
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector


TRACKS = ((-0.085, 0.0003), (0.0, 0.0004), (0.085, 0.0005))
MASS_SLOTS = {100: 0.275, 200: 0.338, 300: 0.400}
TOLERANCE = 0.000002


def close(actual, expected, tolerance=TOLERANCE):
    assert math.isclose(actual, expected, abs_tol=tolerance, rel_tol=0), (actual, expected)


def vector_close(actual, expected, tolerance=TOLERANCE):
    assert (Vector(actual) - Vector(expected)).length <= tolerance, (tuple(actual), tuple(expected))


def bounds(objects, frame=None):
    inverse = frame.matrix_world.inverted() if frame else Matrix.Identity(4)
    corners = [inverse @ obj.matrix_world @ Vector(corner)
               for obj in objects if obj.type == "MESH" for corner in obj.bound_box]
    return tuple(min(corner[axis] for corner in corners) for axis in range(3)), tuple(
        max(corner[axis] for corner in corners) for axis in range(3))


def position(name):
    return bpy.data.objects[name].matrix_world.translation.copy()


def mesh_hit_z(obj, x, y, z=0.25):
    inverse = obj.matrix_world.inverted()
    hit, point, _, _ = obj.ray_cast(inverse @ Vector((x, y, z)), Vector((0, 0, -1)))
    return (obj.matrix_world @ point).z if hit else None


def expect_closed_mesh(obj):
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    closed = all(edge.is_manifold for edge in mesh.edges)
    mesh.free()
    assert closed, obj.name


def caps(obj, num_vertices):
    return [obj.matrix_world @ poly.center for poly in obj.data.polygons
            if len(poly.vertices) == num_vertices]


def check_geometry():
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    assert scene.unit_settings.system == "METRIC"
    close(scene.unit_settings.scale_length, 1)
    assert scene.camera.name == "CAM_OVERVIEW"
    cameras = {obj.name for obj in scene.objects if obj.type == "CAMERA"}
    assert cameras == {"CAM_OVERVIEW", "CAM_FRONT", "CAM_TOP", "CAM_CLAMPS",
                       "CAM_PULLEYS", "CAM_MEASURE", "CAM_INSTRUMENTS"}
    assert len(scene.collection.children) == 8
    assert len(scene.objects) == len({obj.name for obj in scene.objects})
    tabletop = bpy.data.objects["TABLE_TOP"]
    panel = bpy.data.objects["PANEL_GRAPHITE"]
    vector_close(tabletop.dimensions, (1.150, 0.720, 0.035))
    vector_close(panel.dimensions, (0.650, 0.380, 0.030))
    vector_close(bounds([tabletop])[0], (-0.580, -0.360, -0.035))
    vector_close(bounds([tabletop])[1], (0.570, 0.360, 0))
    vector_close(bpy.data.objects["METER_BODY"].dimensions, (0.180, 0.062, 0.078))
    vector_close(position("METER_BODY"), (0.315, 0.155, 0.164))
    vector_close(position("METER_DISPLAY"), (0.280, 0.124, 0.169))
    vector_close(position("STOPWATCH_DISPLAY"), (0.367, 0.124, 0.169))
    expect_closed_mesh(panel)

    deviations = []
    for index, (y, diameter) in enumerate(TRACKS, 1):
        prefix = f"STR_{index:02}"
        locations = {
            "A": (0.000, y, 0.160), "B": (0.600, y, 0.160), "MID": (0.300, y, 0.160),
            "PULLEY_AXIS": (0.600, y, 0.135), "TANGENT_OUT": (0.625, y, 0.135),
            "HOOK": (0.625, y, 0.090), "SENSOR": (0.300, y + 0.023, 0.163),
        }
        for key, expected in locations.items():
            vector_close(position(f"{prefix}_{key}"), expected)
        vector_close(position(f"SENSOR_{index:02}"), locations["SENSOR"])
        vector_close(bpy.data.objects[f"SENSOR_{index:02}_HEAD"].dimensions, (0.022, 0.014, 0.020))

        span = bpy.data.objects[f"{prefix}_SPAN_PREVIEW"]
        tail = bpy.data.objects[f"{prefix}_TAIL_PREVIEW"]
        assert span.get("replace_with_runtime") and tail.get("replace_with_runtime")
        vector_close(span.dimensions, (0.600, diameter, diameter))
        ends = sorted(caps(span, 16), key=lambda point: point.x)
        assert len(ends) == 2, span.name
        vector_close(ends[0], locations["A"])
        vector_close(ends[1], locations["B"])
        tail_ends = sorted(caps(tail, 16), key=lambda point: point.z)
        assert len(tail_ends) == 2, tail.name
        vector_close(tail_ends[0], locations["HOOK"])
        vector_close(tail_ends[1], locations["B"])
        pull_clearance = (0.160 - 0.010 - diameter / 2) - 0.125
        assert pull_clearance >= 0.0247
        close(mesh_hit_z(panel, 0.300, y), 0.117)
        close(mesh_hit_z(panel, 0.300, y + 0.0145), 0.125)
        close(mesh_hit_z(panel, 0.5501, y), 0.125)
        close(mesh_hit_z(panel, 0.0199, y), 0.125)
        wheel = bpy.data.objects[f"PULLEY_{index:02}_WHEEL"]
        expect_closed_mesh(wheel)
        vector_close(wheel.dimensions, (0.052, 0.016, 0.052))
        vector_close(wheel.matrix_world.translation, locations["PULLEY_AXIS"])
        vector_close(wheel.matrix_world.to_3x3() @ Vector((0, 1, 0)), (0, 1, 0))
        # A downward envelope of 10 mm tests clearance without simulating the string.
        gear_gaps = []
        for step in range(1, 261):
            x = 0.600 - step * 0.0001
            groove = mesh_hit_z(wheel, x, y)
            if groove is not None:
                wire_bottom = 0.160 - 0.010 * math.sin(math.pi * x / 0.600) - diameter / 2
                gear_gaps.append(wire_bottom - groove)
        assert gear_gaps and min(gear_gaps) > -TOLERANCE, (wheel.name, min(gear_gaps))
        close(mesh_hit_z(wheel, 0.600, y), 0.160 - diameter / 2)
        for side in (1, 2):
            cheek = bpy.data.objects[f"FORK_{index:02}_CHEEK_{side}"]
            expect_closed_mesh(cheek)
            for x in (0.597, 0.600, 0.603):
                inside = cheek.matrix_world.inverted() @ Vector((x, y, 0.135))
                hit, *_ = cheek.ray_cast(inside, Vector((0, -1 if side == 1 else 1, 0)))
                assert not hit, (cheek.name, "pin clearance", x)
        clip = bpy.data.objects[f"PARK_CLIP_{index:02}"]
        clip_low, clip_high = map(Vector, bounds(clip.children, clip))
        vector_close(clip_high - clip_low, (0.014, 0.010, 0.012))
        deviations.append({"track": index, "span_mm": 600, "wire_mm": 1000 * diameter,
                           "min_panel_clearance_mm": round(pull_clearance * 1000, 4),
                           "min_approach_gap_mm": round(min(gear_gaps) * 1000, 6)})

    mass_results = []
    for mass, x in MASS_SLOTS.items():
        root = bpy.data.objects[f"WEIGHT_{mass}"]
        assert root.get("mass_g_including_holder") == mass
        low, high = map(Vector, bounds(root.children_recursive))
        local_low, local_high = low - root.location, high - root.location
        assert local_high.x - local_low.x <= 0.034 + TOLERANCE
        assert local_high.z - local_low.z <= 0.065 + TOLERANCE
        vector_close(position(f"RACK_SLOT_{mass}"), (x, -0.280, 0.0665))
        if mass == 200:
            vector_close(root.location, position("STR_01_HOOK"))
        else:
            vector_close(root.location, position(f"RACK_SLOT_{mass}"))
        for disk in (obj for obj in root.children if "_DISK_" in obj.name):
            expect_closed_mesh(disk)
            hit, *_ = disk.ray_cast(Vector((0, 0, 0.015)), Vector((0, 0, -1)))
            assert not hit, (disk.name, "stem bore")
        for index, _ in enumerate(TRACKS, 1):
            hook = position(f"STR_{index:02}_HOOK")
            assert hook.x + local_low.x >= 0.608 - TOLERANCE
            assert hook.z + local_low.z >= 0.025 - TOLERANCE
        mass_results.append({"grams": mass, "height_mm": round(1000 * (local_high.z - local_low.z), 3),
                             "underside_mm": round(1000 * (0.090 + local_low.z), 3)})
    result = {"objects": len(scene.objects), "collections": len(scene.collection.children),
              "tracks": deviations, "weights": mass_results, "table_side_clearance_mm": 38}
    print("GEOMETRY " + json.dumps(result))
    return result


def glb_json(path):
    data = path.read_bytes()
    magic, version, byte_length = struct.unpack_from("<4sII", data)
    assert magic == b"glTF" and version == 2 and byte_length == len(data), path
    chunk_length, kind = struct.unpack_from("<I4s", data, 12)
    assert kind == b"JSON", path
    return json.loads(data[20:20 + chunk_length])


def node_world_matrices(document):
    matrices = {}

    def visit(index, parent):
        node = document["nodes"][index]
        if "matrix" in node:
            values = node["matrix"]
            local = Matrix(tuple(tuple(values[c * 4 + r] for c in range(4)) for r in range(4)))
        else:
            x, y, z, w = node.get("rotation", (0, 0, 0, 1))
            local = (Matrix.Translation(Vector(node.get("translation", (0, 0, 0))))
                     @ Quaternion((w, x, y, z)).to_matrix().to_4x4()
                     @ Matrix.Diagonal(Vector((*node.get("scale", (1, 1, 1)), 1))))
        matrix = parent @ local
        if "name" in node:
            matrices[node["name"]] = matrix
        for child in node.get("children", ()):
            visit(child, matrix)

    for index in document["scenes"][document.get("scene", 0)]["nodes"]:
        visit(index, Matrix.Identity(4))
    return matrices


def export_selection(path, selected):
    view_layer = bpy.context.view_layer
    for obj in view_layer.objects:
        obj.select_set(obj in selected)
    view_layer.objects.active = next(iter(selected))
    result = bpy.ops.export_scene.gltf(
        filepath=str(path), export_format="GLB", use_selection=True,
        export_yup=True, export_cameras=False, export_lights=False,
        export_extras=True, export_apply=True, export_animations=False,
    )
    assert result == {"FINISHED"}, result
    return glb_json(path)


def glb_summary(path, document):
    triangles = 0
    for mesh in document.get("meshes", ()):
        for primitive in mesh["primitives"]:
            if primitive.get("mode", 4) == 4:
                accessor = primitive.get("indices", primitive["attributes"]["POSITION"])
                triangles += document["accessors"][accessor]["count"] // 3
    meshes = document.get("meshes", ())
    primitives = sum(len(meshes[node["mesh"]]["primitives"])
                     for node in document["nodes"] if "mesh" in node)
    return {"bytes": path.stat().st_size, "nodes": len(document["nodes"]),
            "triangles": triangles, "mesh_primitives_per_instance": primitives}


def check_glb():
    lab_root = bpy.data.objects["LAB_ROOT"]
    selected = {lab_root, *(obj for obj in lab_root.children_recursive if not obj.get("replace_with_runtime"))}
    weights = set()
    for mass in MASS_SLOTS:
        root = bpy.data.objects[f"WEIGHT_{mass}"]
        weights.update((root, *root.children_recursive))
    view_layer = bpy.context.view_layer
    previous_active = view_layer.objects.active
    previous_selected = set(bpy.context.selected_objects)
    try:
        with tempfile.TemporaryDirectory(prefix="standing-wave-glb-") as directory:
            apparatus_path = Path(directory) / "apparatus.glb"
            weights_path = Path(directory) / "weights.glb"
            apparatus = export_selection(apparatus_path, selected)
            weight_doc = export_selection(weights_path, weights)
            apparatus_nodes, weight_nodes = map(node_world_matrices, (apparatus, weight_doc))
            assert {"METER_DISPLAY", "STOPWATCH_DISPLAY", "WEIGHT_RACK"} <= apparatus_nodes.keys()
            assert not any(name.endswith("_PREVIEW") or name.startswith(("CAM_", "LIGHT_", "STUDIO_"))
                           for name in apparatus_nodes)
            assert not apparatus.get("cameras")
            for index in range(1, 4):
                prefix = f"STR_{index:02}"
                for suffix in ("A", "B", "MID", "PULLEY_AXIS", "TANGENT_OUT", "HOOK", "SENSOR"):
                    name = f"{prefix}_{suffix}"
                    x, y, z = position(name)
                    vector_close(apparatus_nodes[name].translation, (x, z, -y), 0.0005)
                close((apparatus_nodes[f"{prefix}_B"].translation
                       - apparatus_nodes[f"{prefix}_A"].translation).length, 0.600, 0.0005)
                wheel_name = f"PULLEY_{index:02}_WHEEL"
                x, y, z = position(wheel_name)
                vector_close(apparatus_nodes[wheel_name].translation, (x, z, -y), 0.0005)
            for mass in MASS_SLOTS:
                assert f"RACK_SLOT_{mass}" in apparatus_nodes
                root_name = f"WEIGHT_{mass}"
                x, y, z = position(root_name)
                vector_close(weight_nodes[root_name].translation, (x, z, -y), 0.0005)
            summaries = {"apparatus": glb_summary(apparatus_path, apparatus),
                         "weights": glb_summary(weights_path, weight_doc)}
            print("GLB " + json.dumps(summaries))
            return summaries
    finally:
        for obj in view_layer.objects:
            obj.select_set(obj in previous_selected)
        view_layer.objects.active = previous_active


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glb", action="store_true", help="Run trial GLB export in a temporary directory.")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    check_geometry()
    if args.glb:
        check_glb()
