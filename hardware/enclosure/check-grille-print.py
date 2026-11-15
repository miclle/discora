"""Read P1 toolpaths, plate contact and support backing for the recessed locally relieved grille."""
import argparse,hashlib,json,zipfile
from pathlib import Path
import FreeCAD
from shapely import from_wkt,union_all
from shapely.geometry import LineString,Point
import slice_layer_geometry as geo

def check(w):
    mesh=w/'print/FrontShell.stl';plate=w/'print/slicer/FrontShell';gcode=plate/'plate_1.gcode'
    # Always validate the section cache hash; the initial caller runs audit()
    # on the current slice before reusing its detailed path classification.
    layers=geo.parse(gcode);polys=geo.sections(mesh,layers,w/'sections-FrontShell.json')
    audit=geo.audit('FrontShell',mesh,gcode,w)
    raw={}
    for p in audit['unbacked_paths']:raw.setdefault(p['layer']-1,[]).append(p)
    residual=[];contact=[];grille_support=[];under_support=[];first_grille_layer=None
    for i,l in enumerate(layers):
        if i==0:
            circle=Point(76+6.86842105263158,128).buffer(64.8)
            contact=[s for s in l['segments'] if s['feature'] not in ('Support','Support interface','Brim','Skirt','Custom') and LineString((s['a'],s['b'])).intersects(circle)]
        # No supports may be interleaved inside the perforated mesh thickness.
        if 1.7 < l['z'] <=4:
            roi=Point(82.86842105263158,128).buffer(65)
            grille_support.extend(i+1 for s in l['segments'] if s['feature'].startswith('Support') and LineString((s['a'],s['b'])).intersection(roi).length>.01)
        roi=Point(82.86842105263158,128).buffer(64.8)
        if l['z']<1.5:
            under_support.extend(i+1 for seg in l['segments'] if seg['feature'].startswith('Support') and LineString((seg['a'],seg['b'])).intersection(roi).length>.01)
        if first_grille_layer is None and l['z']>=1.5 and any(seg['feature'] not in ('Brim','Skirt','Custom') and not seg['feature'].startswith('Support') and LineString((seg['a'],seg['b'])).intersection(roi).length>.01 for seg in l['segments']):first_grille_layer=i+1
        if i not in raw:continue
        supports=[]
        for lower in layers[max(0,i-3):i]:
            if l['z']-lower['z']>l['h']+.2+.02:continue
            supports.extend(LineString((s['a'],s['b'])).buffer(s['width']/2+.1) for s in lower['segments'] if s['feature'].startswith('Support'))
        # This allowance distinguishes a bead beside an advancing edge from
        # a long bridge; the configured 0.42/0.45 mm bead and 0.2 mm layers
        # still require physical surface-quality acceptance.
        backing=polys[i-1].buffer(.35).union(union_all(supports))
        for p in raw[i]:
            line=LineString((p['a'],p['b']));free=line.difference(backing)
            spans=[v.length for v in getattr(free,'geoms',[free]) if v.length>.5]
            if spans:residual.append(dict(layer=i+1,z=l['z'],feature=p['feature'],max_free_mm=max(spans),a=p['a'],b=p['b']))
    warnings=json.loads((plate/'result.json').read_text())['sliced_plates'][0]['warning_message']
    with zipfile.ZipFile(plate/'Discora-FrontShell.3mf') as z:
        assert z.read('Metadata/plate_1.gcode')==gcode.read_bytes();settings=json.loads(z.read('Metadata/project_settings.config'))
        for key,val in [('enable_support','1'),('support_type','tree(auto)'),('support_on_build_plate_only','1'),('support_critical_regions_only','0'),('max_bridge_length','0')]:assert settings[key]==val
    r=dict(model_sha256=hashlib.sha256((w/'Discora.FCStd').read_bytes()).hexdigest(),stl_sha256=hashlib.sha256(mesh.read_bytes()).hexdigest(),gcode_sha256=hashlib.sha256(gcode.read_bytes()).hexdigest(),
           layers=len(layers),first_grille_model_layer=first_grille_layer,under_grille_support_layers=sorted(set(under_support)),support_access='Support lies below recessed grille and is accessible across the open front mouth; physical removal force not tested',new_islands=audit['new_islands'],first_layer_grille_model_segments=len(contact),support_segments_inside_mesh=grille_support,warnings=warnings,
           remaining_spans_after_model_and_support=sorted(residual,key=lambda x:x['max_free_mm'],reverse=True),
           method='All layers: closed mesh sections and new islands; all flagged bridge/overhang paths backed by previous model within 0.35 mm (lateral edge allowance, distinct from bridge length) or support within the configured 0.2 mm vertical gap.',
           physical_print_test=False)
    r['acceptance'] = dict(lateral_edge_allowance_mm=.35, maximum_local_bridge_mm=4.0, maximum_local_overhang_path_mm=2.5, scope='Geometric slice screening; not a physical print or dynamic speaker test')
    r['all_pass'] = first_grille_layer is not None and bool(under_support) and not grille_support and all(v['support_ratio']>.9 for v in audit['new_islands']) and not warnings and all(p['max_free_mm'] <= (4.0 if p['feature']=='Bridge' else 2.5) for p in residual)
    (w/'support-checks.json').write_text(json.dumps(r,indent=2)+'\n')
    print('SUPPORT_REVIEW',len(layers),'islands',audit['new_islands'],'first layer',len(contact),'mesh supports',len(grille_support),'warnings',warnings,'longest residual',r['remaining_spans_after_model_and_support'][:10],flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);check(p.parse_args().work)
