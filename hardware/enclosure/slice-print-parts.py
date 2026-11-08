"""Slice exported meshes locally with installed Bambu profiles; never send to a printer.

Run export-print-parts.py first. STL, vendor profiles and G-code stay in tmp/.
Only the evidence summary is written alongside the CAD model.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parent
PROFILES={'machine':'Bambu Lab P2S 0.4 nozzle','process':'0.20mm Standard @BBL P2S','filament':'Generic PLA @BBL P2S'}
OVERRIDES=dict(enable_support='1',support_type='tree(auto)',support_on_build_plate_only='1',
               support_threshold_angle='30',support_top_z_distance='0.2',wall_loops='3',
               sparse_infill_density='15%',sparse_infill_pattern='gyroid',brim_type='outer_only',brim_width='5')

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--meshes',type=Path,default=Path('tmp/pla-print'))
    p.add_argument('--model',type=Path,default=ROOT/'Discora.FCStd')
    p.add_argument('--bambu',type=Path,default=Path('/Applications/BambuStudio.app/Contents/MacOS/BambuStudio'))
    p.add_argument('--profiles',type=Path,default=Path('/Applications/BambuStudio.app/Contents/Resources/profiles/BBL'))
    p.add_argument('--output',type=Path,default=ROOT/'print-checks.json')
    args=p.parse_args();meshes=args.meshes.resolve();out=meshes/'slicer';out.mkdir(exist_ok=True)
    report=json.loads((meshes/'mesh-report.json').read_text())
    assert report['model_sha256']==digest(args.model),'Mesh and model revisions differ'
    paths={f.stem:f for f in args.profiles.rglob('*.json')}
    def resolve(name,chain=()):
        assert name not in chain,name
        data=json.loads(paths[name].read_text());flat={}
        if data.get('inherits'):flat.update(resolve(data['inherits'],chain+(name,)))
        for inc in data.get('include',[]):flat.update(resolve(inc,chain+(name,)))
        flat.update(data)
        for k in ('inherits','include'):flat.pop(k,None)
        return flat
    settings={}
    for key,name in PROFILES.items():
        data=resolve(name)
        if key=='process':data.update(OVERRIDES)
        path=out/(key+'.json');path.write_text(json.dumps(data,indent=2)+'\n');settings[key]=path
    report.update(profile_names=PROFILES,process_overrides=OVERRIDES,
                  profile_sha256={k:digest(v) for k,v in settings.items()},plates={},
                  printer_profile_mapping='User P2SC; installed Bambu P2S profile used for local slicing only',
                  printer_contacted=False,gcode_execution_validated=False)
    for name in ('RearShell','FrontShell','SpeakerCarrier','SmallParts'):
        target=out/name;target.mkdir(exist_ok=True)
        names=[name] if name!='SmallParts' else ['LPort','RPort','PlayPauseKey','EjectKey','PrevKey','NextKey','ButtonRetainer','Knob']
        for n in names:assert digest(meshes/(n+'.stl'))==report['parts'][n]['stl_sha256']
        command=[str(args.bambu.resolve()),'--datadir',str(out/('userdata-'+name)),
                 '--load-settings',str(settings['machine'])+';'+str(settings['process']),
                 '--load-filaments',str(settings['filament']),'--slice','0','--outputdir',str(target)]
        if name=='SmallParts':command+=['--arrange','1']
        command += [str(meshes/(n+'.stl')) for n in names]
        log=out/(name+'.log')
        with log.open('w') as stream:run=subprocess.run(command,cwd=out,stdout=stream,stderr=subprocess.STDOUT)
        assert run.returncode==0,f'{name}: slicing failed; see {log}'
        gcode=target/'plate_1.gcode';content=gcode.read_text()
        def field(pattern):
            found=re.search(pattern,content)
            assert found,pattern
            return found.group(1)
        report['slicer_version']=field(r'; BambuStudio ([^\n]+)')
        report['plates'][name]=dict(parts=names,exit_code=run.returncode,gcode_sha256=digest(gcode),
            total_estimated_time=field(r'total estimated time: ([^\n]+)'),
            filament_g=float(field(r'total filament weight \[g\] : ([\d.]+)')),
            layers=int(field(r'total layer number: (\d+)')),
            vendor_T65535_parser_notice='Invalid T command (T65535)' in log.read_text())
        print('SLICE_OK',name,report['plates'][name],flush=True)
    assert report['model_sha256']==digest(args.model),'Model changed during slicing'
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('PRINT_CHECKS_OK',args.output)

if __name__=='__main__':main()
