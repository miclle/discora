"""Verify the relocated controls and 28 mm knob in the current saved CAD."""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path

import FreeCAD as A
import MeshPart
import Part

ROOT = Path(__file__).resolve().parent
V = A.Vector
Y = V(0, 1, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'control-layout-current-checks.json')
    args = parser.parse_args()
    model = ROOT/'Discora.FCStd'
    doc = A.openDocument(str(model))
    pose = A.Placement(V(52, 20, 165+20*27/38), A.Rotation(Y, V(0, 27/38, -1)))
    knob = doc.Knob.Shape.copy()
    knob.Placement = pose.inverse().multiply(knob.Placement)
    section = knob.common(Part.makeBox(30, .01, 30, V(-15, -8, -15))).BoundBox
    assert abs(section.XLength-28)<1e-6 and abs(section.ZLength-28)<1e-6
    assert len(knob.Solids)==2 and knob.Solids[0].common(knob.Solids[1]).Volume<.001
    fused = knob.Solids[0].fuse(knob.Solids[1]).removeSplitter()
    assert fused.isValid() and len(fused.Solids)==1
    mesh = MeshPart.meshFromShape(Shape=fused, LinearDeflection=.025, AngularDeflection=.15, Relative=False)
    assert mesh.isSolid()
    sweep = Part.makeCylinder(14, 12.5, V(0, -12.9, 0), Y).fuse(
        Part.makeCylinder(12, 1.4, V(0, -.4, 0), Y))
    sweep = sweep.cut(Part.makeCylinder(3, 14, V(0, -13, 0), Y))
    sweep = sweep.cut(Part.makeCylinder(6, 3.5, V(0, -2.4, 0), Y))
    sweep.Placement = pose
    collisions = {}
    for group in ('Shell', 'Controls', 'Carrier', 'Hardware'):
        for obj in doc.getObject(group).Group:
            if obj.Name=='Knob' or not sweep.BoundBox.intersect(obj.Shape.BoundBox):
                continue
            overlap = sweep.common(obj.Shape).Volume
            if overlap>.001:
                collisions[obj.Name] = overlap
    assert not collisions, collisions
    assert sweep.BoundBox.YMin>1
    source = ROOT/'build.FCMacro'
    tree = ast.parse(source.read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=='volume_shapes')
    scope = dict(Part=Part, math=math, V=V, X=V(1,0,0), Y=Y, Z=V(0,0,1))
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), scope)
    built = scope['volume_shapes']()['knob']
    delta = built.cut(knob).Volume+knob.cut(built).Volume
    assert delta<.001, delta
    report = dict(model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                  cross_span_mm=[section.XLength, section.ZLength],
                  continuous_rotation_clashes=collisions,
                  front_edge_gap_mm=sweep.BoundBox.YMin,
                  build_knob_difference_mm3=delta, closed_knob_mesh=True,
                  all_pass=True, physical_fit_verified=False)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print('CONTROL_LAYOUT_OK', report)


if __name__=='__main__':
    main()
