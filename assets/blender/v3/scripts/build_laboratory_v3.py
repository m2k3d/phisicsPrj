"""Build the review scene in Blender 5.3. All modeling dimensions are in mm."""

import math
import os
from pathlib import Path

import bpy
import bmesh
from mathutils import Quaternion, Vector


HERE = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("LAB_V3_OUTPUT_DIR", HERE.parent)).resolve()
OUTPUT = MODEL_DIR / "laboratory_v3.blend"
COLLECTION_NAMES = (
    "01_BENCH", "02_FRAME", "03_STRING_HARDWARE", "04_RACK",
    "05_INSTRUMENTS", "06_ATTACHMENTS", "07_WEIGHTS", "08_STUDIO",
)
CHANNELS = ((-110, 0.3), (0, 0.4), (110, 0.5))
RAIL_SCREWS = ((-180, 60), (-180, 90), (180, 60), (180, 90))
MASS_POSITIONS = ((100, 249), (200, 311), (300, 373))
SEAT_Z = 115
WEIGHT_DIA = 34
WEIGHT_TOP = -19
EYE_MAJOR = 6.3
EYE_MINOR = 1.05
HOOK_RADIUS = 1.25
HOOK_BEND = 5.3
RACK_FLOOR = 12
FRONT = (math.pi / 2, 0, 0)
COLLECTIONS = {}
M = {}
SCREWS = {}


def mm(values):
    return tuple(value / 1000 for value in values)


def place(obj, name, group, parent=None, position=None):
    obj.name = name
    collection = COLLECTIONS[group]
    if collection not in obj.users_collection:
        collection.objects.link(obj)
    for previous in list(obj.users_collection):
        if previous != collection:
            previous.objects.unlink(obj)
    obj.parent = parent
    if position is not None:
        obj.location = mm(position)
    return obj


def empty(name, position, group=6, parent=None):
    obj = bpy.data.objects.new(name, None)
    place(obj, name, group, parent, position)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.006
    return obj


