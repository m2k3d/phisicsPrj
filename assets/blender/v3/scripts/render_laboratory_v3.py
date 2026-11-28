"""Render all review cameras from the open V3 or V3.1 scene."""

import argparse
import sys
from pathlib import Path

import bpy


def render():
    parser = argparse.ArgumentParser()
    parser.add_argument("--view", action="append", help="Camera name, repeat for more views")
    parser.add_argument("--percent", type=int, default=100)
    parser.add_argument("--samples", type=int, default=40)
    parser.add_argument("--device", choices=("CPU", "CUDA", "OPTIX"), default="CPU")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

    scene = bpy.context.scene
    render_dirs = {
        "STANDING_WAVE_LAB_V3": "renders/v3",
        "STANDING_WAVE_LAB_V3_1": "renders/v3-1",
    }
    if scene.name not in render_dirs:
        raise RuntimeError("Open laboratory_v3.blend or laboratory_v3_1.blend before running this script.")
    studio = bpy.data.collections["08_STUDIO"]
    cameras = sorted((obj for obj in studio.objects if obj.type == "CAMERA"), key=lambda obj: obj.name)
    if args.view:
        by_name = {camera.name: camera for camera in cameras}
        cameras = [by_name[name] for name in args.view]

    output = args.output or Path(bpy.data.filepath).parent / render_dirs[scene.name]
    output.mkdir(parents=True, exist_ok=True)
    for setting in ("use_stamp", "use_stamp_filename", "use_stamp_hostname", "use_stamp_date", "use_stamp_time", "use_stamp_note"):
        setattr(scene.render, setting, False)
    scene.render.resolution_percentage = args.percent
    scene.cycles.samples = args.samples
    if args.device != "CPU":
        settings = bpy.context.preferences.addons["cycles"].preferences
        settings.compute_device_type = args.device
        settings.refresh_devices()
        for device in settings.devices:
            device.use = device.type == args.device
        if not any(device.use for device in settings.devices):
            raise RuntimeError(f"Cycles could not find a {args.device} device.")
        scene.cycles.device = "GPU"
    original_camera = scene.camera
    for camera in cameras:
        scene.camera = camera
        scene.render.resolution_x, scene.render.resolution_y = camera["review_pixels"]
        scene.render.filepath = str(output / (camera.name + ".png"))
        bpy.ops.render.render(write_still=True)
    scene.camera = original_camera


if __name__ == "__main__":
    render()
