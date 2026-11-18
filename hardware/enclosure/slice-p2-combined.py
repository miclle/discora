"""Slice the fixed P2/small-part layout with P2's released PLA settings; no printer contact."""
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path
from importlib.machinery import SourceFileLoader
ROOT=Path(__file__).resolve().parent
base=SourceFileLoader('discora_slicer',str(ROOT/'slice-print-parts.py')).load_module()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--bambu',type=Path,default=Path('/Applications/BambuStudio.app/Contents/MacOS/BambuStudio'));p.add_argument('--profiles',type=Path,default=Path('/Applications/BambuStudio.app/Contents/Resources/profiles/BBL'));a=p.parse_args();w=a.work.resolve();target=w/'slice';target.mkdir(exist_ok=True);meshes=w/'meshes'
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();layout=json.loads((meshes/'layout.json').read_text());assert layout['model_sha256']==sha(ROOT/'Discora.FCStd')
 paths={f.stem:f for f in a.profiles.rglob('*.json')}
 def resolve(name):
  data=json.loads(paths[name].read_text());flat=resolve(data['inherits']) if data.get('inherits') else {}
  for inc in data.get('include',[]):flat.update(resolve(inc))
  flat.update(data)
  for k in ('inherits','include'):flat.pop(k,None)
  return flat
 settings={}
 for key,name in base.PROFILES.items():
  data=resolve(name)
  if key=='process':data.update(base.OVERRIDES,support_on_build_plate_only='0',support_critical_regions_only='0',layer_height='0.16',curr_bed_type='Textured PEI Plate')
  path=target/(key+'.json');path.write_text(json.dumps(data,indent=2)+'\n');settings[key]=path
 with zipfile.ZipFile(ROOT/'print/Discora-P2-RearShell.3mf') as z:original=json.loads(z.read('Metadata/project_settings.config'))
 process=json.loads(settings['process'].read_text());keys=list(base.OVERRIDES)+['layer_height','initial_layer_print_height','print_sequence']
 for k in keys:assert process[k]==original[k],(k,process[k],original[k])
 command=[str(a.bambu),'--datadir',str(w/'userdata'),'--load-settings',str(settings['machine'])+';'+str(settings['process']),'--load-filaments',str(settings['filament']),'--slice','0','--outputdir',str(target),'--export-3mf','Discora-P2-Combined.3mf','--arrange','0','--orient','0','--ensure-on-bed']
 for item in layout['parts']:
  file=meshes/item['file'];assert sha(file)==item['stl_sha256'];command.append(str(file))
 with (w/'bambu.log').open('w') as log:run=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,cwd=w)
 assert run.returncode==0,run.returncode
 project=target/'Discora-P2-Combined.3mf'
 with zipfile.ZipFile(project) as z:members={n:z.read(n) for n in z.namelist()}
 config=json.loads(members['Metadata/project_settings.config']);overrides=set(keys)|{'initial_layer_print_height'}
 assert config['curr_bed_type']=='Textured PEI Plate',config['curr_bed_type']
 config['different_settings_to_system'][0]=';'.join(sorted(set(filter(None,config['different_settings_to_system'][0].split(';')))|overrides))
 for k in keys:assert config[k]==original[k],(k,config[k],original[k])
 members['Metadata/project_settings.config']=json.dumps(config,indent=2).encode()
 for n,b in list(members.items()):
  if n.endswith(('.config','.model')):members[n]=re.sub(r'/Users/[^"\s<>]+/([^/"\s<>]+)',r'\1',b.decode()).encode()
 with zipfile.ZipFile(project,'w',zipfile.ZIP_DEFLATED) as z:
  for n,b in members.items():z.writestr(n,b)
 gcode=target/'plate_1.gcode';text=gcode.read_text()
 def field(pattern):return re.search(pattern,text)[1]
 stats=json.loads((target/'result.json').read_text());assert len(stats['sliced_plates'])==1
 report=dict(model_sha256=layout['model_sha256'],layout_sha256=sha(meshes/'layout.json'),project_sha256=sha(project),gcode_sha256=sha(gcode),total_estimated_time=field(r'total estimated time: ([^\n]+)'),filament_g=float(field(r'total filament weight \[g\] : ([\d.]+)')),layers=int(field(r'total layer number: (\d+)')),settings={k:config[k] for k in keys},plate_type=config['curr_bed_type'],bed_temperature_c=float(config['textured_plate_temp'][0]),first_layer_bed_temperature_c=float(config['textured_plate_temp_initial_layer'][0]),warnings=stats['sliced_plates'][0]['warning_message'],physical_piece_count=8,printer_contacted=False)
 (w/'slice-checks.json').write_text(json.dumps(report,indent=2)+'\n');print('COMBINED_SLICE_OK',report,flush=True)
if __name__=='__main__':main()
