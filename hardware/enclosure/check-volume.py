"""Check saved bare B50K, solder and lead envelopes, mounting and assembly with FreeCAD Python."""
import argparse
import ast
import zipfile
import struct
import xml.etree.ElementTree as ET
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
def delta(a,b):return 0.0 if a.exportBrepToString()==b.exportBrepToString() else a.cut(b).Volume+b.cut(a).Volume
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
    if n in ('FrontShell','VolumePot'):continue
    d=delta(o.Shape,old.getObject(n).Shape)
    assert d<.001,(n,d)
    report['unchanged_finished_parts_difference_mm3'][n]=d
print('UNCHANGED_PARTS',len(report['unchanged_finished_parts_difference_mm3']),flush=True)
# Rebuild only the local component function and compare with saved geometry.
node=next(n for n in ast.parse((ROOT/'build.FCMacro').read_text()).body
          if isinstance(n,ast.FunctionDef) and n.name=='volume_shapes')
scope=dict(Part=Part,math=math,V=V,X=V(1,0,0),Y=V(0,1,0),Z=V(0,0,1))
exec(compile(ast.Module(body=[node],type_ignores=[]),'volume_shapes','exec'),scope)
expected=scope['volume_shapes']()
report['build_source_difference_mm3']={}
for key,name in [('body','VolumePot'),('shaft','Encoder'),('knob','Knob'),
                 ('solder','VolumeSolderClearance'),('audio_lead','VolumeAudioLeadClearance')]:
 value=delta(world(expected[key]),doc.getObject(name).Shape)
 assert value<.001,(name,value)
 report['build_source_difference_mm3'][name]=value
