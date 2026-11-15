"""Read back every formal STL/3MF against the saved CAD and release manifest.

Run with FreeCAD Python. Does not contact a printer or regenerate toolpaths.
"""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import FreeCAD as A
import Mesh

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    folder = ROOT/'print'
    manifest = json.loads((folder/'manifest.json').read_text())
    model = ROOT/'Discora.FCStd'
    assert digest(model) == manifest['model_sha256']
    doc = A.openDocument(str(model))
    meshes, plates = {}, {}
    assert len(manifest['parts']) == 11 and len(manifest['plates']) == 6
    assigned = [part for plate in manifest['plates'].values() for part in plate['parts']]
    assert len(assigned) == len(set(assigned)) == 11
    assert set(assigned) == set(manifest['parts'])
    for name, item in manifest['parts'].items():
        path = folder/item['file']
        assert digest(path) == item['stl_sha256'], name
        mesh = Mesh.Mesh(str(path))
        assert mesh.isSolid() and mesh.CountFacets == item['facets'], name
        b = mesh.BoundBox
        assert abs(b.ZMin)<.001 and min(b.XMin,b.YMin)>=4.99
        assert max(b.XMax,b.YMax)<=251.01 and b.ZMax<=256
        assert all(abs(a-b)<.001 for a,b in zip((b.XLength,b.YLength,b.ZLength),item['size_xyz_mm']))
        volume = doc.getObject(name).Shape.Volume
        error = abs(mesh.Volume-volume)/volume
        assert error<.01, (name,error)
        meshes[name] = dict(closed=True, relative_cad_volume_error=error,
                            on_bed=True, fits_bed=True)
    for name, plate in manifest['plates'].items():
        path = folder/plate['file']
        assert digest(path)==plate['project_sha256'], name
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            config = json.loads(archive.read('Metadata/project_settings.config'))
            assert float(config['nozzle_diameter'][0])==.4
            for key,value in plate['support_settings'].items():
                assert config[key]==value, (name,key)
            if name in ('RearShell','SpeakerCarrier'):
                expected='0' if name=='RearShell' else '1'
                assert config['support_on_build_plate_only']==config['support_critical_regions_only']==expected
                overrides=config['different_settings_to_system'][0].split(';')
                assert {'support_on_build_plate_only','support_critical_regions_only'}<=set(overrides)
            settings=ET.fromstring(archive.read('Metadata/model_settings.config'))
            objects=settings.findall('object')
            assert len(objects)==len(plate['parts']), name
            repairs=[]
            for obj in objects:
                parts=obj.findall('part')
                assert len(parts)==(2 if name in ('Keys','Knob') else 1)
                for part in parts:
                    repairs.extend(int(v) for k,v in part.find('mesh_stat').attrib.items() if k!='face_count')
            assert not any(repairs), (name,repairs)
            if name in ('Keys','Knob'):
                assert config['filament_colour']==(['#FF671F','#FFFFFF'] if name=='Keys' else ['#000000','#FFFFFF'])
                for obj in objects:
                    assert {p.find("metadata[@key='extruder']").get('value') for p in obj.findall('part')}=={'1','2'}
            h=hashlib.sha256();count=0;extrusions=0
            with archive.open('Metadata/plate_1.gcode') as stream:
                for raw in stream:
                    h.update(raw)
                    if raw.startswith(b'; Z_HEIGHT:'):count+=1
                    if count and raw.startswith((b'G1 ',b'G2 ',b'G3 ')):
                        match=re.search(rb' E(-?[\d.]+)',raw)
                        if match and float(match[1])>0:extrusions+=1
            assert h.hexdigest()==plate['gcode_sha256']
            assert count==plate['layers'] and extrusions>0, (name,count)
            for entry in archive.namelist():
                if entry.endswith(('.config','.model')):
                    assert b'/Users/' not in archive.read(entry), entry
            plates[name]=dict(layers=count, extrusion_moves=extrusions, mesh_repairs=0,
                              settings_persisted=True, archive_valid=True)
        print('PLATE_OK',name,count,flush=True)
    p3=json.loads((ROOT/'p3-terminal-mouth-checks.json').read_text())
    p2=json.loads((ROOT/'p2-trapezoid-outlet-checks.json').read_text())
    controls=json.loads((ROOT/'control-layout-checks.json').read_text())
    charging=json.loads((ROOT/'charging-port-checks.json').read_text())
    charging_print=json.loads((ROOT/'charging-port-print-checks.json').read_text())
    grille=json.loads((ROOT/'grille-clearance-checks.json').read_text())
    grille_print=json.loads((ROOT/'grille-print-checks.json').read_text())
    battery=json.loads((ROOT/'battery-floor-checks.json').read_text())
    assert battery['all_pass'] and battery['model_sha256']==manifest['model_sha256']
    assert grille['model_sha256']==grille_print['model_sha256']==battery['baseline_sha256']
    assert all(battery['unchanged_shapes_difference_mm3'][n]<.001 for n in manifest['parts'] if n!='RearShell')
    assert grille['all_pass'] and grille_print['all_pass']
    assert all(grille['preserved_shape_difference_mm3'][n]<.001 for n in manifest['parts'] if n not in ('FrontShell','RearShell'))
    depth_print=json.loads((ROOT/'p2-depth-print-checks.json').read_text())
    assert depth_print['all_pass'] and depth_print['model_sha256']==manifest['model_sha256']
    assert charging['model_sha256']==charging_print['model_sha256']==grille['baseline_sha256']
    assert charging['all_pass'] and charging_print['all_pass']
    assert controls['model_sha256']==charging['baseline_sha256'] and controls['all_pass']
    assert all(charging['unchanged_finished_parts_difference_mm3'][name]<.001
               for name in manifest['parts'] if name!='RearShell')
    assert controls['baseline_sha256']==p3['model_sha256'] and p3['all_pass'] and p2['all_pass']
    assert all(controls['unchanged_finished_parts_difference_mm3'][name]<.001
               for name in ('RearShell','SpeakerCarrier'))
    assert p3['geometry']['baseline_sha256']==p2['model_sha256']
    assert p3['geometry']['p2_entire_shape_difference_mm3']<.001
    for name, audit in [('FrontShell',grille_print),('RearShell',depth_print),('SpeakerCarrier',p3['slice'])]:
        assert manifest['plates'][name]['gcode_sha256']==audit['gcode_sha256']
        assert manifest['parts'][name]['stl_sha256']==audit['stl_sha256']
    report=dict(model_sha256=manifest['model_sha256'],manifest_sha256=digest(folder/'manifest.json'),
                meshes=meshes, plates=plates, all_pass=True, printer_contacted=False)
    (ROOT/'print-release-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    A.closeDocument(doc.Name)
    print('PRINT_RELEASE_OK',sum(p['layers'] for p in plates.values()),flush=True)


if __name__=='__main__':
    main()
