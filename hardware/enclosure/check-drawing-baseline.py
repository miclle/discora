"""Bridge the last annotated drawing revision to the current saved CAD.

Only unchanged objects may reuse older measurements or material face indices.
P2/P3 are measured and rendered again, including the retained P2 screw ribs.
"""
import argparse
import hashlib
import json
from pathlib import Path

import FreeCAD as A

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    source = ROOT / 'Discora.FCStd'
    old_hash = hashlib.sha256(args.baseline.read_bytes()).hexdigest()
    assert old_hash == json.loads((ROOT/'p3-flat-back-checks.json').read_text())['model_sha256']
    doc = A.openDocument(str(source))
    old = A.openDocument(str(args.baseline.resolve()))
    differences, faces = {}, {}
    for group in ('Shell', 'Controls', 'Carrier', 'Hardware'):
        for obj in doc.getObject(group).Group:
            if obj.Name in ('RearShell', 'SpeakerCarrier'):
                continue
            before, after = old.getObject(obj.Name).Shape, obj.Shape
            same = before.exportBrepToString() == after.exportBrepToString()
            delta = 0 if same else before.cut(after).Volume + after.cut(before).Volume
            assert delta < .001, (obj.Name, delta)
            differences[obj.Name] = delta
            if obj.Name in ('PlayPauseKey', 'EjectKey', 'PrevKey', 'NextKey', 'Knob'):
                assert len(before.Faces) == len(after.Faces)
                equal = all(abs(a.Area-b.Area)<1e-7 and (a.CenterOfMass-b.CenterOfMass).Length<1e-7
                            for a,b in zip(before.Faces, after.Faces))
                assert equal, obj.Name
                faces[obj.Name] = True
    report = dict(model_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  baseline_sha256=old_hash, unchanged_finished_parts_difference_mm3=differences,
                  color_face_order_preserved=faces, all_pass=True)
    (ROOT/'drawing-baseline-checks.json').write_text(json.dumps(report, indent=2)+'\n')
    print('DRAWING_BASELINE_OK', len(differences), flush=True)


if __name__ == '__main__':
    main()
