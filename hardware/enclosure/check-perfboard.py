"""Check the saved perfboard mounts, wire envelopes and powered-off service access."""
import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path

import FreeCAD as App
import Part

import perfboard_geometry as geometry

ROOT = Path(__file__).resolve().parent
V = App.Vector
FRONT_PARTS = (
    "FrontShell", "Window", "StatusArt", "PlayPauseKey", "EjectKey", "PrevKey",
    "NextKey", "ButtonRetainer", "DisplayRetainer", "Knob", "Encoder", "VolumePot",
    "DisplayPCB", "DisplayHeader", "PlayPauseSwitch", "EjectSwitch", "PrevSwitch",
    "NextSwitch",
)
TOL = .001


def hits(shape, obstacles):
    found = {}
    for name, obstacle in obstacles.items():
        if not shape.BoundBox.intersect(obstacle.BoundBox):
            continue
        volume = shape.common(obstacle).Volume
        if volume > TOL:
            found[name] = round(volume, 5)
    return found


def difference(a, b):
    if a.exportBrepToString() == b.exportBrepToString():
        return 0.0
    return a.cut(b).Volume + b.cut(a).Volume


def grip_corridor(unplug):
    center = unplug.BoundBox.Center
    return geometry.box(center.x-6, -24, center.z-5, 12, center.y+24, 10)


