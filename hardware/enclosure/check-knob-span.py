"""Verify a knob-only span revision against its validated predecessor (FreeCAD Python)."""
import argparse
import hashlib
import json
from pathlib import Path
import FreeCAD as A
import Part

ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--model',type=Path,default=ROOT/'Discora.FCStd')
p.add_argument('--previous',type=Path,required=True)
p.add_argument('--output',type=Path,default=ROOT/'knob-span-checks.json')
args=p.parse_args()
doc=A.openDocument(str(args.model.resolve()));old=A.openDocument(str(args.previous.resolve()))
V=A.Vector
pose=A.Placement(V(48,18,165+18*27/38),A.Rotation(V(0,1,0),V(0,27/38,-1)))
def local(s):
    s=s.copy();s.Placement=pose.inverse().multiply(s.Placement);return s
def difference(a,b):return a.cut(b).Volume+b.cut(a).Volume
objects={o.Name:o for g in ('Shell','Controls','Carrier','Hardware') for o in doc.getObject(g).Group}
same={}
for n,o in objects.items():
    if n=='Knob':continue
    before=old.getObject(n).Shape
    # Exact saved topology equality avoids expensive repeated grille booleans.
    equal=o.Shape.exportBrepToString()==before.exportBrepToString()
    assert equal,n
    same[n]=True
a=local(doc.Knob.Shape);b=local(old.Knob.Shape)
assert a.isValid() and len(a.Solids) in (1,2)
if len(a.Solids)==2:a=a.Solids[0].fuse(a.Solids[1]).removeSplitter()
assert len(a.Solids)==1
cross=a.common(Part.makeBox(26,.01,26,V(-13,-8,-13))).BoundBox
assert abs(cross.XLength-24)<1e-6 and abs(cross.ZLength-24)<1e-6
arm=a.common(Part.makeBox(.01,.01,26,V(6,-8,-13))).BoundBox
assert abs(arm.ZLength-6.8)<1e-6
assert abs(a.BoundBox.YMin+12.9)<1e-6 and abs(a.BoundBox.YMax-1)<1e-6
# Check the full mounting core; the outermost 0.2 mm of the root receives a foot fillet.
centre=Part.makeCylinder(7.0,16,V(0,-14,0),V(0,1,0))
centre_delta=difference(a.common(centre),b.common(centre))
assert centre_delta<.001,'Press-fit bore, nut relief or central root changed'
envelope=Part.makeCylinder(12,13.9,V(0,-12.9,0),V(0,1,0))
outside=a.cut(envelope).Volume
assert outside<.001,'Grip exceeds the already-checked 24 mm rotation envelope'
clashes=[];overlap=0
for n,o in objects.items():
    if n=='Knob' or not doc.Knob.Shape.BoundBox.intersect(o.Shape.BoundBox):continue
    v=doc.Knob.Shape.common(o.Shape).Volume
    if n=='Encoder':
        overlap=v
        previous=old.Knob.Shape.common(old.Encoder.Shape).Volume
        assert abs(v-previous)<1e-6 and 0<v<4.2
    elif v>.001:clashes.append(dict(object=n,volume_mm3=v))
assert not clashes,clashes
report=dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
    previous_model_sha256=hashlib.sha256(args.previous.read_bytes()).hexdigest(),
    unchanged_finished_shape_brep=same,cross_span_mm=[cross.XLength,cross.ZLength],
    arm_width_mm=arm.ZLength,central_radius_7_difference_mm3=centre_delta,
    outside_previous_rotation_envelope_mm3=outside,intentional_press_fit_mm3=overlap,
    unexpected_clashes=clashes,physical_fit_verified=False,all_pass=True)
args.output.write_text(json.dumps(report,indent=2)+'\n')
print('KNOB_SPAN_OK',len(same),'unchanged finished parts',flush=True)
