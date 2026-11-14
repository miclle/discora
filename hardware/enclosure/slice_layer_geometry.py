"""Audit every sliced layer against the preceding closed mesh section."""
from pathlib import Path
import json,re,hashlib
import Mesh
from shapely.geometry import Polygon,LineString,Point
from shapely import union_all,from_wkt
def parse(path):
 layers=[];x=y=0.;feature='';width=.42;height=.2
 for line in path.read_text().splitlines():
  if line.startswith('; Z_HEIGHT:'):layers.append({'z':float(line.split()[-1]),'segments':[]})
  if line.startswith('; LAYER_HEIGHT:'):height=float(line.split()[-1]);layers[-1]['h']=height
  if line.startswith('; FEATURE:'):feature=line.split(': ',1)[1].strip()
  if line.startswith('; LINE_WIDTH:'):width=float(line.split()[-1])
  if layers and line.startswith(('G0 ','G1 ','G2 ','G3 ')):
   q={k:float(v) for k,v in re.findall(r' ([XYE])(-?[\d.]+)',line.partition(';')[0])};nx=q.get('X',x);ny=q.get('Y',y)
   if q.get('E',0)>0 and (nx!=x or ny!=y):
    assert not line.startswith(('G2 ','G3 '));layers[-1]['segments'].append({'a':[x,y],'b':[nx,ny],'feature':feature,'width':width})
   x,y=nx,ny
 return layers

def sections(meshpath,layers,cache):
 sha=hashlib.sha256(meshpath.read_bytes()).hexdigest()
 if cache.exists():
  data=json.loads(cache.read_text())
  if isinstance(data,dict) and data['sha256']==sha:return [from_wkt(x) for x in data['sections']]
 mesh=Mesh.Mesh(str(meshpath));res=[]
 for i,l in enumerate(layers):
  z=l['z']-l.get('h',.2)/2
  for eps in (.0001,.001,.003,.007):
   # Curved outlet meshes contain sub-millimetre facets; tighter
   # stitching avoids prematurely joining neighbouring intersections.
   loops=mesh.crossSections([((0,0,z-eps),(0,0,1))],.0001)[0]
   if all((p[0]-p[-1]).Length<.001 for p in loops):
    shapes=[Polygon([(v.x,v.y) for v in p]) for p in loops if len(p)>3]
    if all(p.is_valid for p in shapes):break
  assert all((p[0]-p[-1]).Length<.001 for p in loops),(i,z)
  shapes=[Polygon([(v.x,v.y) for v in p]) for p in loops if len(p)>3]
  assert all(p.is_valid for p in shapes),(i,z)
  shape=Polygon()
  for p in shapes:shape=shape.symmetric_difference(p)
  res.append(shape)
 cache.write_text(json.dumps({'sha256':sha,'sections':[x.wkt for x in res]}));return res

def audit(name,mesh,gcode,output):
 layers=parse(gcode);polys=sections(mesh,layers,output/('sections-'+name+'.json'))
 newislands=[];overhangs=[];layerchecks=[];firstboss=[]
 for i,(l,shape) in enumerate(zip(layers,polys)):
  if i==0:continue
  prev=polys[i-1];near=prev.buffer(.03);islands=[]
  for p in getattr(shape,'geoms',[shape]):
   if p.area>.05 and p.intersection(near).area<.001:
    supports=[]
    for lower in layers[max(0,i-4):i]:
     for s in lower['segments']:
      if s['feature'].startswith('Support'):
       line=LineString((s['a'],s['b']))
       if line.distance(p)<.6:supports.append(line.buffer(s['width']/2+.35))
    coverage=p.intersection(union_all(supports)).area/p.area if supports else 0
    v={'layer':i+1,'z':l['z'],'area':p.area,'bounds':p.bounds,'support_ratio':coverage};newislands.append(v);islands.append(v)
  # Actual Bridge/overhang paths with more than 1 mm of unbacked centreline.
  for s in l['segments']:
   if s['feature'] not in ('Bridge','Overhang wall'):continue
   line=LineString((s['a'],s['b']));free=line.difference(near)
   if free.length<1:continue
   spans=[]
   for part in getattr(free,'geoms',[free]):
    if part.length<1:continue
    spans.append(part.length)
   if not spans:continue
   record={**s,'layer':i+1,'z':l['z'],'free':max(spans),'a_on_model':near.covers(Point(s['a'])),'b_on_model':near.covers(Point(s['b']))}
   overhangs.append(record)
  layerchecks.append({'layer':i+1,'z':l['z'],'component_count':len(getattr(shape,'geoms',[shape])),'new_islands':len(islands),'uncovered_new_islands':sum(v['support_ratio']<.05 for v in islands)})
 result={'layers':len(layers),'layer_checks':layerchecks,'new_islands':newislands,'unbacked_paths':overhangs}
 (output/(name+'-layer-audit.json')).write_text(json.dumps(result,indent=2))
 print(name,'layers',len(layers),'new islands',newislands,flush=True)
 print(name,'longest free',sorted(overhangs,key=lambda v:v['free'],reverse=True)[:8],flush=True)
 return result
