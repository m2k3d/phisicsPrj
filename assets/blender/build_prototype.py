"""Build the variant A working model in Blender 5.3, in metres."""

import argparse
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


TRACK_Y = (-0.085, 0.000, 0.085)
WIRE_DIAMETERS = (0.0003, 0.0004, 0.0005)
MASS_SLOTS = {100: 0.275, 200: 0.338, 300: 0.400}
SCENE_NAME = "Standing Wave Lab - Prototype A"
GENERATOR_ID = "standing-wave-lab-variant-a"
COLLECTIONS = (
    "01_TABLE",
    "02_FRAME",
    "03_CHANNEL_HARDWARE",
    "04_WEIGHTS",
    "05_INSTRUMENTS",
    "06_ATTACHMENT_POINTS",
    "07_STRING_PREVIEWS",
    "08_STUDIO",
)


def mesh_object(name, vertices, faces, collection, material=None, *, smooth=False):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    work = bmesh.new()
    work.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(work, faces=list(work.faces))
    work.to_mesh(mesh)
    work.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    if material:
        mesh.materials.append(material)
    if smooth:
        for polygon in mesh.polygons:
            polygon.use_smooth = len(polygon.vertices) == 4
    return obj


def place(obj, location, parent=None):
    obj.parent = parent
    obj.location = location
    return obj


def empty(name, location, collection, parent=None, *, size=0.012):
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = size
    return place(obj, location, parent)


def edge_finish(obj, radius, segments=2):
    bevel = obj.modifiers.new("Machined edge", "BEVEL")
    bevel.width = radius
    bevel.segments = segments
    bevel.limit_method = "ANGLE"
    bevel.harden_normals = True
    normals = obj.modifiers.new("Surface normals", "WEIGHTED_NORMAL")
    normals.keep_sharp = True


