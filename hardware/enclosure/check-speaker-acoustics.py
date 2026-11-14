"""Verify P3 wall topology and serviceable wire exits, not acoustic performance."""
import argparse
import hashlib
import json
from pathlib import Path

import FreeCAD as App
import Part
import speaker_wire_geometry as wire

V = App.Vector
TOL = .001


def difference(a, b):
    if a.exportBrepToString() == b.exportBrepToString():
        return 0.0
    return a.cut(b).Volume + b.cut(a).Volume


def side_cap(x):
    middle = Part.makeBox(3, 18, 45, V(x, 40, 57.5))
    ends = [Part.makeCylinder(9, 3, V(x, 49, z), V(1, 0, 0))
            for z in (57.5, 102.5)]
    return middle.multiFuse(ends).removeSplitter()


def check_wire_corridor(doc):
    # A routing reservation above the nominal basket and behind its frame.
    # This does not represent the unmeasured solder joint or bend radius.
    parts = [Part.makeBox(3.6, 31, 1.8, V(24.2, 24, 113.1)),
             Part.makeBox(36.6, 1.8, 1.8, V(24.2, 54.1, 113.1)),
             Part.makeBox(3.6, 9.8, 1.8, V(57.2, 46.1, 113.1)),
             Part.makeBox(3.6, 1.8, 4.9, V(57.2, 46.1, 113.1))]
    right = Part.makeCompound(parts)
    matrix = App.Matrix(); matrix.A11 = -1
    left = right.copy(); left.transformShape(matrix, True)
    for shape in (left, right):
        for name in ('SpeakerCarrier', 'LDriver', 'RDriver'):
            assert shape.common(doc.getObject(name).Shape).Volume < TOL
    return {
        'pair_envelope_mm': [3.6, 1.8],
        'right_waypoints_xyz_mm': [[26, 24, 114], [26, 55, 114],
                                   [59, 55, 114], [59, 47, 114], [59, 47, 118]],
        'left_mirrored': True, 'collision_mm3': 0,
        'terminal_and_bend_radius_verified': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    old = App.openDocument(str(args.baseline.resolve()))
    doc = App.openDocument(str(args.model.resolve()))
    core = doc.SpeakerCarrier.Shape
    assert core.isValid() and len(core.Solids) == 1
    tools = [tool for sign in (-1, 1) for tool in wire.exit_tools(sign)]
    expected = old.SpeakerCarrier.Shape.cut(Part.makeCompound(tools))
    delta = difference(core, expected)
    assert delta < TOL, delta

    # Check all other saved bodies, including editable construction sources.
    changed = {'LChamber', 'RChamber', 'SpeakerCarrier'}
    preserved = {}
    for obj in old.Objects:
        if (obj.Name in changed or hasattr(obj, 'Group')
                or not hasattr(obj, 'Shape') or obj.Shape.isNull()):
            continue
        preserved[obj.Name] = difference(obj.Shape, doc.getObject(obj.Name).Shape)
    assert max(preserved.values()) < TOL, preserved
    mirror = App.Matrix(); mirror.A11 = -1
    left = doc.LChamber.Shape.copy(); left.transformShape(mirror, True)
    symmetry = difference(left, doc.RChamber.Shape)
    assert symmetry < TOL, symmetry

    # Neither rear-down contact face is altered by the top exits.
    contact = {}
    for name in ('LChamber', 'RChamber'):
        face_area = sum(f.Area for f in doc.getObject(name).Shape.Faces
                        if f.BoundBox.YLength < 1e-7
                        and abs(f.CenterOfMass.y - 62.5) < 1e-7)
        assert abs(face_area - 6929) < TOL, (name, face_area)
        contact[name] = face_area

    exit_checks = {}
    hardware = {o.Name: o.Shape for group in ('Shell', 'Hardware')
                for o in doc.getObject(group).Group}
    for sign in (-1, 1):
        x = sign * wire.EXIT_X
        # Two measured circular insulated wires, touching side by side.
        wires = Part.makeCompound([
            Part.makeCylinder(.9, 8, V(x+dx, wire.EXIT_Y, 116))
            for dx in (-.9, .9)])
        assert wires.common(core).Volume < TOL
        # Keep a 0.5 mm lateral clearance to each nominal wire surface.
        assert abs(wires.distToShape(core)[0] - .5) < 1e-6
        # Access from above is checked after removing the perfboard assembly.
        # The modeled board edge partly overhangs the left edge of the recess.
        access = wire.capsule(x, wire.EXIT_Y, 120.5001, *wire.POCKET, 18)
        obstacles = {'SpeakerCarrier': core, **hardware}
        clashes = {n: s.common(access).Volume for n, s in obstacles.items()
                   if s.BoundBox.intersect(access.BoundBox)
                   and s.common(access).Volume > TOL}
        assert not clashes, clashes
        # Confirm a continuous 1.9 mm floor under the annular sealing recess.
        ring = wire.capsule(x, wire.EXIT_Y, 118, *wire.POCKET, 1.9).cut(
            wire.capsule(x, wire.EXIT_Y, 117.9, *wire.THROAT, 2.1))
        assert ring.cut(core).Volume < TOL
        exit_checks['left' if sign < 0 else 'right'] = {
            'center_xy_mm': [x, wire.EXIT_Y], 'throat_xy_mm': wire.THROAT,
            'pocket_xy_mm': wire.POCKET, 'pocket_depth_mm': wire.POCKET_DEPTH,
            'remaining_roof_mm': 1.9, 'nominal_wire_diameter_mm': 1.8,
            'nominal_wire_radial_clearance_mm': .5,
            'access_height_above_roof_mm': 18, 'access_clashes_mm3': clashes,
        }

    # Close only the designed front entries, side mouths and new wire throats.
    # Topological connectivity is independent of the nominal speaker basket.
    domain = Part.makeBox(180, 80, 110, V(-90, -5, 20))
    fronts = [Part.makeBox(46, 2.2, 81, V(x-23, 4.9, 35.5))
              for x in (-26, 26)]
    mouths = fronts + [side_cap(-79.4), side_cap(76.4)]
    sealed = domain.cut(core).cut(Part.makeCompound(mouths+tools))
    seeds = {'left': V(-55, 55, 76), 'right': V(55, 55, 76),
             'outside': V(0, -4, 25)}
    indices = {}
    for name, point in seeds.items():
        hits = [i for i, s in enumerate(sealed.Solids) if s.isInside(point, 1e-6, True)]
        assert len(hits) == 1, (name, hits)
        indices[name] = hits[0]
    assert len(set(indices.values())) == 3, indices
    # Each chamber must connect to the exterior if either wire opening is left
    # unsealed; this catches a false-positive topology check with misplaced caps.
    open_air = domain.cut(core).cut(Part.makeCompound(mouths))
    exterior = next(s for s in open_air.Solids if s.isInside(seeds['outside'], 1e-6, True))
    assert all(exterior.isInside(seeds[n], 1e-6, True) for n in ('left', 'right'))
    report = {
        'model_sha256': hashlib.sha256(args.model.read_bytes()).hexdigest(),
        'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        'only_planned_exit_cuts_difference_mm3': delta,
        'unchanged_shapes_difference_mm3': preserved,
        'chamber_mirror_difference_mm3': symmetry,
        'back_contact_area_mm2': contact, 'wire_exits': exit_checks,
        'capped_air_components': indices, 'left_right_and_exterior_separate': True,
        'unsealed_wire_exits_connect_chambers_to_exterior': True,
        'speaker_mount_and_hardware_pose_preserved': True,
        'p2_and_side_mouths_preserved': True, 'all_pass': True,
        'internal_wire_corridor': check_wire_corridor(doc),
        'limitations': [
            'Caps are analytical only; printed porosity and real sealing are not tested.',
            'Terminal protrusion, solder joints and minimum wire bend radius remain unmeasured.',
            'Wire passages accept free wire ends, not preinstalled connectors.',
            'P2/P3 side mouths retain 0.7 mm unsealed sliding clearance; side paths remain untuned.',
            'No net acoustic volume, frequency response or tuning claim is made.',
        ],
    }
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('SPEAKER_ACOUSTICS_GEOMETRY_OK', exit_checks, flush=True)


if __name__ == '__main__':
    main()
