"""Verify the local P3 mouth change against its paired P2/P3 baseline."""
import argparse
import hashlib
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

import FreeCAD as A
import Part
import speaker_duct_geometry as duct

ROOT = Path(__file__).resolve().parent
base = SourceFileLoader('duct_check', str(ROOT / 'check-speaker-duct.py')).load_module()


def check(model, baseline):
    report = base.check(model, baseline)
    doc = A.openDocument(str(model.resolve()))
    old = A.openDocument(str(baseline.resolve()))
    core, rear = doc.SpeakerCarrier.Shape, doc.RearShell.Shape
    p2_delta = base.ac.difference(rear, old.RearShell.Shape)
    assert p2_delta < .001
    zones = Part.makeCompound([
        Part.makeBox(6.0, 43, 30, A.Vector(x, 23, 50))
        for x in (-79.4, 73.4)])
    outside = base.ac.difference(core.cut(zones), old.SpeakerCarrier.Shape.cut(zones))
    assert outside < .001, outside

    # Reconstruct the previous lumen independently of the new flare.
    vertical = Part.makeLoft([duct.vertical_wire(55), duct.vertical_wire(98)], True, True)
    previous_lumen = vertical.fuse(duct.outlet_prism(-80, 14.5)).removeSplitter()
    lumen, envelope = duct.duct_shapes()
    assert previous_lumen.cut(lumen).Volume < .001
    assert previous_lumen.common(core).Volume < .001
    # The changed air passage is confined to the final 4 mm; the cutting
    # tool also extends beyond the open end, outside the physical part.
    flare_zone = Part.makeBox(6, 45, 32, A.Vector(-81, 22, 49))
    assert lumen.cut(previous_lumen).cut(flare_zone).Volume < .001

    projection = Part.Face(duct.trapezoid_outlet_wire(-85.1, -1.8)).extrude(A.Vector(5.8, 0, 0))
    obstruction = projection.common(rear).Volume
    assert obstruction < .001
    mouth_area = Part.Face(duct.trapezoid_outlet_wire(duct.EXIT_X, -1.8)).Area
    sections = {}
    mouth, _ = duct.terminal_mouth()
    for i in range(17):
        x = duct.EXIT_X + .001 + i * 3.998 / 16
        # The complete lumen also intersects the pre-existing vertical leg
        # near the root. Check the flare itself separately from that junction.
        sections[str(x)] = sum(Part.Face(w).Area for w in mouth.slice(A.Vector(1, 0, 0), x))
    assert min(sections.values()) >= 400 - 1e-5
    assert all(a >= b - 1e-4 for a, b in zip(list(sections.values()), list(sections.values())[1:]))
    # Actual final rim contains the complete nominal transverse 1.8 mm ring.
    outer = Part.Face(duct.trapezoid_outlet_wire(duct.EXIT_X+.001))
    inner = Part.Face(duct.trapezoid_outlet_wire(duct.EXIT_X+.001, -1.8))
    ring = outer.cut(inner).extrude(A.Vector(.002, 0, 0))
    missing_rim = ring.cut(core).Volume
    assert missing_rim < .001
    assert abs(outer.OuterWire.distToShape(inner.OuterWire)[0] - 1.8) < 1e-6
    report.update({
        'p2_entire_shape_difference_mm3': p2_delta,
        'p3_outside_terminal_zones_difference_mm3': outside,
        'old_400mm2_passage_retained': True,
        'terminal_flare_length_mm': 4,
        'terminal_collar_length_mm': 5.8,
        'terminal_transverse_rim_mm': 1.8,
        'nominal_rim_missing_from_saved_core_mm3': missing_rim,
        'terminal_open_area_mm2': mouth_area,
        'terminal_transition_tool_sections_mm2': sections,
        'full_new_mouth_p2_obstruction_mm3': obstruction,
        'baseline_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
        'limits_terminal': 'Rim thickness is transverse; no strength or acoustic validation.'})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = check(args.model, args.baseline)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('TERMINAL_MOUTH_OK', result['terminal_open_area_mm2'], flush=True)
