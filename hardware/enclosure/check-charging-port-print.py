"""Audit the updated rear-shell layers, open charging bores and side-outlet supports."""
import argparse
import hashlib
import json
from pathlib import Path
import FreeCAD  # Initialize FreeCAD before Mesh is loaded by the layer helper.
from shapely.geometry import box, LineString, Point
from shapely import union_all
import slice_layer_geometry as layers

ROOT=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--baseline-mesh',type=Path,required=True)
    args=p.parse_args();w=args.work
    mesh=w/'meshes/RearShell.stl';gcode=w/'meshes/slicer/RearShell/plate_1.gcode'
    ls=layers.parse(gcode)
    audit=layers.audit('RearShell',mesh,gcode,w)
    polys=layers.sections(mesh,ls,w/'sections-RearShell.json')
    base=layers.sections(args.baseline_mesh,ls,w/'sections-baseline.json')
    # Match the print exporter: X=128+CAD X; Y=128+CAD Z-shell Z center.
    doc=FreeCAD.openDocument(str((ROOT/'Discora.FCStd').resolve()))
    shift=128-doc.RearShell.Shape.BoundBox.Center.z
    bores={'DC':Point(58,12+shift).buffer(5.4-.35),
           'TypeC':box(58-5.65+.35,24+shift-2.85+.35,58+5.65-.35,24+shift+2.85-.35)}
    blockers=[];support_counts={name:0 for name in bores};support_layers={name:set() for name in bores}
    new_overhangs=[];outlet_unbacked=[]
    outlet=box(42.5,77,48.5,114).union(box(207.5,77,213.5,114))
    def support_before(i):
        return union_all([LineString((s['a'],s['b'])).buffer(s['width']/2+.35)
                          for lower in ls[max(0,i-4):i] for s in lower['segments']
                          if s['feature'].startswith('Support')])
    for i,layer in enumerate(ls):
        if layer['z']<=10+.001:
            for s in layer['segments']:
                line=LineString((s['a'],s['b']))
                for name,bore in bores.items():
                    if line.intersection(bore).length>.05:
                        if s['feature'].startswith('Support'):
                            support_counts[name]+=1;support_layers[name].add(i+1)
                        else:blockers.append(dict(layer=i+1,port=name,feature=s['feature']))
        if not i:continue
        extra=polys[i].difference(polys[i-1].buffer(.35)).difference(
            base[i].difference(base[i-1].buffer(.35)).buffer(.03))
        if extra.area>.05:
            support=support_before(i)
            new_overhangs.append(dict(layer=i+1,area_mm2=extra.area,
                                      unsupported_mm2=extra.difference(support).area))
    for entry in audit['unbacked_paths']:
        line=LineString((entry['a'],entry['b']))
        if line.intersection(outlet).length<=1 or not 21<=93-entry['z']<=69:continue
        free=line.difference(polys[entry['layer']-2].buffer(.03))
        ratio=free.intersection(support_before(entry['layer']-1)).length/free.length if free.length else 1
        if ratio<.95:outlet_unbacked.append(dict(layer=entry['layer'],support_ratio=ratio))
    warnings=json.loads((w/'meshes/slicer/RearShell/result.json').read_text())['sliced_plates'][0]['warning_message']
    report=dict(model_sha256=hashlib.sha256((ROOT/'Discora.FCStd').read_bytes()).hexdigest(),
                stl_sha256=hashlib.sha256(mesh.read_bytes()).hexdigest(),
                gcode_sha256=hashlib.sha256(gcode.read_bytes()).hexdigest(),
                layers=len(ls),bore_layers_checked=sum(l['z']<=10+.001 for l in ls),
                bore_toolpath_obstructions=blockers,new_overhangs=new_overhangs,
                bore_support_segments=support_counts,
                bore_support_layers={n:sorted(v) for n,v in support_layers.items()},
                bore_support_cleanup_required=any(support_counts.values()),
                ports_requiring_support_cleanup=[n for n,v in support_counts.items() if v],
                support_access='Straight 10 mm through bores, accessible from rear and open shell; physical removal force not verified',
                unsupported_outlet_paths=outlet_unbacked,
                uncovered_islands=[x for x in audit['new_islands'] if x['support_ratio']<.05],
                slicer_warnings=warnings,physical_print_verified=False)
    report['all_pass']=not(blockers or outlet_unbacked or report['uncovered_islands'] or warnings
                           or any(x['unsupported_mm2']>.05 for x in new_overhangs))
    (ROOT/'charging-port-print-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    assert report['all_pass'],'Rear-shell layer audit failed; see charging-port-print-checks.json'
    print('CHARGING_PRINT_OK',len(ls),report['bore_layers_checked'])


if __name__=='__main__':main()
