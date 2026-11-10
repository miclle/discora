"""Slice and verify the two-material knob with installed Bambu profiles; never print."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as E
import zipfile

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--meshes',type=Path,default=ROOT.parent.parent/'tmp/dual-color-knob')
    parser.add_argument('--output',type=Path,default=ROOT/'dual-color-knob-checks.json')
    args=parser.parse_args()
    w=args.meshes.resolve();out=w/'slicer';out.mkdir(exist_ok=True)
    report=json.loads((w/'mesh-report.json').read_text())
    assert report['model_sha256']==hashlib.sha256((ROOT/'Discora.FCStd').read_bytes()).hexdigest()
    assert report['file_sha256']==hashlib.sha256((w/report['file']).read_bytes()).hexdigest()
    paths={p.stem:p for p in Path('/Applications/BambuStudio.app/Contents/Resources/profiles/BBL').rglob('*.json')}
    def resolve(name,chain=()):
        assert name not in chain
        data=json.loads(paths[name].read_text());flat={}
        if data.get('inherits'):flat.update(resolve(data['inherits'],chain+(name,)))
        for inc in data.get('include',[]):flat.update(resolve(inc,chain+(name,)))
        flat.update(data)
        for k in ('inherits','include'):flat.pop(k,None)
        return flat
    names=dict(machine='Bambu Lab P2S 0.4 nozzle',process='0.12mm High Quality @BBL P2S',black='Bambu PLA Basic @BBL P2S',white='Bambu PLA Lite @BBL P2S 0.4 nozzle')
    overrides=dict(initial_layer_print_height='0.12',wall_generator='arachne',wall_loops='3',sparse_infill_density='15%',sparse_infill_pattern='gyroid',enable_support='1',support_type='tree(auto)',support_on_build_plate_only='1',support_threshold_angle='30',support_top_z_distance='0.2',brim_type='outer_only',brim_width='5',enable_prime_tower='1')
    for k,n in names.items():
        d=resolve(n)
        if k=='process':d.update(overrides)
        if k in ('black','white'):d['filament_colour']=['#000000' if k=='black' else '#FFFFFF']
        (out/(k+'.json')).write_text(json.dumps(d,indent=2)+'\n')
    command=['/Applications/BambuStudio.app/Contents/MacOS/BambuStudio','--datadir',str(out/'userdata'),'--load-settings',str(out/'machine.json')+';'+str(out/'process.json'),'--load-filaments',str(out/'black.json')+';'+str(out/'white.json'),'--arrange','1','--slice','0','--export-3mf','Discora-knob-bambu.3mf','--outputdir',str(out),str(w/'Discora-knob-black-white.3mf')]
    with (out/'slice.log').open('w') as f:p=subprocess.run(command,cwd=out,stdout=f,stderr=subprocess.STDOUT)
    assert p.returncode==0,f'Slicing failed ({p.returncode}); see {out / "slice.log"}'
    settings=dict(profile_names=names,process_overrides=overrides,profile_sha256={k:hashlib.sha256((out/(k+'.json')).read_bytes()).hexdigest() for k in names})
    print('SLICE_OK',flush=True)

    s=out;content=(s/'plate_1.gcode').read_text()
    project=s/'Discora-knob-bambu.3mf'
    with zipfile.ZipFile(project) as z:
        config=E.fromstring(z.read('Metadata/model_settings.config'));objs=config.findall('object');assert len(objs)==1
        parts=objs[0].findall('part');assert len(parts)==2
        materials={part.find("metadata[@key='name']").get('value'):part.find("metadata[@key='extruder']").get('value') for part in parts}
        assert materials=={'Knob_Black':'1','Knob_WhiteIndex':'2'}
        presets=json.loads(z.read('Metadata/project_settings.config'));assert presets['filament_colour']==['#000000','#FFFFFF']
        ident=config.find("plate/model_instance/metadata[@key='identify_id']").get('value')
        assert all(int(v)==0 for part in parts for k,v in part.find('mesh_stat').attrib.items() if k!='face_count')
        # Save the actual slicer's own plate preview for local inspection.
        (w/'bambu-preview.png').write_bytes(z.read('Metadata/plate_1.png'))
    obj=None;tool=None;height=None;xy=[0.,0.];moves={};relative=False
    for line in content.splitlines():
        line=line.strip()
        if line.startswith('; Z_HEIGHT:'):
            height=float(line.split(':')[1]);obj=None
        if line in ('; WIPE_TOWER_START','; CP TOOLCHANGE START'):obj=None
        if line.startswith('; OBJECT_ID:'):obj=line.split(':')[1].strip()
        if re.fullmatch(r'T\d+',line):tool=int(line[1:])
        if line.startswith('M83'):relative=True
        if line.startswith('M82'):relative=False
        if not re.match(r'G[0123]\s',line):continue
        values={k:float(v) for k,v in re.findall(r'([XYE])(-?(?:\d+(?:\.\d*)?|\.\d+))',line)}
        for i,k in enumerate('XY'):
            if k in values:xy[i]=values[k]
        if obj==ident and tool==1 and values.get('E',0)>0 and ('X' in values or 'Y' in values):
            assert relative
            moves.setdefault(height,[]).append(tuple(xy))
    assert len(moves)==5 and min(moves)>13.3 and max(moves)<=14,moves
    for points in moves.values():
        assert len(points)>=4
        assert all(max(v[i] for v in points)-min(v[i] for v in points)<2.5 for i in (0,1))
    white={str(h):dict(extrusion_moves=len(v),xy_bounds_mm=[[min(p[i] for p in v),max(p[i] for p in v)] for i in (0,1)]) for h,v in moves.items()}
    def field(pattern):return re.search(pattern,content).group(1)
    report['slicing']=dict(exit_code=0,version=field(r'; BambuStudio ([^\n]+)'),layer_height_mm=.12,first_layer_height_mm=.12,layers=int(field(r'total layer number: (\d+)')),estimated_time=field(r'total estimated time: ([^\n]+)'),filament_g_including_purge=[float(x) for x in field(r'total filament weight \[g\] : ([^\n]+)').split(',')],white_toolpaths_by_height=white,gcode_sha256=hashlib.sha256((s/'plate_1.gcode').read_bytes()).hexdigest(),vendor_T65535_parser_notice='Invalid T command (T65535)' in (s/'slice.log').read_text(),printer_contacted=False,physical_print_test=False,**settings)
    report['bambu_project']=dict(file=project.name,sha256=hashlib.sha256(project.read_bytes()).hexdigest(),object_count=1,volumes_per_object=2,material_assignment_verified=True,mesh_repair_count=0)
    assert report['model_sha256']==hashlib.sha256((ROOT/'Discora.FCStd').read_bytes()).hexdigest(), 'Model changed during slicing'
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('DUAL_COLOR_KNOB_SLICE_OK',args.output)

if __name__=='__main__':main()
