"""Export a 32x44 mm PCB-module mounting sample, exterior face on bed.

Run with FreeCAD Python; no printer is contacted. Geometry comes from saved CAD.
"""
from pathlib import Path
import FreeCAD as A
import Part,MeshPart,argparse
V=A.Vector
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--model',type=Path,default=root/'Discora.FCStd')
p.add_argument('--output',type=Path,default=root.parent.parent/'tmp'/'pla-print'/'VolumeMountCoupon.stl')
args=p.parse_args();model=args.model.resolve()
doc=A.openDocument(str(model))
pose=A.Placement(V(48,18,165+18*27/38),A.Rotation(V(0,1,0),V(0,27/38,-1)))
s=doc.FrontShell.Shape.copy();s.Placement=pose.inverse().multiply(s.Placement)
s=s.common(Part.makeBox(32,5,44,V(-16,0,-22)))
assert s.isValid() and len(s.Solids)==1
s.Placement=A.Placement(V(),A.Rotation(V(0,1,0),V(0,0,1))).multiply(s.Placement)
b=s.BoundBox;s.translate(V(128-b.Center.x,128-b.Center.y,-b.ZMin))
mesh=MeshPart.meshFromShape(Shape=s,LinearDeflection=.05,AngularDeflection=.2,Relative=False)
assert mesh.isSolid()
out=args.output.resolve();out.parent.mkdir(parents=True,exist_ok=True);mesh.write(str(out))
print('COUPON_OK',mesh.CountFacets,flush=True)
