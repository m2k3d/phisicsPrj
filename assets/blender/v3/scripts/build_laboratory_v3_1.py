"""Add the approved measurement system to a copy of the V3 Blender scene."""

import math
import os
import runpy
from pathlib import Path

import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("LAB_V3_OUTPUT_DIR", HERE.parent)).resolve()
SOURCE = MODEL_DIR / "laboratory_v3.blend"
OUTPUT = MODEL_DIR / "laboratory_v3_1.blend"
SCENE_NAME = "STANDING_WAVE_LAB_V3_1"
BASE = runpy.run_path(str(HERE / "build_laboratory_v3.py"))
for key in ("mm", "mesh", "block", "empty", "turn", "circle", "cylinder", "bore", "boolean",
            "apply", "bevel", "material", "lettering", "font_from_paths", "prism", "camera", "aim",
            "area", "screw"):
    globals()[key] = BASE[key]
COLLECTIONS = BASE["COLLECTIONS"]
M = BASE["M"]
FRONT = BASE["FRONT"]
REAR = (-math.pi / 2, 0, 0)
RIGHT = (0, math.pi / 2, 0)
LEFT = (0, -math.pi / 2, 0)
PICKUP_GROUP = 9
CABLE_GROUP = 10
CHANNELS = (-110, 0, 110)
PITCH = math.radians(14)
POLE_Y = 8.2
POLE_Z = 410
SCOPE_ORIGIN = (-307.325, -150, 0)
SCOPE_INPUTS = (-104, -57, -10, 37)
PREAMP_ORIGIN = (-379.5, 187, 0)
PREAMP_INPUTS_Y = (-27, 0, 27)
PREAMP_OUTPUTS_X = (-34, 0, 34)
CHANNEL_COLORS = ("ch1", "ch2", "ch3", "ch4")


def initialize_collections(scene):
    for index, name in enumerate(BASE["COLLECTION_NAMES"], 1):
        COLLECTIONS[index] = bpy.data.collections[name]
    for index, name in ((PICKUP_GROUP, "09_PICKUPS"), (CABLE_GROUP, "10_CABLING")):
        col = bpy.data.collections.new(name)
        scene.collection.children.link(col)
        COLLECTIONS[index] = col
    old = list(COLLECTIONS[5].objects)
    old += [obj for obj in COLLECTIONS[8].objects if obj.name.startswith(("DEMO_METER_", "DEMO_STOPWATCH_"))]
    old += [scene.objects[key] for key in ("METER_DISPLAY", "STOPWATCH_DISPLAY")]
    for obj in old:
        bpy.data.objects.remove(obj, do_unlink=True)


