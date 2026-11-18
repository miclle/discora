"""Reproduce P1 0.16 mm and the 0.12 mm sequential controls plate.

Run with FreeCAD Python. Uses released colored meshes, only translates them,
keeps the four keys in one print group, and never contacts a printer.
"""
import argparse
import importlib.util
import json
import re
import subprocess
import xml.etree.ElementTree as E
import zipfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('remaining_checks', ROOT/'check-remaining-prints.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
NS = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
E.register_namespace('', NS)


def export(path, groups):
    model = E.Element('model', unit='millimeter', xmlns=NS)
    resources = E.SubElement(model, 'resources')
    build = E.SubElement(model, 'build')
    config = E.Element('config')
    ident = 1
    for name, parts in groups:
        child_ids = []
        for part in parts:
            child_ids.append((ident, part))
            obj = E.SubElement(resources, 'object', id=str(ident), type='model')
            mesh = E.SubElement(obj, 'mesh')
            vertices = E.SubElement(mesh, 'vertices')
            triangles = E.SubElement(mesh, 'triangles')
            for v in part['vertices']:
                E.SubElement(vertices, 'vertex', **dict(zip(('x','y','z'), (f'{n:.9f}' for n in v))))
            for face in part['faces']:
                E.SubElement(triangles, 'triangle', **dict(zip(('v1','v2','v3'), map(str,face))))
            ident += 1
        parent = E.SubElement(resources, 'object', id=str(ident), type='model', name=name)
        components = E.SubElement(parent, 'components')
        cfg = E.SubElement(config, 'object', id=str(ident))
        E.SubElement(cfg, 'metadata', key='name', value=name)
        E.SubElement(cfg, 'metadata', key='extruder', value=str(parts[0]['material']))
        for child, part in child_ids:
            E.SubElement(components, 'component', objectid=str(child))
            pm = E.SubElement(cfg, 'part', id=str(child), subtype='normal_part')
            E.SubElement(pm, 'metadata', key='name', value=part['name'])
            E.SubElement(pm, 'metadata', key='extruder', value=str(part['material']))
        E.SubElement(build, 'item', objectid=str(ident), transform='1 0 0 0 1 0 0 0 1 0 0 0')
        ident += 1
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model',E.tostring(model))
        z.writestr('Metadata/model_settings.config',E.tostring(config))


def place(parts, xy):
    vertices=np.concatenate([p['vertices'] for p in parts])
    origin=(vertices.min(axis=0)+vertices.max(axis=0))/2
    origin[2]=vertices[:,2].min()
    for part in parts: part['vertices']=part['vertices']-origin+np.array([*xy,0.])
    return parts


def main(work):
    work.mkdir(parents=True,exist_ok=True)
    front_path=ROOT/'print/Discora-P1-FrontShell.3mf'
    # Keep the exact source for later hash/geometry readback, before any release update.
    (work/'baseline-Discora-P1-FrontShell.3mf').write_bytes(front_path.read_bytes())
    (work/'baseline-manifest.json').write_bytes((ROOT/'print/manifest.json').read_bytes())
    front=place(checks.read_project(front_path)[0],(128,128))
    keys=checks.read_project(ROOT/'print/Discora-Keys-Orange-White.3mf')[0]
    grouped=[]
    for i,name in enumerate(checks.KEYS):
        grouped.extend(place([p for p in keys if p['parent']==name],(20+30*i,20)))
    knob=place(checks.read_project(ROOT/'print/Discora-Knob-Black-White.3mf')[0],(180,150))
    for part in knob:
        if part['material']==1: part['material']=3
    profiles=Path('/Applications/BambuStudio.app/Contents/Resources/profiles/BBL')
    paths={p.stem:p for p in profiles.rglob('*.json')}
    def resolve(name):
        d=json.loads(paths[name].read_text()); result=resolve(d['inherits']) if d.get('inherits') else {}
        for inc in d.get('include',[]): result.update(resolve(inc))
        result.update(d)
        for key in ('inherits','include'): result.pop(key,None)
        return result
    presets={'machine':('Bambu Lab P2S 0.4 nozzle',None),'orange':('Bambu PLA Lite @BBL P2S 0.4 nozzle','#FF671F'),'white':('Bambu PLA Lite @BBL P2S 0.4 nozzle','#FFFFFF'),'black':('Bambu PLA Basic @BBL P2S','#000000')}
    for key,(name,color) in presets.items():
        data=resolve(name)
        if color: data['filament_colour']=[color]
        (work/(key+'.json')).write_text(json.dumps(data,indent=2)+'\n')
    for name,groups,materials,height,first in [('FrontShell',[('FrontShell',front)],['orange'],.16,.2),('Controls',[('Knob',knob),('FourKeys',grouped)],['orange','white','black'],.12,.12)]:
        out=work/name;out.mkdir(exist_ok=True);export(out/'input.3mf',groups)
        process=resolve('0.20mm Standard @BBL P2S' if name=='FrontShell' else '0.12mm High Quality @BBL P2S')
        overrides=dict(layer_height=str(height),initial_layer_print_height=str(first),wall_generator='classic' if name=='FrontShell' else 'arachne',wall_loops='3',sparse_infill_density='15%',sparse_infill_pattern='gyroid',enable_support='1',support_type='tree(auto)',support_on_build_plate_only='1',support_critical_regions_only='0',support_threshold_angle='30',support_top_z_distance='0.2',brim_type='outer_only',brim_width='5',enable_prime_tower='1',prime_tower_width='35',prime_tower_brim_width='3',curr_bed_type='Textured PEI Plate',wipe_tower_x=['200' if name=='FrontShell' else '20'],wipe_tower_y=['220'],print_sequence='by layer' if name=='FrontShell' else 'by object')
        process.update(overrides);(out/'process.json').write_text(json.dumps(process,indent=2)+'\n')
        filename='Discora-P1-FrontShell.3mf' if name=='FrontShell' else 'Discora-Controls-Sequential.3mf'
        command=['/Applications/BambuStudio.app/Contents/MacOS/BambuStudio','--datadir',str(out/'userdata'),'--load-settings',str(work/'machine.json')+';'+str(out/'process.json'),'--load-filaments',';'.join(str(work/(v+'.json')) for v in materials),'--arrange','0','--orient','0','--ensure-on-bed','--slice','0','--outputdir',str(out),'--export-3mf',filename,str(out/'input.3mf')]
        with (out/'slice.log').open('w') as log: result=subprocess.run(command,cwd=out,stdout=log,stderr=subprocess.STDOUT)
        assert result.returncode==0,(name,result.returncode)
        project=out/filename
        with zipfile.ZipFile(project) as z: members={n:z.read(n) for n in z.namelist()}
        settings=json.loads(members['Metadata/project_settings.config'])
        settings['different_settings_to_system'][0]=';'.join(sorted(set(filter(None,settings['different_settings_to_system'][0].split(';')))|set(overrides)))
        members['Metadata/project_settings.config']=json.dumps(settings,indent=2).encode()
        for n,b in list(members.items()):
            if n.endswith(('.config','.model')): members[n]=re.sub(r'/Users/[^"\s<>]+/([^/"\s<>]+)',r'\1',b.decode()).encode()
        with zipfile.ZipFile(project,'w',zipfile.ZIP_DEFLATED) as z:
            for n,b in members.items(): z.writestr(n,b)
        print('SLICE_OK',name,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    main(parser.parse_args().work.resolve())
