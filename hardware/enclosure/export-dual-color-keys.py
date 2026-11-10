"""Export four two-volume keys as a Bambu-readable 3MF; never contact a printer.

Run with FreeCAD Python. Material 1 is orange PLA Lite, material 2 white PLA Lite.
The source CAD contains one compound per key: orange solid first, white islands after.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import FreeCAD as A
import Part
import MeshPart

ROOT = Path(__file__).resolve().parent
KEYS = ('PlayPauseKey', 'EjectKey', 'PrevKey', 'NextKey')
NS = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
ET.register_namespace('', NS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, default=ROOT/'Discora.FCStd')
    parser.add_argument('--output', type=Path, default=ROOT.parent.parent/'tmp/dual-color-keys')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    doc = A.openDocument(str(args.model.resolve()))
    model = ET.Element('model', unit='millimeter', attrib={'xmlns': NS})
    ET.SubElement(model, 'metadata', name='Application').text = 'Discora'
    resources = ET.SubElement(model, 'resources')
    build = ET.SubElement(model, 'build')
    config = ET.Element('config')
    report = dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                  white_depth_mm=.6, minimum_symbol_stroke_mm=.8,
                  materials={'1': 'PLA Lite Orange #FF671F', '2': 'PLA Lite White #FFFFFF'},
                  orientation='Symbol face up; flange on bed',
                  printer_contacted=False, physical_print_test=False, keys={})
    normal = A.Vector(0, -27, 38)
    rotation = A.Rotation(normal, A.Vector(0, 0, 1))
    for index, name in enumerate(KEYS):
        shape = doc.getObject(name).Shape.copy()
        assert shape.isValid() and len(shape.Solids) in (3, 4), name
        shape.Placement = A.Placement(A.Vector(), rotation).multiply(shape.Placement)
        b = shape.BoundBox
        shape.translate(A.Vector(-b.Center.x, -b.Center.y, -b.ZMin))
        body, marks = shape.Solids[0], Part.makeCompound(shape.Solids[1:])
        assert body.common(marks).Volume < 1e-7
        fused = body.multiFuse(marks.Solids).removeSplitter()
        assert fused.isValid() and len(fused.Solids) == 1
        assert abs(marks.BoundBox.ZLength-.6) < 1e-6
        assert abs(marks.BoundBox.ZMax-shape.BoundBox.ZMax) < 1e-6
        parent_id = index*3+3
        cfg = ET.SubElement(config, 'object', id=str(parent_id))
        ET.SubElement(cfg, 'metadata', key='name', value=name)
        ET.SubElement(cfg, 'metadata', key='extruder', value='1')
        volume_ids = []
        meshes = []
        for material, solid in enumerate((body, marks), 1):
            mesh = MeshPart.meshFromShape(Shape=solid, LinearDeflection=.025,
                                         AngularDeflection=.15, Relative=False)
            assert mesh.isSolid(), (name, material)
            volume_id = index*3+material
            volume_ids.append(volume_id)
            label = name+('_Orange' if material == 1 else '_WhiteSymbols')
            obj = ET.SubElement(resources, 'object', id=str(volume_id), type='model', name=label)
            node = ET.SubElement(obj, 'mesh')
            vertices = ET.SubElement(node, 'vertices')
            points, triangles = mesh.Topology
            for v in points:
                ET.SubElement(vertices, 'vertex', x=f'{v.x:.9f}', y=f'{v.y:.9f}', z=f'{v.z:.9f}')
            faces = ET.SubElement(node, 'triangles')
            for a, b, c in triangles:
                ET.SubElement(faces, 'triangle', v1=str(a), v2=str(b), v3=str(c))
            part = ET.SubElement(cfg, 'part', id=str(volume_id), subtype='normal_part')
            ET.SubElement(part, 'metadata', key='name', value=label)
            ET.SubElement(part, 'metadata', key='extruder', value=str(material))
            mesh.write(str(args.output/(label+'.stl')))
            meshes.append(dict(material=material, closed_mesh=True, facets=mesh.CountFacets,
                               solids=len(solid.Solids), volume_mm3=solid.Volume))
        assembly = ET.SubElement(resources, 'object', id=str(parent_id), type='model', name=name)
        components = ET.SubElement(assembly, 'components')
        for volume_id in volume_ids:
            ET.SubElement(components, 'component', objectid=str(volume_id))
        x, y = 110+index%2*22, 110+index//2*22
        ET.SubElement(build, 'item', objectid=str(parent_id), transform=f'1 0 0 0 1 0 0 0 1 {x} {y} 0')
        report['keys'][name] = dict(volumes=meshes, overlap_mm3=body.common(marks).Volume,
                                    assembled_single_connected_solid=True,
                                    size_mm=[shape.BoundBox.XLength, shape.BoundBox.YLength, shape.BoundBox.ZLength])
    types = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'
    rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'
    target = args.output/'Discora-buttons-orange-white.3mf'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', types)
        archive.writestr('_rels/.rels', rels)
        archive.writestr('3D/3dmodel.model', ET.tostring(model, encoding='utf-8', xml_declaration=True))
        archive.writestr('Metadata/model_settings.config', ET.tostring(config, encoding='utf-8', xml_declaration=True))
    report['file'] = target.name
    report['file_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
    (args.output/'mesh-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    A.closeDocument(doc.Name)
    print('DUAL_COLOR_KEYS_OK', target)


if __name__ == '__main__':
    main()
