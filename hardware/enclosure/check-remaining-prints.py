"""Audit P1 and the sequential knob/four-key plate from saved 3MF meshes and G-code.

Run with FreeCAD Python. Does not send a print job.
"""
import argparse
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import FreeCAD
import Mesh
import numpy as np
from scipy.spatial import cKDTree
from shapely import union_all
from shapely.geometry import LineString, MultiPoint, Point
import slice_layer_geometry as geo

ROOT = Path(__file__).resolve().parent
NS = {'c': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
PROD = '{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'
KEYS = ['PlayPauseKey', 'EjectKey', 'PrevKey', 'NextKey']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transform(vertices, value):
    matrix = np.array(list(map(float, value.split()))).reshape(4, 3)
    return vertices @ matrix[:3] + matrix[3]


def read_project(path):
    parts = []
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        config = json.loads(archive.read('Metadata/project_settings.config'))
        meta = ET.fromstring(archive.read('Metadata/model_settings.config'))
        model = ET.fromstring(archive.read('3D/3dmodel.model'))
        for item in model.findall('c:build/c:item', NS):
            ident = item.get('objectid')
            obj = model.find("c:resources/c:object[@id='" + ident + "']", NS)
            info = meta.find("object[@id='" + ident + "']")
            parent = info.find("metadata[@key='name']").get('value')
            for comp in obj.findall('c:components/c:component', NS):
                source = ET.fromstring(archive.read(comp.get(PROD + 'path').lstrip('/')))
                mesh = source.find("c:resources/c:object[@id='" + comp.get('objectid') + "']/c:mesh", NS)
                vertices = np.array([[float(v.get(k)) for k in ('x', 'y', 'z')] for v in mesh.find('c:vertices', NS)])
                vertices = transform(transform(vertices, comp.get('transform')), item.get('transform'))
                faces = np.array([[int(t.get(k)) for k in ('v1', 'v2', 'v3')] for t in mesh.find('c:triangles', NS)])
                pm = info.find("part[@id='" + comp.get('objectid') + "']")
                name = pm.find("metadata[@key='name']").get('value')
                ext = pm.find("metadata[@key='extruder']")
                assert not any(int(v) for k, v in pm.find('mesh_stat').attrib.items() if k != 'face_count')
                parts.append(dict(name=name, parent=parent, material=int(ext.get('value')) if ext is not None else 1, vertices=vertices, faces=faces))
        gcode = archive.read('Metadata/plate_1.gcode')
    return parts, config, gcode


def mesh_for(parts):
    mesh = Mesh.Mesh()
    for part in parts:
        mesh.addMesh(Mesh.Mesh([[tuple(v) for v in triangle] for triangle in part['vertices'][part['faces']]]))
    return mesh


def sorted_faces(faces):
    faces = np.sort(faces, axis=1)
    return faces[np.lexsort((faces[:, 2], faces[:, 1], faces[:, 0]))]


def validate_geometry(source, target, anchor):
    allv = np.concatenate([p['vertices'] for p in source])
    origin = (allv.min(axis=0) + allv.max(axis=0)) / 2
    origin[2] = allv[:, 2].min()
    delta = np.array([*anchor, 0.]) - origin
    errors = []
    for part in target:
        old = next(p for p in source if (p['material'] == 2) == (part['material'] == 2))
        distances, indices = cKDTree(old['vertices'] + delta).query(part['vertices'])
        assert distances.max() < .0005, (part['name'], distances.max())
        assert np.array_equal(sorted_faces(indices[part['faces']]), sorted_faces(old['faces'])), part['name']
        errors.append(float(distances.max()))
    return max(errors)


def audit_group(work, name, parts, text):
    mesh = mesh_for(parts)
    meshpath = work / (name + '.stl')
    mesh.write(str(meshpath))
    gcode = work / (name + '.gcode')
    gcode.write_text(text)
    layers = geo.parse(gcode)
    cache = work / ('sections-' + name + '.json')
    if len(parts) > 1:
        # Adjacent color volumes share faces. Section each closed volume first,
        # then union their occupied areas instead of stitching duplicate faces.
        volumes = []
        for i, part in enumerate(parts):
            volume_path = work / (name + '-volume-' + str(i) + '.stl')
            mesh_for([part]).write(str(volume_path))
            volumes.append(geo.sections(volume_path, layers, work/(name+'-volume-'+str(i)+'.json')))
        polys = [union_all([v[i] for v in volumes]) for i in range(len(layers))]
        assert all(p.is_valid for p in polys)
        cache.write_text(json.dumps(dict(sha256=sha(meshpath), layer_schedule=[[l['z'],l['h']] for l in layers], sections=[p.wkt for p in polys], method='Union of separately sectioned color volumes')))
    else:
        polys = geo.sections(meshpath, layers, cache)
    audit = geo.audit(name, meshpath, gcode, work)
    raw = {}
    for path in audit['unbacked_paths']:
        raw.setdefault(path['layer'] - 1, []).append(path)
    residual = []
    for i, paths in raw.items():
        layer = layers[i]
        supports = []
        for lower in layers[max(0, i - 3):i]:
            if layer['z'] - lower['z'] > layer['h'] + .22:
                continue
            supports.extend(LineString((s['a'], s['b'])).buffer(s['width']/2 + .1) for s in lower['segments'] if s['feature'].startswith('Support'))
        backing = polys[i-1].buffer(.35).union(union_all(supports))
        for p in paths:
            line = LineString((p['a'], p['b']))
            free = line.difference(backing)
            if free.length <= .5:
                continue
            count = max(1, int(line.length/.2))
            distance = max(line.interpolate(j/count, normalized=True).distance(backing) for j in range(count+1))
            residual.append(dict(layer=i+1, z=layer['z'], feature=p['feature'], maximum_distance_to_backing_mm=distance, free_length_mm=free.length, both_ends_backed=backing.covers(Point(p['a'])) and backing.covers(Point(p['b']))))
    report = dict(layers=len(layers), new_islands=audit['new_islands'], residual_paths=residual, maximum_local_distance_to_backing_mm=max((p['maximum_distance_to_backing_mm'] for p in residual), default=0), first_layer_model_segments=sum(not s['feature'].startswith('Support') and s['feature'] not in ('Brim', 'Skirt', 'Custom') for s in layers[0]['segments']))
    # The existing knob shaft roof is a short, two-ended bridge (~5.3 mm).
    # Treat that separately from unanchored overhang width, without filling the shaft with support.
    report['acceptance'] = dict(maximum_local_overhang_distance_mm=2, maximum_knob_anchored_bridge_mm=6)
    report['all_pass'] = bool(report['first_layer_model_segments']) and all(p['support_ratio'] >= .9 for p in audit['new_islands']) and all(p['maximum_distance_to_backing_mm']<=2 or (name.startswith('Knob') and p['feature']=='Bridge' and p['both_ends_backed'] and p['free_length_mm']<=6) for p in residual)
    return report, layers, mesh


def check(work):
    front_path = work/'FrontShell/Discora-P1-FrontShell.3mf'
    controls_path = work/'Controls/Discora-Controls-Sequential.3mf'
    front, front_config, front_gcode = read_project(front_path)
    controls, config, raw = read_project(controls_path)
    old_front, _, _ = read_project(work/'baseline-Discora-P1-FrontShell.3mf')
    old_keys, _, _ = read_project(ROOT/'print/Discora-Keys-Orange-White.3mf')
    old_knob, _, _ = read_project(ROOT/'print/Discora-Knob-Black-White.3mf')
    errors = {'FrontShell': validate_geometry(old_front, front, (128, 128))}
    knob = [p for p in controls if p['parent'] == 'Knob']
    keys = [p for p in controls if p['parent'] == 'FourKeys']
    assert len(front) == 1 and len(knob) == 2 and len(keys) == 8
    errors['Knob'] = validate_geometry(old_knob, knob, (180, 150))
    for i, name in enumerate(KEYS):
        errors[name] = validate_geometry([p for p in old_keys if p['parent'] == name], [p for p in keys if p['name'].startswith(name)], (20+30*i, 20))
    assert front_config['filament_colour'] == ['#FF671F']
    assert config['filament_colour'] == ['#FF671F', '#FFFFFF', '#000000']
    assert config['print_sequence'] == 'by object'
    for settings, height, first in [(front_config, .16, .2), (config, .12, .12)]:
        assert settings['curr_bed_type'] == 'Textured PEI Plate'
        assert float(settings['layer_height']) == height and float(settings['initial_layer_print_height']) == first
        assert all(float(v) == 55 for k in ('textured_plate_temp', 'textured_plate_temp_initial_layer') for v in settings[k])
        assert settings['support_on_build_plate_only'] == '1' and settings['support_critical_regions_only'] == '0'
        assert float(settings['nozzle_diameter'][0]) == .4
    text = raw.decode()
    for code in (front_gcode.decode(), text):
        assert re.search(r'^\s*M140 S55', code, re.M) and re.search(r'^\s*M190 S55', code, re.M)
        assert 'G29.1 Z0.01 ; for Textured PEI Plate' in code
    starts = list(re.finditer(r'^; Z_HEIGHT: ([\d.]+)', text, re.M))
    resets = [i for i in range(1, len(starts)) if float(starts[i][1]) < float(starts[i-1][1])]
    assert resets == [116], resets
    cut = starts[resets[0]].start()
    front_audit, front_layers, front_mesh = audit_group(work, 'FrontShell', front, front_gcode.decode())
    knob_audit, knob_layers, knob_mesh = audit_group(work, 'Knob', knob, text[:cut])
    keys_audit, key_layers, key_mesh = audit_group(work, 'FourKeys', keys, text[cut:])
    assert len(front_layers) == 306 and len(knob_layers) == 116 and len(key_layers) == 60
    assert abs(front_layers[0]['h']-.2) < 1e-5 and all(abs(l['h']-.16)<1e-5 for l in front_layers[1:])
    assert all(abs(l['h']-.12)<1e-5 for l in knob_layers+key_layers)
    # Grille underside remains reachable from the open front; no support through its perforations.
    roi = Point(76+front_mesh.BoundBox.XMin, 128).buffer(64.8)
    underneath = []; interleaved = []; first_grille = None
    for i, layer in enumerate(front_layers):
        if layer['z'] > 4: break
        for s in layer['segments']:
            if LineString((s['a'], s['b'])).intersection(roi).length <= .01: continue
            support = s['feature'].startswith('Support')
            if support and layer['z'] < 1.5: underneath.append(i+1)
            if support and 1.7 < layer['z'] <= 4: interleaved.append(i+1)
            if not support and s['feature'] not in ('Brim', 'Skirt', 'Custom') and layer['z'] >= 1.5 and first_grille is None: first_grille=i+1
    assert underneath and not interleaved and first_grille is not None
    # Conservatively expand the completed knob/support footprint by the full head radius.
    footprint = MultiPoint([tuple(v[:2]) for p in knob for v in p['vertices']]).convex_hull
    support_lines = [LineString((s['a'],s['b'])).buffer(s['width']/2) for layer in knob_layers for s in layer['segments'] if s['feature'].startswith('Support') or s['feature']=='Brim']
    occupied = footprint.union(union_all(support_lines))
    maximum_radius = float(config['extruder_clearance_max_radius'])
    second_paths = [LineString((s['a'],s['b'])) for layer in key_layers for s in layer['segments'] if s['feature']!='Custom']
    print_distance = min(line.distance(occupied) for line in second_paths)
    assert print_distance > maximum_radius
    assert knob_mesh.BoundBox.ZMax < float(config['extruder_clearance_height_to_rod'])
    # Check actual low-Z straight travel after the restart, including trips to the purge area.
    xyz = [0.,0.,0.]; relative=False; low_distances=[]; tool=0; white={}; switches=[]
    for match in re.finditer(r'^.*$', text, re.M):
        s=match[0].strip()
        if s=='G90': relative=False
        if s=='G91': relative=True
        t=re.fullmatch(r'T(\d+)(?:\s*;.*)?',s)
        if t and int(t[1])<255: tool=int(t[1]); switches.append(tool)
        if s.startswith('; Z_HEIGHT:'): height=float(s.split()[-1])
        if not s.startswith(('G0 ','G1 ')): continue
        v={k:float(value) for k,value in re.findall(r'\b([XYZE])(-?(?:\d+(?:\.\d*)?|\.\d+))',s.partition(';')[0])}
        nxt=[xyz[i]+v.get(k,0) if relative else v.get(k,xyz[i]) for i,k in enumerate('XYZ')]
        if match.start() >= cut and min(xyz[2],nxt[2]) < 13.92 and nxt[:2]!=xyz[:2]:
            low_distances.append(LineString((xyz[:2],nxt[:2])).distance(occupied))
        xyz=nxt
        if tool==1 and v.get('E',0)>0 and ('X' in v or 'Y' in v):
            if 15<xyz[1]<25 and 10<xyz[0]<120: name=KEYS[min(range(4),key=lambda i:abs(xyz[0]-(20+30*i)))]
            elif 130<xyz[1]<170 and 160<xyz[0]<200: name='Knob'
            else: continue
            white.setdefault(name,set()).add(height)
    assert len(white)==5 and all(len(v)==5 for v in white.values())
    assert min(low_distances)>maximum_radius
    changes=sum(a!=b for a,b in zip(switches,switches[1:])); assert changes==11
    stats={name:json.loads((work/name/'result.json').read_text())['sliced_plates'][0] for name in ('FrontShell','Controls')}
    assert all(not s['warning_message'] for s in stats.values())
    report=dict(model_sha256=sha(ROOT/'Discora.FCStd'), projects={'FrontShell':dict(file=front_path.name,sha256=sha(front_path),gcode_sha256=hashlib.sha256(front_gcode).hexdigest()),'Controls':dict(file=controls_path.name,sha256=sha(controls_path),gcode_sha256=hashlib.sha256(raw).hexdigest())},geometry_coordinate_error_mm=errors,geometry_and_colors_preserved=True,plate='Textured PEI Plate',bed_temperature_c=55,nozzle_mm=.4,layer_height_mm={'FrontShell':.16,'Controls':.12},first_layer_height_mm={'FrontShell':.2,'Controls':.12},audits={'FrontShell':front_audit,'Knob':knob_audit,'FourKeys':keys_audit},grille=dict(first_model_layer=first_grille,under_support_layers=sorted(set(underneath)),interleaved_support_layers=interleaved),collision=dict(slicer_pass=True,sequence=['Knob','FourKeys'],completed_knob_height_mm=knob_mesh.BoundBox.ZMax,head_radius_mm=maximum_radius,minimum_second_group_print_distance_mm=print_distance,minimum_low_travel_distance_mm=min(low_distances),head_radius_margin_mm=min(print_distance,min(low_distances))-maximum_radius),white_layers={k:sorted(v) for k,v in white.items()},filament_changes=changes,stats={k:{'total_seconds':v['total_predication'],'filament_g':sum(f['total_used_g'] for f in v['filaments']),'filament_changes':v['filament_change_times'],'warnings':v['warning_message']} for k,v in stats.items()},physical_print_verified=False,printer_contacted=False)
    report['all_pass']=all(a['all_pass'] for a in report['audits'].values())
    (work/'remaining-print-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print('REMAINING_PRINT_CHECK',report['all_pass'],report['collision'],flush=True)
    assert report['all_pass']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    check(parser.parse_args().work.resolve())