def mesh(name, vertices, faces, position, group, parent=None, material=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata([mm(vertex) for vertex in vertices], [], faces)
    data.update()
    work = bmesh.new()
    work.from_mesh(data)
    bmesh.ops.recalc_face_normals(work, faces=list(work.faces))
    work.to_mesh(data)
    work.free()
    obj = place(bpy.data.objects.new(name, data), name, group, parent, position)
    if material:
        data.materials.append(M[material])
    return obj


def prism(name, points, depth, position, group, parent=None, material=None):
    """Extrude an XY outline symmetrically along local Z."""
    count = len(points)
    vertices = [(x, y, z) for z in (-depth / 2, depth / 2) for x, y in points]
    faces = [tuple(reversed(range(count))), tuple(range(count, 2 * count))]
    for i in range(count):
        j = (i + 1) % count
        faces.append((i, j, j + count, i + count))
    return mesh(name, vertices, faces, position, group, parent, material)


def apply(obj, modifier):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def bevel(obj, edge, steps=2, apply_now=False):
    if not edge:
        return obj
    mod = obj.modifiers.new("Machined edge", "BEVEL")
    mod.width = edge / 1000
    mod.segments = steps
    mod.angle_limit = math.radians(27)
    mod.harden_normals = True
    if apply_now:
        apply(obj, mod)
    return obj


def block(name, dims, position, material, group, parent=None, edge=0):
    x, y, z = (size / 2 for size in dims)
    outline = ((-x, -y), (x, -y), (x, y), (-x, y))
    return bevel(prism(name, outline, z * 2, position, group, parent, material), edge)


def circle(radius, count, start=0):
    return [(radius * math.cos(start + math.tau * i / count),
             radius * math.sin(start + math.tau * i / count)) for i in range(count)]


def turn(name, rings, position, material, group, parent=None, count=40, smooth=True, sharp_rings=False):
    """Turn closed stock from (height, radius) stations, starting at the bottom."""
    vertices = [(x, y, z) for z, r in rings for x, y in circle(r, count)]
    top = (len(rings) - 1) * count
    faces = [tuple(reversed(range(count))), tuple(range(top, top + count))]
    for base in range(0, top, count):
        for i in range(count):
            j = (i + 1) % count
            faces.append((base + i, base + j, base + j + count, base + i + count))
    obj = mesh(name, vertices, faces, position, group, parent, material)
    if smooth:
        for face in list(obj.data.polygons)[2:]:
            face.use_smooth = True
        for edge in obj.data.edges:
            a, b = edge.vertices
            if a // count == b // count and (sharp_rings or a // count in (0, len(rings) - 1)):
                edge.use_edge_sharp = True
    return obj


def cylinder(name, radius, length, position, material, group, parent=None, count=32):
    return turn(name, ((-length / 2, radius), (length / 2, radius)),
                position, material, group, parent, count, count > 8)


def boolean(obj, cutter, operation="DIFFERENCE"):
    mod = obj.modifiers.new("Machined volume", "BOOLEAN")
    mod.operation = operation
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.context.view_layer.update()
    apply(obj, mod)
    bpy.data.objects.remove(cutter, do_unlink=True)


def bore(obj, center, radius, length, group, axis="Z", count=32):
    cutter = cylinder("Tool_Bore", radius, length, center, None, group, obj.parent, count)
    if axis == "Y":
        cutter.rotation_euler = FRONT
    elif axis == "X":
        cutter.rotation_euler = (0, math.pi / 2, 0)
    boolean(obj, cutter)


def tube(name, points, radius, material, group, parent=None, steps=12, normal_axis=(0, 1, 0)):
    vectors = [Vector(p) for p in points]
    vertices = []
    for i, point in enumerate(vectors):
        tangent = (vectors[min(i + 1, len(vectors) - 1)] - vectors[max(i - 1, 0)]).normalized()
        normal = tangent.cross(Vector(normal_axis)).normalized()
        binormal = tangent.cross(normal)
        vertices.extend(point + x * normal + y * binormal for x, y in circle(radius, steps))
    end = (len(points) - 1) * steps
    faces = [tuple(reversed(range(steps))), tuple(range(end, end + steps))]
    for start in range(0, end, steps):
        for i in range(steps):
            j = (i + 1) % steps
            faces.append((start + i, start + j, start + j + steps, start + i + steps))
    obj = mesh(name, vertices, faces, (0, 0, 0), group, parent, material)
    for face in list(obj.data.polygons)[2:]:
        face.use_smooth = True
    return obj


def bezier(points, steps):
    a, b, c, d = map(Vector, points)
    return [tuple((1 - t)**3 * a + 3 * t * (1 - t)**2 * b
                  + 3 * t**2 * (1 - t) * c + t**3 * d)
            for t in (i / steps for i in range(steps + 1))]


def rgb(hex_value):
    srgb = [int(hex_value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v < 0.04045 else ((v + 0.055) / 1.055)**2.4 for v in srgb)


def material(key, title, color, roughness, metallic=0, emission=0, brushing=0):
    mat = bpy.data.materials.new(title)
    rgba = (*rgb(color), 1)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    link = mat.node_tree.links.new
    pbr = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    pbr.inputs["Base Color"].default_value = rgba
    pbr.inputs["Roughness"].default_value = roughness
    pbr.inputs["Metallic"].default_value = metallic
    pbr.inputs["Emission Color"].default_value = rgba
    pbr.inputs["Emission Strength"].default_value = emission
    if brushing:
        coords = nodes.new("ShaderNodeTexCoord")
        mapping = nodes.new("ShaderNodeVectorMath")
        mapping.operation = "MULTIPLY"
        mapping.inputs[1].default_value = (34, 6200, 6200)
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 1
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = brushing
        bump.inputs["Distance"].default_value = 0.00006
        link(coords.outputs["Object"], mapping.inputs[0])
        link(mapping.outputs["Vector"], noise.inputs["Vector"])
        link(noise.outputs["Fac"], bump.inputs["Height"])
        link(bump.outputs["Normal"], pbr.inputs["Normal"])
        anisotropy = pbr.inputs.get("Anisotropic")
        if anisotropy is not None:
            anisotropy.default_value = 0.23
    M[key] = mat


def materials():
    material("hpl", "Bench | warm grey HPL", "ACAEA8", 0.56)
    material("ply", "Bench | birch laminate", "B59A76", 0.63)
    material("ply_dark", "Bench | dark birch ply", "8F7557", 0.62)
    material("coat", "Bench | powder-coated steel", "313D46", 0.47, 0.22)
    material("support", "Frame | satin aluminum", "9DA8AE", 0.32, 0.8, brushing=0.12)
    material("plate", "Board | clear anodized aluminum", "A9B8C0", 0.38, 0.84, brushing=0.2)
    material("steel", "Hardware | polished stainless", "CCD3D8", 0.24, 0.82)
    material("insert", "Hardware | hardened steel insert", "657582", 0.37, 0.82)
    material("fastener", "Hardware | oxide steel", "485359", 0.33, 0.76)
    material("bracket", "Frame | satin structural steel", "87959E", 0.39, 0.76)
    material("brass", "Cap | brushed brass", "B99758", 0.32, 0.77)
    material("weight", "Weights | blued turned steel", "495866", 0.31, 0.87, brushing=0.12)
    material("rubber", "Feet | black elastomer", "20272C", 0.78)
    material("rack", "Rack | graphite polymer", "39454D", 0.58)
    material("case", "Meter | matte ABS", "2E3A44", 0.49)
    material("panel", "Meter | face plate", "202930", 0.5)
    material("lens", "Meter | smoked lens", "0C1F27", 0.42)
    material("ink", "Markings | warm white", "DFE4E5", 0.63)
    material("etch", "Markings | graphite", "303B42", 0.62)
    material("frequency", "Meter | lit frequency glyphs", "C2EBD9", 0.45, emission=0.6)
    material("time", "Meter | lit stopwatch glyphs", "D2E7F3", 0.45, emission=0.5)
    material("button", "Meter | subdued teal button", "568782", 0.49)
    material("amber", "Channel 02 | ochre identification", "A78146", 0.42, 0.16)
    material("wire", "Studio | steel wire", "DBE7EE", 0.24, 0.6, 0.25)
    material("wire_live", "Studio | selected steel wire", "E5DBC0", 0.26, 0.59, 0.33)
    material("floor", "Studio | blue slate", "343D46", 0.79)


def font_from_paths(*paths):
    for path in paths:
        if path and Path(path).is_file():
            return bpy.data.fonts.load(str(path), check_existing=True)
    raise RuntimeError("Set LAB_V3_FONT to a TTF with Cyrillic glyphs.")


def lettering(name, value, size, position, material, group, parent, font,
              rotation=FRONT, curve_radius=None, align="CENTER"):
    data = bpy.data.curves.new(name, "FONT")
    data.body = value
    data.font = font
    data.align_x = align
    data.align_y = "CENTER"
    data.size = size / 1000
    data.resolution_u = 3
    data.materials.append(M[material])
    obj = place(bpy.data.objects.new(name, data), name, group, parent, position)
    obj.rotation_euler = rotation
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    geometry = bpy.data.meshes.new_from_object(evaluated)
    if curve_radius is not None:
        radius = curve_radius / 1000
        for vertex in geometry.vertices:
            angle = vertex.co.x / radius
            vertex.co.x = radius * math.sin(angle)
            vertex.co.z = radius * (math.cos(angle) - 1)
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.curves.remove(data)
    obj = place(bpy.data.objects.new(name, geometry), name, group, parent, position)
    obj.rotation_euler = rotation
    return obj


def screw(name, size, position, group, parent, rotation=(0, 0, 0)):
    """The origin of each socket head is its underside, on the bearing surface."""
    if size not in SCREWS:
        r, h = size * 0.81, size * 0.53
        obj = turn(name, ((0, r - 0.25), (0.25, r), (h - 0.32, r), (h, r - 0.32)),
                   (0, 0, 0), "fastener", group, count=24)
        bore(obj, (0, 0, h), size * 0.4, h * 1.4, group, count=6)
        SCREWS[size] = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
    obj = place(bpy.data.objects.new(name, SCREWS[size]), name, group, parent, position)
    obj.rotation_euler = rotation
    return obj


def washer(name, position, outer, inner, depth, group, parent):
    obj = cylinder(name, outer, depth, position, "steel", group, parent)
    bore(obj, position, inner, depth + 2, group)
    return obj


def bench(root):
    base = empty("BENCH_STATIC", (0, 0, 0), 1, root)
    corners = ((-450, -280), (450, -280), (450, 280), (-450, 280))
    vertices = [(x, y, -14 + 28 * i / 9) for i in range(10) for x, y in corners]
    faces = [(3, 2, 1, 0), (36, 37, 38, 39)]
    for ring in range(9):
        for side in range(4):
            a = 4 * ring + side
            b = 4 * ring + (side + 1) % 4
            faces.append((a, b, b + 4, a + 4))
    core = mesh("BENCH_BIRCH_CORE", vertices, faces, (0, 30, -15), 1, base, "ply")
    core.data.materials.append(M["ply_dark"])
    for face in list(core.data.polygons)[2:]:
        face.material_index = ((face.index - 2) // 4) % 2
    layers = [core, block("BENCH_HPL_TOP", (900, 560, 1), (0, 30, -0.5), "hpl", 1, base),
              block("BENCH_HPL_BOTTOM", (900, 560, 1), (0, 30, -29.5), "hpl", 1, base)]
    for obj in layers:
        for x in (-180, 180):
            for dx in (-30, 30):
                for y in (120, 190):
                    bore(obj, (x + dx, y, obj.location.z * 1000), 3.25, 32, 1, count=20)
        bore(obj, (-312, 252, obj.location.z * 1000), 9.1, 32, 1)
    grommet = cylinder("BENCH_CABLE_GROMMET", 11, 2, (-312, 252, 1), "rubber", 1, base)
    bore(grommet, (-312, 252, 1), 4.1, 5, 1)
    for x, side in ((-375, "L"), (375, "R")):
        for y, end in ((-175, "FRONT"), (235, "REAR")):
            block(f"BENCH_LEG_{side}_{end}", (42, 42, 700), (x, y, -380), "coat", 1, base, 1.3)
            block(f"BENCH_FOOT_{side}_{end}", (44, 44, 10), (x, y, -735), "rubber", 1, base, 1.8)
        block(f"BENCH_SIDE_APRON_{side}", (38, 368, 45), (x, 30, -52.5), "coat", 1, base, 0.7)
        block(f"BENCH_SIDE_STRETCHER_{side}", (30, 368, 29), (x, 30, -525), "coat", 1, base, 0.9)
    for y, end in ((-175, "FRONT"), (235, "REAR")):
        block(f"BENCH_{end}_APRON", (708, 37, 45), (0, y, -52.5), "coat", 1, base, 0.7)
    block("BENCH_REAR_STRETCHER", (708, 29, 30), (0, 235, -525), "coat", 1, base, 0.9)
    block("BENCH_LOAD_CROSS_RAIL", (712, 40, 38), (0, 155, -55), "coat", 1, base, 0.6)
    for i, x in enumerate((-180, 180), 1):
        tag = f"{i:02}"
        backing = block(f"BENCH_BACKING_PLATE_{tag}", (90, 125, 6), (x, 155, -33),
                        "fastener", 1, base)
        for dx in (-30, 30):
            for y in (120, 190):
                bore(backing, (x + dx, y, -33), 3.25, 10, 1, count=20)
                key = f"{tag}_{'L' if dx < 0 else 'R'}_{'F' if y < 155 else 'B'}"
                cylinder(f"FRAME_THROUGH_BOLT_{key}", 3, 51.7, (x + dx, y, -18.25),
                         "steel", 1, base, count=20)
                washer(f"BENCH_UNDER_WASHER_{key}", (x + dx, y, -36.8), 6.2, 3.25, 1.6, 1, base)
                nut = cylinder(f"BENCH_LOCK_NUT_{key}", 5.8, 5, (x + dx, y, -40.1),
                               "fastener", 1, base, count=6)
                bore(nut, (x + dx, y, -40.1), 3, 7, 1, count=20)


def extrusion(name, length, position, parent, orientation=(0, 0, 0)):
    edge = [(-15, -15), (-3.2, -15), (-3.2, -12), (-5.8, -12),
            (-5.8, -7.8), (5.8, -7.8), (5.8, -12), (3.2, -12), (3.2, -15)]
    outline = []
    for i in range(4):
        outline.extend(edge)
        edge = [(-y, x) for x, y in edge]
    obj = prism(name, outline, length, position, 2, parent, "support")
    obj.rotation_euler = orientation
    return bevel(obj, 0.38)


def frame(root):
    base = empty("FRAME_STATIC", (0, 0, 0), 2, root)
    extrusion("FRAME_REAR_TIE", 330, (0, 155, 447), base, (math.pi / 2, 0, math.pi / 2))
    for i, x in enumerate((-180, 180), 1):
        tag = f"{i:02}"
        foot = block(f"FRAME_BASE_PLATE_{tag}", (90, 125, 6), (x, 155, 3), "bracket", 2, base)
        for dx in (-30, 30):
            for y in (120, 190):
                bore(foot, (x + dx, y, 3), 3.25, 10, 2, count=20)
                key = f"{tag}_{'L' if dx < 0 else 'R'}_{'F' if y < 155 else 'B'}"
                washer(f"FRAME_WASHER_{key}", (x + dx, y, 6.8), 6.2, 3.25, 1.6, 2, base)
                screw(f"FRAME_ANCHOR_{key}", 6, (x + dx, y, 7.6), 2, base)
        extrusion(f"FRAME_POST_{tag}", 462, (x, 155, 237), base)
        block(f"FRAME_POST_CAP_{tag}", (30, 30, 3), (x, 155, 469.5), "rubber", 2, base, 0.65)
        for handed in (-1, 1):
            side = "L" if handed < 0 else "R"
            mount = x + handed * 15
            key = f"{tag}_{side}"
            flange = block(f"FRAME_FOOT_UPRIGHT_{key}", (4, 24, 51), (mount + handed * 2, 155, 31.5),
                           "bracket", 2, base)
            bore(flange, (mount + handed * 2, 155, 36), 2.2, 6, 2, "X", 20)
            bevel(flange, 0.45)
            base_flange = block(f"FRAME_FOOT_FLANGE_{key}", (25, 24, 4), (mount + handed * 16.5, 155, 8),
                                "bracket", 2, base)
            bolt_x = mount + handed * 22
            bore(base_flange, (bolt_x, 155, 8), 2.2, 6, 2, count=20)
            bore(foot, (bolt_x, 155, 5.5), 2, 7, 2, count=20)
            bevel(base_flange, 0.45)
            coords = [(0, 0), (handed * 22, 0), (0, 36)]
            brace = prism(f"FRAME_FOOT_BRACE_{key}", coords, 4,
                          (mount + handed * 4, 163, 10), 2, base, "bracket")
            brace.rotation_euler = FRONT
            bevel(brace, 0.4)
            screw(f"FRAME_FOOT_BASE_BOLT_{key}", 4, (bolt_x, 155, 10), 2, base)
            cylinder(f"FRAME_FOOT_BASE_STUD_{key}", 1.95, 7.5, (bolt_x, 155, 6.25),
                     "steel", 2, base, count=20)
            screw(f"FRAME_FOOT_POST_BOLT_{key}", 4, (mount + handed * 4, 155, 36),
                  2, base, (0, handed * math.pi / 2, 0))
            nut = block(f"FRAME_FOOT_T_NUT_{key}", (2.8, 10, 9), (mount - handed * 4.5, 155, 36),
                        "steel", 2, base)
            bore(nut, (mount - handed * 4.5, 155, 36), 2, 5, 2, "X", 20)
            stud = cylinder(f"FRAME_FOOT_POST_STUD_{key}", 1.95, 10, (mount - handed, 155, 36),
                            "steel", 2, base, count=20)
            stud.rotation_euler = (0, math.pi / 2, 0)
        bevel(foot, 0.6)
        backplate = block(f"FRAME_CONSOLE_MOUNT_{tag}", (31, 5, 86), (x, 137.5, 392),
                          "bracket", 2, base)
        # Bearings on the front T-slot. The slot nuts sit in the channel behind the mount.
        for z in (362, 399):
            bore(backplate, (x, 137.5, z), 2.6, 9, 2, axis="Y", count=20)
            nut = block(f"FRAME_T_NUT_{tag}_{z}", (10, 3, 9), (x, 144.5, z), "steel", 2, base)
            bore(nut, (x, 144.5, z), 2.5, 5, 2, "Y", 20)
            stud = cylinder(f"FRAME_CONSOLE_STUD_{tag}_{z}", 2.4, 9.5,
                            (x, 139.75, z), "fastener", 2, base, count=20)
            stud.rotation_euler = FRONT
            screw(f"FRAME_CONSOLE_BOLT_{tag}_{z}", 5, (x, 135, z), 2, base, FRONT)
        bevel(backplate, 0.55)
        arm = block(f"FRAME_CONSOLE_ARM_{tag}", (32, 105, 9), (x, 82.5, 430.5),
                    "bracket", 2, base)
        for y in (60, 90):
            bore(arm, (x, y, 431), 2.05, 9, 2, count=24)
        bevel(arm, 0.6)
        gusset_outline = [(135, 359), (135, 426), (39, 426), (45, 421), (129, 361)]
        for j, dx in enumerate((-10, 10), 1):
            gusset = prism(f"FRAME_GUSSET_{tag}_{j}", gusset_outline, 4,
                           (x + dx, 0, 0), 2, base, "fastener")
            for v in gusset.data.vertices:
                v.co = (v.co.z, v.co.x, v.co.y)
            bevel(gusset, 0.45)
        inward = -1 if x > 0 else 1
        x_mount = x + 15 * inward
        angle = prism(f"FRAME_TIE_ANGLE_{tag}", [(0, 0), (inward * 32, 0),
                      (inward * 32, -4), (inward * 4, -4), (inward * 4, -26), (0, -26)],
                      15, (x_mount, 155, 432), 2, base, "fastener")
        for v in angle.data.vertices:
            v.co = (v.co.x, -v.co.z, v.co.y)
        cross_x = x_mount + inward * 22
        post_x = x_mount + inward * 4
        bore(angle, (cross_x, 155, 430), 2.2, 6, 2, count=20)
        bore(angle, (x_mount + inward * 2, 155, 416), 2.2, 6, 2, "X", 20)
        bevel(angle, 0.4)
        screw(f"FRAME_TIE_BOLT_{tag}", 4, (cross_x, 155, 428), 2, base, (math.pi, 0, 0))
        screw(f"FRAME_TIE_POST_BOLT_{tag}", 4, (post_x, 155, 416),
              2, base, (0, inward * math.pi / 2, 0))
        nut_cross = block(f"FRAME_TIE_T_NUT_{tag}", (9, 10, 2.8), (cross_x, 155, 436.5),
                          "steel", 2, base)
        bore(nut_cross, (cross_x, 155, 436.5), 2, 5, 2, count=20)
        nut_post = block(f"FRAME_TIE_POST_T_NUT_{tag}", (2.8, 10, 9), (x_mount - inward * 4.5, 155, 416),
                         "steel", 2, base)
        bore(nut_post, (x_mount - inward * 4.5, 155, 416), 2, 5, 2, "X", 20)
        cylinder(f"FRAME_TIE_STUD_{tag}", 1.95, 10, (cross_x, 155, 433), "steel", 2, base, count=20)
        stud = cylinder(f"FRAME_TIE_POST_STUD_{tag}", 1.95, 10, (x_mount - inward, 155, 416),
                        "steel", 2, base, count=20)
        stud.rotation_euler = (0, math.pi / 2, 0)


def slot_cutter(x, parent, group):
    # 3.2 mm finished slot with a milled nose and lead-in on the front edge.
    r = 1.6
    shape = [(-3.2, -38), (3.2, -38), (3.2, -35), (r, -33)]
    shape += [(r * math.cos(math.pi * i / 16), r * math.sin(math.pi * i / 16))
              for i in range(17)]
    shape += [(-r, -33), (-3.2, -35)]
    return prism("Tool_Slot", shape, 20, (x, 0, 8), group, parent)


def board_and_channels(root, font):
    frame_root = bpy.data.objects["FRAME_STATIC"]
    board = block("TOP_BOARD", (420, 140, 16), (0, 35, 443), "plate", 2, frame_root)
    # Use a mounting datum so all cutters share the underside of the board as local zero.
    board.location = mm((0, 0, 435))
    for vertex in board.data.vertices:
        vertex.co += Vector(mm((0, 35, 8)))
    for x, y in RAIL_SCREWS:
        bore(board, (x, y, 443), 2.2, 19, 2, count=24)
        head_tool = turn("Tool_Board_Countersink", ((11.8, 2.2), (15.8, 4.5), (17, 4.5)),
                         (x, y, 435), None, 2, frame_root, 32)
        boolean(board, head_tool)
        screw_obj = turn(f"BOARD_FLUSH_SCREW_{x + 180:03}_{y}", ((-20, 2), (-4.2, 2),
                         (-4.2, 2.2), (-0.3, 4.25), (0, 4.25)),
                         (x, y, 450.8), "fastener", 2, frame_root, 32)
        bore(screw_obj, (x, y, 450.8), 1.45, 2.15, 2, count=6)
    for i, (x, _) in enumerate(CHANNELS, 1):
        boolean(board, slot_cutter(x, board, 2))
        pocket = cylinder("Tool_Insert_Pocket", 8, 3.2, (x, 0, 451), None, 2, frame_root)
        boolean(board, pocket)
    bevel(board, 0.18, 3)

    for i, (x, diameter) in enumerate(CHANNELS, 1):
        tag = f"{i:02}"
        active = i == 2
        top = empty(f"STR_{tag}_TOP", (x, 0, 435), parent=root)
        mid = empty(f"STR_{tag}_MID", (x, 0, 285), parent=root)
        mid["pluck_limit_mm"] = 23
        end = empty(f"STR_{tag}_END", (x, 0, 135), parent=root)
        empty(f"STR_{tag}_HOOK_SEAT", (x, 0, SEAT_Z), parent=root)
        insert = cylinder(f"SLOT_INSERT_{tag}", 7.96, 1.6, (x, 0, 450.2), "insert", 3, root)
        slot = slot_cutter(x, board, 3)
        boolean(insert, slot)
        bevel(insert, 0.11)
        cap = empty(f"CAP_{tag}", (0, 0, 0), 3, top)
        cap["channel_diameter_mm"] = diameter
        head = turn(f"CAP_HEAD_{tag}", ((16, 5.64), (16.35, 6), (20.55, 6), (21, 5.55)),
                    (0, 0, 0), "brass" if active else "steel", 3, cap)
        bore(head, (0, 0, 16.6), 1.33, 1.5, 3)
        shank = turn(f"CAP_SHANK_{tag}", ((0, 1.14), (0.25, 1.3), (17.15, 1.3)),
                     (0, 0, 0), "steel", 3, cap, 32)
        bore(shank, (0, 0, 0), diameter / 2, 2.6, 3, count=16)
        label = f"{diameter:.2f}".replace(".", ",") + " мм"
        label_x = x - 28
        lettering(f"BOARD_DIAMETER_{tag}", label, 8.3, (label_x, -35.09, 443), "etch",
                  2, frame_root, font)
        block(f"BOARD_INDEX_{tag}", (4, 0.25, 4.5), (label_x - 19, -35.125, 443),
              "amber" if active else "etch", 2, frame_root, 0.08)
        hook = empty(f"HOOK_{tag}", (0, 0, 0), 3, end)
        sleeve = turn(f"HOOK_CRIMP_{tag}", ((-7, 1.66), (-6.65, 2.05), (-0.4, 2.05), (0, 1.7)),
                      (0, 0, 0), "steel", 3, hook, 28)
        bore(sleeve, (0, 0, -6.6), HOOK_RADIUS + 0.04, 4, 3, count=24)
        bore(sleeve, (0, 0, 0), diameter / 2, 2.9, 3, count=16)
        center_z = SEAT_Z - 135 - HOOK_RADIUS + HOOK_BEND
        entry = [(0, 0, -4.62)] + bezier([(0, 0, -7.8), (0, 0, -10), (-HOOK_BEND, 0, -9.1),
                        (-HOOK_BEND, 0, center_z)], 16)
        angles = [math.radians(180 + 90 * j / 22) for j in range(1, 23)]
        angles += [math.radians(270 + 114 * j / 26) for j in range(1, 27)]
        arc = [(HOOK_BEND * math.cos(a), 0, center_z + HOOK_BEND * math.sin(a)) for a in angles]
        wire_hook = tube(f"HOOK_WIRE_{tag}", entry + arc, HOOK_RADIUS, "steel", 3, hook, steps=16)
        wire_hook["seat_surface_z_mm"] = SEAT_Z
        demo = cylinder(f"DEMO_WIRE_{tag}", diameter / 2, 300, (x, 0, 285),
                        "wire_live" if active else "wire", 8, root, count=16)
        demo["exclude_from_glb"] = True


def rack(root, font):
    base = empty("WEIGHT_RACK", (311, -30, 0), 4, root)
    block("RACK_ANTI_SLIP_PAD", (192, 113, 3), (0, 0, 1.5), "rubber", 4, base, 1.4)
    shell = block("RACK_MOLDED_BODY", (195, 116, 17), (0, 0, 11.5), "rack", 4, base, 2.6)
    apply(shell, shell.modifiers[0])
    cutter = block("Tool_Tray_Interior", (185, 106, 12), (0, 0, 23.5), None, 4, base, 2.3)
    apply(cutter, cutter.modifiers[0])
    boolean(shell, cutter)
    for mass, x in MASS_POSITIONS:
        dx = x - 311
        tool = turn("Tool_Weight_Well", ((12, 19.6), (12.5, 20), (16.8, 20),
                                        (17.5, 21), (24, 21)), (dx, 0, 0), None, 4, base, 48)
        boolean(shell, tool)
        lettering(f"RACK_LABEL_{mass}", f"{mass} г", 7.2, (dx, -58.04, 11.7), "ink", 4, base, font)
    bevel(shell, 0.32)


def solid_volume_mm3(obj):
    work = bmesh.new()
    work.from_mesh(obj.data)
    volume = work.calc_volume() * 1e9
    work.free()
    return volume


def weight_eye(parent, mass):
    center_z = -(EYE_MAJOR - EYE_MINOR)
    major_steps, minor_steps = 48, 32
    stations = []
    for y, z in circle(EYE_MAJOR, major_steps):
        stations.extend((x, y * (1 + radial / EYE_MAJOR),
                         center_z + z * (1 + radial / EYE_MAJOR))
                        for radial, x in circle(EYE_MINOR, minor_steps))
    faces = []
    count = len(stations)
    for major in range(major_steps):
        for minor in range(minor_steps):
            a = major * minor_steps + minor
            b = major * minor_steps + (minor + 1) % minor_steps
            faces.append((a, (a + minor_steps) % count, (b + minor_steps) % count, b))
    eye = mesh(f"WEIGHT_EYE_{mass}", stations, faces, (0, 0, 0), 7, parent, "steel")
    arbor = turn("Tool_Eye_Arbor", ((-23, 1.95), (-19, 1.95), (-19, 2.65), (-17.6, 2.65),
                                     (-16.5, 2), (-11.5, 2)), (0, 0, 0), None, 7, parent, 32)
    boolean(eye, arbor, "UNION")
    for face in eye.data.polygons:
        face.use_smooth = True
    return eye


def weight_blank(name, parent, height):
    r, z = WEIGHT_DIA / 2, WEIGHT_TOP
    stations = ((z - height, r - 0.9), (z - height + 0.9, r),
                (z - min(3.1, height / 3), r), (z - 2.1, r - 0.32),
                (z - 1.35, r - 0.32), (z - 0.85, r), (z, r - 0.85))
    body = turn(name, stations, (0, 0, 0), "weight", 7, parent, 64, sharp_rings=True)
    bore(body, (0, 0, z + 0.45), 2.02, 9.2, 7)
    return body


def weights(root, font):
    for mass, x in MASS_POSITIONS:
        weight = empty(f"WEIGHT_{mass}", (0, 0, 0), 7)
        eye = weight_eye(weight, mass)
        eye_volume = solid_volume_mm3(eye)
        density = 0.0078
        # Find the height using the faceted stock, bevels, relief and blind bore.
        height = (mass / density - eye_volume) / (math.pi * (WEIGHT_DIA / 2)**2)
        for iteration in range(3):
            body = weight_blank(f"WEIGHT_BODY_{mass}", weight, height)
            volume = solid_volume_mm3(body) + eye_volume
            if iteration < 2:
                height += (mass / density - volume) / (math.pi * (WEIGHT_DIA / 2)**2)
                old_geometry = body.data
                bpy.data.objects.remove(body, do_unlink=True)
                bpy.data.meshes.remove(old_geometry)
        lettering(f"WEIGHT_MARK_{mass}", f"{mass} г", 6.1, (0, -17.035, WEIGHT_TOP - height / 2),
                  "ink", 7, weight, font, curve_radius=17.035)
        contact_height = height - WEIGHT_TOP
        weight["nominal_mass_g"] = mass
        weight["solid_mass_estimate_g"] = round(volume * density, 3)
        weight["contact_to_base_mm"] = round(contact_height, 4)
        weight["hook_contact"] = "Local origin at upper inside eye surface"
        slot = empty(f"RACK_SLOT_{mass}", (x, -30, RACK_FLOOR + contact_height), parent=root)
        weight.location = mm((0, 0, SEAT_Z)) if mass == 300 else slot.location


def instrument(root, font, mono, bold):
    base = empty("INSTRUMENT_BODY", (-310, 20, 0), 5, root)
    housing = block("INSTRUMENT_ABS_SHELL", (160, 85, 111), (0, 0, 59.5), "case", 5, base, 4)
    apply(housing, housing.modifiers[0])
    inset = block("Tool_Face_Plate", (150, 4, 101), (0, -42.5, 59.5), None, 5, base, 1.5)
    apply(inset, inset.modifiers[0])
    boolean(housing, inset)
    for x in (-57, 57):
        for y in (-27, 27):
            block(f"INSTRUMENT_FOOT_{x + 57:03}_{y + 27:02}", (19, 16, 4),
                  (x, y, 2), "rubber", 5, base, 1.2)
    panel = block("INSTRUMENT_FACE_PLATE", (148, 2, 99), (0, -41.5, 59.5), "panel", 5, base, 0.75)
    apply(panel, panel.modifiers[0])
    for key, z, title, value, suffix, color in (
        ("METER", 83, "ЧАСТОТОМЕР", "91,33", "Гц", "frequency"),
        ("STOPWATCH", 43, "СЕКУНДОМЕР", "0,055", "с", "time"),
    ):
        cutter = block("Tool_Display_Window", (110, 5, 24), (0, -42, z), None, 5, base, 0.8)
        apply(cutter, cutter.modifiers[0])
        boolean(panel, cutter)
        block(f"{key}_LENS", (109.6, 2.5, 23.6), (0, -41.75, z), "lens", 5, base, 0.66)
        display = empty(f"{key}_DISPLAY", (-310, -23, z), parent=root)
        display.rotation_euler = FRONT
        display["window_mm"] = [109.6, 23.6]
        lettering(f"{key}_LEGEND", title, 6.9, (-54, -42.53, z + 17.2), "ink", 5, base, bold, align="LEFT")
        lettering(f"DEMO_{key}_DIGITS", value, 22.2, (-11, -43.06, z), color, 8, base, mono)
        lettering(f"DEMO_{key}_UNIT", suffix, 8.6, (36, -43.06, z - 2.2), color, 8, base, font)
    for i, (x, title) in enumerate(((-28, "ПУСК"), (37, "СБРОС")), 1):
        opening = block("Tool_Button_Well", (25, 4, 11), (x - 13, -42.6, 19.5), None, 5, base, 1.6)
        apply(opening, opening.modifiers[0])
        boolean(panel, opening)
        block(f"INSTRUMENT_BUTTON_{i:02}", (24, 4.5, 10), (x - 13, -43.25, 19.5),
              "button" if i == 1 else "rack", 5, base, 1.5)
        lettering(f"INSTRUMENT_BUTTON_LABEL_{i:02}", title, 5.9, (x + 3, -42.55, 19.5),
                  "ink", 5, base, font, align="LEFT")
    for i, (x, z) in enumerate(((-65, 102), (65, 102), (-65, 17), (65, 17)), 1):
        screw(f"INSTRUMENT_FACE_SCREW_{i:02}", 2.5, (x, -42.5, z), 5, base, FRONT)
    for i in range(5):
        vent = block(f"Tool_Vent_{i}", (4, 25, 1.7), (79.3, 10, 35 + i * 4.3), None, 5, base)
        boolean(housing, vent)
    outlet = turn("INSTRUMENT_STRAIN_RELIEF",
                  ((0, 4.8), (2, 4.8), (2, 3.75), (7, 3.4), (11, 2.1)),
                  (-2, 42.5, 31), "rubber", 5, base)
    outlet.rotation_euler = (-math.pi / 2, 0, 0)
    span = bezier([(-2, 53.5, 31), (-2, 82, 31), (-2, 82, 4.0), (-2, 112, 3.1)], 24)
    bend = bezier([(-2, 112, 3.1), (-2, 148, 2.4), (-2, 193, 2.4), (-2, 211, 2.4)], 18)
    drop = bezier([(-2, 211, 2.4), (-2, 231.8, 2.4), (-2, 232, 8), (-2, 232, -42)], 26)
    tube("INSTRUMENT_SIGNAL_CABLE", span + bend[1:] + drop[1:], 2.1, "rubber", 5, base,
         normal_axis=(1, 0, 0))


def aim(obj, position, target, top=False):
    obj.location = mm(position)
    direction = Vector(mm(target)) - obj.location
    obj.rotation_euler = (Quaternion((0, 0, 1), 0) if top else
                          direction.to_track_quat("-Z", "Y")).to_euler()


def camera(name, position, target, size, pixels, ortho=True, top=False):
    data = bpy.data.cameras.new(name)
    obj = place(bpy.data.objects.new(name, data), name, 8)
    aim(obj, position, target, top)
    data.clip_start = 0.005
    data.clip_end = 18
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = size / 1000
    else:
        data.lens = size
    obj["review_pixels"] = list(pixels)
    return obj


def area(name, position, target, watts, size, color, width=None):
    data = bpy.data.lights.new(name, "AREA")
    obj = place(bpy.data.objects.new(name, data), name, 8)
    aim(obj, position, target)
    data.energy = watts
    data.color = color
    if width:
        data.shape = "RECTANGLE"
        data.size_y = width / 1000
    else:
        data.shape = "DISK"
    data.size = size / 1000
    return obj


def studio(scene):
    radius = 1250
    sweep = [(-7000, -740)]
    for y, z in circle(radius, 96)[72:]:
        sweep.append((950 + y, radius - 740 + z))
    sweep += [(950 + radius, radius - 740), (950 + radius, 4000)]
    vertices = [(x, y, z) for y, z in sweep for x in (-7000, 7000)]
    faces = [(i, i + 1, i + 3, i + 2) for i in range(0, len(vertices) - 2, 2)]
    backdrop = mesh("STUDIO_CYCLORAMA", vertices, faces, (0, 0, 0), 8, material="floor")
    for face in backdrop.data.polygons:
        face.use_smooth = True
    area("LIGHT_KEY", (-750, -950, 1420), (0, 0, 50), 145, 1250, (0.83, 0.91, 1))
    area("LIGHT_FILL", (950, -220, 660), (0, 10, 220), 72, 1150, (1, 0.89, 0.77))
    area("LIGHT_RIM", (160, 575, 1030), (0, 0, 250), 135, 920, (0.77, 0.88, 1), 360)
    area("LIGHT_FRONT_STRIP", (-240, -780, 310), (0, 0, 258), 12, 860, (0.9, 0.95, 1), 85)
    area("LIGHT_BACK_WASH", (-500, 990, 450), (220, 1930, 180), 20, 1020, (0.67, 0.78, 1))
    world = bpy.data.worlds.new("Studio | neutral fill")
    world.use_nodes = True
    background = next(node for node in world.node_tree.nodes if node.type == "BACKGROUND")
    background.inputs["Color"].default_value = (*rgb("838D9A"), 1)
    background.inputs["Strength"].default_value = 0.42
    scene.world = world
    views = [
        camera("01_overview", (166, -1250, 650), (0, 40, 198), 43, (1720, 1130), False),
        camera("02_front", (0, -1600, 246), (0, 0, 246), 960, (1600, 940)),
        camera("03_side", (1520, 0, 207), (0, 0, 207), 750, (1220, 940)),
        camera("04_top", (0, 30, 1700), (0, 30, 0), 985, (1500, 1040), top=True),
        camera("05_upper_mounts", (255, -430, 696), (0, 49, 429), 485, (1600, 910)),
        camera("06_hooks_weights", (250, -540, 255), (121, -8, 89), 635, (1700, 830)),
        camera("07_instruments", (-483, -374, 206), (-307, 10, 60), 232, (1400, 1040)),
        camera("08_rear_structure", (-625, 983, 652), (-13, 126, 219), 810, (1450, 1110)),
        camera("09_full_bench", (458, -1775, 973), (0, 51, -145), 48, (1350, 1440), False),
    ]
    scene.camera = views[0]
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.render.resolution_x, scene.render.resolution_y = views[0]["review_pixels"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = -0.75
    return views


def configure_view(scene):
    # Open on the apparatus above the bench, with visible geometry and no studio guides.
    bpy.data.objects["STUDIO_CYCLORAMA"].hide_set(True)
    for screen in bpy.data.screens:
        for area_type in screen.areas:
            if area_type.type != "VIEW_3D":
                continue
            space = area_type.spaces.active
            space.overlay.show_overlays = False
            space.shading.color_type = "MATERIAL"
            view = space.region_3d
            view.view_location = mm((0, 38, 195))
            view.view_rotation = bpy.data.objects["01_overview"].rotation_euler.to_quaternion()
            view.view_distance = 1.25
            view.view_perspective = "PERSP"
            space.clip_start = 0.004
    scene.render.filepath = "//renders/v3/01_overview.png"


def build():
    if bpy.data.filepath and Path(bpy.data.filepath).resolve() != OUTPUT:
        raise RuntimeError("Start a new Blender session or open laboratory_v3.blend.")
    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for data in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.curves):
        for unused in [block for block in data if not block.users]:
            data.remove(unused)
    COLLECTIONS.clear()
    SCREWS.clear()
    for i, name in enumerate(COLLECTION_NAMES, 1):
        collection = bpy.data.collections.new(name)
        scene.collection.children.link(collection)
        COLLECTIONS[i] = collection
    scene.name = "STANDING_WAVE_LAB_V3"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 1.0
    scene["review_pose"] = "300 g on CH 02, 100 and 200 g in rack"
    scene["axis_convention"] = "+X right, +Y rear, +Z up; 1 Blender unit = 1 m"
    regular = font_from_paths(os.environ.get("LAB_V3_FONT"), "C:/Windows/Fonts/arial.ttf",
                              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf")
    bold = font_from_paths(os.environ.get("LAB_V3_BOLD"), "C:/Windows/Fonts/arialbd.ttf",
                           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", regular.filepath)
    mono = font_from_paths(os.environ.get("LAB_V3_MONO"), "C:/Windows/Fonts/consola.ttf",
                           "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", regular.filepath)
    materials()
    root = empty("LAB_ROOT", (0, 0, 0))
    bench(root)
    frame(root)
    board_and_channels(root, regular)
    rack(root, bold)
    weights(root, bold)
    instrument(root, regular, mono, bold)
    studio(scene)
    configure_view(scene)
    bpy.context.view_layer.update()
    # Lettering has been converted to geometry. Drop the temporary font data.
    bpy.data.batch_remove(ids={regular, bold, mono})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT), compress=True)
    print(f"Saved {OUTPUT} with {len(scene.objects)} objects")


if __name__ == "__main__":
    build()
