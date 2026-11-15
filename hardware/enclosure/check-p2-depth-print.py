"""Audit the extended P2 slice, including side mouths and rear connector bores."""
import argparse,hashlib,json,zipfile
from pathlib import Path
import FreeCAD
from shapely import union_all
from shapely.geometry import LineString,Point,box
import slice_layer_geometry as geo

def check(w):
    mesh=w/'print/RearShell.stl';plate=w/'print/slicer/RearShell';gcode=plate/'plate_1.gcode'
    layers=geo.parse(gcode);polys=geo.sections(mesh,layers,w/'sections-RearShell.json')
    audit=geo.audit('RearShell',mesh,gcode,w);raw={}
    for p in audit['unbacked_paths']:raw.setdefault(p['layer']-1,[]).append(p)
    residual=[]
    for i,paths in raw.items():
        l=layers[i];supports=[]
        for lower in layers[max(0,i-3):i]:
            if l['z']-lower['z']>l['h']+.22:continue
            supports.extend(LineString((s['a'],s['b'])).buffer(s['width']/2+.1) for s in lower['segments'] if s['feature'].startswith('Support'))
        backing=polys[i-1].buffer(.35).union(union_all(supports))
        for p in paths:
            free=LineString((p['a'],p['b'])).difference(backing)
            spans=[v.length for v in getattr(free,'geoms',[free]) if v.length>.5]
            if spans:
                line=LineString((p['a'],p['b']))
                distances=[line.interpolate(j/max(1,int(line.length/.2)),normalized=True).distance(backing) for j in range(max(1,int(line.length/.2))+1)]
                residual.append(dict(layer=i+1,z=l['z'],feature=p['feature'],max_free_mm=max(spans),maximum_distance_to_backing_mm=max(distances),a=p['a'],b=p['b']))
    # P2 is rear-down: Xbed=X+128, Ybed=Z+128-centerZ, Zbed=94.7-Y.
    doc=FreeCAD.openDocument(str((w/'Discora.FCStd').resolve()));cz=doc.RearShell.Shape.BoundBox.Center.z
    rois={'DC':Point(58,12+128-cz).buffer(5.4-.3), 'TypeC':box(58-5.65+.3,24+128-cz-2.85+.3,58+5.65-.3,24+128-cz+2.85-.3)}
    bore_support={k:[] for k in rois};obstructions=[]
    for i,l in enumerate(layers):
        if l['z']>10:break
        for name,roi in rois.items():
            for s in l['segments']:
                if LineString((s['a'],s['b'])).intersection(roi).length<.05:continue
                if s['feature'].startswith('Support'):bore_support[name].append(i+1)
                elif s['feature'] not in ('Brim','Skirt','Custom'):obstructions.append(dict(bore=name,layer=i+1,feature=s['feature']))
    with zipfile.ZipFile(plate/'Discora-RearShell.3mf') as z:
        assert z.read('Metadata/plate_1.gcode')==gcode.read_bytes();settings=json.loads(z.read('Metadata/project_settings.config'))
        assert settings['support_on_build_plate_only']==settings['support_critical_regions_only']=='0'
    warnings=json.loads((plate/'result.json').read_text())['sliced_plates'][0]['warning_message']
    r=dict(model_sha256=hashlib.sha256((w/'Discora.FCStd').read_bytes()).hexdigest(),stl_sha256=hashlib.sha256(mesh.read_bytes()).hexdigest(),gcode_sha256=hashlib.sha256(gcode.read_bytes()).hexdigest(),layers=len(layers),new_islands=audit['new_islands'],remaining_spans_after_model_and_support=sorted(residual,key=lambda p:p['max_free_mm'],reverse=True),bore_support_layers={k:sorted(set(v)) for k,v in bore_support.items()},bore_toolpath_obstructions=obstructions,warnings=warnings,support_access='Open front cavity and open side mouths; straight 10 mm charging bores accessible from both ends. P3 chamber/duct geometry and its original sliced project are unchanged.',physical_print_verified=False)
    r['acceptance']={'maximum_local_distance_to_backing_mm':2,'sample_spacing_mm':.2,'lateral_edge_allowance_mm':.35,'scope':'Screens local unsupported width; long paths alongside a backed edge are not their full length in bridging span. Physical print quality and removal remain unverified.'}
    r['all_pass']=not warnings and not obstructions and not audit['new_islands'] and all(p['maximum_distance_to_backing_mm']<=2 for p in residual)
    (w/'p2-depth-print-checks.json').write_text(json.dumps(r,indent=2)+'\n');print('P2_SUPPORT',r['all_pass'],r['remaining_spans_after_model_and_support'][:12],len(obstructions),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);check(p.parse_args().work)
