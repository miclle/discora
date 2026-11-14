"""Verify printable P3 transitions, preserved trial interfaces and air paths."""
from pathlib import Path
import sys,json,hashlib
import FreeCAD as A
import Part
from importlib.machinery import SourceFileLoader
import argparse
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--model',type=Path,required=True)
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
args=p.parse_args()
r=Path(__file__).resolve().parents[2];sys.path.insert(0,str(r/'hardware/enclosure'))
acoustics=SourceFileLoader('acoustics',str(r/'hardware/enclosure/check-speaker-acoustics.py')).load_module()
d=A.openDocument(str(args.model));o=A.openDocument(str(args.baseline));V=A.Vector
core=d.SpeakerCarrier.Shape
# All functional interfaces in the first 13 mm retain the trial-coupon geometry.
front=Part.makeBox(101,23,84,V(-50.5,-10,34))
def diff(a,b):return acoustics.difference(a,b)
assert diff(core.common(front),o.SpeakerCarrier.Shape.common(front))<.001
preserved={}
for obj in o.Objects:
 if obj.Name in ('SpeakerCarrier','LDriverFrame','RDriverFrame','LChamber','RChamber') or hasattr(obj,'Group') or not hasattr(obj,'Shape') or obj.Shape.isNull():continue
 preserved[obj.Name]=diff(obj.Shape,d.getObject(obj.Name).Shape)
assert max(preserved.values())<.001
mirror=A.Matrix();mirror.A11=-1;s=d.LDriverFrame.Shape.copy();s.transformShape(mirror,True)
assert diff(s,d.RDriverFrame.Shape)<.001
import speaker_print_geometry as geometry
assert diff(d.LDriverFrame.Shape,geometry.make_left_frame_printable(o.LDriverFrame.Shape))<.001
assert diff(d.LChamber.Shape,geometry.smooth_left_wing(o.LChamber.Shape))<.001
s=d.LChamber.Shape.copy();s.transformShape(mirror,True);assert diff(s,d.RChamber.Shape)<.001
for name in ('LChamber','RChamber'):
 area=sum(f.Area for f in d.getObject(name).Shape.Faces if f.BoundBox.YLength<1e-7 and abs(f.CenterOfMass.y-62.5)<1e-7)
 assert abs(area-6929)<.001
# Check the full original 8 mm rear transfer region is unchanged, not just a centreline.
rear=Part.makeBox(157,8,84,V(-78.5,52,34))
assert diff(core.common(rear),o.SpeakerCarrier.Shape.common(rear))<.001
# Keep blind bores and their bottoms: whole original boss envelopes unchanged.
bosses=[]
for x in (-44,-8,8,44):
 for z in (41,111):
  env=Part.makeCylinder(4,11.5,V(x,10,z),V(0,1,0))
  bosses.append(diff(core.common(env),o.SpeakerCarrier.Shape.common(env)))
assert max(bosses)<.001
wire=acoustics.check_wire_corridor(d)
# Closed analytical air volumes: both speaker baskets and outer paths remain connected.
fronts=[Part.makeBox(46,2.2,81,V(x-23,4.9,35.5)) for x in (-26,26)]
tools=[t for sign in (-1,1) for t in acoustics.wire.exit_tools(sign)]
cap=Part.makeCompound(fronts+[acoustics.side_cap(-79.4),acoustics.side_cap(76.4)]+tools)
domain=Part.makeBox(180,80,110,V(-90,-5,20));air=domain.cut(core).cut(cap)
ids={}
for name,p in {'Lmain':V(-26,55,76),'Lside':V(-70,49,80),'Rmain':V(26,55,76),'Rside':V(70,49,80),'outside':V(0,-4,25)}.items():
 matches=[i for i,s in enumerate(air.Solids) if s.isInside(p,1e-6,True)];assert len(matches)==1,(name,matches);ids[name]=matches[0]
assert ids['Lmain']==ids['Lside'] and ids['Rmain']==ids['Rside'] and len(set(ids.values()))==3,ids
clashes={n:core.common(d.getObject(n).Shape).Volume for n in ('LDriver','RDriver')};assert max(clashes.values())<.001
# Net additions avoid the protected 0.5 mm basket-clearance prism.
import speaker_print_geometry as frame_geometry
adds=core.cut(o.SpeakerCarrier.Shape);clear=frame_geometry.basket_clearance();c2=clear.copy();c2.transformShape(mirror,True)
assert adds.common(clear.fuse(c2)).Volume<.001
report={'model_sha256':hashlib.sha256((args.model).read_bytes()).hexdigest(),'baseline_sha256':hashlib.sha256((args.baseline).read_bytes()).hexdigest(),'front_interface_delta_mm3':0,'rear_8mm_passage_delta_mm3':0,'boss_envelope_delta_mm3':bosses,'other_objects_delta_mm3':preserved,'frame_symmetry_delta_mm3':0,'driver_collisions_mm3':clashes,'air_components':ids,'internal_wire_corridor':wire,'main_to_side_passages_connected':True,'left_right_air_separate':True,'added_mm3':adds.Volume,'removed_mm3':o.SpeakerCarrier.Shape.cut(core).Volume,'all_pass':True,'physical_print_test':False}
(args.output).write_text(json.dumps(report,indent=2)+'\n');print('GEOMETRY_OK', {k:v for k,v in report.items() if k not in ('other_objects_delta_mm3','internal_wire_corridor')},flush=True)
