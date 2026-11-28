from math import cos, pi, sin
from pathlib import Path
import subprocess
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


def line(name, coordinates, radius, surface):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    points = curve.splines.new("POLY")
    points.points.add(len(coordinates) - 1)
    for point, position in zip(points.points, coordinates):
        point.co = (*position, 1)
    obj = bpy.data.objects.new(name, curve)
    curve.materials.append(surface)
    bpy.context.collection.objects.link(obj)


def hook(name, x, y, bottom, surface):
    angles = [pi - step * 1.55 * pi / 24 for step in range(25)]
    coordinates = [(x, y, bottom), (x, y, bottom - 0.004)]
    coordinates.extend((x + 0.0038 + 0.0038 * cos(a), y, bottom - 0.004 + 0.0038 * sin(a)) for a in angles)
    line(name, coordinates, 0.0012, surface)


def text(label, location, size, font, surface):
    bpy.ops.object.text_add(location=location, rotation=(pi / 2, 0, 0))
    obj = finish(label, surface)
    obj.data.body = label
    obj.data.font = font
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size


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
    font_path = subprocess.check_output(["fc-match", "-f", "%{file}", "sans-serif:lang=ru"], text=True)
    font = bpy.data.fonts.load(font_path)
    font.pack()
    aluminum = material("Satin aluminum", (0.40, 0.47, 0.53), 0.6)
    graphite = material("Graphite", (0.028, 0.042, 0.061), 0.25)
    display = material("Display glass", (0.009, 0.032, 0.044), 0.25, 0.26)
    lettering = material("Pale lettering", (0.72, 0.87, 0.91), roughness=0.55)
    steel = material("Polished steel", (0.64, 0.71, 0.78), 0.72, 0.25)
    brass = material("Brass weights", (0.55, 0.27, 0.075), 0.63, 0.27)
    active = material("Mounted string marker", (0.96, 0.54, 0.16), 0.40, 0.3)
    trace = material("Amplitude envelope", (0.64, 0.26, 0.062), roughness=0.55)

    wire_xs = (-0.144, -0.024, 0.096)
    wire_y, top_z, span = 0.013, 0.389, 0.30
    lower_z = top_z - span
    panel_thickness = 0.016
    panel_z = top_z + panel_thickness / 2
    box("Rear strip of board", (-0.024, 0.060, panel_z), (0.40, 0.070, panel_thickness), aluminum)
    slot_width = 0.007
    edges = [-0.224]
    for x in wire_xs:
        edges.extend((x - slot_width / 2, x + slot_width / 2))
    edges.append(0.176)
    for left, right in zip(edges[::2], edges[1::2]):
        box("Front section between slots", ((left + right) / 2, -0.005, panel_z),
            (right - left, 0.060, panel_thickness), aluminum)

    for index, (x, radius) in enumerate(zip(wire_xs, (0.00085, 0.00110, 0.00135)), start=1):
        wire = active if index == 1 else steel
        cylinder(f"Ball-end stop {index}", (x, wire_y, top_z + panel_thickness + 0.0045),
                 0.010, 0.009, brass if index == 1 else steel, 0.0025)
        cylinder(f"String through slot {index}", (x, wire_y, panel_z), radius, panel_thickness, wire)
        cylinder(f"String {index}", (x, wire_y, (top_z + lower_z) / 2), radius, span, wire)
        hook(f"Hook {index}", x, wire_y, lower_z, steel)

    for direction in (-1, 1):
        samples = [step / 64 for step in range(65)]
        outline = [(wire_xs[0] + direction * 0.014 * sin(pi * p), wire_y, top_z - span * p) for p in samples]
        line("Real-time envelope", outline, 0.00065, trace)

    weight(200, wire_xs[0] + 0.004, wire_y, lower_z - 0.041, brass, steel)
    tray_x = 0.275
    box("Tray bottom", (tray_x, -0.067, 0.005), (0.241, 0.090, 0.014), graphite, 0.003)
    for y in (-0.112, -0.022):
        box("Tray rim", (tray_x, y, 0.016), (0.241, 0.004, 0.016), graphite)
    for x in (tray_x - 0.118, tray_x + 0.118):
        box("Tray end", (x, -0.067, 0.016), (0.005, 0.088, 0.016), graphite)
    for mass, x in zip((100, 200, 300), (tray_x - 0.076, tray_x, tray_x + 0.076)):
        cylinder(f"Tray position {mass} g", (x, -0.067, 0.0125), 0.027, 0.001, aluminum, 0.0002)
        text(f"{mass} г", (x, -0.1142, 0.016), 0.011, font, lettering)
        if mass != 200:
            weight(mass, x, -0.067, 0.013, brass, steel)

    instrument_x = -0.301
    box("Instrument housing", (instrument_x, -0.075, 0.059), (0.174, 0.087, 0.122), graphite, 0.005)
    for title, reading, height in (("СЕКУНДОМЕР", "0,050 с", 0.086), ("ЧАСТОТОМЕР", "99,42 Гц", 0.032)):
        box(f"{title} display", (instrument_x, -0.119, height), (0.153, 0.003, 0.041), display)
        text(title, (instrument_x, -0.121, height + 0.011), 0.011, font, lettering)
        text(reading, (instrument_x, -0.121, height - 0.007), 0.017, font, lettering)

    floor = material("Preview floor", (0.054, 0.075, 0.11), roughness=0.84)
    box("Preview floor", (0, 0, -0.017), (200, 200, 0.03), floor, 0)
    area_light("Key", (-0.43, -0.53, 0.76), 26, 0.55, (0.81, 0.91, 1))
    area_light("Fill", (0.53, -0.11, 0.53), 16, 0.40, (1, 0.82, 0.63))
    area_light("Rim", (0.05, 0.39, 0.65), 20, 0.38, (0.71, 0.81, 1))

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    bpy.ops.object.camera_add(location=(0.10, -1.15, 0.63))
    scene.camera = bpy.context.object
    scene.camera.name = "Preview camera"
    aim(scene.camera, (0, -0.01, 0.204))
    scene.camera.data.type = "ORTHO"
    scene.camera.data.ortho_scale = 0.93
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 780
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