assert sum(delta(world(expected['pocket']),solid)<.001 for solid in doc.CowlTool.Shape.Solids)==1
report['source_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                       ('build.FCMacro','perfboard_geometry.py','rear_setback_geometry.py')}
with zipfile.ZipFile(args.model) as archive:
 xml=ET.fromstring(archive.read('GuiDocument.xml'))
 vp=next(el for el in xml.iter('ViewProvider') if el.get('name')=='VolumePot')
 ref=next(iter(next(el for el in vp.iter('Property') if el.get('name')=='ShapeAppearance'))).get('file')
 raw=archive.read(ref);count=struct.unpack('<I',raw[:4])[0]
 assert count==len(doc.VolumePot.Shape.Faces) and len(raw)==4+count*36
 for name in ('VolumeSolderClearance','VolumeAudioLeadClearance'):
  vp=next(el for el in xml.iter('ViewProvider') if el.get('name')==name)
  visibility=next(el for el in vp.iter('Property') if el.get('name')=='Visibility')
  assert next(iter(visibility)).get('value')=='false'
report['gui_payload']=dict(volume_face_material_count=count,new_allowances_hidden=True,gui_reopen_verified=False)
print('BUILD_SOURCE_AND_GUI_PAYLOAD_OK',flush=True)

front=doc.FrontShell.Shape;before=old.FrontShell.Shape
# Changes are confined to the previous/new volume pockets, not the grille.
zone=world(Part.makeBox(30,35,40,V(-15,0,-20)))
changes=[front.common(zone).cut(before.common(zone)),before.common(zone).cut(front.common(zone))]
report['front_change_outside_mount_mm3']=delta(front.cut(zone),before.cut(zone))
assert report['front_change_outside_mount_mm3']<.001
shell=local(front).common(Part.makeBox(30,35,40,V(-15,-1,-20)))
body=local(doc.VolumePot.Shape);b=body.BoundBox
for actual,expected in zip((b.XLength,b.YLength,b.ZLength,b.XMin,b.YMin,b.ZMin),(9.5,14.5,14.7,-4.75,3.6,-6.2)):equal(actual,expected)
assert len(body.Solids)==2
for solid,expected in zip(body.Solids,((9.5,14.5,11.2),(9.5,14.5,3.5))):
 bb=solid.BoundBox
 for actual,value in zip((bb.XLength,bb.YLength,bb.ZLength),expected):equal(actual,value)
report.update(module_local_size_xyz_mm=[b.XLength,b.YLength,b.ZLength],
              bare_body_size_xyz_mm=[9.5,14.5,11.2],pin_projection_mm=3.5,
              solder_insulation_allowance_mm=3.8,module_rotation_about_shaft_deg=0,
              dimensions_user_confirmed=True)
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
# Continuous rectangular pin envelope fills unknown pin spacing.
envelope=Part.makeBox(9.5,14.5,14.7,V(-4.75,3.6,-6.2))
hits=clashes(world(envelope),('VolumePot','Encoder'))
assert not hits,hits
report['complete_module_envelope']={'clashes':hits,'pcb_present':False,'pin_spacing_verified':False}
report['module_clearances_mm']={n:world(envelope).distToShape(o.Shape)[0] for n,o in objects.items()
                               if n not in ('VolumePot','Encoder','Knob')}
# Read saved construction allowances; test them against all finished parts,
# existing service loops, board underside wires and connector service zones.
report['wiring_clearances']={}
extras={n:doc.getObject(n).Shape for n in ('PerfboardUnderWiring','DriveDataWire','DACAudioWire',
         'ButtonsHarnessClosed','OLEDHarnessClosed','VolumeSwitchHarnessClosed',
         'ButtonsLeadBend','OLEDLeadBend','VolumeSwitchLeadBend')}
for name in ('VolumeSolderClearance','VolumeAudioLeadClearance'):
 shape=doc.getObject(name).Shape
 hits=clashes(shape)
 for n,other in extras.items():
  overlap=shape.common(other).Volume
  if overlap>.001:hits.append(dict(object=n,volume_mm3=overlap))
 assert not hits,(name,hits)
 report['wiring_clearances'][name]=dict(clashes=hits,clearances_mm={n:shape.distToShape(doc.getObject(n).Shape)[0] for n in
     ('Perfboard','MCUChip','SpeakerCarrier','ButtonRetainer','RearShell','Drive')})
# Body pocket side walls assist anti-rotation at its installation face.
for x in (-5.05,5.05):
 probe=Part.makeBox(.05,.5,1,V(x-(.05 if x<0 else 0),4,0))
 assert probe.common(shell).Volume>.024
report['body_side_clearance_mm']=.3
report['analog_exit_allowance']=dict(bundle_diameter_mm=3,length_mm=12,
    scope='local exit only; actual amplifier pads and remote analogue harness remain unverified')
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
report['limits']=['User reconfirmed the original bare B50K dimensions; pin envelope does not encode pin numbers or spacing.',
                  'Pins project 3.5 mm; another 3.8 mm is reserved for solder, insulation and exit. Local analogue bundle allowance is diameter 3 x length 12 mm; actual wire size/bend radius need assembly confirmation.',
                  'Latest perfboard, P3 geometry and placement are preserved; the switch harness cover-end route follows the new solder zone.',
                  'Remote analogue harness to the amplifier, electrical pinout and switch ratings remain unverified.',
                  'Six sacrificial grip ribs retain their 0.1 mm radial nominal interference; torque and retention need physical validation.',
                  'Nut threads and spline teeth are envelopes; printed fit is unverified.']
report['preserved_construction_difference_mm3']={}
for n in ('FrontGrille','FrontBezel','PerfboardUnderWiring','ButtonsHarnessClosed','ButtonsHarnessOpen','OLEDHarnessClosed','OLEDHarnessOpen','DriveDataWire','DACAudioWire'):
 value=delta(doc.getObject(n).Shape,old.getObject(n).Shape)
 assert value<.001,(n,value)
 report['preserved_construction_difference_mm3'][n]=value
report['color_face_order_preserved']={}
for n in ('Knob','PlayPauseKey','EjectKey','PrevKey','NextKey'):
 aa=doc.getObject(n).Shape.Faces;bb=old.getObject(n).Shape.Faces
 equal_faces=len(aa)==len(bb) and all(abs(a.Area-b.Area)<1e-7 and (a.CenterOfMass-b.CenterOfMass).Length<1e-7 for a,b in zip(aa,bb))
 assert equal_faces,n
 report['color_face_order_preserved'][n]=equal_faces
report['all_pass']=True
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('VOLUME_CHECKS_OK',flush=True)
