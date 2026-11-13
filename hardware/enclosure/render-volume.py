"""Render the saved volume assembly; black material lit for contour visibility."""
from pathlib import Path
import importlib.util
import FreeCAD as A
import Part
import numpy as np
from PIL import Image
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('colors',root/'render-drawing-colors.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
doc=A.openDocument(str(root/'Discora.FCStd'))
V=A.Vector
pose=A.Placement(V(48,18,165+18*27/38),A.Rotation(V(0,1,0),V(0,27/38,-1)))
def local(s):
 s=s.copy();s.Placement=pose.inverse().multiply(s.Placement);return s
palette=m.palette_from_build()
for name,rotation in [('volume-detail',A.Rotation(V(0,0,1),15).multiply(A.Rotation(V(1,0,0),65))),('volume-pcb-mount',A.Rotation(V(0,0,1),-18).multiply(A.Rotation(V(1,0,0),-65)))]:
 mat=rotation.inverted().toMatrix();rows=np.array([[getattr(mat,f'A{i}{j}') for j in range(1,4)] for i in range(1,4)])
 names=['FrontShell','Knob'] if name=='volume-detail' else ['FrontShell','Encoder','VolumePot']
 parts=[];points=[]
 for n in names:
  s=local(doc.getObject(n).Shape)
  if n=='FrontShell':s=s.common(Part.makeBox(46,7,48,V(-23,-1,-24)))
  color=palette['ORANGE' if n=='FrontShell' else 'KNOB_BLACK' if n=='Knob' else 'SILVER' if n=='Encoder' else 'PCB']
  # Lift the black surface under studio light so the fillets remain legible.
  if n=='Knob':color=(.16,.16,.16)
  regions=[(s.Solids[0],color),(s.Solids[1],palette['WHITE'])] if n=='Knob' else [(s,color)]
  if n=='VolumePot':
   regions=list(zip(s.Solids,[palette[k] for k in ('RUBBER','PCB','WHITE','SILVER')]))
  for region,tint in regions:
   surfaces=[([loop*3 for loop in loops],normal) for loops,normal in m.surface_polygons(region)]
   parts.append((surfaces,tint,np.zeros(3)))
  points.extend([[v.Point.x,v.Point.y,v.Point.z] for v in s.Vertexes])
 pts=np.array(points)@rows.T;lo=pts.min(axis=0);hi=pts.max(axis=0)
 center=(lo+hi)/2;size=np.array([max(hi[0]-lo[0],hi[1]-lo[1])*1.15]*2+[hi[2]-lo[2]])
 lo=center-size/2;hi=center+size/2
 dest=root/(name+'.png')
 m.render(parts,rows,dict(min=(lo*3).tolist(),max=(hi*3).tolist(),size=(size*3).tolist()),dest)
 im=Image.open(dest).convert('RGBA');bg=Image.new('RGBA',im.size,'#f3f1ed');bg.alpha_composite(im)
 bg.convert('RGB').resize((1000,1000),Image.Resampling.LANCZOS).save(dest)
 print(name,flush=True)
