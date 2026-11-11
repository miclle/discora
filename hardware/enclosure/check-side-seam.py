"""Check constant-width front rims and a symmetric rear-housing side outline (FreeCAD Python)."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import FreeCAD as A
import Part

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model', type=Path, default=ROOT/'Discora.FCStd')
parser.add_argument('--baseline', type=Path, required=True)
parser.add_argument('--output', type=Path, default=ROOT/'side-seam-checks.json')
args = parser.parse_args()
doc = A.openDocument(str(args.model.resolve()))
old = A.openDocument(str(args.baseline.resolve()))
tol = .001
report = dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
              baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
              unchanged_finished_parts_difference_mm3={}, physical_assembly_test=False)
def difference(a, b):
    if a.exportBrepToString()==b.exportBrepToString():return 0.0
    return a.cut(b).Volume+b.cut(a).Volume

for group in ('Shell', 'Controls', 'Carrier', 'Hardware'):
    for obj in doc.getObject(group).Group:
        assert obj.Shape.isValid(), obj.Name
        if obj.Name in ('FrontShell', 'RearShell', 'SpeakerCarrier'):
            assert len(obj.Shape.Solids) == 1, obj.Name
            continue
        delta = difference(obj.Shape, old.getObject(obj.Name).Shape)
        assert delta < tol, (obj.Name, delta)
        report['unchanged_finished_parts_difference_mm3'][obj.Name] = delta

front, rear = doc.FrontShell.Shape, doc.RearShell.Shape
old_front = old.FrontShell.Shape
# The front may change only at the upper folded edge; rear roof and centered
# side openings, plus the matching carrier outlets, are the other changed areas.
report['changed_parts_outside_allowed_regions_mm3'] = {}
port_zones=Part.makeCompound([Part.makeBox(14,40,80,A.Vector(x,20,40)) for x in (-72,58)])
roof_zone=Part.makeBox(144,81,80,A.Vector(-72,0,160))
for name,zone in [('FrontShell',roof_zone),('RearShell',roof_zone.fuse(port_zones)),('SpeakerCarrier',port_zones)]:
    current,previous=doc.getObject(name).Shape,old.getObject(name).Shape
    delta=difference(current.cut(zone),previous.cut(zone))
    assert delta<tol,(name,delta)
    report['changed_parts_outside_allowed_regions_mm3'][name]=delta
report['shell_overlap_mm3']=front.common(rear).Volume
assert report['shell_overlap_mm3']<tol
# Read a thin exterior-side slab, including the visible port opening, so inner
# DAC pads, screw wells and other deliberately asymmetric hardware do not mask
# the requested symmetry of the rear housing's side elevation.
slab=rear.common(Part.makeBox(.25,100,250,A.Vector(-71,-10,0)))
mirror=A.Matrix();mirror.A22=-1;mirror.A24=85
reflected=slab.copy();reflected.transformShape(mirror,True)
report['rear_side_outline_mirror_difference_mm3']=difference(slab,reflected)
assert report['rear_side_outline_mirror_difference_mm3']<tol
peak=doc.FoldSection.Geometry[5].StartPoint
foot=doc.FoldSection.Geometry[10].StartPoint
rear_foot=doc.FoldSection.Geometry[6].StartPoint
assert abs(foot.y-rear_foot.y)<1e-7
assert abs(peak.x-(foot.x+rear_foot.x)/2)<1e-7
assert abs(peak.y-(165+peak.x*27/38-5*(1+(27/38)**2)**.5))<1e-7
assert abs(rear.BoundBox.ZMax-peak.y)<1e-7
report['rear_outline_yz_mm']=[[foot.x,foot.y],[peak.x,peak.y],[rear_foot.x,rear_foot.y]]
report['rear_center_y_mm']=peak.x
report['front_above_rear_eave_mm']=165-foot.y
report['rear_roof_to_drive_minimum_distance_mm']=doc.RearRoof.Shape.distToShape(doc.Drive.Shape)[0]
assert report['rear_roof_to_drive_minimum_distance_mm']>2
report['port_translation_mm']=[0,2.5,0]
for name in ('LPort','RPort'):
    previous=old.getObject(name).Shape.copy();previous.translate(A.Vector(0,2.5,0))
    assert difference(doc.getObject(name).Shape,previous)<tol,name
    assert abs(doc.getObject(name).Shape.BoundBox.Center.y-peak.x)<1e-7
slope = 27/38
normal = A.Vector(0,-slope,1); normal.normalize()
report['side_normal_thickness_mm'] = {}
report['baseline_side_normal_thickness_mm'] = {}
for x in (-70,70):
    for y in (5,12,24,32,37):
        point = A.Vector(x,y,165+slope*y)
        probe = Part.makeLine(point-normal*10,point+normal*10)
        thickness = sum(e.Length for e in front.common(probe).Edges)
        assert abs(thickness-5) < 1e-6, (x,y,thickness)
        report['side_normal_thickness_mm'][f'{x},{y}'] = thickness
        report['baseline_side_normal_thickness_mm'][f'{x},{y}'] = sum(e.Length for e in old_front.common(probe).Edges)
report['key_and_knob_face_order_preserved'] = {}
for name in ('PlayPauseKey','EjectKey','PrevKey','NextKey','Knob'):
    a,b = doc.getObject(name).Shape.Faces,old.getObject(name).Shape.Faces
    same = len(a)==len(b) and all(abs(x.Area-y.Area)<1e-7 and (x.CenterOfMass-y.CenterOfMass).Length<1e-7 for x,y in zip(a,b))
    assert same,name
    report['key_and_knob_face_order_preserved'][name] = same
with zipfile.ZipFile(args.baseline) as a, zipfile.ZipFile(args.model) as b:
    gui = a.read('GuiDocument.xml')
    refs = list(dict.fromkeys(v for e in ET.fromstring(gui).iter() for k,v in e.attrib.items() if k.lower()=='file' and v))
    assert all(a.read(n)==b.read(n) for n in ['GuiDocument.xml',*refs])
    assert b.namelist()[-len(refs)-1:] == ['GuiDocument.xml',*refs]
report['gui_resources_preserved_in_reference_order'] = True
report['gui_readback_performed'] = False
report['all_pass'] = True
args.output.write_text(json.dumps(report,indent=2)+'\n')
print('SYMMETRIC_REAR_AND_SIDE_SEAM_OK',flush=True)
