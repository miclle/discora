"""Measure the extended rear shoulder and recheck rear-access screw tools."""
import argparse,hashlib,json,math
from pathlib import Path
import FreeCAD as A
import Part
V=A.Vector
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();doc=A.openDocument(str(a.model.resolve()))
profile=[(e.StartPoint.x,e.StartPoint.y) for e in doc.FoldSection.Geometry]
(oy,oz),(ey,ez)=profile[5:7];(iy,iz),(jy,jz)=profile[7:9]
normal=V(0,-(oz-ez),-(ey-oy));normal.normalize()
# Analytic intersection of rays normal to the actual straight outer shoulder
# with the saved inner shoulder, excluding edge corners and the disc slot.
lengths=[]
for t in (.1,.25,.5,.75,.9):
 y=oy+(ey-oy)*t;z=oz+(ez-oz)*t
 slope=(jz-iz)/(jy-iy)
 d=(iz+slope*(y-iy)-z)/(normal.z-slope*normal.y)
 assert d>4.8 and d<5.1,(t,d)
 lengths.append(dict(fraction=t,normal_thickness_mm=d))
access=[];fixed=[o for g in ('Shell','Controls','Carrier','Hardware') for o in doc.getObject(g).Group]
for x,z,seat in [(-79.4,33,14.2),(79.4,33,14.2),(-29,179,39.2),(29,179,39.2)]:
 entry=94.7 if z==33 else oy+(z-oz)*(ey-oy)/(ez-oz)
 tool=Part.makeCylinder(2,entry-seat+20,V(x,seat+.001,z),V(0,1,0))
 hits=[]
 for o in fixed:
  if tool.BoundBox.intersect(o.Shape.BoundBox):
   v=tool.common(o.Shape).Volume
   if v>.001:hits.append(dict(object=o.Name,volume_mm3=v))
 assert not hits,(x,z,hits)
 access.append(dict(rear_center_xyz_mm=[x,entry,z],seat_y_mm=seat,well_depth_mm=entry-seat,tool_diameter_mm=4,clashes=hits))
# Side outlets retain the original local shapes, and their 0.7 mm axial gap.
assert abs(doc.LPort.Shape.BoundBox.XMax+80)<.001
assert abs(doc.LChamber.Shape.BoundBox.XMin+79.3)<.001
r=dict(model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),rear_access=access,rear_shoulder_normal_thickness=lengths,minimum_sampled_normal_thickness_mm=min(v['normal_thickness_mm'] for v in lengths),front_horizontal_run_mm=44,rear_horizontal_run_mm=45.7,front_angle_deg=math.degrees(math.atan2(profile[2][1]-profile[1][1],44)),rear_angle_deg=math.degrees(math.atan2(oz-ez,ey-oy)),side_outlet_axial_gap_mm=.7,physical_fit_verified=False,all_pass=True)
a.output.write_text(json.dumps(r,indent=2)+'\n');print('REAR_DEPTH_OK',r,flush=True)
