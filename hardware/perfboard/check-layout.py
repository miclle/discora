"""Read-only envelope study. Run with a Python environment importing FreeCAD/Part.

Writes analysis.json beside this script; never modifies or saves the source CAD.
Shell translations are experiments, not validated enclosure modifications.
"""
import hashlib
import itertools
import json
from pathlib import Path

import FreeCAD as App
import Part


def main():
    folder = Path(__file__).resolve().parent
    spec = json.loads((folder / "layout.json").read_text())
    model = folder.parent / "enclosure" / "Discora.FCStd"
    doc = App.openDocument(str(model))
    try:
        ox, oy, oz = spec["case_board_origin_xyz_mm"]
        width, depth, thickness = spec["board_size_mm"]

        def box(origin, size):
            return Part.makeBox(*size, App.Vector(*origin))

        def part_shape(part):
            u, v = part["uv_mm"]
            w, d = part["size_uv_mm"]
            bottom = part.get("bottom_above_board_mm", 0)
            return box((ox + u, oy - v - d, oz + thickness + bottom),
                       (w, d, part["above_board_mm"]))

        shapes = {
            "Board": box((ox, oy - depth, oz), (width, depth, thickness)),
            "UndersideWiring": box((ox, oy - depth, oz - spec["underside_wiring_allowance_mm"]),
                                   (width, depth, spec["underside_wiring_allowance_mm"])),
        }
        shapes.update({p["id"]: part_shape(p) for p in spec["parts"] + spec["service_zones"]})

        def intersections(candidates, obstacles):
            hits, near = [], []
            for name, shape in candidates.items():
                for other, obstacle in obstacles.items():
                    volume = 0
                    if shape.BoundBox.intersect(obstacle.BoundBox):
                        volume = shape.common(obstacle).Volume
                    if volume > 0.001:
                        hits.append({"pair": [name, other], "mm3": round(volume, 3)})
                    else:
                        gap = shape.distToShape(obstacle)[0]
                        if gap < spec["clearance_screen_mm"] - 1e-6:
                            near.append({"pair": [name, other], "gap_mm": round(gap, 3)})
            return {"clashes": hits, "below_clearance_screen": near}

        footprints = spec["parts"]
        planar = []
        for a, b in itertools.combinations(footprints, 2):
            dx = max(a["uv_mm"][0] - b["uv_mm"][0] - b["size_uv_mm"][0],
                     b["uv_mm"][0] - a["uv_mm"][0] - a["size_uv_mm"][0], 0)
            dy = max(a["uv_mm"][1] - b["uv_mm"][1] - b["size_uv_mm"][1],
                     b["uv_mm"][1] - a["uv_mm"][1] - a["size_uv_mm"][1], 0)
            planar.append({"pair": [a["id"], b["id"]], "gap_mm": round((dx*dx+dy*dy)**0.5, 3)})
        outside = [p["id"] for p in footprints
                   if p["uv_mm"][0] < 0 or p["uv_mm"][1] < 0
                   or p["uv_mm"][0] + p["size_uv_mm"][0] > width
                   or p["uv_mm"][1] + p["size_uv_mm"][1] > depth]
        trials = []
        for rise in spec["shell_translation_trials_mm"]:
            obstacles = {n: doc.getObject(n).Shape.copy() for n in spec["obstacles"]}
            for name in spec["translated_objects"]:
                obstacles[name].translate(App.Vector(0, 0, rise))
            check = intersections(shapes, obstacles)
            trials.append({"upper_translation_mm": rise, **check})
            print(f"Upper translation {rise} mm: {len(check['clashes'])} intersections, "
                  f"{len(check['below_clearance_screen'])} gaps below screen", flush=True)
        report = {
            "revision": spec["revision"], "model": "../enclosure/Discora.FCStd",
            "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
            "layout_sha256": hashlib.sha256((folder / "layout.json").read_bytes()).hexdigest(),
            "freecad_version": App.Version()[:3],
            "nominal_parts_outside_board": outside, "planar_part_gaps": planar,
            "trials": trials,
            "current_support_check": intersections(shapes, {"SpeakerCarrier": doc.getObject("SpeakerCarrier").Shape}),
            "limits": spec["limits"], "physical_validation": False,
            "complete_enclosure_validation": False,
        }
        (folder / "analysis.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    finally:
        App.closeDocument(doc.Name)


if __name__ == "__main__":
    main()
