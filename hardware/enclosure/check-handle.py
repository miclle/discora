"""Compare a taller-handle model with its saved pre-change baseline (FreeCAD Python)."""
import argparse
from pathlib import Path
import json, hashlib
import FreeCAD as A
import Part
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model',type=Path,default=root/'Discora.FCStd')
parser.add_argument('--baseline',type=Path,required=True)
parser.add_argument('--output',type=Path,default=root/'handle-checks.json')
args=parser.parse_args()
target=args.model;baseline=args.baseline
doc=A.openDocument(str(target.resolve()));old=A.openDocument(str(baseline.resolve()))
report=dict(model_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),unchanged_finished_parts_difference_mm3={})
for group in ('Shell','Controls','Carrier','Hardware'):
 for o in doc.getObject(group).Group:
  assert o.Shape.isValid(),o.Name
  if o.Name=='FrontShell':continue
  b=old.getObject(o.Name).Shape
  delta=o.Shape.cut(b).Volume+b.cut(o.Shape).Volume
  assert delta<.001,(o.Name,delta)
  report['unchanged_finished_parts_difference_mm3'][o.Name]=delta
  print('UNCHANGED',o.Name,flush=True)
a=doc.FrontShell.Shape;b=old.FrontShell.Shape
zone=Part.makeBox(144,7,46,A.Vector(-72,36.5,165+37.5*27/38))
report['front_change_outside_handle_mm3']=a.cut(b).cut(zone).Volume+b.cut(a).cut(zone).Volume
assert report['front_change_outside_handle_mm3']<.001
mirror=a.copy(); mat=A.Matrix();mat.A11=-1;mirror=mirror.transformGeometry(mat)
handle=Part.makeBox(144,7,46,A.Vector(-72,36.5,165+37.5*27/38))
report['handle_mirror_difference_mm3']=a.common(handle).cut(mirror).Volume+mirror.common(handle).cut(a).Volume
assert report['handle_mirror_difference_mm3']<.001
shoulder=doc.FoldSection.Geometry[2].StartPoint.y
height=doc.FoldSection.Geometry[3].StartPoint.y-shoulder
opening=doc.SymmetricCowlTool.Shape.Solids[0].BoundBox
thickness=doc.FoldSection.Geometry[4].StartPoint.x-doc.FoldSection.Geometry[2].StartPoint.x
assert abs(height-45)<1e-6 and abs(thickness-5)<1e-6
assert abs(opening.XLength-90)<1e-6 and abs(opening.ZLength-24)<1e-6
report['handle_height_mm']=height
report['handle_opening_mm']=[opening.XLength,opening.ZLength]
report['handle_thickness_mm']=thickness
rails=[opening.ZMin-shoulder,shoulder+height-opening.ZMax]
assert all(abs(value-10.5)<1e-6 for value in rails)
# Measure the finished solid along the centre line of the upper/lower rails.
for z in (shoulder+5.25,shoulder+height-5.25):
 probe=Part.makeLine(A.Vector(0,35,z),A.Vector(0,45,z))
 assert abs(sum(e.Length for e in doc.FrontShell.Shape.common(probe).Edges)-5)<1e-6
report['lower_upper_rail_height_mm']=rails
report['physical_load_test']=False
report['key_face_order_preserved']={}
for name in ('PlayPauseKey','EjectKey','PrevKey','NextKey'):
 a=doc.getObject(name).Shape.Faces;b=old.getObject(name).Shape.Faces
 same=len(a)==len(b) and all(abs(x.Area-y.Area)<1e-7 and (x.CenterOfMass-y.CenterOfMass).Length<1e-7 for x,y in zip(a,b))
 assert same,name
 report['key_face_order_preserved'][name]=same

report['gui_appearance_check']='GUI resource bytes preserved from baseline; interactive GUI readback not performed.'
args.output.write_text(json.dumps(report,indent=2)+'\n')
print('HANDLE_COMPARE_OK',flush=True)
