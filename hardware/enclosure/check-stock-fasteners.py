"""Read back stock-screw envelopes and preserved printed parts; no physical fit claim."""
import argparse,hashlib,json,math,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
import FreeCAD as A
import Part
import stock_fastener_geometry as g
ROOT=Path(__file__).resolve().parent
V=A.Vector;Y=V(0,1,0)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 d=A.openDocument(str(a.model.resolve()));old=A.openDocument(str(a.baseline.resolve()))
 objects={o.Name:o.Shape for group in ('Shell','Controls','Carrier','Hardware','ChargingInterfaces','CableClearances') for o in d.getObject(group).Group if hasattr(o,'Shape') and not o.Shape.isNull() and not o.Name.endswith('Open')}
 def hits(s,exclude=()):
  found={}
  for n,b in objects.items():
   if n in exclude or not s.BoundBox.intersect(b.BoundBox):continue
   v=s.common(b).Volume
   if v>.001:found[n]=v
  return found
 def delta(s,t):return 0 if s.exportBrepToString()==t.exportBrepToString() else s.cut(t).Volume+t.cut(s).Volume
 changed={};preserved={}
 for n,s in objects.items():
  o=old.getObject(n)
  if o is None:continue
  v=delta(s,o.Shape)
  (changed if v>.001 else preserved)[n]=v
  print('COMPARED',n,round(v,6),flush=True)
 assert set(changed)=={'FrontShell','RearShell','ButtonRetainer','DisplayRetainer','DriveRetainer'},changed
 assert preserved['SpeakerCarrier']<.001 and preserved['LDriver']<.001 and preserved['RDriver']<.001
 colors={}
 with zipfile.ZipFile(a.model) as z,zipfile.ZipFile(a.baseline) as before:
  current=ET.fromstring(z.read('GuiDocument.xml'));previous=ET.fromstring(before.read('GuiDocument.xml'))
  assert current.find('.//ViewProvider[@name="CarrierWashers"]') is not None
  for n in ('PlayPauseKey','EjectKey','PrevKey','NextKey','Knob','VolumePot'):
   s=d.getObject(n).Shape;t=old.getObject(n).Shape
   assert len(s.Faces)==len(t.Faces)
   assert all(abs(x.Area-y.Area)<1e-7 and (x.CenterOfMass-y.CenterOfMass).Length<1e-7 for x,y in zip(s.Faces,t.Faces)),n
   vp=current.find(f'.//ViewProvider[@name="{n}"]');orig=previous.find(f'.//ViewProvider[@name="{n}"]')
   assert ET.tostring(vp)==ET.tostring(orig),n
   refs=[v for el in vp.iter() for k,v in el.attrib.items() if k.lower()=='file' and v]
   assert all(z.read(f)==before.read(f) for f in refs)
   colors[n]=True
 locks=[]
 for sign in (-1,1):
  for x,z,root,end,bottom,head in g.LOCKS:
   x*=sign;top=head-.3;tip=top-30;cone=(6.8-3.5)/2
   screw=Part.makeCylinder(1.75,30-cone,V(x,tip,z),Y).fuse(Part.makeCone(1.75,3.4,cone,V(x,top-cone,z),Y))
   assert not hits(screw,('FrontShell',)),hits(screw,('FrontShell',))
   thread=Part.makeCylinder(1.751,end-tip+.001,V(x,tip-.0005,z),Y)
   assert screw.common(d.FrontShell.Shape).cut(thread).Volume<.001
   for radius in (3.4,3):assert not hits(Part.makeCylinder(radius,120-top,V(x,top+.0001,z),Y))
   assert Part.makeCylinder(1.399,end-bottom,V(x,bottom,z),Y).common(d.FrontShell.Shape).Volume<.001
   assert Part.makeCylinder(1.399,.5,V(x,bottom-.5,z),Y).cut(d.FrontShell.Shape).Volume<.001
   # Actual axis intersection with the back envelope, read from saved geometry.
   bb=d.RearShell.Shape.BoundBox
   # The well is open; find the rear profile boundary at this axis from FoldSection.
   pts=[(e.StartPoint.x,e.StartPoint.y) for e in d.FoldSection.Geometry]
   env=Part.Face(Part.makePolygon([V(x,y,zz) for y,zz in pts[:7]+[(g.rear.DEPTH,1),pts[0]]]))
   ray=Part.makeLine(V(x,0,z),V(x,120,z)).common(env)
   entry=max(v.Point.y for v in ray.Vertexes)
   locks.append(dict(center_xz_mm=[x,z],rear_center_xyz_mm=[x,entry,z],seat_y_mm=top,well_depth_mm=entry-top,screw_top_y_mm=top,screw_tip_y_mm=tip,engagement_mm=end-tip,tip_to_bottom_mm=tip-bottom,head_diameter_mm=6.8,total_length_mm=30,head_sweep_clear=True,tool_diameter_mm=6,tool_clear=True))
 rows=[]
 def flat(group,x,z,under,length,diam,head_d,head_h,seat,bottom,host,pose=None):
  direction=1 if group in ('P3','Drive') else -1
  tip=under+direction*length
  shaft=g.cyl(diam/2,length,x,min(tip,under),z)
  head=g.cyl(head_d/2,head_h,x,under-head_h if direction==1 else under,z)
  tool=g.cyl(2,20,x,under-head_h-20 if direction==1 else under+head_h,z)
  if pose:shaft=g.posed(shaft,pose);head=g.posed(head,pose);tool=g.posed(tool,pose)
  assert not hits(shaft,(host,)),(group,hits(shaft,(host,)))
  assert not hits(head),(group,hits(head))
  # P1 must be removed before the internal screws can be accessed.
  if pose:
   front_names={'FrontShell','Window','StatusArt','PlayPauseKey','EjectKey','PrevKey','NextKey','ButtonRetainer','DisplayRetainer','Knob','PlayPauseSwitch','EjectSwitch','PrevSwitch','NextSwitch','Encoder','VolumePot','DisplayPCB','DisplayHeader'}
   tool.translate(V(0,-60,0));tool_hits={}
   for n,source in objects.items():
    if n.endswith(('Clearance','Closed')):continue  # disconnected cable reservations
    body=source.copy()
    if n in front_names:body.translate(V(0,-60,0))
    v=tool.common(body).Volume if tool.BoundBox.intersect(body.BoundBox) else 0
    if v>.001:tool_hits[n]=v
   assert not tool_hits,(group,tool_hits)
  else:
   excluded=('FrontShell','SpeakerCarrier','DriveDataWire') if group=='Drive' else ('FrontShell',)
   assert not hits(tool,excluded),(group,hits(tool,excluded))
  engaged=abs(tip-seat);margin=abs(tip-bottom)
  assert engaged>3.5 and margin>=.19
  rows.append(dict(group=group,local_xz_mm=[x,z],underhead_depth_mm=under,thread_length_mm=length,thread_diameter_mm=diam,head_diameter_mm=head_d,head_height_mm=head_h,engagement_mm=engaged,tip_margin_mm=margin,head_and_tool_clear=True,tool_access_prerequisite='Front cover removed; for drive also P3 removed and drive cable disconnected'))
 bearing=[]
 for x in (-64,64):
  for z in (27,124):
   ring=g.cyl(2.899,.01,x,6.7,z).cut(g.cyl(2.401,.02,x,6.695,z))
   coverage=ring.common(d.SpeakerCarrier.Shape).Volume/ring.Volume
   assert coverage>.999,(x,z,coverage)
   bearing.append(dict(center_xz_mm=[x,z],flat_bearing_coverage=coverage,nominal_bearing_area_mm2=math.pi*(2.9**2-2.4**2)))
   flat('P3',x,z,5.5,10,2.5,4,1.3,8.7,15.7,'RearShell')
   assert g.cyl(2.9,.001,x,6.699,z).cut(g.cyl(2.4,.003,x,6.698,z)).cut(d.CarrierWashers.Shape).Volume<.001
   assert g.cyl(3.199,1.99,x,3.205,z).common(d.FrontShell.Shape).Volume<.001
   assert g.cyl(3,.1,x,3,z).cut(d.FrontShell.Shape).Volume<.001
 front=d.DriveCarrier.Shape.BoundBox.YMin
 for x in (-66.75,66.75):flat('Drive',x,117,front-3,10,2.5,4,1.3,front,front+8.9,'RearShell')
 edge=d.FoldSection.Geometry[1];slope=(edge.EndPoint.y-edge.StartPoint.y)/(edge.EndPoint.x-edge.StartPoint.x);rot=A.Rotation(Y,V(0,slope,-1))
 for group,base,xs,z,under,seat,bottom in [('Buttons',V(-54,17.5,165+17.5*slope),(-14,14),0,18.5,16.5,7),('OLED',V(0,18,165+18*slope),(-20.5,20.5),-7,10.2,6.4,2)]:
  for x in xs:flat(group,x,z,under,7.8,2.8,5.9,2,seat,bottom,'FrontShell',A.Placement(base,rot))
 mirror=A.Matrix();mirror.A11=-1
 symmetry={}
 for n in ('FrontFastenerPosts','RearFastenerCuts','DriveCarrier','DriveRetainer','CarrierWashers','DisplayRetainer'):
  s=d.getObject(n).Shape;t=s.copy();t.transformShape(mirror,True);symmetry[n]=delta(s,t)
 assert max(symmetry.values())<.001,symmetry
 assert len(d.CarrierWashers.Shape.Solids)==4
 assert abs(d.RearShell.Shape.BoundBox.YMax-94.7)<1e-6
 report=dict(model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),baseline_sha256=hashlib.sha256(a.baseline.read_bytes()).hexdigest(),changed_finished_objects_difference_mm3=changed,unchanged_shapes_difference_mm3=preserved,color_face_order_preserved=colors,locks=locks,flat_head_screws=rows,head_well_diameter_mm=7.4,nominal_countersink_angle_degrees=90,countersink_angle_measured=False,washer=dict(saved_p3_flat_bearing=bearing,quantity=4,outer_diameter_mm=5.8,inner_diameter_mm=2.8,thickness_mm=1.2,front_head_gap_mm=1,remaining_p1_wall_mm=3.2),symmetry_difference_mm3=symmetry,inventory=dict(case_m35_total30=4,p3_25x10=4,drive_25x10=2,buttons_28x78=2,oled_28x78=2,spare_28x95_unused=6,additional_m2x4_required=3),physical_screw_fit_verified=False,printed_p3_unchanged=True,all_pass=True)
 a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('STOCK_FASTENERS_OK',flush=True)
if __name__=='__main__':main()