def box(name, location, size, collection, material, parent=None, bevel=0.0):
    x, y, z = (value / 2 for value in size)
    vertices = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
                (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    obj = place(mesh_object(name, vertices, faces, collection, material), location, parent)
    if bevel:
        edge_finish(obj, bevel)
    return obj


def cylinder(name, location, radius, depth, collection, material, parent=None,
             *, sides=24, axis="Z", bevel=0.0, flat_front=None, bore=None):
    vertices = []
    rings = [(radius, -depth / 2), (radius, depth / 2)]
    if bore:
        rings.extend([(bore, depth / 2), (bore, -depth / 2)])
    for ring_radius, z in rings:
        for index in range(sides):
            angle = 2 * math.pi * index / sides
            x, y = ring_radius * math.cos(angle), ring_radius * math.sin(angle)
            if flat_front is not None:
                y = max(y, flat_front)
            vertices.append({"Z": (x, y, z), "Y": (x, z, -y), "X": (z, y, -x)}[axis])
    if bore:
        faces = closed_rings(len(rings), sides)
    else:
        faces = [tuple(reversed(range(sides))), tuple(range(sides, sides * 2))]
        for a in range(sides):
            b = (a + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    obj = place(mesh_object(name, vertices, faces, collection, material, smooth=True), location, parent)
    for polygon in obj.data.polygons:
        if abs(polygon.normal.z) > 0.98 and axis == "Z":
            polygon.use_smooth = False
    if bevel:
        edge_finish(obj, bevel)
    return obj


def tube(name, points, radius, collection, material, parent=None, *, sides=12):
    """Make capped tubing along a path in the XZ plane, with its origin at the start."""
    origin = Vector(points[0])
    path = [Vector(point) - origin for point in points]
    vertices = []
    side = Vector((0, 1, 0))
    for index, position in enumerate(path):
        tangent = path[min(index + 1, len(path) - 1)] - path[max(index - 1, 0)]
        tangent.normalize()
        radial = tangent.cross(side).normalized()
        for section in range(sides):
            angle = 2 * math.pi * section / sides
            vertices.append(position + radius * (math.cos(angle) * radial + math.sin(angle) * side))
    end = (len(path) - 1) * sides
    faces = [tuple(reversed(range(sides))), tuple(range(end, end + sides))]
    for ring in range(len(path) - 1):
        for a in range(sides):
            b = (a + 1) % sides
            offset = ring * sides
            faces.append((offset + a, offset + b, offset + b + sides, offset + a + sides))
    return place(mesh_object(name, vertices, faces, collection, material, smooth=True),
                 origin, parent)


def material(name, color, metallic=0.0, roughness=0.5, emission=0.0, *, specular=0.5):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    surface = next(node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    surface.inputs["Base Color"].default_value = (*color, 1.0)
    surface.inputs["Metallic"].default_value = metallic
    surface.inputs["Roughness"].default_value = roughness
    surface.inputs["Specular IOR Level"].default_value = specular
    if emission:
        surface.inputs["Emission Color"].default_value = (*color, 1.0)
        surface.inputs["Emission Strength"].default_value = emission
    return mat


def make_materials():
    return {
        "aluminum": material("ALUMINUM_MATTE", (0.49, 0.55, 0.59), 0.76, 0.39),
        "steel": material("STEEL_SATIN", (0.40, 0.44, 0.47), 0.76, 0.31),
        "wire": material("STEEL_WIRE", (0.72, 0.77, 0.80), 0.73, 0.25),
        "weight": material("STEEL_WEIGHT", (0.30, 0.34, 0.37), 0.80, 0.33),
        "graphite": material("GRAPHITE_PANEL", (0.021, 0.026, 0.032), 0.0, 0.81, specular=0.10),
        "channel": material("CHANNEL_LINER", (0.006, 0.009, 0.013), 0.0, 0.86, specular=0.05),
        "rubber": material("RUBBER_BLACK", (0.016, 0.021, 0.025), 0.0, 0.78, specular=0.18),
        "acetal": material("ACETAL_ROLLER", (0.037, 0.046, 0.056), 0.0, 0.30),
        "plastic": material("ABS_INSTRUMENT", (0.023, 0.032, 0.043), 0.0, 0.51, specular=0.20),
        "glass": material("DISPLAY_GLASS", (0.014, 0.027, 0.032), 0.18, 0.28),
        "lit": material("DISPLAY_INK", (0.55, 0.80, 0.79), 0.0, 0.44, 0.22),
        "led": material("SENSOR_STATUS", (0.47, 0.60, 0.48), 0.0, 0.34, 0.14),
        "scale": material("SCALE_ENAMEL", (0.53, 0.58, 0.59), 0.16, 0.59),
        "ink": material("SCALE_INK", (0.010, 0.013, 0.017), 0.0, 0.87, specular=0.03),
        "white_ink": material("LABEL_OFF_WHITE", (0.72, 0.74, 0.74), 0.0, 0.70),
        "table": material("TABLE_LAMINATE", (0.44, 0.47, 0.48), 0.0, 0.59),
        "table_steel": material("TABLE_POWDER_COAT", (0.15, 0.19, 0.21), 0.18, 0.56),
        "studio": material("STUDIO_GRAY", (0.21, 0.25, 0.28), 0.0, 0.81),
    }


def load_font(path=None):
    candidates = [Path(path)] if path else [
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return bpy.data.fonts.load(str(candidate))
    raise FileNotFoundError("Pass --font with a local TrueType font that supports Cyrillic.")


def label(name, value, location, size, collection, material, font, parent=None,
          *, front=False, alignment="CENTER"):
    curve = bpy.data.curves.new(name, "FONT")
    curve.body = value
    curve.font = font
    curve.size = size
    curve.align_x = alignment
    curve.resolution_u = 4
    helper = bpy.data.objects.new(f"{name}_TEXT_TMP", curve)
    collection.objects.link(helper)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    label_mesh = bpy.data.meshes.new_from_object(helper.evaluated_get(depsgraph))
    bpy.data.objects.remove(helper, do_unlink=True)
    bpy.data.curves.remove(curve)
    label_mesh.name = name
    label_mesh.materials.append(material)
    obj = bpy.data.objects.new(name, label_mesh)
    collection.objects.link(obj)
    if front:
        obj.rotation_euler.x = math.pi / 2
    return place(obj, location, parent)


def panel_with_recesses(collection, material, parent):
    xs = (-0.080, 0.020, 0.550, 0.570)
    ys = [-0.190]
    for y in TRACK_Y:
        ys.extend((y - 0.014, y + 0.014))
    ys.append(0.190)
    bottom = 0.095
    levels = {(i, j): 0.117 if i == 1 and j in (1, 3, 5) else 0.125
              for i in range(len(xs) - 1) for j in range(len(ys) - 1)}
    points = {}
    faces = []

    def quad(*corners):
        faces.append([points.setdefault(point, len(points)) for point in corners])

    for (i, j), top in levels.items():
        x0, x1 = xs[i:i + 2]
        y0, y1 = ys[j:j + 2]
        quad((x0, y0, top), (x1, y0, top), (x1, y1, top), (x0, y1, top))
        quad((x0, y1, bottom), (x1, y1, bottom), (x1, y0, bottom), (x0, y0, bottom))
        for neighbor, a, b in (
            ((i - 1, j), (x0, y1), (x0, y0)), ((i + 1, j), (x1, y0), (x1, y1)),
            ((i, j - 1), (x0, y0), (x1, y0)), ((i, j + 1), (x1, y1), (x0, y1)),
        ):
            lower = levels.get(neighbor, bottom)
            if lower < top:
                quad((*a, lower), (*b, lower), (*b, top), (*a, top))
    obj = mesh_object("PANEL_GRAPHITE", list(points), faces, collection, material)
    return place(obj, (0, 0, 0), parent)


def build_table(collection, root, mats):
    table = empty("TABLE_STATIC", (0, 0, 0), collection, root)
    box("TABLE_TOP", (-0.005, 0, -0.0175), (1.150, 0.720, 0.035),
        collection, mats["table"], table, 0.003)
    for i, x in enumerate((-0.520, 0.510), 1):
        for j, y in enumerate((-0.310, 0.310), 1):
            box(f"TABLE_LEG_{i}{j}", (x, y, -0.405), (0.045, 0.045, 0.740),
                collection, mats["table_steel"], table, 0.0015)
    for side in (-1, 1):
        box(f"TABLE_APRON_{side:+d}".replace("+", "P").replace("-", "N"),
            (-0.005, side * 0.310, -0.055), (0.985, 0.026, 0.040),
            collection, mats["table_steel"], table, 0.001)
        box(f"TABLE_BRACE_{side:+d}".replace("+", "P").replace("-", "N"),
            (0.510 if side == 1 else -0.520, 0, -0.055), (0.026, 0.575, 0.040),
            collection, mats["table_steel"], table, 0.001)


def build_frame(collection, root, mats):
    frame = empty("FRAME_STATIC", (0, 0, 0), collection, root)
    for index, sign in enumerate((-1, 1), 1):
        box(f"FRAME_LONG_{index:02}", (0.245, sign * 0.1775, 0.0825),
            (0.650, 0.025, 0.025), collection, mats["aluminum"], frame, 0.0010)
        box(f"FRAME_END_{index:02}", (0.245 + sign * 0.3125, 0, 0.0825),
            (0.025, 0.330, 0.025), collection, mats["aluminum"], frame, 0.0010)
    for i, x in enumerate((-0.056, 0.546), 1):
        for j, y in enumerate((-0.1735, 0.1735), 1):
            cylinder(f"FRAME_FOOT_{i}{j}", (x, y, 0.0075), 0.016, 0.015,
                     collection, mats["rubber"], frame, bevel=0.0015)
            cylinder(f"FRAME_POST_{i}{j}", (x, y, 0.0425), 0.0085, 0.055,
                     collection, mats["aluminum"], frame, bevel=0.0006)
            cylinder(f"FASTENER_PANEL_{i}{j}", (x, y, 0.1256), 0.003, 0.0012,
                     collection, mats["steel"], frame, sides=16, bevel=0.0002)
    panel_with_recesses(collection, mats["graphite"], frame)
    for index, y in enumerate(TRACK_Y, 1):
        box(f"CHANNEL_{index:02}_LINER", (0.285, y, 0.1176), (0.528, 0.0274, 0.0012),
            collection, mats["channel"], frame, 0.00028)


def build_scale(index, y, collection, channel, mats, font):
    code = f"{index:02}"
    ruler_y = y - 0.025
    box(f"SCALE_{code}", (0.300, ruler_y, 0.1257), (0.600, 0.012, 0.0014),
        collection, mats["scale"], channel, 0.00025)
    tick_vertices, tick_faces = [], []
    for mm in range(0, 601, 10):
        x = min(0.5996, max(0.0004, mm / 1000))
        length = 0.0033 if mm % 50 == 0 else 0.0014
        width = 0.00052 if mm % 50 == 0 else 0.00026
        top, bottom = ruler_y + 0.0052, ruler_y + 0.0052 - length
        first = len(tick_vertices)
        tick_vertices.extend([(x - width / 2, bottom, 0.12645), (x + width / 2, bottom, 0.12645),
                              (x + width / 2, top, 0.12645), (x - width / 2, top, 0.12645)])
        tick_faces.append(tuple(range(first, first + 4)))
        if mm % 100 == 0:
            align = "LEFT" if mm == 0 else "RIGHT" if mm == 600 else "CENTER"
            label(f"LABEL_SCALE_{code}_{mm:03}", str(mm), (x, ruler_y - 0.0039, 0.12649),
                  0.0040, collection, mats["ink"], font, channel, alignment=align)
    place(mesh_object(f"SCALE_TICKS_{code}", tick_vertices, tick_faces, collection, mats["ink"]),
          (0, 0, 0), channel)
    label_y = y - 0.049
    box(f"LABEL_CHANNEL_{code}_PLATE", (0.059, label_y, 0.12545),
        (0.035, 0.015, 0.0009), collection, mats["graphite"], channel, 0.0003)
    diameter = f"{WIRE_DIAMETERS[index - 1] * 1000:.2f}".replace(".", ",")
    label(f"LABEL_CHANNEL_{code}", f"{index}  /  {diameter} мм",
          (0.059, label_y - 0.0016, 0.12595), 0.0037, collection, mats["white_ink"], font, channel)


def closed_rings(ring_count, sides):
    """Connect ordered rings around a closed cross-section."""
    faces = []
    for row in range(ring_count):
        next_row = (row + 1) % ring_count
        for a in range(sides):
            b = (a + 1) % sides
            faces.append((row * sides + a, row * sides + b, next_row * sides + b, next_row * sides + a))
    return faces


def fork_cheek(name, y, collection, channel, mats):
    """Extrude a plate around a through bore concentric with the pulley pin."""
    bounds = (-0.059, 0.011, -0.004, 0.011)
    corners = [(x, z) for x in bounds[:2] for z in bounds[2:]]
    angles = sorted({2 * math.pi * k / 32 for k in range(32)}
                    | {math.atan2(z, x) % (2 * math.pi) for x, z in corners})
    vertices = []
    for outer, local_y in ((True, -0.002), (True, 0.002), (False, 0.002), (False, -0.002)):
        for angle in angles:
            x, z = math.cos(angle), math.sin(angle)
            limit_x = (bounds[1] if x > 0 else bounds[0]) / x if abs(x) > 1e-10 else math.inf
            limit_z = (bounds[3] if z > 0 else bounds[2]) / z if abs(z) > 1e-10 else math.inf
            radius = min(limit_x, limit_z) if outer else 0.00315
            vertices.append((radius * x, local_y, radius * z))
    obj = mesh_object(name, vertices, closed_rings(4, len(angles)), collection, mats["aluminum"])
    place(obj, (0.600, y, 0.135), channel)
    edge_finish(obj, 0.00026)


def wheel(index, y, wire_radius, collection, channel, mats):
    crown = 0.025 - wire_radius
    section = [(-0.008, 0.0031), (-0.008, 0.0249), (-0.0071, 0.026),
               (-0.00100, 0.026), (-0.0008, 0.0255), (-0.0006, crown),
               (0.0006, crown), (0.0008, 0.0255), (0.00100, 0.026),
               (0.0071, 0.026), (0.008, 0.0249), (0.008, 0.0031)]
    sides = 48
    vertices = [(r * math.cos(2 * math.pi * k / sides), local_y, r * math.sin(2 * math.pi * k / sides))
                for local_y, r in section for k in range(sides)]
    faces = closed_rings(len(section), sides)
    obj = mesh_object(f"PULLEY_{index:02}_WHEEL", vertices, faces, collection, mats["acetal"], smooth=True)
    place(obj, (0.600, y, 0.135), channel)
    obj["local_rotation_axis"] = "Y"
    obj["wire_path_radius_m"] = 0.025
    return obj


def build_channel(index, y, diameter, collections, root, mats, font):
    hardware, anchors, previews = (collections[key] for key in
                                   ("03_CHANNEL_HARDWARE", "06_ATTACHMENT_POINTS", "07_STRING_PREVIEWS"))
    code = f"{index:02}"
    channel = empty(f"CHANNEL_{code}", (0, 0, 0), hardware, root)
    channel["nominal_diameter_mm"] = diameter * 1000
    build_scale(index, y, hardware, channel, mats, font)
    locations = {
        "A": (0.000, y, 0.160), "B": (0.600, y, 0.160), "MID": (0.300, y, 0.160),
        "PULLEY_AXIS": (0.600, y, 0.135), "TANGENT_OUT": (0.625, y, 0.135),
        "HOOK": (0.625, y, 0.090), "SENSOR": (0.300, y + 0.023, 0.163),
    }
    for suffix, location in locations.items():
        anchor = empty(f"STR_{code}_{suffix}", location, anchors, channel, size=0.005)
        anchor["channel"] = index

    box(f"CLAMP_{code}_BASE", (-0.026, y, 0.128), (0.052, 0.036, 0.006),
        hardware, mats["aluminum"], channel, 0.001)
    box(f"CLAMP_{code}_RISER", (-0.017, y, 0.140), (0.026, 0.024, 0.018),
        hardware, mats["graphite"], channel, 0.001)
    box(f"CLAMP_{code}_JAW", (-0.013, y, 0.1565), (0.026, 0.021, 0.015),
        hardware, mats["steel"], channel, 0.0006)
    cylinder(f"CLAMP_{code}_SCREW", (-0.015, y, 0.166), 0.0050, 0.0040,
             hardware, mats["aluminum"], channel, sides=20, bevel=0.00070)
    for side, sign in enumerate((-1, 1), 1):
        cylinder(f"FASTENER_CLAMP_{code}_{side}", (-0.043, y + sign * 0.011, 0.1315),
                 0.0026, 0.0010, hardware, mats["steel"], channel, sides=16)

    box(f"FORK_{code}_BASE", (0.543, y, 0.128), (0.050, 0.038, 0.006),
        hardware, mats["aluminum"], channel, 0.0009)
    for side, sign in enumerate((-1, 1), 1):
        fork_cheek(f"FORK_{code}_CHEEK_{side}", y + sign * 0.012, hardware, channel, mats)
        cylinder(f"FASTENER_FORK_{code}_{side}", (0.529, y + sign * 0.012, 0.1320),
                 0.0027, 0.0020, hardware, mats["steel"], channel, sides=16, bevel=0.0002)
        cylinder(f"PULLEY_{code}_CAP_{side}", (0.600, y + sign * 0.0148, 0.135),
                 0.0045, 0.0016, hardware, mats["steel"], channel, axis="Y", bevel=0.0003)
    cylinder(f"PULLEY_{code}_PIN", locations["PULLEY_AXIS"], 0.0030, 0.028,
             hardware, mats["steel"], channel, axis="Y")
    wheel(index, y, diameter / 2, hardware, channel, mats)
    clip = empty(f"PARK_CLIP_{code}", (0.611, y + 0.0105, 0.132), hardware, channel, size=0.004)
    clip.rotation_euler.z = math.radians(28 if index == 1 else 0)
    clip["local_rotation_axis"] = "Z"
    box(f"PARK_CLIP_{code}_ARM", (0.007, -0.00075, -0.0035), (0.014, 0.0015, 0.007),
        hardware, mats["steel"], clip, 0.0003)
    box(f"PARK_CLIP_{code}_JAW", (0.0135, -0.003, -0.0095), (0.001, 0.006, 0.005),
        hardware, mats["steel"], clip, 0.0002)
    box(f"PARK_CLIP_{code}_PAD", (0.0135, -0.008, -0.010), (0.001, 0.004, 0.004),
        hardware, mats["rubber"], clip, 0.0002)

    span = tube(f"STR_{code}_SPAN_PREVIEW", [locations["A"], locations["B"]],
                diameter / 2, previews, mats["wire"], channel, sides=16)
    span["replace_with_runtime"] = True
    span["diameter_mm"] = diameter * 1000
    arc = [(0.600 + 0.025 * math.sin(angle), y, 0.135 + 0.025 * math.cos(angle))
           for angle in (math.pi * k / 96 for k in range(49))]
    arc[0], arc[-1] = locations["B"], locations["TANGENT_OUT"]
    tail = tube(f"STR_{code}_TAIL_PREVIEW", [*arc, locations["HOOK"]],
                diameter / 2, previews, mats["wire"], channel, sides=16)
    tail["replace_with_runtime"] = True


def build_rack(collection, anchors, root, mats, font):
    rack = empty("WEIGHT_RACK", (0, 0, 0), collection, root)
    box("RACK_FLOOR", (0.3375, -0.280, 0.003), (0.185, 0.100, 0.006),
        collection, mats["plastic"], rack, 0.0018)
    for side, y in enumerate((-0.326, -0.234), 1):
        box(f"RACK_LONG_RIM_{side}", (0.3375, y, 0.012), (0.185, 0.008, 0.012),
            collection, mats["plastic"], rack, 0.0014)
    for side, x in enumerate((0.249, 0.426), 1):
        box(f"RACK_END_RIM_{side}", (x, -0.280, 0.012), (0.008, 0.084, 0.012),
            collection, mats["plastic"], rack, 0.0014)

    for mass, x in MASS_SLOTS.items():
        cylinder(f"RACK_PAD_{mass}", (x, -0.280, 0.0065), 0.0220, 0.001,
                 collection, mats["rubber"], rack, bevel=0.00028)
        label(f"LABEL_RACK_{mass}", f"{mass} г", (x, -0.314, 0.00605),
              0.005, collection, mats["white_ink"], font, rack)
        empty(f"RACK_SLOT_{mass}", (x, -0.280, 0.0665), anchors, rack, size=0.005)


def build_weight(mass, collection, mats, font):
    # Mount one real assembly in the review pose. The rack slot remains available.
    location = (0.625, TRACK_Y[0], 0.090) if mass == 200 else (MASS_SLOTS[mass], -0.280, 0.0665)
    root = empty(f"WEIGHT_{mass}", location, collection, size=0.006)
    root["mass_g_including_holder"] = mass
    root["pivot_role"] = "hanger eye"
    root["rack_slot"] = f"RACK_SLOT_{mass}"
    cylinder(f"WEIGHT_{mass}_HOLDER_BASE", (0, 0, -0.057),
             0.017, 0.005, collection, mats["steel"], root, sides=48, bevel=0.00065)
    cylinder(f"WEIGHT_{mass}_STEM", (0, 0, -0.030),
             0.00215, 0.049, collection, mats["steel"], root, sides=20, bevel=0.00035)
    eye = [(0.0040 * math.sin(theta), 0, 0.0040 * math.cos(theta))
           for theta in (math.radians(34 + (360 - 68) * step / 36) for step in range(37))]
    tube(f"WEIGHT_{mass}_EYE", eye, 0.00070, collection, mats["steel"], root, sides=10)
    cylinder(f"WEIGHT_{mass}_EYE_SEAT", (0, 0, -0.0051), 0.0022, 0.0008,
             collection, mats["steel"], root, sides=16)
    count = mass // 100
    bottom = -0.0545
    for disk in range(count):
        thickness = 0.0105 if disk == 0 else 0.0140
        top = bottom + thickness
        cylinder(f"WEIGHT_{mass}_DISK_{disk + 1:02}", (0, 0, (bottom + top) / 2), 0.0168,
                 thickness, collection, mats["weight"], root, sides=48, bevel=0.00055,
                 flat_front=-0.015, bore=0.00235)
        bottom = top + 0.00035
    label(f"LABEL_WEIGHT_{mass}", f"{mass} г", (0, -0.01508, bottom - 0.0061),
          0.0047, collection, mats["white_ink"], font, root, front=True)


def build_instruments(collection, anchors, root, mats, font):
    for index, y in enumerate(TRACK_Y, 1):
        code = f"{index:02}"
        y += 0.023
        sensor = empty(f"SENSOR_{code}", (0.300, y, 0.163), collection, root, size=0.005)
        box(f"SENSOR_{code}_HEAD", (0, 0, 0), (0.022, 0.014, 0.020),
            collection, mats["plastic"], sensor, 0.0015)
        cylinder(f"SENSOR_{code}_STALK", (0, 0, -0.023),
                 0.003, 0.026, collection, mats["steel"], sensor, sides=20)
        cylinder(f"SENSOR_{code}_FOOT", (0, 0, -0.037), 0.0045, 0.002,
                 collection, mats["aluminum"], sensor, sides=20, bevel=0.0003)
        cylinder(f"SENSOR_{code}_LENS", (0, -0.00765, -0.0027), 0.004, 0.0013,
                 collection, mats["glass"], sensor, axis="Y", bevel=0.0003)
        cylinder(f"LED_{code}", (0.0061, -0.0076, 0.0044), 0.0012, 0.0011, collection,
                 mats["led"] if index == 1 else mats["glass"], sensor, sides=16, axis="Y")
        tube(f"SENSOR_{code}_LEAD", [(0.011, 0, -0.004), (0.016, 0, -0.004),
             (0.019, 0, -0.010), (0.022, 0, -0.028), (0.024, 0, -0.035), (0.024, 0, -0.037)],
             0.0015, collection, mats["rubber"], sensor, sides=10)
        cylinder(f"SENSOR_{code}_GROMMET", (0.024, 0, -0.037),
                 0.0032, 0.002, collection, mats["rubber"], sensor, sides=16)

    meter = box("METER_BODY", (0.315, 0.155, 0.164), (0.180, 0.062, 0.078),
                collection, mats["plastic"], root, 0.0035)
    box("METER_FACE", (0, -0.0317, 0), (0.171, 0.0014, 0.069),
        collection, mats["aluminum"], meter, 0.00045)
    for name, x, width, height, caption, demo, font_size in (
        ("METER_DISPLAY", -0.035, 0.096, 0.032, "ЧАСТОТА, Гц", "49,55", 0.015),
        ("STOPWATCH_DISPLAY", 0.052, 0.048, 0.020, "СЕКУНДОМЕР, с", "0,000", 0.008),
    ):
        screen = empty(name, (x, -0.031, 0.005), anchors, meter, size=0.004)
        screen.rotation_euler.x = math.pi / 2
        box(f"{name}_GLASS", (x, -0.03315, 0.005), (width, 0.00145, height),
            collection, mats["glass"], meter, 0.00055)
        label(f"LABEL_{name}_TITLE", caption, (x, -0.03249, 0.0255),
              0.0045, collection, mats["ink"], font, meter, front=True)
        label(f"LABEL_{name}_DEMO", demo, (x, -0.0340, 0.0010),
              font_size, collection, mats["lit"], font, meter, front=True)
    for index, x in enumerate((0.028, 0.051, 0.074), 1):
        box(f"METER_KEY_{index:02}", (x, -0.033, -0.019), (0.014, 0.0012, 0.005),
            collection, mats["plastic"], meter, 0.0004)


def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def camera(name, location, target, collection, *, fov=38, ortho=None):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = location
    if target:
        aim(obj, target)
    data.clip_start = 0.01
    data.clip_end = 50
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = ortho
    else:
        data.sensor_fit = "VERTICAL"
        data.sensor_height = 32
        data.lens = 16 / math.tan(math.radians(fov / 2))
    return obj


def area_light(name, location, target, power, size, collection, *, width=None, color=(1, 1, 1)):
    light = bpy.data.lights.new(name, "AREA")
    obj = bpy.data.objects.new(name, light)
    collection.objects.link(obj)
    obj.location = location
    light.energy = power
    light.color = color
    light.size = size
    if width:
        light.shape = "RECTANGLE"
        light.size_y = width
    aim(obj, target)


def build_studio(scene, collection, mats):
    box("STUDIO_FLOOR", (0, 0, -0.786), (200, 200, 0.020), collection, mats["studio"])
    scene.camera = camera("CAM_OVERVIEW", (1.02, -0.88, 0.60), (0.300, -0.015, 0.105), collection)
    camera("CAM_FRONT", (0.028, -2.80, -0.240), (0.028, 0, -0.240), collection, ortho=1.76)
    camera("CAM_TOP", (0.030, 0, 1.60), None, collection, ortho=1.34)
    camera("CAM_CLAMPS", (0.235, -0.365, 0.355), (-0.003, 0, 0.151), collection, fov=33)
    camera("CAM_PULLEYS", (0.960, -0.470, 0.350), (0.600, 0, 0.110), collection, fov=31)
    camera("CAM_MEASURE", (0.310, -0.680, 0.290), (0.300, 0, 0.150), collection)
    camera("CAM_INSTRUMENTS", (0.040, -0.310, 0.640), (0.303, 0.095, 0.160), collection, fov=29)
    area_light("LIGHT_KEY", (-0.28, -0.58, 1.03), (0.20, 0, 0.09), 77, 0.84,
               collection, color=(1.00, 0.96, 0.90))
    area_light("LIGHT_FILL", (0.94, -0.51, 0.57), (0.34, 0, 0.09), 32, 0.69,
               collection, color=(0.89, 0.94, 1.00))
    area_light("LIGHT_RIM", (0.35, 0.56, 1.04), (0.31, 0, 0.12), 105, 0.86,
               collection, color=(0.93, 0.96, 1.00))
    area_light("LIGHT_WIRE_STRIP", (0.26, 0.02, 0.66), (0.29, -0.01, 0.10), 33, 0.75,
               collection, width=0.095)
    world = bpy.data.worlds.new("LAB_STUDIO_WORLD")
    world.use_nodes = True
    background = next(node for node in world.node_tree.nodes if node.type == "BACKGROUND")
    background.inputs["Color"].default_value = (0.52, 0.59, 0.67, 1)
    background.inputs["Strength"].default_value = 0.35
    scene.world = world


def is_factory_scene(scene):
    return (not bpy.data.filepath and not bpy.data.is_dirty and scene.name == "Scene"
            and {(obj.name, obj.type) for obj in scene.objects} ==
            {("Cube", "MESH"), ("Camera", "CAMERA"), ("Light", "LIGHT")})


def remove_scene_objects(scene):
    """Remove only a verified generator-owned or factory scene."""
    owned_data = {obj.data for obj in scene.objects if obj.data and len(obj.users_scene) == 1}
    materials = {mat for data in owned_data if isinstance(data, bpy.types.Mesh)
                 for mat in data.materials if mat}
    world = scene.world
    for obj in list(scene.objects):
        if len(obj.users_scene) == 1:
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(scene.collection.children):
        if collection.users == 1:
            bpy.data.collections.remove(collection)
    bpy.data.scenes.remove(scene)
    bpy.data.batch_remove(ids=[item for item in owned_data if item.users == 0])
    bpy.data.batch_remove(ids=[mat for mat in materials if mat.users == 0])
    if world and world.users == 0:
        bpy.data.worlds.remove(world)


def build(font_path=None):
    previous = bpy.context.scene
    is_ours = previous.get("generated_by") == GENERATOR_ID
    factory = is_factory_scene(previous)
    scene = bpy.data.scenes.new("Prototype Under Construction")
    if bpy.context.window is None:
        raise RuntimeError("Blender needs a window context for mesh lettering.")
    bpy.context.window.scene = scene
    if is_ours:
        remove_scene_objects(previous)
    scene.name = SCENE_NAME
    scene["generated_by"] = GENERATOR_ID
    scene["specification"] = "docs/installation.md, variant A"
    scene["review_pose"] = "200 g on S1; other masses parked"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = -0.35

    collections = {}
    for name in COLLECTIONS:
        collection = bpy.data.collections.new(name)
        scene.collection.children.link(collection)
        collections[name] = collection
    root = empty("LAB_ROOT", (0, 0, 0), collections["02_FRAME"], size=0.040)
    mats = make_materials()
    font = load_font(font_path)
    build_table(collections["01_TABLE"], root, mats)
    build_frame(collections["02_FRAME"], root, mats)
    for index, (y, diameter) in enumerate(zip(TRACK_Y, WIRE_DIAMETERS), 1):
        build_channel(index, y, diameter, collections, root, mats, font)
    build_rack(collections["04_WEIGHTS"], collections["06_ATTACHMENT_POINTS"], root, mats, font)
    for mass in MASS_SLOTS:
        build_weight(mass, collections["04_WEIGHTS"], mats, font)
    build_instruments(collections["05_INSTRUMENTS"], collections["06_ATTACHMENT_POINTS"], root, mats, font)
    build_studio(scene, collections["08_STUDIO"], mats)
    # All labels are meshes. Drop the private font datablock before saving.
    bpy.data.fonts.remove(font)
    if factory:
        remove_scene_objects(previous)
    bpy.context.view_layer.update()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                space.overlay.show_overlays = False
                space.clip_start = 0.005
                space.clip_end = 50
                space.region_3d.view_perspective = "CAMERA"
    return scene


def save_prototype(output):
    path = Path(output).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    file_preferences = bpy.context.preferences.filepaths
    save_versions = file_preferences.save_version
    try:
        file_preferences.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True, relative_remap=False)
    finally:
        file_preferences.save_version = save_versions


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("prototype.blend"))
    parser.add_argument("--font", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    build(args.font)
    save_prototype(args.output)
