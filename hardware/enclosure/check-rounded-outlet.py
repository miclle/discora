"""Check rounded P2 outlets without changing the validated P3 assembly."""
from pathlib import Path
import argparse,json,sys,hashlib,zipfile
from importlib.machinery import SourceFileLoader
import FreeCAD as A,Part
r=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description='Verify a P2-only rounded outlet update against its paired P2/P3 baseline.')
p.add_argument('--model',type=Path,required=True)
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--profile',choices=('rectangle','trapezoid'),default='rectangle')
args=p.parse_args()
import speaker_duct_geometry as duct
trapezoid=args.profile=='trapezoid'
wire=duct.trapezoid_outlet_wire if trapezoid else duct.rounded_outlet_wire
mouth_offset=1.6 if trapezoid else .5
blank_offset=3 if trapezoid else 2.8
ac=SourceFileLoader('ac',str(r/'hardware/enclosure/check-speaker-acoustics.py')).load_module()
d=A.openDocument(str(args.model));old=A.openDocument(str(args.baseline))
changed={'RearShell','LPanel','RPanel','LPanelTool','LPort','RPort'}
preserved={}
za=zipfile.ZipFile(args.baseline);zb=zipfile.ZipFile(args.model)
for o in old.Objects:
 if o.Name in changed or hasattr(o,'Group') or not hasattr(o,'Shape') or o.Shape.isNull():continue
 key=o.Name+'.Shape.brp'
 if key in za.namelist() and key in zb.namelist() and za.read(key)==zb.read(key) and o.Placement==d.getObject(o.Name).Placement:
  preserved[o.Name]=0.0
 else:
  print('COMPARE',o.Name,flush=True)
  preserved[o.Name]=ac.difference(o.Shape,d.getObject(o.Name).Shape)
 assert preserved[o.Name]<.001,(o.Name,preserved[o.Name])
print('ALL unchanged shapes compared',preserved['SpeakerCarrier'],flush=True)
rear=d.RearShell.Shape;assert rear.isValid() and len(rear.Solids)==1
m=A.Matrix();m.A11=-1
sym=rear.copy();sym.transformShape(m,True);symdiff=ac.difference(sym,rear);assert symdiff<.001
zone=Part.makeCompound([Part.makeBox(6,49 if trapezoid else 43,90,A.Vector(x,21 if trapezoid else 25,38)) for x in (-85.5,79.5)])
outside=ac.difference(rear.cut(zone),old.RearShell.Shape.cut(zone));assert outside<.001
print('P2 valid, symmetric and local',flush=True)
areas={};missing={}
for i in range(11):
 x=-84.99+i*4.98/10
 # Check local clearance as well as the complete projection: a Boolean
 # spanning the entire loft can miss small retained corner fragments.
 blank=Part.Face(wire(x-.001,blank_offset)).extrude(A.Vector(.002,0,0))
 areas[x]=blank.cut(rear).Volume/.002
 throat=duct.outlet_prism(x-.001,.002,1)
 missing[x]=throat.common(rear).Volume/.002
 print('SECTION',i,areas[x],missing[x],flush=True)
assert max(missing.values())<1e-6,missing
assert min(areas.values())>482.11
assert all(a>=b-1e-5 for a,b in zip(list(areas.values()),list(areas.values())[1:]))
projection=duct.outlet_prism(-85,5,1)
obstruction=projection.common(rear).Volume;assert obstruction<.001
interface=d.LChamber.Shape.common(Part.makeBox(4,45,35,A.Vector(-80,25,48)))
gap=interface.distToShape(rear)[0];assert abs(gap-.7)<1e-6
prior_name='p2-rounded-outlet-checks.json' if trapezoid else 'p2-p3-duct-checks.json'
prior=json.loads((r/'hardware/enclosure'/prior_name).read_text())
assert hashlib.sha256((args.baseline).read_bytes()).hexdigest()==prior['model_sha256']
mouth=Part.Face(wire(-85,mouth_offset));bounds=mouth.BoundBox
report={'model_sha256':hashlib.sha256((args.model).read_bytes()).hexdigest(),'baseline_sha256':prior['model_sha256'],'profile':args.profile,'all_unmodified_shapes_difference_mm3':preserved,'p3_whole_shape_difference_mm3':preserved['SpeakerCarrier'],'p2_actual_opening_sections_mm2':areas,'section_method':'mean area of a 0.002 mm thick solid slab at each of 11 X stations','inner_throat_projection_obstruction_mm2':missing,'full_482mm2_throat_projection_obstruction_mm3':obstruction,'sliding_gap_mm':gap,'p2_symmetry_difference_mm3':symdiff,'p2_outside_port_zone_difference_mm3':outside,'outer_mouth_size_yz_mm':[bounds.YLength,bounds.ZLength],'outer_mouth_bounds_yz_mm':[bounds.YMin,bounds.YMax,bounds.ZMin,bounds.ZMax],'outer_mouth_radius_mm':5.6 if trapezoid else 3.5,'outer_mouth_area_mm2':mouth.Area,'only_p2_outlet_changed':True,'p3_acoustic_and_print_evidence':'p2-p3-duct-checks.json; unchanged entire P3 and construction sources verified by exact B-rep difference','all_pass':True}
(args.output).write_text(json.dumps(report,indent=2)+'\n');print('ROUNDED_OUTLET_OK',flush=True)