def set_materials():
    M.update({tag: bpy.data.materials[key] for tag, key in {
        "steel": "Hardware | polished stainless",
        "fastener": "Hardware | oxide steel",
        "rubber": "Feet | black elastomer",
    }.items()})
    specs = [
        ("acrylic", "F2F7F7", 0.09, 0, 0),
        ("copper", "B26438", 0.26, 0.78, 0),
        ("bobbin", "273338", 0.50, 0, 0),
        ("magnet", "4F5158", 0.42, 0.55, 0),
        ("carrier", "ADB9BE", 0.34, 0.66, 0),
        ("carrier_dark", "465A61", 0.44, 0.35, 0),
        ("enclosure", "B2B8B6", 0.49, 0.32, 0),
        ("scope_face", "C2C9C8", 0.42, 0, 0),
        ("scope_case", "374448", 0.43, 0, 0),
        ("scope_dark", "1D2A2E", 0.42, 0, 0),
        ("bezel", "151D25", 0.33, 0, 0),
        ("screen", "10262C", 0.37, 0, 0.3),
        ("grid", "36555A", 0.46, 0, 0.32),
        ("trace", "82E6C2", 0.43, 0, 0.9),
        ("ui", "D0E8E7", 0.45, 0, 0.45),
        ("mark", "25343C", 0.49, 0, 0),
        ("legend", "DBE3E3", 0.54, 0, 0),
        ("lcd", "A0AD8A", 0.46, 0, 0.14),
        ("digits", "263128", 0.5, 0, 0),
        ("ch1", "C69946", 0.43, 0, 0),
        ("ch2", "52A89B", 0.43, 0, 0),
        ("ch3", "6299BE", 0.43, 0, 0),
        ("ch4", "AF7996", 0.43, 0, 0),
        ("cable", "28353C", 0.58, 0, 0),
        ("pair_hot", "85564A", 0.53, 0, 0),
    ]
    for name, hex_value, roughness, metal, glow in specs:
        material(name, f"Measurement | {name}", hex_value, roughness, metal, glow)
    pbr = next(node for node in M["acrylic"].node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    pbr.inputs["IOR"].default_value = 1.49
    pbr.inputs["Transmission Weight"].default_value = 1.0
    pbr.inputs["Coat Weight"].default_value = 0.18


def rounded_panel(name, width, length, depth, position, material_key, group, parent, corner):
    outline = []
    for i, (x, y) in enumerate(((width / 2 - corner, length / 2 - corner),
                                 (-width / 2 + corner, length / 2 - corner),
                                 (-width / 2 + corner, -length / 2 + corner),
                                 (width / 2 - corner, -length / 2 + corner))):
        for j in range(7):
            angle = math.radians(90 * i + 15 * j)
            outline.append((x + corner * math.cos(angle), y + corner * math.sin(angle)))
    return prism(name, outline, depth, position, group, parent, material_key)


def axial_ring(name, profile, inner, position, mat, group, parent, rotation=FRONT, count=32):
    start, end = profile[0][0], profile[-1][0]
    stations = [*profile, (end, inner), (start, inner)]
    vertices = [(x, y, z) for z, radius in stations for x, y in circle(radius, count)]
    faces = []
    for i in range(len(stations)):
        a = i * count
        b = ((i + 1) % len(stations)) * count
        faces.extend((a + j, a + (j + 1) % count, b + (j + 1) % count, b + j)
                     for j in range(count))
    part = mesh(name, vertices, faces, position, group, parent, mat)
    part.rotation_euler = rotation
    for f in part.data.polygons:
        f.use_smooth = True
    for edge in part.data.edges:
        i, j = edge.vertices
        edge.use_edge_sharp = i // count == j // count
    return part


def terminal(name, pos, group, parent, rotation, color, bnc=False):
    pivot = empty(name, pos, group, parent)
    pivot.rotation_euler = rotation
    if bnc:
        axial_ring(name + "_INSULATOR", [(0, 7.3), (0.9, 7.3)], 5.4, (0, 0, 0),
                   color, group, pivot, (0, 0, 0))
        axial_ring(name + "_SHELL", [(0, 5.35), (1.6, 5.35), (2, 4.8), (7, 4.8), (7.55, 4.48)],
                   3.78, (0, 0, 0), "steel", group, pivot, (0, 0, 0))
        axial_ring(name + "_DIELECTRIC", [(1, 3.76), (3.8, 3.76)], 0.95, (0, 0, 0),
                   "scope_face", group, pivot, (0, 0, 0))
        axial_ring(name + "_CONTACT", [(1, 0.95), (4.6, 0.95)], 0.63, (0, 0, 0),
                   "copper", group, pivot, (0, 0, 0), 24)
        for sign, tag in ((-1, "L"), (1, "R")):
            peg = cylinder(f"{name}_LUG_{tag}", 1, 1.4, (sign * 5.4, 0, 5), "steel", group, pivot, 16)
            peg.rotation_euler = RIGHT
        return pivot
    axial_ring(name + "_COLLAR", [(0, 4.35), (1.5, 4.35), (2, 3.9)], 2.65, (0, 0, 0),
               color, group, pivot, (0, 0, 0))
    axial_ring(name + "_CONTACT", [(0.7, 2.65), (1.95, 2.65)], 2.0, (0, 0, 0),
               "steel", group, pivot, (0, 0, 0))
    return pivot


def plugs(jack, tag, color, bnc=False):
    base = empty(tag, (0, 0, 0), CABLE_GROUP, jack)
    length = 20 if bnc else 10.2
    r = 6.35 if bnc else 3.8
    start = 6 if bnc else 2
    axial_ring(tag + "_COUPLING", [(start, r - 0.18), (start + 0.35, r),
                                  (start + 5.3, r), (start + 5.6, r - 0.3)],
               5.12 if bnc else 2.7, (0, 0, 0),
               "steel" if bnc else color, CABLE_GROUP, base, (0, 0, 0), 24)
    turn(tag + "_STRAIN_RELIEF", [(start + 5.6, r - 0.35), (length - 1.9, 2.95 if bnc else 2.2),
                                  (length, 1.85 if bnc else 1.15)],
         (0, 0, 0), "cable" if bnc else color, CABLE_GROUP, base, 24, sharp_rings=True)
    return base, length


def rounded_route(points, bend):
    points = [Vector(p) for p in points]
    result = [points[0]]
    for previous, center, next_point in zip(points, points[1:], points[2:]):
        incoming, outgoing = previous - center, next_point - center
        trim = min(bend, incoming.length * 0.40, outgoing.length * 0.40)
        a = center + trim * incoming.normalized()
        b = center + trim * outgoing.normalized()
        result.extend((1 - t)**2 * a + 2 * t * (1 - t) * center + t**2 * b
                      for t in (i / 7 for i in range(8)))
    result.append(points[-1])
    return result


def cable(name, points, radius, mat, parent, bend=10):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.bevel_depth = radius / 1000
    data.bevel_resolution = 2
    data.use_fill_caps = True
    data.materials.append(M[mat])
    spline = data.splines.new("POLY")
    rounded = rounded_route(points, bend)
    spline.points.add(len(rounded) - 1)
    for p, co in zip(spline.points, rounded):
        p.co = (*mm(co), 1)
    obj = bpy.data.objects.new(name, data)
    COLLECTIONS[CABLE_GROUP].objects.link(obj)
    obj.parent = parent
    bpy.context.view_layer.update()
    mesh_data = bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(obj, do_unlink=True)
    stored = bpy.data.objects.new(name, mesh_data)
    COLLECTIONS[CABLE_GROUP].objects.link(stored)
    stored.parent = parent
    return stored


def point(obj, local=(0, 0, 0)):
    return tuple((obj.matrix_world @ Vector(mm(local))) * 1000)


def sensor_shell(pickup, tag):
    group = PICKUP_GROUP
    for side, x in (("L", -38.85), ("R", 38.85)):
        block(f"PU_{tag}_ACRYLIC_{side}", (2.3, 25, 35), (x, 12.5, 0), "acrylic", group, pickup, 0.55)
    for side, z in (("LOWER", -16.45), ("UPPER", 16.45)):
        block(f"PU_{tag}_ACRYLIC_{side}", (75.4, 25, 2.1), (0, 12.5, z),
              "acrylic", group, pickup, 0.5)
    face = block(f"PU_{tag}_ACRYLIC_FACE", (75.4, 2.3, 30.8), (0, 1.15, 0), "acrylic", group, pickup)
    bore(face, (0, 1, 0), 5.45, 7, group, "Y")
    for x in (-29, 29):
        bore(face, (x, 1, 1), 2.7, 7, group, "Y", 24)
    bevel(face, 0.44)
    block(f"PU_{tag}_ACRYLIC_BACK", (75.4, 2.4, 30.8), (0, 23.8, 0), "acrylic", group, pickup, 0.54)
    axis = cylinder(f"PU_{tag}_POLE", 4.95, 10.5, (0, 5.55, 0), "steel", group, pickup)
    axis.rotation_euler = FRONT
    magnet = cylinder(f"PU_{tag}_MAGNET", 6.7, 6.2, (0, 18.1, 0), "magnet", group, pickup, 40)
    magnet.rotation_euler = FRONT
    axial_ring(f"PU_{tag}_BOBBIN", [(0, 9.4), (1.4, 9.4), (1.6, 6.05),
                                  (10.65, 6.05), (10.9, 9.4), (12.2, 9.4)],
               5.12, (0, 14.85, 0), "bobbin", group, pickup)
    winding = [(0, 8.6), (0.6, 8.9), *((0.7 + j * .26, 8.83 + .10 * (j % 2)) for j in range(34)),
               (9.6, 8.89), (10, 8.62)]
    axial_ring(f"PU_{tag}_COPPER_WINDING", winding, 6.1, (0, 13.5, 0), "copper", group, pickup, count=40)
    for x in (-35, 35):
        for z in (-11, 11):
            screw(f"PU_{tag}_FACE_SCREW_{x + 35:02}_{z + 11:02}", 2.5, (x, 0, z), group, pickup, FRONT)
    return [terminal(f"PU_{tag}_{polarity}", (x, 0, 1), group, pickup, FRONT, color)
            for polarity, x, color in (("HI", -29, "pair_hot"), ("LO", 29, "bobbin"))]


def pickup_support(root, pickup, x, tag):
    group = PICKUP_GROUP
    block(f"PU_{tag}_RAIL_SHOE", (29, 19, 4), (x, 79.5, 352),
          "carrier_dark", group, root, 0.9)
    step = block(f"PU_{tag}_RISER", (21, 12, 36.5), (x, 79.5, 374.25),
                 "carrier", group, root)
    step["fastening"] = "Clamp on rail, height adjustable with slotted upright"
    tool = block(f"TOOL_PU_{tag}_RISER_SLOT", (5.4, 13, 17), (x, 79.5, 373.5),
                 None, group, root, 2.3)
    apply(tool, tool.modifiers[0])
    boolean(step, tool)
    bevel(step, .55)
    screw(f"PU_{tag}_HEIGHT_LOCK", 4, (x, 73.5, 374), group, root, FRONT)
    slide = block(f"PU_{tag}_UPPER_SLIDE", (28, 63.2, 4.5), (x, 53.3, 394),
                  "carrier_dark", group, root)
    for side in (-1, 1):
        slot = block(f"TOOL_PU_{tag}_DEPTH_SLOT_{side}", (3.7, 14, 7), (x + 8 * side, 69, 394),
                     None, group, root, 1.65)
        apply(slot, slot.modifiers[0])
        boolean(slide, slot)
        screw(f"PU_{tag}_DEPTH_LOCK_{side + 1}", 3, (x + 8 * side, 72, 396.25), group, root)
    bevel(slide, .52)
    for offset in (-8, 8):
        screw(f"PU_{tag}_SHOE_BOLT_{offset + 8:02}", 3, (x + offset, 80, 354), group, root)
    # The tilted saddle joins the acrylic back half to the adjustment slide.
    block(f"PU_{tag}_SADDLE", (42, 22, 2.5), (0, 15, -18.75),
          "carrier", group, pickup, 0.85)
    for sign, side in ((-1, "L"), (1, "R")):
        block(f"PU_{tag}_CUSHION_{side}", (5.5, 16, 1.25), (sign * 17, 17, -17.9),
              "rubber", group, pickup, 0.42)
        block(f"PU_{tag}_CLAMP_{side}", (3.8, 13, 9), (sign * 40.8, 17, -12.9),
              "carrier_dark", group, pickup, 0.6)
    block(f"PU_{tag}_SADDLE_LINK", (24, 14, 5.7), (x, 29, 396.75),
          "carrier_dark", group, root, .58)


def pickups(root):
    rail = empty("PICKUP_RAIL_ASSEMBLY", (0, 0, 0), PICKUP_GROUP, root)
    # 20 x 20 profile with machined visual slots along the exposed faces.
    member = block("PICKUP_RAIL_20X20", (360, 20, 20), (0, 80, 340),
                   "carrier", PICKUP_GROUP, rail)
    for name, dims, pos in (("FRONT", (362, 3.8, 5.5), (0, 70, 340)),
                            ("TOP", (362, 5.5, 3.8), (0, 80, 350))):
        tool = block(f"TOOL_RAIL_SLOT_{name}", dims, pos, None, PICKUP_GROUP, rail)
        boolean(member, tool)
    bevel(member, .42)
    for i, x in enumerate((-180, 180), 1):
        block(f"PICKUP_RAIL_END_ARM_{i:02}", (19, 46, 14), (x, 113, 338),
              "carrier_dark", PICKUP_GROUP, rail, .8)
        flange = block(f"PICKUP_RAIL_FRAME_FLANGE_{i:02}", (25, 4, 28), (x, 138, 335),
                       "carrier", PICKUP_GROUP, rail)
        for z in (328, 343):
            bore(flange, (x, 138, z), 2.2, 7, PICKUP_GROUP, "Y", 24)
            screw(f"PICKUP_RAIL_FRAME_BOLT_{i:02}_{z}", 4, (x, 136, z), PICKUP_GROUP, rail, FRONT)
            nut = block(f"PICKUP_RAIL_FRAME_NUT_{i:02}_{z}", (9.8, 2.65, 8.5),
                        (x, 144.6, z), "steel", PICKUP_GROUP, rail)
            bore(nut, (x, 144.6, z), 2, 5, PICKUP_GROUP, "Y", 24)
            stud = cylinder(f"PICKUP_RAIL_FRAME_STUD_{i:02}_{z}", 1.94, 9.95, (x, 140.975, z),
                            "steel", PICKUP_GROUP, rail, 24)
            stud.rotation_euler = FRONT
        bevel(flange, .54)
        block(f"PICKUP_RAIL_END_CAP_{i:02}", (2.0, 20, 20), (x + math.copysign(1, x), 80, 340),
              "rubber", PICKUP_GROUP, rail, 0.58)
    outputs = []
    for i, x in enumerate(CHANNELS, 1):
        tag = f"{i:02}"
        p = x + 6.5
        pickup = empty(f"PICKUP_{tag}", (p, POLE_Y, POLE_Z), PICKUP_GROUP, root)
        pickup.rotation_euler.x = PITCH
        pickup["reference"] = "Eisco PH0731"
        pickup["housing_mm"] = [80, 35, 25]
        pickup["angle_from_vertical_deg"] = 14
        pickup["active_geometry"] = "provisional coil and pole arrangement"
        jacks = sensor_shell(pickup, tag)
        pickup_support(rail, pickup, p, tag)
        outputs.append((pickup, jacks))
    return outputs


def knob(name, x, z, r, depth, parent):
    grip = turn(name, [(0, r - .7), (1.1, r), (depth - .9, r - .35), (depth, r - 1.2)],
                (x, -.3, z), "scope_case", 5, parent, 36, sharp_rings=True)
    grip.rotation_euler = FRONT
    for i, (dx, dz) in enumerate(circle(r - .22, 16)):
        rib = block(f"{name}_RIB_{i:02}", (1.0, depth - 2.8, .82),
                    (x + dx, -.3 - depth / 2, z + dz), "scope_dark", 5, parent, .24)
        rib.rotation_euler.y = -math.atan2(dz, dx)


def rear_vent(scope):
    # Black recess and separately perforated honeycomb grill.
    block("SCOPE_REAR_VENT_DARK", (99, 1, 49), (15, 70.8, 90), "scope_dark", 5, scope, 2)
    vertices, faces = [], []
    for row in range(7):
        for column in range(14):
            x = -29 + 6.65 * column + 3.32 * (row % 2)
            z = 70.0 + 6.35 * row
            start = len(vertices)
            for depth in (0, 1.7):
                for radius in (3.55, 2.79):
                    vertices.extend((x + dx, depth, z + dz) for dx, dz in circle(radius, 6, math.pi / 6))
            for i in range(6):
                j = (i + 1) % 6
                faces.extend(tuple(start + q for q in face) for face in
                             ((i, j, j + 6, i + 6), (12 + i, 18 + i, 18 + j, 12 + j),
                              (i, 12 + i, 12 + j, j), (i + 6, j + 6, j + 18, i + 18)))
    mesh("SCOPE_REAR_HONEYCOMB", vertices, faces, (0, 74.8, 0), 5, scope, "scope_case")


def scope(root, regular, bold, mono):
    base = empty("OSCILLOSCOPE", SCOPE_ORIGIN, 5, root)
    base["reference"] = "Rigol DHO804"
    base["envelope_mm_W_H_D"] = [265.35, 161.75, 77.38]
    block("SCOPE_SHELL", (261.2, 60, 147.8), (0, 39, 80.9), "scope_case", 5, base, 5)
    face = block("SCOPE_FRONT_BEZEL", (265.35, 9, 151.75), (0, 4.5, 85.875),
                 "scope_face", 5, base, 5.0)
    apply(face, face.modifiers[0])
    glass_tool = block("TOOL_SCOPE_SCREEN_POCKET", (167, 5, 98.6), (-39, -.5, 98.7),
                       None, 5, base, 3)
    apply(glass_tool, glass_tool.modifiers[0])
    boolean(face, glass_tool)
    block("SCOPE_SCREEN_BEZEL", (166.7, .9, 98.3), (-39, 1.55, 98.7), "bezel", 5, base, .36)
    pivot = empty("OSCILLOSCOPE_DISPLAY", (-39, .99, 98.7), 6, base)
    pivot.rotation_euler = FRONT
    pivot["display_mm"] = [153.45, 89.91]
    pivot["preview_quantity"] = "normalized pickup voltage"
    plane = mesh("OSCILLOSCOPE_DISPLAY_SURFACE",
                 [(-76.725, -44.955, 0), (76.725, -44.955, 0),
                  (76.725, 44.955, 0), (-76.725, 44.955, 0)], [(0, 1, 2, 3)],
                 (0, 0, 0), 5, pivot, "screen")
    uv = plane.data.uv_layers.new(name="Display")
    for index, xy in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[index].uv = xy
    block("SCOPE_LEFT_SIDE_TRIM", (1.4, 48, 98), (-130.6, 39, 79), "scope_dark", 5, base, .68)
    block("SCOPE_RIGHT_SIDE_TRIM", (1.4, 48, 98), (130.6, 39, 79), "scope_dark", 5, base, .68)
    rear = block("SCOPE_REAR_COVER", (257, 8.38, 142), (0, 73.19, 81), "scope_case", 5, base, 4.1)
    apply(rear, rear.modifiers[0])
    vent_tool = block("TOOL_REAR_VENT", (102, 12, 50.7), (15, 76.2, 90), None, 5, base, 2)
    apply(vent_tool, vent_tool.modifiers[0])
    boolean(rear, vent_tool)
    rear_vent(base)
    for i, (name, x, z, w, h) in enumerate((
            ("USB_C_POWER", -101, 31, 9.5, 3.9), ("LAN", -75, 32, 15, 12),
            ("HDMI", -51, 31, 13.5, 5), ("USB_DEVICE", -29, 31, 10.3, 8.5)), 1):
        cut = block(f"TOOL_SCOPE_{name}", (w + .6, 8, h + .65), (x, 77, z), None, 5, base, .65)
        apply(cut, cut.modifiers[0])
        boolean(rear, cut)
        block(f"SCOPE_REAR_{name}_INNER", (w - .5, 1.2, h - .55),
              (x, 74.2, z), "bezel", 5, base, .4)
        lettering(f"SCOPE_REAR_PORT_LABEL_{i}", name.replace("_", " "), 2.7,
                  (x, 77.43, z + 9.5), "legend", 5, base, regular, (math.pi / 2, 0, math.pi))
    for label, x, z in (("HORIZ", 62, 145), ("VERT", 91, 145), ("TRIG", 112, 114)):
        lettering("SCOPE_LABEL_" + label, label, 3.7, (x, -.055, z), "mark", 5, base, regular)
    for label, x, z, r, d in (("HORIZONTAL", 62, 129, 8.1, 7.1),
                              ("VERTICAL", 91, 129, 8.0, 7.1),
                              ("TRIGGER", 110, 100, 7.8, 7.3),
                              ("SELECT", 101, 52, 8.95, 8.5)):
        knob("SCOPE_KNOB_" + label, x, z, r, d, base)
    for i, (x, z, text, color) in enumerate((
            (57, 105, "CURSOR", "scope_dark"), (79, 105, "MEAS", "scope_dark"),
            (57, 90, "AUTO", "scope_dark"), (79, 90, "SINGLE", "ch1"),
            (57, 75, "MENU", "scope_dark"), (79, 75, "RUN", "ch2"),
            (53, 51, "1", "ch1"), (66, 51, "2", "ch2"), (79, 51, "3", "ch3"), (110, 72, "4", "ch4"),
           ), 1):
        w = 18.5 if len(text) > 1 else 10
        block(f"SCOPE_KEY_{i:02}", (w, 2.8, 8.15), (x, -1.4, z), color, 5, base, 1.6)
        lettering(f"SCOPE_KEY_LEGEND_{i:02}", text, 3.55, (x, -2.85, z),
                  "legend" if color != "ch1" else "mark", 5, base, bold)
    power = cylinder("SCOPE_POWER_KEY", 4.3, 2, (115, -1, 20), "scope_dark", 5, base, 28)
    power.rotation_euler = FRONT
    lettering("SCOPE_POWER_MARK", "I", 4.2, (115, -2.05, 20), "legend", 5, base, bold)
    lettering("SCOPE_FACE_CAPTION", "ЦИФРОВОЙ ОСЦИЛЛОГРАФ", 6.25, (-116, -.055, 150),
              "mark", 5, base, bold, align="LEFT")
    lettering("SCOPE_BANDWIDTH_LABEL", "70 MHz   •   4 CH", 3.6, (-113, -.055, 43),
              "mark", 5, base, regular, align="LEFT")
    inputs = []
    for i, x in enumerate(SCOPE_INPUTS, 1):
        inputs.append(terminal(f"OSC_CH_{i:02}_BNC", (x, 0, 24), 5, base, FRONT, CHANNEL_COLORS[i - 1], True))
        lettering(f"SCOPE_BNC_LABEL_{i:02}", f"CH{i}", 4.1, (x, -.045, 35.8),
                  "mark", 5, base, bold)
    for side in (-1, 1):
        code = "L" if side < 0 else "R"
        block(f"SCOPE_FRONT_FOOT_{code}", (26, 22, 8), (side * 96, 15, 4), "rubber", 5, base, 1.4)
        block(f"SCOPE_REAR_FOOT_{code}", (26, 25, 10), (side * 96, 64, 5),
              "scope_dark", 5, base, 1.45)
        stand = block(f"SCOPE_FOLDING_STAND_{code}", (17, 36, 5), (side * 103, 62.8, 22),
                      "scope_dark", 5, base, 1.6)
        stand.rotation_euler.x = math.radians(64)
        hinge = cylinder(f"SCOPE_STAND_HINGE_{code}", 5.2, 23, (side * 103, 69.6, 38.15),
                         "scope_case", 5, base, 28)
        hinge.rotation_euler = RIGHT
    screen_preview(pivot, regular, mono)
    return base, inputs


def screen_preview(pivot, font, mono):
    # The studio trace is the derivative of the model displacement, normalized
    # for illustration. Material and geometry of the glass have a separate pivot.
    left, right, center = -68, 68, 0.0
    start, stop = -.007, .077
    frequency = 91.326
    tau = .35
    omega = math.tau * frequency
    initial_phase = math.atan(-1 / (omega * tau))
    first = (math.pi + initial_phase) / omega
    last = first + 5 / frequency

    def screen_x(t):
        return left + (t - start) / (stop - start) * (right - left)

    def wire_signal(t):
        if t < 0:
            return 0
        return math.exp(-t / tau) * (-math.sin(omega * t) - math.cos(omega * t) / (omega * tau))

    def strip(name, xy, thickness, mat):
        vertices, faces = [], []
        for i, (x, y) in enumerate(xy):
            a = Vector(xy[max(i - 1, 0)])
            b = Vector(xy[min(i + 1, len(xy) - 1)])
            n = (b - a).normalized()
            vertices.extend(((x - n.y * thickness / 2, y + n.x * thickness / 2, .11),
                             (x + n.y * thickness / 2, y - n.x * thickness / 2, .11)))
            if i:
                j = 2 * i
                faces.append((j - 2, j - 1, j + 1, j))
        mesh(name, vertices, faces, (0, 0, 0), 8, pivot, mat)

    for i in range(11):
        x = left + (right - left) * i / 10
        strip(f"DEMO_SCOPE_GRID_V_{i:02}", [(x, -28), (x, 26)], .28, "grid")
    for i in range(7):
        y = -28 + 9 * i
        strip(f"DEMO_SCOPE_GRID_H_{i:02}", [(left, y), (right, y)], .28, "grid")
    for i, t in enumerate((first, last), 1):
        x = screen_x(t)
        for row in range(10):
            z = -27 + row * 5.35
            strip(f"DEMO_SCOPE_CURSOR_{i}_{row:02}", [(x, z), (x, z + 2.8)], .44, "ch1")
    xy = [(screen_x(t), center + 22 * wire_signal(t))
          for t in (start + i / 800 * (stop - start) for i in range(801))]
    strip("DEMO_SCOPE_PICKUP_VOLTAGE", xy, .7, "trace")
    for name, value, pos, size, mat, selected_font in (
            ("CHANNEL", "CH2   ЗАХВАТ", (-68, 35, .13), 5.75, "trace", mono),
            ("UNITS", "U / Uпик", (37, 35, .13), 5, "ui", font),
            ("FREQUENCY", f"{frequency:.2f}".replace(".", ",") + " Гц", (-68, -36, .13), 7.45, "ui", mono),
            ("WINDOW", "5 периодов · 54,75 мс", (-16, -36.7, .13), 4.7, "ui", font),
            ("TIME", "t, мс", (60, -36.7, .13), 4.5, "ui", font),
            ):
        lettering("DEMO_SCOPE_" + name, value, size, pos, mat, 8, pivot, selected_font, (0, 0, 0), align="LEFT")


def stopwatch(root, bold, mono):
    stand = empty("STOPWATCH_CRADLE", (-125, -161, 0), 5, root)
    block("STOPWATCH_CRADLE_BASE", (63, 53, 5), (0, 4, 2.5), "scope_dark", 5, stand, 2)
    for side, sign in (("L", -1), ("R", 1)):
        brace = prism(f"STOPWATCH_CRADLE_{side}", [(-15, 5), (25, 5), (24, 31), (10, 31)],
                      5.5, (sign * 22, 0, 0), 5, stand, "scope_dark")
        for v in brace.data.vertices:
            v.co = (v.co.z, v.co.x, v.co.y)
        bevel(brace, .92)
    body = empty("DIGITAL_STOPWATCH", (0, -1.0, 30.5), 5, stand)
    body.rotation_euler.x = math.radians(58)
    body["reference"] = "Casio HS-3V"
    body["case_mm"] = [64, 62, 17]
    # Handheld shell in its local face plane; the cradle remains independent.
    case = rounded_panel("STOPWATCH_RESIN_CASE", 64, 60, 15.5, (0, -1, -.7),
                         "scope_dark", 5, body, 21)
    bevel(case, 2.15, 3)
    bezel = rounded_panel("STOPWATCH_TOP_INSERT", 54, 43, 1.45, (0, 1.8, 7.775),
                          "scope_case", 5, body, 13)
    bevel(bezel, .65)
    block("STOPWATCH_LCD_MASK", (48, 27, 1), (0, 4.5, 9.0), "bezel", 5, body, 1.9)
    block("STOPWATCH_LCD_SURFACE", (43, 19.4, .78), (0, 6, 9.89), "lcd", 5, body, 1.1)
    display = empty("STOPWATCH_DISPLAY", (0, 6, 10.28), 6, body)
    for i, (x, y, w, color) in enumerate(((-19, 24.8, 15.5, "pair_hot"), (19, 24.8, 15.5, "ch3"),
                                         (0, 25.8, 10, "scope_case")), 1):
        block(f"STOPWATCH_KEY_{i:02}", (w, 8.3, 5.9), (x, y, 6), color, 5, body, 2.0)
    lettering("STOPWATCH_FRONT_LEGEND", "СЕКУНДОМЕР", 5.2, (0, -15.0, 8.58),
              "legend", 5, body, bold, (0, 0, 0))
    lettering("DEMO_STOPWATCH_READING", "00:00.05", 10, (0, 0, .055),
              "digits", 8, display, mono, (0, 0, 0))
    sticker = cylinder("STOPWATCH_REAR_CELL_COVER", 9.6, 1.2, (0, -4, -8.87),
                       "scope_case", 5, body, 40)
    sticker["cell"] = "CR2025"


def preamp(root, bold, regular):
    base = empty("PREAMPLIFIER", PREAMP_ORIGIN, 5, root)
    base["reference"] = "Hammond 1590BB with proposed three-channel OPA1654 circuit"
    base["power"] = "isolated 9–12 V DC; circuit to be verified"
    casing = block("PREAMP_DIECAST_BODY", (119, 94, 27.8), (0, 0, 15.4),
                   "enclosure", 5, base, 3)
    apply(casing, casing.modifiers[0])
    cavity = block("TOOL_PREAMP_INTERIOR", (112.4, 87.6, 26), (0, 0, 18.0), None, 5, base, 2.2)
    apply(cavity, cavity.modifiers[0])
    boolean(casing, cavity)
    receivers = []
    for i, y in enumerate(PREAMP_INPUTS_Y, 1):
        sockets = []
        for direction, z, color in (("HI", 21.5, "pair_hot"), ("LO", 10.5, "scope_dark")):
            bore(casing, (59.5, y, z), 2.7, 10, 5, "X", 24)
            sockets.append(terminal(f"PREAMP_IN_{i:02}_{direction}", (59.5, y, z), 5, base, RIGHT, color))
        receivers.append(sockets)
        lettering(f"PREAMP_INPUT_LABEL_{i:02}", f"IN {i}", 3.5, (59.57, y, 27.3),
                  "mark", 5, base, regular, (math.pi / 2, 0, math.pi / 2))
    outputs = []
    for i, x in enumerate(PREAMP_OUTPUTS_X, 1):
        bore(casing, (x, -47, 17), 4.9, 11, 5, "Y", 24)
        outputs.append(terminal(f"PREAMP_OUT_{i:02}_BNC", (x, -47, 17), 5, base, FRONT,
                                CHANNEL_COLORS[i - 1], True))
        lettering(f"PREAMP_OUTPUT_LABEL_{i:02}", f"OUT {i}", 4.25, (x, -47.05, 25.8),
                  "mark", 5, base, regular)
    bore(casing, (32, 47, 17), 4.4, 10, 5, "Y")
    dc = empty("PREAMP_DC_IN", (32, 47, 17), 5, base)
    dc.rotation_euler = REAR
    axial_ring("PREAMP_DC_FLANGE", [(0, 4.5), (1.7, 4.5), (2.1, 4.1)],
               2.78, (0, 0, 0), "scope_dark", 5, dc, (0, 0, 0))
    cylinder("PREAMP_DC_PIN", 1.05, 2, (0, 0, 1), "steel", 5, dc, 24)
    block("PREAMP_LID", (119, 94, 4.8), (0, 0, 31.6), "enclosure", 5, base, 1.9)
    for x in (-52, 52):
        for y in (-39.5, 39.5):
            screw(f"PREAMP_LID_SCREW_{x+52:03}_{y+39.5:02.0f}", 2.8, (x, y, 34), 5, base)
            block(f"PREAMP_FOOT_{x+52:03}_{y+39.5:02.0f}", (12, 12, 1.5), (x, y, .75),
                  "rubber", 5, base, .56)
    lettering("PREAMP_LID_TITLE", "ПРЕДУСИЛИТЕЛЬ", 9.2, (0, 12, 34.065),
              "mark", 5, base, bold, (0, 0, 0))
    lettering("PREAMP_LID_SUBTITLE", "3 КАНАЛА   •   9–12 В DC", 5.4, (0, -3, 34.065),
              "mark", 5, base, regular, (0, 0, 0))
    for i, x in enumerate(PREAMP_OUTPUTS_X, 1):
        block(f"PREAMP_CH_TAG_{i:02}", (12, 3, .3), (x, -32, 34.15),
              CHANNEL_COLORS[i - 1], 5, base, .13)
    return base, receivers, outputs, dc


def harness(root, sensors, amp_ports, amp_out, scope_ports, scope_body, amp_power):
    bundle = empty("MEASUREMENT_CABLES", (0, 0, 0), CABLE_GROUP, root)
    sensor_pairs = []
    for i, ((pickup, jacks), receivers) in enumerate(zip(sensors, amp_ports), 1):
        tag = f"{i:02}"
        p = CHANNELS[i - 1] + 6.5
        upstream = [plugs(port, f"LEAD_{tag}_SENSOR_{k}", "pair_hot" if k == 1 else "cable")
                    for k, port in enumerate(jacks, 1)]
        downstream = [plugs(port, f"LEAD_{tag}_AMP_{k}", "pair_hot" if k == 1 else "cable")
                      for k, port in enumerate(receivers, 1)]
        sensor_pairs.append((p, upstream, downstream))
    links = [
        (plugs(a, f"COAX_{i:02}_AMP_PLUG", CHANNEL_COLORS[i-1], True),
         plugs(b, f"COAX_{i:02}_SCOPE_PLUG", CHANNEL_COLORS[i-1], True))
        for i, (a, b) in enumerate(zip(amp_out, scope_ports), 1)
    ]
    block("SCOPE_USB_C_POWER_PLUG", (9, 11, 4.2), (-101, 82.88, 31),
          "scope_dark", CABLE_GROUP, scope_body, 1.15)
    block("PREAMP_DC_POWER_PLUG", (6.5, 6.5, 12.5), (0, 0, 8),
          "scope_dark", CABLE_GROUP, amp_power, 1.6)
    bpy.context.view_layer.update()

    # The closest preamp input leaves the leftmost column in the clips. This
    # order lets the three tails fan out to the left without crossing.
    runs = (-211.2, -206.6, -202)
    for z in (80, 174, 264):
        clip = block(f"CABLE_POST_CLIP_{z:03}", (21, 12, 5.6), (-205.5, 153, z),
                     "carrier_dark", CABLE_GROUP, bundle)
        for x in runs:
            bore(clip, (x, 153, z), 1.72, 7.6, CABLE_GROUP, count=24)
        bevel(clip, .48)
    for i, (p, upstream, downstream) in enumerate(sensor_pairs, 1):
        tag = f"{i:02}"
        channel_y, channel_z = 99 + 4.8 * i, 322 - (i - 1) * 4.2
        split_a = (p, 63, 365 - i * 2)
        split_b = (-294, 187 + PREAMP_INPUTS_Y[i - 1], 17.3)
        for j, ((sensor_plug, end_a), (amp_plug, end_b)) in enumerate(zip(upstream, downstream), 1):
            pt_a, pt_b = point(sensor_plug, (0, 0, end_a)), point(amp_plug, (0, 0, end_b))
            ax, ay, az = pt_a
            side = -1 if j == 1 else 1
            cable(f"CABLE_PU_{tag}_TAIL_{j}", [pt_a, (ax, ay - 3.8, az - 3.5),
                  (p + side * 30, 16, 384.5 + (j - 1) * 4.0),
                  (p + side * 24, 43, 374.5 + (j - 1) * 3.0),
                  (split_a[0] + side * .85, split_a[1] - 4, split_a[2])],
                  .83, "pair_hot" if j == 1 else "cable", bundle, 8)
            cable(f"CABLE_PREAMP_{tag}_TAIL_{j}", [
                (split_b[0] - 2.5, split_b[1] + side * 1.1, split_b[2] - side * 1.55),
                (pt_b[0] + 2.8, pt_b[1] - 6, pt_b[2]), pt_b],
                .83, "pair_hot" if j == 1 else "cable", bundle, 4.5)
        run = runs[i - 1]
        fanout_y = split_b[1] + 9
        cable(f"CABLE_PU_{tag}_SHIELDED", [split_a, (p, 64.5, 315), (p, channel_y, channel_z),
              (run, channel_y, channel_z), (run, 129, channel_z), (run, 153, 287), (run, 153, 30),
              (run, fanout_y, 19.5), (-271, fanout_y, 18.5), split_b],
              1.6, "cable", bundle, 12)
        for side, (xx, yy, zz) in (("PH", split_a), ("PRE", split_b)):
            block(f"CABLE_PU_{tag}_FANOUT_{side}", (5.4, 9.0, 4.6), (xx, yy, zz),
                  CHANNEL_COLORS[i - 1], CABLE_GROUP, bundle, 1.3)

    for i, ((amp_plug, a), (scope_plug, b)) in enumerate(links, 1):
        ax, ay, az = point(amp_plug, (0, 0, a))
        bx, by, bz = point(scope_plug, (0, 0, b))
        side = -169 + 2.9 * (i - 1)
        h = 7 + 3.7 * (i - 1)
        front_run = -190 + 5.3 * (i - 1)
        lead = cable(f"CABLE_COAX_CH_{i:02}", [(ax, ay, az), (ax, 86, h + 7),
                (ax + 22, 74 - (i - 1) * 7.0, h), (side - 12, 74 - (i - 1) * 7.0, h),
                (side, 54 - (i - 1) * 7.0, h), (side, front_run + 13, h),
                (side - 12, front_run, h), (bx + 9, front_run, h), (bx, front_run, bz - 4),
                (bx, by, bz)], 1.45, "cable", bundle, 11)
        lead["path"] = f"PREAMP OUT {i} → OSC CH{i}"
        axial_ring(f"CABLE_COAX_CH_{i:02}_ID", [(0, 2.4), (2.5, 2.4)], 1.85,
                   (0, 0, b - 1.0), CHANNEL_COLORS[i - 1], CABLE_GROUP,
                   scope_plug, (0, 0, 0), 20)
    ux, uy, uz = point(scope_body, (-101, 88.38, 31))
    vx, vy, vz = point(amp_power, (0, 0, 14.25))
    cable("CABLE_SCOPE_USB_POWER", [(ux, uy, uz), (ux, -32, 14), (-383, -7, 3.7),
          (-382, 91, 3.7), (-310, 103, 3.7), (-305, 235, 3.7), (-310.45, 252, 4.0),
          (-310.45, 252, -38)], 1.34, "cable", bundle, 7)
    cable("CABLE_PREAMP_DC_POWER", [(vx, vy, vz), (vx, 262, 12), (-326, 267, 4.0),
          (-313.55, 252, 4.0), (-313.55, 252, -38)], 1.25, "cable", bundle, 6)


def configure_studio(scene):
    for obj in list(COLLECTIONS[8].objects):
        if obj.type == "CAMERA":
            bpy.data.objects.remove(obj, do_unlink=True)
    specs = [
        ("01_overview", (128, -1220, 706), (0, 34, 194), 42, (1720, 1130), False),
        ("02_front", (0, -1610, 238), (0, 0, 238), 962, (1600, 940), True),
        ("03_side", (1530, 2, 220), (0, 2, 220), 738, (1300, 970), True),
        ("04_rear_mounts", (-525, 980, 674), (-69, 79, 218), 1010, (1560, 1120), True),
        ("05_pickup_detail", (147, -192, 383), (12, 10, 411), 145, (1480, 1050), True),
        ("06_oscilloscope", (-585, -588, 274), (-295, -119, 84), 372, (1540, 1080), True),
        ("07_preamp_cables", (-164, -48, 278), (-368, 174, 32), 261, (1510, 1120), True),
        ("08_weight_hook", (163, -302, 191), (14, 1, 103), 142, (1450, 1030), True),
        ("09_measurement_system", (-688, -987, 685), (-15, 35, 201), 1070, (1660, 1160), True),
    ]
    views = [camera(*spec) for spec in specs]
    scene.camera = views[0]
    scene.render.resolution_x, scene.render.resolution_y = views[0]["review_pixels"]
    scene.render.filepath = "//renders/v3-1/01_overview.png"
    scene.cycles.max_bounces = 9
    scene.cycles.transmission_bounces = 7
    scene.cycles.glossy_bounces = 5
    area("LIGHT_PICKUP_SOFTBOX", (320, -275, 520), (68, 17, 403), 10, 330, (0.93, 1, 1))
    for screen in bpy.data.screens:
        for region in screen.areas:
            if region.type == "VIEW_3D":
                space = region.spaces.active
                space.region_3d.view_location = mm((0, 38, 198))
                space.region_3d.view_rotation = views[0].rotation_euler.to_quaternion()
                space.region_3d.view_distance = 1.28
                space.region_3d.view_perspective = "PERSP"


def build():
    if Path(bpy.data.filepath).resolve() != SOURCE:
        raise RuntimeError("Open the original laboratory_v3.blend before running this script.")
    scene = bpy.context.scene
    if scene.name != "STANDING_WAVE_LAB_V3":
        raise RuntimeError("Expected the original V3 scene.")
    initialize_collections(scene)
    set_materials()
    scene.name = SCENE_NAME
    scene["measurement_system"] = "B: 3 PH0731 analogues → preamp → CH1–CH3; separate stopwatch"
    regular = font_from_paths(os.environ.get("LAB_V3_FONT"), "C:/Windows/Fonts/arial.ttf",
                              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf")
    bold = font_from_paths(os.environ.get("LAB_V3_BOLD"), "C:/Windows/Fonts/arialbd.ttf",
                           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", regular.filepath)
    mono = font_from_paths(os.environ.get("LAB_V3_MONO"), "C:/Windows/Fonts/consola.ttf",
                           "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", regular.filepath)
    root = scene.objects["LAB_ROOT"]
    sensors = pickups(root)
    scope_body, scope_ports = scope(root, regular, bold, mono)
    stopwatch(root, bold, mono)
    _, amp_ports, amp_out, amp_power = preamp(root, bold, regular)
    harness(root, sensors, amp_ports, amp_out, scope_ports[:3], scope_body, amp_power)
    configure_studio(scene)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.update()
    # Lettering has been converted to geometry. Drop the temporary font data.
    bpy.data.batch_remove(ids={regular, bold, mono})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT), compress=True)
    print(f"Saved {OUTPUT.name} with {len(scene.objects)} objects")


if __name__ == "__main__":
    build()
