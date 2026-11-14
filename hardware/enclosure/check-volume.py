"""Check saved PCB B50K envelope, mounting and assembly with FreeCAD Python."""
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
p.add_argument('--baseline',type=Path,help='Optional predecessor for the control-layout comparison')
p.add_argument('--output',type=Path,default=ROOT/'control-volume-checks.json')
args=p.parse_args()
doc=A.openDocument(str(args.model.resolve()))
old=A.openDocument(str(args.baseline.resolve())) if args.baseline else doc
pose=A.Placement(V(52,20,165+20*27/38),A.Rotation(V(0,1,0),V(0,27/38,-1)))
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
            baseline_sha256=hashlib.sha256((args.baseline or args.model).read_bytes()).hexdigest(),
            unchanged_finished_parts_difference_mm3={},physical_assembly_test=False)
for n,o in objects.items():
    assert o.Shape.isValid() and o.Shape.Solids,n
    if n in ('FrontShell','VolumePot','Knob','Encoder','ButtonRetainer') or n.endswith(('Key','Switch')):continue
    d=delta(o.Shape,old.getObject(n).Shape)
    assert d<.001,(n,d)
    report['unchanged_finished_parts_difference_mm3'][n]=d
print('UNCHANGED_PARTS',len(report['unchanged_finished_parts_difference_mm3']),flush=True)
front=doc.FrontShell.Shape;before=old.FrontShell.Shape
clip=Part.makeBox(174,150,100,V(-87,-25,150))
changes=[front.common(clip).cut(before.common(clip)),before.common(clip).cut(front.common(clip))]
zone=Part.makeCompound([Part.makeBox(45,45,44,V(-75,0,151)),Part.makeBox(40,62,52,V(31,0,140))])
# OCCT can return a non-null, empty compound for the no-added-material case.
outside=[s.cut(zone) for s in changes if s.Solids]
report['front_change_outside_mount_mm3']=sum(s.Volume for s in outside if s.Solids)
assert report['front_change_outside_mount_mm3']<.001
shell=local(front).common(Part.makeBox(30,35,40,V(-15,-1,-20)))
body=local(doc.VolumePot.Shape);b=body.BoundBox
for actual,expected in zip((b.XLength,b.YLength,b.ZLength,b.XMin,b.YMin,b.ZMin),(15,26.2,35,-6.5,3.6,-17.5)):equal(actual,expected)
assert len(body.Solids)==4
pcb=body.Solids[1].BoundBox
for actual,expected in zip((pcb.XLength,pcb.YLength,pcb.ZLength),(1.5,26.2,35)):equal(actual,expected)
report.update(module_local_size_xyz_mm=[b.XLength,b.YLength,b.ZLength],
              pcb_size_width_depth_thickness_mm=[pcb.ZLength,pcb.YLength,pcb.XLength],
              module_rotation_about_shaft_deg=90,pcb_front_edge_flush_with_mount=True,
              original_body_and_shaft_cross_section_retained_as_nominal=True)
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
section=knob.common(Part.makeBox(30,.01,30,V(-15,-8,-15))).BoundBox
equal(section.XLength,28);equal(section.ZLength,28)
arm=knob.common(Part.makeBox(.01,.01,26,V(6,-8,-13))).BoundBox
equal(arm.ZLength,6.8)
report.update(cross_span_mm=28,cross_arm_width_mm=6.8)
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
# Fill every gap in the simplified module; don't rely on invented connector voids.
envelope=Part.makeBox(15,26.2,35,V(-6.5,3.6,-17.5))
hits=clashes(world(envelope),('VolumePot','Encoder'))
assert not hits,hits
report['complete_module_envelope']={'clashes':hits,'plugged_connectors_included':True,
    'extra_connector_thickness_mm':0,'exact_connector_footprint_verified':False}
report['module_clearances_mm']={n:world(envelope).distToShape(o.Shape)[0] for n,o in objects.items()
                               if n not in ('VolumePot','Encoder','Knob')}
# Exact translational sweep of the filled convex box with the detached cover.
# A global axis-aligned box would falsely occupy the space below the slope.
moving=world(envelope);travel=V(0,-140,0)
leading=[face.extrude(travel) for face in moving.Faces if face.normalAt(0,0).dot(travel)>1e-7]
sweep=moving.multiFuse(leading).removeSplitter()
assert sweep.isValid() and len(sweep.Solids)==1
fixed=['RearShell','SpeakerCarrier','LDriver','RDriver','Amp','AmpChip','MCU','MCUChip',
       'DAC','DACChip','Drive','DriveRetainer','Bridge','Battery','Feet']