def check(path, baseline=None):
    doc = App.openDocument(str(path))
    before = App.openDocument(str(baseline)) if baseline else None
    finished = {
        obj.Name: obj.Shape for group in ("Shell", "Controls", "Carrier", "Hardware")
        for obj in doc.getObject(group).Group
    }
    # The grille and exterior slab are below the cables or forward of the cable
    # endpoints throughout the checked travel. Retain all internal posts.
    front = {name: finished.pop(name) for name in FRONT_PARTS}
    front["FrontShell"] = front["FrontShell"].common(geometry.box(-85, 4, 141, 170, 80, 70))
    fixed = finished | {
        name: doc.getObject(name).Shape for name in ("BuckAService", "BuckBService", "DACPowerConnector")
    }
    geometry_changes = {}
    if before is not None:
        unchanged = [
            name for name in (*FRONT_PARTS, "Drive", "Bridge", "Battery", "Amp", "AmpChip",
                              "LDriver", "RDriver", "LPort", "RPort", "LChamber", "RChamber")
        ]
        geometry_changes = {}
        for name in unchanged:
            original = before.getObject(name).Shape
            current = doc.getObject(name).Shape
            if name == "FrontShell":
                # The dense grille was regenerated from the same B-rep source.
                # Verify it directly, then compare the shell outside its cylinder.
                grille = doc.FrontGrille.Shape
                assert difference(before.FrontGrille.Shape, grille) < TOL
                assert difference(before.FrontBezel.Shape, doc.FrontBezel.Shape) < TOL
                grille_zone = Part.makeCylinder(68.1, 9, V(0, -1, 76), V(0, 1, 0))
                original = original.cut(grille_zone)
                current = current.cut(grille_zone)
            geometry_changes[name] = round(difference(original, current), 6)
        print("BASELINE_GEOMETRY_OK", flush=True)
        assert all(value < TOL for value in geometry_changes.values()), geometry_changes
        baseline_rear = before.RearShell.Shape
        if difference(baseline_rear, doc.RearShell.Shape) >= TOL:
            # The original carrier integration removed the old side-mounted DAC pads.
            assert difference(baseline_rear.cut(before.DACPads.Shape), doc.RearShell.Shape) < TOL
        assert len(doc.SpeakerCarrier.Shape.Solids) == 1 and doc.SpeakerCarrier.Shape.isValid()
        low = geometry.box(-85, 0, 0, 170, 93, 120.5)
        assert difference(before.SpeakerCarrier.Shape.common(low), doc.SpeakerCarrier.Shape.common(low)) < TOL

    mount_checks = []
    for index, (x, y, length, hole) in enumerate(geometry.MOUNTS, 1):
        screw = "PerfboardScrew" + str(index)
        shaft = geometry.bore(x, y, 144.4-length, .78, length)
        head_and_tool = geometry.bore(x, y, 144.4, 2.25, 30)
        obstacles = {name: shape for name, shape in fixed.items() if name != screw}
        assert not hits(shaft, {"board": doc.Perfboard.Shape, "carrier": doc.SpeakerCarrier.Shape}), hole
        assert not hits(head_and_tool, obstacles), hole
        pad = geometry.bore(x, y, 142.79, 2.4, .02)
        assert pad.common(doc.SpeakerCarrier.Shape).Volume > .1, hole
        assert pad.common(doc.Perfboard.Shape).Volume > .1, hole
        mount_checks.append({"hole": hole, "center_xy_mm": [x, y], "screw": "M2x"+str(length)})

    allowances = {
        name: doc.getObject(name).Shape for name in (
            "PerfboardUnderWiring", *(name+"LeadBend" for name in geometry.CONNECTORS),
            "DriveDataWire", "DACAudioWire",
        )
    }
    # Soldered board-end leads occupy the allocated board underside. The power
    # and analogue connector end at their own terminal face.
    allowance_hits = {}
    for name, shape in allowances.items():
        obstacles = fixed | front
        if name == "DACAudioWire":
            obstacles = {n:s for n,s in obstacles.items() if n not in ("DAC", "DACChip")}
        found = {}
        for segment in shape.Solids:
            found.update(hits(segment, obstacles))
        if found:
            allowance_hits[name] = found
    assert not allowance_hits, allowance_hits

    print("MOUNTS_AND_LEAD_ENVELOPES_OK", flush=True)
    open_at = geometry.SERVICE_OPENING
    lengths = {name: [] for name in geometry.HARNESS_ROUTES}
    path_hits = []
    steps = list(range(0, open_at+1, 2))
    for opening in steps:
        moved = {name: shape.translated(V(0, -opening, 0)) for name, shape in front.items()}
        occupied = {}
        for name in geometry.HARNESS_ROUTES:
            parts, length = geometry.harness_segments(name, opening)
            lengths[name].append(length)
            obstacles = fixed | moved | occupied
            for part in parts:
                found = hits(part, obstacles)
                if found:
                    path_hits.append({"opening_mm": opening, "harness": name, "clashes": found})
            occupied[name] = Part.makeCompound(parts)
            if opening in (0, open_at):
                suffix = "Closed" if opening == 0 else "Open"
                saved = doc.getObject(name+"Harness"+suffix).Shape
                actual = occupied[name]
                # Exact saved solids, without fusing their intentionally
                # overlapping junctions into a single volume.
                assert len(saved.Solids) == len(actual.Solids)
                assert all(difference(a, b) < TOL for a, b in zip(saved.Solids, actual.Solids))
    print("HARNESS_SAMPLES", len(steps), flush=True)
    assert not path_hits, path_hits
    assert all(max(values)-min(values)<1e-5 for values in lengths.values()), lengths

    service = {}
    # The switch loop crosses the OLED grip area at the service position.
    # Unplug it first and set it aside with the supported cover.
    unplug_order = ("VolumeSwitch", "OLED", "Buttons")
    for name in unplug_order:
        unplug = doc.getObject(name+"Unplug").Shape
        corridor = grip_corridor(unplug)
        obstacles = {key: shape for key, shape in fixed.items() if key != "XH"+name}
        unplug_hits = hits(unplug, obstacles | moved | {
            key: value for key, value in occupied.items() if key != name
        })
        access_hits = hits(corridor, obstacles | moved | {
            key: value for key, value in occupied.items() if key != name
        })
        assert not unplug_hits and not access_hits, (name, unplug_hits, access_hits)
        service[name] = {"unplug_clashes": unplug_hits, "12x10_mm_grip_corridor_clashes": access_hits}
        del occupied[name]

    gaps = {
        "board_to_drive": doc.Perfboard.Shape.distToShape(doc.Drive.Shape)[0],
        "underside_wiring_to_amp": doc.PerfboardUnderWiring.Shape.distToShape(doc.AmpChip.Shape)[0],
        "board_to_B50K": doc.Perfboard.Shape.distToShape(doc.VolumePot.Shape)[0],
    }
    assert min(gaps.values()) >= 1, gaps
    result = {
        "model_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest() if baseline else None,
        "freecad_version": App.Version()[:3],
        "unchanged_geometry_difference_mm3": geometry_changes,
        "mounts": mount_checks,
        "clearances_mm": {name: round(gap, 3) for name, gap in gaps.items()},
        "lead_reservation_clashes": allowance_hits,
        "front_cover_opening_mm": open_at,
        "front_cover_harness_samples_mm": steps,
        "harness_path_clashes": path_hits,
        "harness_centerline_mm": {name: round(values[0], 1) for name, values in lengths.items()},
        "unplug_order": list(unplug_order),
        "unplug_access": service,
        "physical_fit_verified": False,
        "limits": [
            "Nominal XH-style mated envelopes. Actual plug bodies, pitch, wire bundle and bend compliance require physical verification.",
            "The forward path assumes all four rear screws are removed and the front cover is supported during service.",
            "Flexible routes sampled at 2 mm; hand access is a 12x10 mm solid corridor, not an ergonomic or pinch test.",
            "Terminal stubs, the B50K stereo harness, and final power harness beyond local envelopes are not included.",
        ],
    }
    if before is not None and before is not doc:
        App.closeDocument(before.Name)
    App.closeDocument(doc.Name)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=ROOT/"Discora.FCStd")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT/"perfboard-checks.json")
    args = parser.parse_args()
    report = check(args.model.resolve(), args.baseline.resolve() if args.baseline else None)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print("PERFBOARD_OK", report["clearances_mm"], report["harness_centerline_mm"], flush=True)
