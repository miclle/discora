"""Check saved B50K mounting, knob sweep and assembly; run with FreeCAD Python."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import FreeCAD as A
import Part

ROOT=Path(__file__).resolve().parent
V=A.Vector
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--model',type=Path,default=ROOT/'Discora.FCStd')
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--output',type=Path,default=ROOT/'volume-checks.json')
args=p.parse_args()
doc=A.openDocument(str(args.model.resolve()))
old=A.openDocument(str(args.baseline.resolve()))
pose=A.Placement(V(48,18,165+18*27/38),A.Rotation(V(0,1,0),V(0,27/38,-1)))
def local(shape):
    s=shape.copy();s.Placement=pose.inverse().multiply(s.Placement);return s
def world(shape):
    s=shape.copy();s.Placement=pose.multiply(s.Placement);return s
def delta(a,b):return a.cut(b).Volume+b.cut(a).Volume
def equal(a,b):assert abs(a-b)<1e-6,(a,b)
objects={o.Name:o for g in ('Shell','Controls','Carrier','Hardware') for o in doc.getObject(g).Group}
def clashes(shape,excluded=()):
    hits=[]
    for n,o in objects.items():
        if n in excluded or not shape.BoundBox.intersect(o.Shape.BoundBox):continue
        v=shape.common(o.Shape).Volume
        if v>.001:hits.append(dict(object=n,volume_mm3=v))
    return hits
report=dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
            baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
            unchanged_finished_parts_difference_mm3={},physical_assembly_test=False)
for n,o in objects.items():
    assert o.Shape.isValid() and o.Shape.Solids,n
    if n in ('FrontShell','Knob','Encoder','VolumePot'):continue
    d=delta(o.Shape,old.getObject(n).Shape)
    assert d<.001,(n,d)
    report['unchanged_finished_parts_difference_mm3'][n]=d
print('UNCHANGED_PARTS',len(report['unchanged_finished_parts_difference_mm3']),flush=True)
zone=world(Part.makeBox(26,40,28,V(-13,-16,-14)))
front=doc.FrontShell.Shape;before=old.FrontShell.Shape
report['front_change_outside_mount_mm3']=front.cut(before).cut(zone).Volume+before.cut(front).cut(zone).Volume
assert report['front_change_outside_mount_mm3']<.001
shell=local(front).common(Part.makeBox(30,25,30,V(-15,-1,-14)))
body=local(doc.VolumePot.Shape);b=body.BoundBox
for actual,expected in zip((b.XLength,b.YLength,b.ZLength,b.YMin,b.ZMin),(9.5,14.5,11.2,3.6,-2.7)):equal(actual,expected)
report['body_local_size_xyz_mm']=[b.XLength,b.YLength,b.ZLength]
report['shaft_center_to_pin_face_mm']=-b.ZMin
# Measure the saved shell web and outside thickness independently of build constants.
web=Part.makeLine(V(4.5,-1,0),V(4.5,8,0)).common(shell)
equal(sum(e.Length for e in web.Edges),2)
outer=Part.makeLine(V(14,-1,0),V(14,8,0)).common(shell)
equal(sum(e.Length for e in outer.Edges),5)
hole=Part.makeCylinder(3.6,2,V(0,1.6,0),V(0,1,0))
assert shell.common(hole).Volume<.001
report.update(panel_hole_mm=7.2,local_web_mm=2,remaining_panel_mm=5)
shaft=local(doc.Encoder.Shape)
equal(shaft.BoundBox.YMin,-11.4);equal(shaft.BoundBox.YMax,3.6)
# Nut section between its faces: real hex across flats, not a circumscribed disk.
section=shaft.common(Part.makeBox(20,.1,20,V(-10,0,-10))).BoundBox
equal(section.ZLength,9.8);equal(section.XLength,9.8*2/math.sqrt(3))
report.update(nut_across_flats_mm=9.8,nut_thickness_mm=1.9,thread_beyond_nut_mm=1.1)
knob=local(doc.Knob.Shape)
assert len(knob.Solids)==2, 'Black body and white marker must remain separate volumes'
knob=knob.Solids[0].fuse(knob.Solids[1]).removeSplitter();b=knob.BoundBox
# BSpline fillet control points overestimate the full B-rep box; measure the disk slice.
disk=knob.common(Part.makeBox(26,.01,26,V(-13,.5,-13))).BoundBox
for actual,expected in zip((disk.XLength,disk.ZLength,b.YMin,b.YMax),(24,24,-12.9,1)):equal(actual,expected)
assert len(knob.Solids)==1
roof=Part.makeLine(V(0,-13.5,0),V(0,-11,0)).common(knob)
equal(sum(e.Length for e in roof.Edges),1.2)
report.update(knob_disk_diameter_mm=24,knob_height_mm=13.9,knob_face_above_panel_mm=12.9,
              knob_inset_mm=1,recess_depth_mm=1.6,recess_floor_gap_mm=.6,radial_gap_mm=.4,shaft_bore_mm=6,grip_tip_diameter_mm=5.6,shaft_tip_clearance_mm=.3,roof_thickness_mm=1.2)
# Exterior recess and the reduced cross section are measured from saved solids.
floor=Part.makeLine(V(10,-1,0),V(10,8,0)).common(shell)
equal(sum(e.Length for e in floor.Edges),3.4)
for depth,radius in ((.01,12.79),(.5,12.4),(1.59,12.4)):
    probe=Part.makeCylinder(radius-.001,.001,V(0,depth,0),V(0,1,0))
    assert shell.common(probe).Volume<.001
section=knob.common(Part.makeBox(26,.01,26,V(-13,-8,-13))).BoundBox
equal(section.XLength,24);equal(section.ZLength,24)
arm=knob.common(Part.makeBox(.01,.01,26,V(6,-8,-13))).BoundBox
equal(arm.ZLength,6.8)
report.update(cross_span_mm=24,cross_arm_width_mm=6.8)
# The slimmer arms must not expose the nut chamber between their roots.
# Probe a complete annular roof, not just material directly under an arm.
roof_ring=Part.makeCylinder(6,.1,V(0,-2.6,0),V(0,1,0)).cut(
    Part.makeCylinder(3,.1,V(0,-2.6,0),V(0,1,0)))
assert roof_ring.cut(knob).Volume<.001,'Nut chamber breaks through between arms'
# No side screw bore: only planes, fillets and cylinders parallel to the shaft.
side_bores=[f for f in knob.Faces if isinstance(f.Surface,Part.Cylinder) and f.Surface.Radius>1
            and abs(f.Surface.Axis.dot(V(0,1,0)))<1e-6]
assert not side_bores
press=knob.common(shaft)
band=Part.makeCylinder(2.9001,7.0002,V(0,-10.2001,0),V(0,1,0)).cut(
    Part.makeCylinder(2.7999,7.0002,V(0,-10.2001,0),V(0,1,0)))
assert 0<press.Volume<4.2 and press.cut(band).Volume<.001
assert len(press.Solids)==6,len(press.Solids)
report['press_fit']=dict(rib_count=6,radial_interference_max_mm=.1,
    intended_overlap_mm3=press.Volume,unintended_overlap_mm3=press.cut(band).Volume,
    printed_fit_verified=False)
pins=Part.makeBox(9.5,14.5,3.5,V(-4.75,3.6,-6.2))
wire=Part.makeBox(10.1,14.5,3.8,V(-5.05,3.6,-10))
report['terminal_and_wire_clearance']={}
for n,s in [('pin_envelope',pins),('wire_allowance',wire)]:
    hits=clashes(world(s),('VolumePot','Encoder'))
    assert not hits,(n,hits)
    report['terminal_and_wire_clearance'][n]=dict(clashes=hits,footprint_verified=False)
# Cylinder bounds every angular pose outside the shaft/nut. Remove the shared
# axis hole and nut relief to avoid mistaking mating hardware for obstruction.
sweep=Part.makeCylinder(12,13.9,V(0,-12.9,0),V(0,1,0))
sweep=sweep.cut(Part.makeCylinder(3,14,V(0,-13,0),V(0,1,0)))
sweep=sweep.cut(Part.makeCylinder(6,3.5,V(0,-2.4,0),V(0,1,0)))
hits=clashes(world(sweep),('Knob',))
assert not hits,hits
report['continuous_360_degree_knob_envelope_clashes']=hits
# After removing knob and nut, withdraw the body/shaft inward along the axis.
bare=body.fuse(Part.makeCylinder(3.4,5,V(0,-1.4,0),V(0,1,0))).fuse(
    Part.makeCylinder(2.9,10,V(0,-11.4,0),V(0,1,0)))
hits=[]
for step in range(31):
    s=bare.copy();s.translate(V(0,step*.5,0))
    found=clashes(world(s),('VolumePot','Encoder','Knob'))
    if found:hits.append(dict(inward_mm=step*.5,hits=found))
assert not hits,hits
report['pot_removal']=dict(method='31 exact B-rep samples at 0.5 mm; front cover detached before servicing',clashes=hits)
# Check a socket driver on the nut before fitting knob (12.5 mm outer diameter).
tool=Part.makeCylinder(6.25,20,V(0,-20.3,0),V(0,1,0))
hits=clashes(world(tool),('Knob','Encoder'))
assert not hits,hits
report['nut_tool_envelope_clashes']=hits
report['key_face_order_preserved']={}
for n in ('PlayPauseKey','EjectKey','PrevKey','NextKey'):
    a=doc.getObject(n).Shape.Faces;b=old.getObject(n).Shape.Faces
    same=len(a)==len(b) and all(abs(x.Area-y.Area)<1e-7 and (x.CenterOfMass-y.CenterOfMass).Length<1e-7 for x,y in zip(a,b))
    assert same,n
    report['key_face_order_preserved'][n]=same
report['limits']=['Pin pitch/rows and wire bend radius are not measured; rectangular envelopes only.',
                  'Six sacrificial grip ribs intentionally enter the spline envelope by up to 0.1 mm radially; insertion force, torque and pull-out retention need a printed sample.',
                  'Nut threads and spline teeth are envelopes; switch electrical ratings/pinout are unverified.',
                  'GUI unavailable; original GUI resource bytes retained, no interactive color readback.']
report['all_pass']=True
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('VOLUME_CHECKS_OK',flush=True)