fixed += [n for n in objects if n not in fixed and n not in ('FrontShell','VolumePot','Knob','Encoder','ButtonRetainer','Window','StatusArt','DisplayPCB','DisplayHeader','DisplayRetainer') and not n.endswith(('Key','Switch'))]
fixed += ['XHVolumeSwitch']
intersections={n:sweep.common(objects[n].Shape).Volume for n in fixed}
assert all(v<.001 for v in intersections.values()),intersections
report['module_front_cover_sweep']=dict(
    method='continuous exact translation sweep of the filled box, formed by extruding its leading faces',
    translation_xyz_mm=[0,-140,0],fixed=fixed,intersections_mm3=intersections,cables_disconnected=True)
original=world(Part.makeBox(35,26.2,15,V(-17.5,3.6,-6.5)))
report['original_orientation_baseline_clashes_mm3']={n:original.common(old.getObject(n).Shape).Volume
    for n in ('FrontShell','MCUChip')}
# Cylinder bounds every angular pose outside the shaft/nut. Remove the shared
# axis hole and nut relief to avoid mistaking mating hardware for obstruction.
sweep=Part.makeCylinder(14,12.5,V(0,-12.9,0),V(0,1,0)).fuse(Part.makeCylinder(12,1.4,V(0,-.4,0),V(0,1,0)))
sweep=sweep.cut(Part.makeCylinder(3,14,V(0,-13,0),V(0,1,0)))
sweep=sweep.cut(Part.makeCylinder(6,3.5,V(0,-2.4,0),V(0,1,0)))
hits=clashes(world(sweep),('Knob',))
assert not hits,hits
report['continuous_360_degree_knob_envelope_clashes']=hits
# After removing knob and nut, withdraw the body/shaft inward along the axis.
# The front cover has already moved 140 mm forward (sweep checked above).
# Its attached controls retain their relative poses; fixed chassis parts are
# no longer next to the module. In-place inward removal is not the service path.
bare=envelope.fuse(Part.makeCylinder(3.4,5,V(0,-1.4,0),V(0,1,0))).fuse(
    Part.makeCylinder(2.9,10,V(0,-11.4,0),V(0,1,0)))
hits=[]
for step in range(31):
    s=bare.copy();s.translate(V(0,step*.5,0))
    found=clashes(world(s),('VolumePot','Encoder','Knob',*fixed))
    if found:hits.append(dict(inward_mm=step*.5,hits=found))
assert not hits,hits
report['pot_removal']=dict(method='31 exact B-rep samples at 0.5 mm relative to the detached front-cover assembly',
    prerequisite='Front cover translated 140 mm forward and cables disconnected; remove knob and nut before withdrawing module',
    fixed_chassis_excluded_after_cover_removal=fixed,clashes=hits)
# Check a socket driver on the nut before fitting knob (12.5 mm outer diameter).
tool=Part.makeCylinder(6.25,20,V(0,-20.3,0),V(0,1,0))
hits=clashes(world(tool),('Knob','Encoder'))
assert not hits,hits
report['nut_tool_envelope_clashes']=hits
report['key_face_order_preserved']={}
for n in ('PlayPauseKey','EjectKey','PrevKey','NextKey'):
    current=doc.getObject(n).Shape;previous=old.getObject(n).Shape
    offset=current.BoundBox.Center-previous.BoundBox.Center
    a=current.Faces;b=previous.Faces
    same=len(a)==len(b) and all(abs(x.Area-y.Area)<1e-7 and (x.CenterOfMass-y.CenterOfMass-offset).Length<1e-7 for x,y in zip(a,b))
    assert same,n
    report['key_face_order_preserved'][n]=same
report['limits']=['PCB dimensions, flush front edge and total 15 mm plugged thickness are user-confirmed; connector/pin shapes are rectangular envelopes.',
                  'Original bare-B50K body, shaft diameter, bushing and body-to-PCB contact datum are retained as nominal assumptions; physical fit remains unverified.',
                  'The module is rotated 90 degrees about its shaft axis; knob index must be aligned to the actual switch-off stop during assembly.',
                  'Remote wire routing and service unplugging stroke are not included in the static plugged envelope.',
                  'Six sacrificial grip ribs intentionally enter the spline envelope by up to 0.1 mm radially; insertion force, torque and pull-out retention need a printed sample.',
                  'Nut threads and spline teeth are envelopes; switch electrical ratings/pinout are unverified.',
                  'Black and white volume/material checks are recorded separately by export-dual-color-knob.py.']
report['all_pass']=True
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('VOLUME_CHECKS_OK',flush=True)
