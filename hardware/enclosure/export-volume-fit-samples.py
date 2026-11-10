"""Export three open press-fit sleeves from the actual knob builder (FreeCAD Python).

The sleeves compare insertion fit only; full-knob torque and retention need testing.
No printer is contacted. Files are temporary and labelled by rib-tip diameter.
"""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import FreeCAD as A
import Part
import MeshPart

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=ROOT.parent.parent/'tmp'/'volume-fit')
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
source=ROOT/'build.FCMacro'
# Execute only the pure geometry function, never the interactive build entry.
tree=ast.parse(source.read_text())
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='volume_shapes')
V=A.Vector
scope=dict(Part=Part,math=math,V=V,X=V(1,0,0),Y=V(0,1,0),Z=V(0,0,1))
exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),scope)
report=dict(build_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            physical_fit_verified=False,diameter_refers_to='inscribed diameter at six rib tips, not carrier bore',samples=[])
for index,diameter in enumerate((5.5,5.6,5.7)):
    knob=scope['volume_shapes'](diameter)['knob']
    sample=knob.common(Part.makeCylinder(4.6,8,V(0,-10.8,0),V(0,1,0)))
    assert sample.isValid() and len(sample.Solids)==1
    sample.Placement=A.Placement(V(),A.Rotation(V(0,1,0),V(0,0,1))).multiply(sample.Placement)
    b=sample.BoundBox
    sample.translate(V(112+index*16-b.Center.x,128-b.Center.y,-b.ZMin))
    mesh=MeshPart.meshFromShape(Shape=sample,LinearDeflection=.03,AngularDeflection=.15,Relative=False)
    assert mesh.isSolid()
    path=args.output/f'Grip-{diameter:.1f}mm.stl';mesh.write(str(path))
    report['samples'].append(dict(file=path.name,tip_diameter_mm=diameter,
        plate_order_left_to_right=index+1,outer_diameter_mm=9.2,height_mm=8,
        facets=mesh.CountFacets,closed_mesh=True,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    print('FIT_SAMPLE_OK',path.name,flush=True)
(args.output/'fit-samples.json').write_text(json.dumps(report,indent=2)+'\n')
