"""Audit the arranged 3MF's actual small-part meshes and every toolpath layer."""
import argparse,hashlib,json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import FreeCAD
import Mesh
from shapely.geometry import LineString
from shapely import union_all
import slice_layer_geometry as geo
NS={'c':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
P='{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'
def check(w):
 plate=w/'print/slicer/SmallParts';project=plate/'Discora-SmallParts.3mf';gcode=plate/'plate_1.gcode'
 def transform(v,text):
  a=np.array(list(map(float,text.split()))).reshape(4,3);return v@a[:3]+a[3]
 pieces=[];washer=None
 with zipfile.ZipFile(project) as z:
  assert z.read('Metadata/plate_1.gcode')==gcode.read_bytes()
  model=ET.fromstring(z.read('3D/3dmodel.model'))
  for item in model.findall('c:build/c:item',NS):
   obj=model.find("c:resources/c:object[@id='"+item.get('objectid')+"']",NS)
   comp=obj.find('c:components/c:component',NS)
   source=ET.fromstring(z.read(comp.get(P+'path').lstrip('/')))
   mesh=source.find('.//c:mesh',NS)
   vertices=np.array([[float(v.get(k)) for k in ('x','y','z')] for v in mesh.find('c:vertices',NS)])
   vertices=transform(transform(vertices,comp.get('transform')),item.get('transform'))
   triangles=[[int(t.get(k)) for k in ('v1','v2','v3')] for t in mesh.find('c:triangles',NS)]
   shape=Mesh.Mesh([[tuple(vertices[i]) for i in t] for t in triangles]);assert shape.isSolid()
   pieces.append(shape)
   if shape.BoundBox.ZLength<1.21:washer=shape
 assert len(pieces)==4 and washer is not None
 merged=Mesh.Mesh()
 for s in pieces:merged.addMesh(s)
 meshpath=w/'small-parts-arranged.stl';merged.write(str(meshpath))
 layers=geo.parse(gcode);polys=geo.sections(meshpath,layers,w/'sections-SmallParts.json');audit=geo.audit('SmallParts',meshpath,gcode,w)
 residual=[]
 for p in audit['unbacked_paths']:
  i=p['layer']-1;l=layers[i];supports=[]
  for lower in layers[max(0,i-3):i]:
   if l['z']-lower['z']>l['h']+.22:continue
   supports.extend(LineString((s['a'],s['b'])).buffer(s['width']/2+.1) for s in lower['segments'] if s['feature'].startswith('Support'))
  backing=polys[i-1].buffer(.35).union(union_all(supports));line=LineString((p['a'],p['b']))
  free=line.difference(backing)
  if free.length>.5:
   count=max(1,int(line.length/.2));dist=max(line.interpolate(j/count,normalized=True).distance(backing) for j in range(count+1))
   residual.append(dict(layer=i+1,z=l['z'],feature=p['feature'],maximum_distance_to_backing_mm=dist,free_length_mm=free.length,a=p['a'],b=p['b']))
 wp=w/'washers-arranged.stl';washer.write(str(wp));regions=geo.sections(wp,layers,w/'sections-Washers.json')
 washer_support=[];contacts=[]
 for i,l in enumerate(layers):
  region=regions[0].buffer(.1)
  for s in l['segments']:
   length=LineString((s['a'],s['b'])).intersection(region).length
   if length>.05:
    if s['feature'].startswith('Support'):washer_support.append(i+1)
    elif i==0 and s['feature'] not in ('Brim','Skirt','Custom'):contacts.append(length)
 warnings=json.loads((plate/'result.json').read_text())['sliced_plates'][0]['warning_message']
 r=dict(model_sha256=hashlib.sha256((w/'Discora.FCStd').read_bytes()).hexdigest(),project_sha256=hashlib.sha256(project.read_bytes()).hexdigest(),gcode_sha256=hashlib.sha256(gcode.read_bytes()).hexdigest(),layers=len(layers),all_layer_sections_checked=len(polys),new_islands=audit['new_islands'],remaining_spans_after_model_and_support=residual,warnings=warnings,washer_first_layer_model_segments=len(contacts),washer_support_layers=sorted(set(washer_support)),washer_physical_quantity=4,physical_print_verified=False,acceptance=dict(maximum_local_distance_to_backing_mm=2,island_support_ratio_minimum=.9),method='3MF component and build transforms applied to saved meshes; full layer sections and actual support paths checked. Washers lie flat on bed. Retainers have open accessible undersides.',all_pass=not warnings and bool(contacts) and not washer_support and all(x['support_ratio']>=.9 for x in audit['new_islands']) and all(x['maximum_distance_to_backing_mm']<=2 for x in residual))
 (w/'retainer-print-checks.json').write_text(json.dumps(r,indent=2)+'\n');print('RETAINER_PRINT',r['all_pass'],flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);check(p.parse_args().work)
