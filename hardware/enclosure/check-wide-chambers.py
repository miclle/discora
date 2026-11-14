"""Compare the widened chambers with the saved model preceding ADR-0040."""
import argparse
import hashlib
import json
from pathlib import Path

import FreeCAD as App
import Part


def difference(before, after):
    if before.exportBrepToString() == after.exportBrepToString():
        return 0.0
    return before.cut(after).Volume + after.cut(before).Volume


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path,
                        default=Path(__file__).resolve().parent / 'Discora.FCStd')
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    before = App.openDocument(str(args.baseline.resolve()))
    model = App.openDocument(str(args.model.resolve()))
    names = [obj.Name for group in ('Shell', 'Controls', 'Carrier', 'Hardware')
             for obj in model.getObject(group).Group
             if obj.Name not in ('RearShell', 'SpeakerCarrier')]
    names += ['LDriverFrame', 'RDriverFrame', 'FrontBaffle',
              'PerfboardRearRail', 'PerfboardSeats']
    unchanged = {name: difference(before.getObject(name).Shape,
                                  model.getObject(name).Shape) for name in names}
    assert max(unchanged.values()) < .001, unchanged

    for name in ('PlayPauseKey', 'PrevKey', 'NextKey', 'EjectKey', 'Knob'):
        old_faces = before.getObject(name).Shape.Faces
        new_faces = model.getObject(name).Shape.Faces
        assert len(old_faces) == len(new_faces), name
        for old, new in zip(old_faces, new_faces):
            assert abs(old.Area - new.Area) < 1e-6, name
            assert old.CenterOfMass.distanceToPoint(new.CenterOfMass) < 1e-6, name
            assert abs(old.common(new).Area - old.Area) < 1e-6, name

    # Compare complete mounting and electronics regions, including fused features.
    zones = [Part.makeBox(120, 100, 150, App.Vector(-60, 0, 0)),
             Part.makeBox(200, 100, 40, App.Vector(-100, 0, 120.5))]
    for zone in zones:
        assert difference(before.SpeakerCarrier.Shape.common(zone),
                          model.SpeakerCarrier.Shape.common(zone)) < .001
    # Preserve the outer side strips, including the decorations and all four ribs.
    for x in (-85, 80):
        zone = Part.makeBox(5, 100, 250, App.Vector(x, 0, 0))
        assert difference(before.RearShell.Shape.common(zone),
                          model.RearShell.Shape.common(zone)) < .001
    assert abs(model.SpeakerCarrier.Shape.BoundBox.YMax - 62.5) < 1e-7
    contact_area = {}
    for name in ('LChamber', 'RChamber'):
        shape = model.getObject(name).Shape
        contact_area[name] = sum(face.Area for face in shape.Faces
                                 if face.BoundBox.YLength < 1e-7
                                 and abs(face.BoundBox.YMax - 62.5) < 1e-7)
        assert abs(contact_area[name] - (65 * 89 + 14.3 * 80)) < .001

    report = {
        'model_sha256': hashlib.sha256(args.model.read_bytes()).hexdigest(),
        'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        'unchanged_geometry_mm3': unchanged,
        'speaker_mount_region_preserved': True,
        'outer_sidewall_decorations_preserved': True,
        'two_color_face_order_preserved': True,
        'back_plane_y_mm': 62.5,
        'back_contact_area_mm2': contact_area,
        'side_x_mm': 79.3,
        'nominal_side_gap_mm': .7,
        'wing_z_mm': [38, 118],
        'wing_wall_mm': 2.5,
        'physical_fit_verified': False,
        'all_pass': True,
    }
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('GEOMETRY_OK', contact_area, flush=True)


if __name__ == '__main__':
    main()
