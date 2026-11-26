"""Render the review cameras of the saved prototype."""

import argparse
import sys
from pathlib import Path

import bpy


VIEWS = (
    ("CAM_OVERVIEW", "01-overview.png"),
    ("CAM_FRONT", "02-front.png"),
    ("CAM_TOP", "03-top.png"),
    ("CAM_CLAMPS", "04-clamps.png"),
    ("CAM_PULLEYS", "05-pulleys-and-weights.png"),
    ("CAM_INSTRUMENTS", "06-measurement.png"),
)


def render_previews(output, percentage):
    scene = bpy.context.scene
    assert scene.get("generated_by") == "standing-wave-lab-variant-a", scene.name
    output.mkdir(parents=True, exist_ok=True)
    scene.render.resolution_percentage = percentage
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 35
    # Blender can embed stamps as PNG metadata even when they are not drawn.
    for setting in scene.render.bl_rna.properties:
        if setting.identifier.startswith("use_stamp"):
            setattr(scene.render, setting.identifier, False)
    if hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 96
    for camera_name, filename in VIEWS:
        scene.camera = bpy.data.objects[camera_name]
        scene.render.filepath = str(output / filename)
        result = bpy.ops.render.render(write_still=True)
        assert result == {"FINISHED"}, (camera_name, result)
        print(f"REVIEW {filename}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("previews"))
    parser.add_argument("--percentage", type=int, default=100, choices=range(5, 101))
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    render_previews(args.output.resolve(), args.percentage)
