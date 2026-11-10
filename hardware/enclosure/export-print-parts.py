"""Export the twelve rigid PLA pieces in review orientations; no printer is contacted.

Run with FreeCAD Python. Output is intentionally temporary until physical fit is checked.
Key STL files are single-material envelopes; export-dual-color-keys.py preserves their materials.
"""
import argparse
import hashlib
import json
from pathlib import Path
import FreeCAD as A
import MeshPart

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,default=ROOT/'Discora.FCStd')
    parser.add_argument('--output',type=Path,default=ROOT.parent.parent/'tmp'/'pla-print')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    doc=A.openDocument(str(args.model.resolve()))
    normal=A.Vector(0,-27,38);normal.normalize()
    rotations={
        'FrontShell':A.Rotation(A.Vector(1,0,0),90),
        'RearShell':A.Rotation(A.Vector(1,0,0),-90),
        'SpeakerCarrier':A.Rotation(A.Vector(1,0,0),-90),
        'LPort':A.Rotation(A.Vector(1,0,0),A.Vector(0,0,1)),
        'RPort':A.Rotation(A.Vector(-1,0,0),A.Vector(0,0,1)),
        'PlayPauseKey':A.Rotation(normal,A.Vector(0,0,1)),
        'EjectKey':A.Rotation(normal,A.Vector(0,0,1)),
        'PrevKey':A.Rotation(normal,A.Vector(0,0,1)),
        'NextKey':A.Rotation(normal,A.Vector(0,0,1)),
        'ButtonRetainer':A.Rotation(normal,A.Vector(0,0,1)),
        'DisplayRetainer':A.Rotation(normal,A.Vector(0,0,1)),
        'Knob':A.Rotation(normal,A.Vector(0,0,1)),
    }
    report={'model_sha256':hashlib.sha256(args.model.read_bytes()).hexdigest(),
            'freecad_version':A.Version()[:3], 'printer_user_description':'Bambu P2SC',
            'build_volume_mm':[256,256,256], 'primary_nozzle_mm':.4,
            'alternate_nozzle_mm':.2, 'brim_allowance_mm':5,
            'linear_deflection_mm':.1,'angular_deflection_rad':.35,
            'physical_print_test':False,'parts':{}}
    for name,rotation in rotations.items():
        shape=doc.getObject(name).Shape.copy()
        if name in ('PlayPauseKey','EjectKey','PrevKey','NextKey'):
            # STL loses material assignments; the dedicated 3MF retains them.
            shape=shape.Solids[0].multiFuse(shape.Solids[1:]).removeSplitter()
        assert shape.isValid() and len(shape.Solids)==1,name
        shape.Placement=A.Placement(A.Vector(),rotation).multiply(shape.Placement)
        b=shape.BoundBox
        shape.translate(A.Vector(128-b.Center.x,128-b.Center.y,-b.ZMin))
        print('MESH_START',name,flush=True)
        mesh=MeshPart.meshFromShape(Shape=shape,LinearDeflection=.1,AngularDeflection=.35,Relative=False)
        assert mesh.isSolid(),name
        target=args.output/(name+'.stl');mesh.write(str(target))
        b=shape.BoundBox
        fits=min(b.XMin,b.YMin)>=5 and max(b.XMax,b.YMax)<=251 and b.ZMax<=256
        assert fits,(name,b)
        report['parts'][name]={'file':target.name,'size_xyz_mm':[b.XLength,b.YLength,b.ZLength],
            'facets':mesh.CountFacets,'closed_mesh':True,'fits_with_5mm_brim':fits,
            'rotation_quaternion_xyzw':list(rotation.Q),
            'stl_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
        if name.endswith('Key'):
            report['parts'][name]['color_print_source']='export-dual-color-keys.py; STL is a single-material envelope'
        print('MESH_OK',name,mesh.CountFacets,flush=True)
    A.closeDocument(doc.Name)
    (args.output/'mesh-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
