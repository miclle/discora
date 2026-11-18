"""Arrange released P2 and seven small pieces on one plate without changing geometry.

Run with FreeCAD Python. Keys and knob retain their separate two-material projects.
"""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
import FreeCAD as A
import Mesh
ROOT=Path(__file__).resolve().parent

def volume(mesh):
 vertices,faces=mesh.Topology
 points=np.array([tuple(v) for v in vertices],dtype=float);points-=points.mean(axis=0)
 triangles=points[np.array(faces)]
 return abs(np.einsum('ij,ij->i',triangles[:,0],np.cross(triangles[:,1],triangles[:,2])).sum()/6)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((ROOT/'print/manifest.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 assert manifest['model_sha256']==sha(ROOT/'Discora.FCStd')
 layout=[('RearShell',0,53,31.658911058107),('DriveRetainer',0,57,9),('DisplayRetainer',90,7,167),('ButtonRetainer',90,11,120)]
 rows=[];meshes=[]
 def place(mesh,name,source,angle,x,y):
  original_volume=volume(mesh);mat=A.Matrix();mat.rotateZ(math.radians(angle));mesh.transform(mat);b=mesh.BoundBox
  mesh.translate(x-b.XMin,y-b.YMin,-b.ZMin);b=mesh.BoundBox
  assert mesh.isSolid() and abs(volume(mesh)-original_volume)/original_volume<.0001
  assert min(b.XMin,b.YMin)>=5 and max(b.XMax,b.YMax)<=251
  target=a.output/(name+'.stl');mesh.write(str(target));meshes.append(mesh)
  rows.append(dict(name=name,source=source,file=target.name,stl_sha256=sha(target),source_sha256=manifest['parts'][source]['stl_sha256'],rotation_z_degrees=angle,bounds_mm=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],facets=mesh.CountFacets,volume_mm3=mesh.Volume,relative_volume_roundoff=abs(volume(mesh)-original_volume)/original_volume))
 for name,angle,x,y in layout:
  file=ROOT/'print'/manifest['parts'][name]['file'];assert sha(file)==manifest['parts'][name]['stl_sha256'];place(Mesh.Mesh(str(file)),name,name,angle,x,y)
 file=ROOT/'print/CarrierWashers.stl';assert sha(file)==manifest['parts']['CarrierWashers']['stl_sha256']
 washers=Mesh.Mesh(str(file)).getSeparateComponents();assert len(washers)==4
 for i,(mesh,(x,y)) in enumerate(zip(washers,[(11.1,33.1),(31.1,33.1),(11.1,58.1),(31.1,58.1)]),1):place(mesh,f'CarrierWasher{i}','CarrierWashers',0,x,y)
 merged=Mesh.Mesh()
 for mesh in meshes:merged.addMesh(mesh)
 merged.write(str(a.output/'combined-arranged.stl'))
 report=dict(model_sha256=manifest['model_sha256'],source_manifest_sha256=sha(ROOT/'print/manifest.json'),parts=rows,combined_stl_sha256=sha(a.output/'combined-arranged.stl'),physical_piece_count=8,arrangement='Fixed XY layout; source print orientations preserved; four washer solids separated only for packing.',all_pass=True)
 (a.output/'layout.json').write_text(json.dumps(report,indent=2)+'\n');print('COMBINED_LAYOUT_OK',len(rows))
if __name__=='__main__':main()
