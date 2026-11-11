"""Compare R4 lower shell corners with the saved pre-change model (FreeCAD Python)."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import FreeCAD as A
import Part

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model', type=Path, default=ROOT/'Discora.FCStd')
parser.add_argument('--baseline', type=Path, required=True)
parser.add_argument('--output', type=Path, default=ROOT/'bottom-corner-checks.json')
args = parser.parse_args()
doc = A.openDocument(str(args.model.resolve()))
old = A.openDocument(str(args.baseline.resolve()))
report = dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
              baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
              radius_mm=4, unchanged_finished_parts_difference_mm3={},
              shell_checks={}, physical_print_test=False, gui_readback_performed=False)
tol = .001

def difference(a, b):
    if a.exportBrepToString() == b.exportBrepToString():
        return 0.0
    return a.cut(b).Volume + b.cut(a).Volume

zones = Part.makeCompound([Part.makeBox(4,80,4,A.Vector(x,0,3)) for x in (-71,67)])
mirror = A.Matrix(); mirror.A11 = -1
for group in ('Shell','Controls','Carrier','Hardware'):
    for obj in doc.getObject(group).Group:
        current, previous = obj.Shape, old.getObject(obj.Name).Shape
        assert current.isValid() and current.Solids, obj.Name
        if obj.Name not in ('FrontShell','RearShell'):
            delta = difference(current, previous)
            assert delta < tol, (obj.Name, delta)
            report['unchanged_finished_parts_difference_mm3'][obj.Name] = delta
            continue
        assert len(current.Solids) == 1
        removed = previous.cut(current)
        reflected = removed.copy(); reflected.transformShape(mirror, True)
        metrics = dict(removed_mm3=removed.Volume, added_mm3=current.cut(previous).Volume,
                       change_outside_bottom_corners_mm3=removed.cut(zones).Volume,
                       removed_material_mirror_difference_mm3=difference(removed,reflected))
        assert metrics['removed_mm3'] > 0
        assert all(value < tol for key,value in metrics.items() if key != 'removed_mm3'), metrics
        assert abs(obj.BottomCornerRadius.Value-4) < 1e-7
        # Each shell has two cylindrical patches with the same radius as the handle.
        arcs = [f for f in current.Faces if isinstance(f.Surface,Part.Cylinder)
                and abs(f.Surface.Radius-4)<1e-7 and f.BoundBox.ZMax<7.00001]
        assert len(arcs) == 2, (obj.Name,len(arcs))
        metrics['r4_surface_count'] = len(arcs)
        for axis in 'XYZ':
            for end in ('Min','Max'):
                assert abs(getattr(current.BoundBox,axis+end)-getattr(previous.BoundBox,axis+end))<1e-6
        report['shell_checks'][obj.Name] = metrics
# Top reference and all source pieces remain identical; only final P1/P2 are trimmed.
assert difference(doc.CowlEdges.Shape,old.CowlEdges.Shape)<tol
assert any(isinstance(f.Surface,Part.Cylinder) and abs(f.Surface.Radius-4)<1e-7
           and f.BoundBox.ZMin>230 for f in doc.CowlEdges.Shape.Faces)
report['shell_overlap_mm3'] = doc.FrontShell.Shape.common(doc.RearShell.Shape).Volume
assert report['shell_overlap_mm3']<tol
slab=doc.RearShell.Shape.common(Part.makeBox(.25,100,250,A.Vector(-71,-10,0)))
mirror=A.Matrix();mirror.A22=-1;mirror.A24=85
reflected=slab.copy();reflected.transformShape(mirror,True)
report['rear_side_outline_mirror_difference_mm3']=difference(slab,reflected)
assert report['rear_side_outline_mirror_difference_mm3']<tol
report['key_and_knob_face_order_preserved']={}
for name in ('PlayPauseKey','EjectKey','PrevKey','NextKey','Knob'):
    a,b=doc.getObject(name).Shape.Faces,old.getObject(name).Shape.Faces
    same=len(a)==len(b) and all(abs(x.Area-y.Area)<1e-7 and (x.CenterOfMass-y.CenterOfMass).Length<1e-7 for x,y in zip(a,b))
    assert same,name
    report['key_and_knob_face_order_preserved'][name]=same
with zipfile.ZipFile(args.baseline) as a,zipfile.ZipFile(args.model) as b:
    gui=a.read('GuiDocument.xml')
    refs=list(dict.fromkeys(v for e in ET.fromstring(gui).iter() for k,v in e.attrib.items() if k.lower()=='file' and v))
    assert all(a.read(n)==b.read(n) for n in ['GuiDocument.xml',*refs])
    assert b.namelist()[-len(refs)-1:]==['GuiDocument.xml',*refs]
report['gui_resources_preserved_in_reference_order']=True
report['all_pass']=True
args.output.write_text(json.dumps(report,indent=2)+'\n')
print('BOTTOM_CORNERS_OK',flush=True)
