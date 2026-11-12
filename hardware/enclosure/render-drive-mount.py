"""Render the measured drive mount from saved B-rep geometry, without changing CAD."""
import argparse
import importlib.util
from pathlib import Path
import FreeCAD as A
import Part
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--model',type=Path,default=ROOT/'Discora.FCStd')
p.add_argument('--output',type=Path,default=ROOT/'drive-mount.png')
args=p.parse_args()
spec=importlib.util.spec_from_file_location('drive_colors',ROOT/'render-drawing-colors.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
doc=A.openDocument(str(args.model.resolve()))
palette=m.palette_from_build()
V=A.Vector
rotation=A.Rotation(V(0,0,1),21).multiply(A.Rotation(V(1,0,0),76))
matrix=rotation.inverted().toMatrix()
rows=np.array([[getattr(matrix,f'A{i}{j}') for j in range(1,4)] for i in range(1,4)])
parts=[];points=[]
# Housing shown as a cropped support cutaway, not a modified production part.
rear=doc.RearShell.Shape.common(Part.makeBox(doc.Back.Shape.BoundBox.XLength,35,173,V(doc.Back.Shape.BoundBox.XMin,doc.Back.Shape.BoundBox.YMin-30,0)))
shapes=[('housing',rear,'BLACK'),('drive',doc.Drive.Shape,'SILVER'),
        ('retainer',doc.DriveRetainer.Shape,'TEAL'),('adapter',doc.Bridge.Shape,'RUBBER')]
for _,shape,color in shapes:
    parts.append((m.surface_polygons(shape),palette[color],np.zeros(3)))
    points.extend([[v.Point.x,v.Point.y,v.Point.z] for v in shape.Vertexes])
pts=np.array(points)@rows.T
lo=pts.min(axis=0);hi=pts.max(axis=0);center=(lo+hi)/2
height=max(hi[1]-lo[1],hi[0]-lo[0])*1.12
size=np.array([height,height,hi[2]-lo[2]])
m.render(parts,rows,dict(min=(center-size/2).tolist(),max=(center+size/2).tolist(),size=size.tolist()),args.output)
im=Image.open(args.output).convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im)
bg.convert('RGB').resize((1200,1200),Image.Resampling.LANCZOS).save(args.output)
print('DRIVE_MOUNT_RENDER_OK',args.output,flush=True)
