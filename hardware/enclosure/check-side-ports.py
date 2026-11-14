"""Check integral rear-shell ports, symmetry and preservation of unrelated parts.

Use --baseline with the saved pre-integration model to verify the change boundary.
Assembly motion is covered separately by check-assembly.py.
"""
import argparse
import hashlib
import json
from pathlib import Path
import FreeCAD as A
import Part

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path, default=ROOT/'Discora.FCStd')
    p.add_argument('--baseline', type=Path)
    p.add_argument('--output', type=Path, default=ROOT/'side-port-checks.json')
    args = p.parse_args()
    doc = A.openDocument(str(args.model.resolve()))
    rear = doc.RearShell.Shape
    assert rear.isValid() and len(rear.Solids) == 1
    report = dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                  freecad_version=A.Version()[:3], rear_valid=True, rear_solids=1,
                  rigid_pla_pieces=11, ports={}, physical_print_test=False,
                  acoustic_sealing_verified=False)
    for name, sign in [('LPort', -1), ('RPort', 1)]:
        port = doc.getObject(name)
        chamber = doc.getObject('LChamber' if sign < 0 else 'RChamber')
        assert port in doc.Construction.Group and port not in doc.Shell.Group
        assert name in doc.RearShell.ConstructionObjects
        missing = port.Shape.cut(rear).Volume
        gap = (chamber.Shape.BoundBox.XMin-port.Shape.BoundBox.XMax if sign < 0
               else port.Shape.BoundBox.XMin-chamber.Shape.BoundBox.XMax)
        distance = port.Shape.distToShape(chamber.Shape)[0]
        assert missing < .001 and abs(gap-.3) < 1e-6, (name, missing, gap)
        # The corresponding former ear heights must be solid at the current wall.
        sealed = []
        for z in (39, 117):
            probe = Part.makeCylinder(.79, 2.9, A.Vector(sign*(doc.Back.Shape.BoundBox.XLength/2-.05), port.Shape.BoundBox.Center.y, z),
                                      A.Vector(-sign, 0, 0))
            absent = probe.cut(rear).Volume
            assert absent < .001, (name, z, absent)
            sealed.append(dict(center_z_mm=z, missing_wall_mm3=absent))
        report['ports'][name] = dict(missing_from_rear_mm3=missing,
                                    axial_chamber_clearance_mm=gap,
                                    minimum_chamber_distance_mm=distance,
                                    former_screw_holes_sealed=sealed)
    matrix = A.Matrix(); matrix.A11 = -1
    def reflected(shape):
        copy = shape.copy(); copy.transformShape(matrix, True)
        return copy
    def difference(a, b):
        if a.exportBrepToString() == b.exportBrepToString():
            return 0.0
        return a.cut(b).Volume + b.cut(a).Volume
    port_difference = difference(reflected(doc.LPort.Shape), doc.RPort.Shape)
    old_pads = doc.getObject('DACPads')
    if old_pads:
        exception = old_pads.Shape.fuse(reflected(old_pads.Shape))
        rear = rear.cut(exception)
    rear_difference = difference(rear, reflected(rear))
    assert max(port_difference, rear_difference) < .001
    rear_key = 'rear_except_existing_dac_pads' if old_pads else 'rear'
    report['mirror_difference_mm3'] = {'ports': port_difference, rear_key: rear_difference}
    if args.baseline:
        baseline = A.openDocument(str(args.baseline.resolve()))
        differences = {}
        for group in ('Shell', 'Controls', 'Carrier', 'Hardware'):
            for obj in baseline.getObject(group).Group:
                if obj.Name in ('RearShell', 'LPort', 'RPort'):
                    continue
                print('BASELINE_COMPARE', obj.Name, flush=True)
                differences[obj.Name] = difference(obj.Shape, doc.getObject(obj.Name).Shape)
        assert max(differences.values()) < .001, differences
        report['baseline_sha256'] = hashlib.sha256(args.baseline.read_bytes()).hexdigest()
        report['unchanged_finished_parts_difference_mm3'] = differences
        A.closeDocument(baseline.Name)
    report['limits'] = [
        'Shortened tubes butt against the chamber with 0.3 mm nominal clearance; no gasket is modeled.',
        'Air-path continuity is checked in validation.json; acoustic tuning and leakage require physical tests.',
        'Printing, support removal and strength are not established by B-rep or mesh checks.']
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    A.closeDocument(doc.Name)
    print('SIDE_PORT_CHECKS_OK', flush=True)


if __name__ == '__main__':
    main()
