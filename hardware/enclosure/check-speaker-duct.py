"""Check the coordinated P2/P3 air path, preservation and service clearances."""
import argparse
import hashlib
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path
import FreeCAD as A
import Part
import speaker_duct_geometry as duct
import speaker_wire_geometry as wire

V = A.Vector
ROOT = Path(__file__).resolve().parent
ac = SourceFileLoader('acoustics', str(ROOT / 'check-speaker-acoustics.py')).load_module()


def check(model, baseline):
    doc = A.openDocument(str(model.resolve()))
    old = A.openDocument(str(baseline.resolve()))
    core, rear = doc.SpeakerCarrier.Shape, doc.RearShell.Shape
    changed = {'LChamber', 'RChamber', 'SpeakerCarrier', 'RearShell',
               'LPanel', 'RPanel', 'LPanelTool', 'LPort', 'RPort'}
    preserved = {}
    for obj in old.Objects:
        if obj.Name in changed or hasattr(obj, 'Group') or not hasattr(obj, 'Shape') or obj.Shape.isNull():
            continue
        preserved[obj.Name] = ac.difference(obj.Shape, doc.getObject(obj.Name).Shape)
    assert max(preserved.values()) < .001, preserved
    matrix = A.Matrix(); matrix.A11 = -1
    symmetry = {}
    for left, right in [('LChamber', 'RChamber'), ('LPort', 'RPort'), ('RearShell', 'RearShell')]:
        shape = doc.getObject(left).Shape.copy(); shape.transformShape(matrix, True)
        symmetry[left] = ac.difference(shape, doc.getObject(right).Shape)
    assert max(symmetry.values()) < .001, symmetry
    for shape in (core, rear):
        assert shape.isValid() and len(shape.Solids) == 1
    # Final compound must not silently fill a pilot or trial seat.
    seat_zone = Part.makeBox(100, 8, 90, V(-50, 5, 31))
    seat_delta = ac.difference(core.common(seat_zone), old.SpeakerCarrier.Shape.common(seat_zone))
    assert seat_delta < .001
    # Compare the entire original Ø8 boss envelopes, including blind bottoms.
    boss_delta = []
    for cx in (-26, 26):
        for x in (cx-18, cx+18):
            for z in (41, 111):
                zone = Part.makeCylinder(4, 11.5, V(x, 10, z), V(0, 1, 0))
                delta = ac.difference(core.common(zone), old.SpeakerCarrier.Shape.common(zone))
                assert delta < .001
                boss_delta.append(delta)
    wire_check = ac.check_wire_corridor(doc)
    lumen, envelope = duct.duct_shapes()
    assert lumen.common(core).Volume < .001
    # Normal sections along both straight legs, plus the transition plane.
    sections = {}
    for z in (55.01, 60, 65, 70, 75.01, 80, 85, 90, 97.99):
        sections[f'Z={z}'] = sum(Part.Face(w).Area for w in lumen.slice(V(0, 0, 1), z))
    for x in (-79.29, -78, -76, -75.49, -70, -65.51):
        sections[f'X={x}'] = sum(Part.Face(w).Area for w in lumen.slice(V(1, 0, 0), x))
    normal = V(-1, 0, -1); normal.normalize()
    sections['45deg_elbow'] = sum(Part.Face(w).Area for w in lumen.slice(normal, V(-65.5, 50, 65).dot(normal)))
    assert min(sections.values()) >= 400 - 1e-5, sections
    projection = duct.outlet_prism(-85.1, 5.9)
    obstruction = projection.common(rear).Volume
    assert obstruction < .001
    p2_sections = {}
    for x in (-84.99, -84.5, -84, -83, -82, -81, -80.01):
        face = Part.Face(duct.outlet_wire(x))
        p2_sections[str(x)] = face.cut(rear).Area
    assert all(abs(area-400) < 1e-5 for area in p2_sections.values())
    throat_area = Part.Face(duct.outlet_wire(-80, 1)).Area
    # Close only intentional openings. Every chamber must be isolated from
    # its neighbour and the exterior; blocking the inlet must isolate the duct.
    fronts = [Part.makeBox(46, 2.2, 81, V(x-23, 4.9, 35.5)) for x in (-26, 26)]
    sidecaps = [Part.makeBox(.701, 65, 90, V(x, 0, 34)) for x in (-80, 79.299)]
    tools = [t for sign in (-1, 1) for t in wire.exit_tools(sign)]
    air = Part.makeBox(180, 80, 110, V(-90, -5, 20)).cut(core).cut(Part.makeCompound(fronts+sidecaps+tools))
    def component(shape, point):
        hits = [s for s in shape.Solids if s.isInside(V(*point), 1e-6, True)]
        assert len(hits) == 1, point
        return hits[0]
    main = component(air, (-26, 55, 76))
    assert main.isInside(V(-65.5, 50, 85), 1e-6, True)
    assert main.isInside(V(-79, 50, 65), 1e-6, True)
    for point in ((26, 55, 76), (0, -4, 25)):
        assert not main.isInside(V(*point), 1e-6, True)
    blocked = air.cut(Part.makeBox(22, 27, 1, V(-76.5, 34, 97.5)))
    isolated = component(blocked, (-26, 55, 76))
    assert not isolated.isInside(V(-65.5, 50, 85), 1e-6, True)
    assert not isolated.isInside(V(-79, 50, 65), 1e-6, True)
    # Removing outlet caps opens the chambers: negative control for topology.
    open_air = Part.makeBox(180, 80, 110, V(-90, -5, 20)).cut(core).cut(Part.makeCompound(fronts+tools))
    exterior = component(open_air, (0, -4, 25))
    assert all(exterior.isInside(V(x, 55, 76), 1e-6, True) for x in (-26, 26))
    interface = doc.LChamber.Shape.common(Part.makeBox(4, 45, 35, V(-80, 25, 48)))
    gap = interface.distToShape(rear)[0]
    assert abs(gap-.7) < 1e-6, gap
    contact = {}
    for name in ('LChamber', 'RChamber'):
        contact[name] = sum(f.Area for f in doc.getObject(name).Shape.Faces
                            if f.BoundBox.YLength < 1e-7 and abs(f.CenterOfMass.y-62.5) < 1e-7)
        assert abs(contact[name]-6929) < .001
    # All changes to the outer shell stay in the original outlet neighbourhood.
    zone = Part.makeCompound([Part.makeBox(6, 43, 90, V(x, 25, 38)) for x in (-85.5, 79.5)])
    outside_delta = ac.difference(rear.cut(zone), old.RearShell.Shape.cut(zone))
    assert outside_delta < .001, outside_delta
    duct_volume = main.common(lumen).Volume
    report = {'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
              'baseline_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
              'unchanged_shapes_difference_mm3': preserved, 'symmetry_difference_mm3': symmetry,
              'trial_seat_difference_mm3': seat_delta, 'eight_bosses_difference_mm3': boss_delta,
              'wire_corridor': wire_check, 'normal_air_sections_mm2': sections,
              'p2_projected_exit_area_mm2': p2_sections, 'p2_throat_area_mm2': throat_area,
              'p2_projected_exit_obstruction_mm3': obstruction, 'sliding_clearance_mm': gap,
              'left_right_and_exterior_separate_when_capped': True,
              'blocking_inlet_disconnects_duct': True, 'open_outlet_connects_exterior': True,
              'rear_contact_area_mm2': contact, 'p2_outside_port_zone_difference_mm3': outside_delta,
              'left_capped_air_mm3': main.Volume, 'left_duct_air_mm3': duct_volume,
              'left_main_air_minus_entire_driver_envelope_mm3': main.cut(doc.LDriver.Shape).Volume-duct_volume,
              'nominal_centerline_length_mm': 46.8, 'physical_acoustics_verified': False,
              'volume_caveat': 'Full conservative driver envelope deducted; not measured net acoustic volume.',
              'all_pass': True}
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    report = check(args.model, args.baseline)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print('DUCT_GEOMETRY_OK', report['normal_air_sections_mm2'], report['p2_throat_area_mm2'], flush=True)
