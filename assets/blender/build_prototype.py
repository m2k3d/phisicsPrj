from math import cos, pi, sin
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def material(name, rgb, metallic=0, roughness=0.4):
    surface = bpy.data.materials.new(name)
    surface.use_nodes = True
    shader = surface.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = (*rgb, 1)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    return surface


def finish(name, surface, bevel=0):
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(surface)
    if bevel:
        modifier = obj.modifiers.new("Machined edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        obj.modifiers.new("Face normals", "WEIGHTED_NORMAL")
    return obj


def box(name, location, dimensions, surface, bevel=0.001):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    bpy.context.object.scale = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(name, surface, bevel)


def cylinder(name, location, radius, depth, surface, bevel=0):
    bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=radius, depth=depth, location=location)
    obj = finish(name, surface, bevel)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def hook(name, x, y, bottom, surface):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.0012
    points = curve.splines.new("POLY")
    angles = [pi - step * 1.55 * pi / 24 for step in range(25)]
    coordinates = [(x, y, bottom), (x, y, bottom - 0.004)]
    coordinates.extend((x + 0.0038 + 0.0038 * cos(a), y, bottom - 0.004 + 0.0038 * sin(a)) for a in angles)
    points.points.add(len(coordinates) - 1)
    for point, position in zip(points.points, coordinates):
        point.co = (*position, 1)
    obj = bpy.data.objects.new(name, curve)
    curve.materials.append(surface)
    bpy.context.collection.objects.link(obj)


def weight(mass, x, y, bottom, surface, steel):
    radius, height = {100: (0.017, 0.020), 200: (0.020, 0.028), 300: (0.022, 0.035)}[mass]
    cylinder(f"Weight {mass} g", (x, y, bottom + height / 2), radius, height, surface, 0.0014)
    bpy.ops.mesh.primitive_torus_add(
        major_segments=36, minor_segments=12, major_radius=0.0034, minor_radius=0.0011,
        location=(x, y, bottom + height + 0.004), rotation=(pi / 2, 0, pi / 2),
    )
    finish(f"Eye {mass} g", steel)


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def area_light(name, location, power, size, color):
    bpy.ops.object.light_add(type="AREA", location=location)
    source = bpy.context.object
    source.name = name
    source.data.energy = power
    source.data.shape = "DISK"
    source.data.size = size
    source.data.color = color
    aim(source, (0, 0, 0.22))


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    aluminum = material("Satin aluminum", (0.38, 0.43, 0.49), 0.72)
    graphite = material("Graphite", (0.028, 0.042, 0.061), 0.25)
    steel = material("Polished steel", (0.64, 0.71, 0.78), 0.72, 0.25)
    brass = material("Brass weights", (0.55, 0.27, 0.075), 0.63, 0.27)
    active = material("Mounted string marker", (0.96, 0.54, 0.16), 0.40, 0.3)

    for x in (-0.224, 0.224):
        box("Foot", (x, 0, 0.012), (0.072, 0.25, 0.024), graphite, 0.004)
        box("Upright", (x, 0.036, 0.231), (0.028, 0.029, 0.414), aluminum, 0.002)
        box("Upright channel", (x, 0.021, 0.231), (0.007, 0.002, 0.397), graphite)
        box("Upright shoe", (x, 0.036, 0.037), (0.047, 0.046, 0.032), aluminum, 0.002)

    wire_xs = (-0.107, 0, 0.107)
    wire_y, top_z, span = 0.009, 0.417, 0.30
    lower_z = top_z - span
    beam_z = 0.427
    box("Rear half of top rail", (0, 0.046, beam_z), (0.486, 0.034, 0.028), aluminum, 0.002)
    edges = [-0.243]
    for x in wire_xs:
        edges.extend((x - 0.012, x + 0.012))
    edges.append(0.243)
    for left, right in zip(edges[::2], edges[1::2]):
        box("Front section between slots", ((left + right) / 2, 0.009, beam_z),
            (right - left, 0.040, 0.028), aluminum, 0.002)

    for index, (x, radius) in enumerate(zip(wire_xs, (0.00085, 0.00110, 0.00135)), start=1):
        marker = active if index == 2 else graphite
        box(f"Clamp {index}", (x, 0.017, 0.433), (0.020, 0.028, 0.034), marker)
        cylinder(f"Clamp screw {index}", (x, 0.017, 0.453), 0.006, 0.008, steel, 0.0007)
        cylinder(f"String {index}", (x, wire_y, (top_z + lower_z) / 2), radius, span,
                 active if index == 2 else steel)
        hook(f"Hook {index}", x, wire_y, lower_z, steel)

    weight(200, 0.004, wire_y, lower_z - 0.041, brass, steel)
    box("Tray bottom", (0, -0.074, 0.004), (0.285, 0.084, 0.012), graphite, 0.003)
    for y in (-0.115, -0.033):
        box("Tray rim", (0, y, 0.014), (0.285, 0.004, 0.014), graphite)
    for x in (-0.14, 0.14):
        box("Tray end", (x, -0.074, 0.014), (0.005, 0.078, 0.014), graphite)
    weight(100, -0.074, -0.074, 0.010, brass, steel)
    weight(300, 0.074, -0.074, 0.010, brass, steel)

    floor = material("Preview floor", (0.054, 0.075, 0.11), roughness=0.84)
    box("Preview floor", (0, 0, -0.017), (200, 200, 0.03), floor, 0)
    area_light("Key", (-0.43, -0.53, 0.76), 26, 0.55, (0.81, 0.91, 1))
    area_light("Fill", (0.53, -0.11, 0.53), 16, 0.40, (1, 0.82, 0.63))
    area_light("Rim", (0.05, 0.39, 0.65), 20, 0.38, (0.71, 0.81, 1))

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    bpy.ops.object.camera_add(location=(0.46, -0.96, 0.58))
    scene.camera = bpy.context.object
    scene.camera.name = "Preview camera"
    aim(scene.camera, (0, 0, 0.213))
    scene.camera.data.type = "ORTHO"
    scene.camera.data.ortho_scale = 0.74
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 960
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    bpy.ops.object.select_all(action="DESELECT")
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
                area.spaces.active.overlay.show_overlays = False
    return scene


if __name__ == "__main__":
    output = Path(sys.argv[sys.argv.index("--") + 1]).resolve() if "--" in sys.argv else Path(__file__).resolve().parent
    output.mkdir(parents=True, exist_ok=True)
    scene = build()
    scene.render.filepath = "//prototype.png"
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "prototype.blend"), compress=True)
    scene.render.filepath = str(output / "prototype.png")
    bpy.ops.render.render(write_still=True)
