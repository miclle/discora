"""Verify the 5 mm rear housing, retained hardware, and fit against a saved baseline."""
import argparse
import hashlib
import json
import runpy
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import FreeCAD as A
import Part

ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--model',type=Path,default=ROOT/'Discora.FCStd')
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--output',type=Path,default=ROOT/'rear-thickness-checks.json')
args=p.parse_args()
d=A.openDocument(str(args.model.resolve()));old=A.openDocument(str(args.baseline.resolve()))
V=A.Vector;tol=.001
report=dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
            baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
            physical_assembly_test=False,unchanged_finished_parts_difference_mm3={})
def difference(a,b):
    if a.exportBrepToString()==b.exportBrepToString():return 0.0
    return a.cut(b).Volume+b.cut(a).Volume
for g in ('Shell','Controls','Carrier','Hardware'):
    for o in d.getObject(g).Group:
        assert o.Shape.isValid(),o.Name
        if o.Name in ('FrontShell','RearShell','SpeakerCarrier','Feet'):continue
        delta=difference(o.Shape,old.getObject(o.Name).Shape)
        assert delta<tol,(o.Name,delta)
        report['unchanged_finished_parts_difference_mm3'][o.Name]=delta
rear=d.RearShell.Shape
normal=V(0,27/38,1);normal.normalize()
probes=[('back',V(0,82,100),V(0,1,0)),('bottom',V(63,40,1),V(0,0,1))]
for side in (-1,1):
    for y,z in ((20,100),(60,130),(30,145)):
        probes.append((f'side_{side}_{y}_{z}',V(side*73,y,z),V(1,0,0)))
roof=d.FoldSection.Geometry[5]
for x,y in ((0,55),(20,60),(-20,75)):
    z=roof.StartPoint.y+(y-roof.StartPoint.x)*(roof.EndPoint.y-roof.StartPoint.y)/(roof.EndPoint.x-roof.StartPoint.x)
    probes.append((f'roof_{x}_{y}',V(x,y,z),normal))
report['rear_body_normal_thickness_samples_mm']={}
for name,point,axis in probes:
    length=sum(e.Length for e in rear.common(Part.makeLine(point-axis*8,point+axis*8)).Edges)
    report['rear_body_normal_thickness_samples_mm'][name]=length
    assert abs(length-5)<1e-6,(name,length)
report['clearances_mm']={}
for a,b in [('RearRoof','Drive'),('Back','Battery'),('LPanel','DAC'),('LPort','SpeakerCarrier'),('RPort','SpeakerCarrier'),('Battery','FrontShell'),('Battery','SpeakerCarrier')]:
    gap=d.getObject(a).Shape.distToShape(d.getObject(b).Shape)[0]
    report['clearances_mm'][a+' / '+b]=gap
    assert gap>=(.3 if a in ('LPort','RPort') else 1)-1e-6,(a,b,gap)
report['roof_to_drive_previous_mm']=old.RearRoof.Shape.distToShape(old.Drive.Shape)[0]
# Floor, rear wall and side wall inner planes remain at their original positions.
report['inner_planes_mm']=dict(floor=d.Base.Shape.BoundBox.ZMax,rear=d.Back.Shape.BoundBox.YMin,
                             left=d.LPanel.Shape.BoundBox.XMax,right=d.RPanel.Shape.BoundBox.XMin)
assert all(abs(report['inner_planes_mm'][k]-v)<1e-7 for k,v in dict(floor=6,rear=77,left=-68,right=68).items())
# Preserve the 2 mm space beneath the pack for the existing strap route.
report['battery_under_pack_space_mm']=d.Battery.Shape.BoundBox.ZMin-d.Base.Shape.BoundBox.ZMax
assert abs(report['battery_under_pack_space_mm']-2)<1e-7
# The side surface including its port is symmetric in side elevation.
slab=rear.common(Part.makeBox(.25,100,260,V(-73,-10,-10)))
m=A.Matrix();m.A22=-1;m.A24=87
ref=slab.copy();ref.transformShape(m,True)
report['rear_side_outline_mirror_difference_mm3']=difference(slab,ref)
assert report['rear_side_outline_mirror_difference_mm3']<tol
report['shell_overlap_mm3']=d.FrontShell.Shape.common(rear).Volume
assert report['shell_overlap_mm3']<tol
report['bottom_corner_cylinders']={}
for name in ('FrontShell','RearShell'):
    shape=d.getObject(name).Shape
    arcs=[f for f in shape.Faces if isinstance(f.Surface,Part.Cylinder)
          and abs(f.Surface.Radius-4)<1e-6 and f.BoundBox.ZMax<5+1e-6]
    assert len(arcs)==2,(name,len(arcs))
    report['bottom_corner_cylinders'][name]=len(arcs)
# Feet move with the lower outside surface; all electronics remain fixed.
previous=old.Feet.Shape.copy();previous.translate(V(0,0,-2))
assert difference(previous,d.Feet.Shape)<tol
report['feet_translation_xyz_mm']=[0,0,-2]

# Sample all depth intervals of the longer side port; the outer decoration remains 2 mm.
aperture_face=runpy.run_path(str(ROOT/'check-port-reinforcement.py'))['aperture_face']
areas=[]
for i in range(31):
    x=-72.95+i*.25
    face=aperture_face(x);face.translate(V(0,3.5,0))
    opening=face.cut(rear)
    areas.append(dict(x_mm=x,free_area_mm2=opening.Area,passages=len(opening.Faces)))
report['side_port_free_area_sections']=areas
report['side_port_minimum_sampled_area_mm2']=min(row['free_area_mm2'] for row in areas)
assert abs(report['side_port_minimum_sampled_area_mm2']-384.244125)<1e-5

report['key_and_knob_face_order_preserved']={}
for name in ('PlayPauseKey','EjectKey','PrevKey','NextKey','Knob'):
    a,b=d.getObject(name).Shape.Faces,old.getObject(name).Shape.Faces
    same=len(a)==len(b) and all(abs(x.Area-y.Area)<1e-7 and (x.CenterOfMass-y.CenterOfMass).Length<1e-7 for x,y in zip(a,b))
    assert same,name
    report['key_and_knob_face_order_preserved'][name]=same
with zipfile.ZipFile(args.baseline) as a,zipfile.ZipFile(args.model) as b:
    gui=a.read('GuiDocument.xml')
    refs=list(dict.fromkeys(v for e in ET.fromstring(gui).iter() for k,v in e.attrib.items() if k.lower()=='file' and v))
    assert all(a.read(n)==b.read(n) for n in ['GuiDocument.xml',*refs])
report['gui_resources_preserved']=True
report['gui_readback_performed']=False
report['all_pass']=True
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('REAR_THICKNESS_OK',report['clearances_mm'],flush=True)
