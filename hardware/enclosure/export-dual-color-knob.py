"""Export the black knob and flush white index as one two-material 3MF.

Run with FreeCAD Python. The two closed volumes retain their shared origin;
STL exports are companion volumes, not separately arranged print objects.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile

import FreeCAD as A
import Part
import MeshPart

ROOT = Path(__file__).resolve().parent
NS = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
ET.register_namespace('', NS)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path, default=ROOT/'Discora.FCStd')
    p.add_argument('--previous', type=Path, help='Optional saved model before the white index revision')
    p.add_argument('--output', type=Path, default=ROOT.parent.parent/'tmp/dual-color-knob')
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    doc = A.openDocument(str(args.model.resolve()))
    shape = doc.Knob.Shape.copy()
    assert shape.isValid() and len(shape.Solids) == 2
    body, mark = shape.Solids
    assert body.common(mark).Volume < 1e-7
    fused = body.fuse(mark).removeSplitter()
    assert fused.isValid() and len(fused.Solids) == 1
    indices = [i for i, f in enumerate(shape.Faces) if any(f.isSame(m) for m in mark.Faces)]
    assert len(indices) == 6
    # Verify the stored face-material array, without claiming a GUI reopen test.
    with zipfile.ZipFile(args.model) as z:
        gui = ET.fromstring(z.read('GuiDocument.xml'))
        name = gui.find(".//ViewProvider[@name='Knob']/Properties/Property[@name='ShapeAppearance']/MaterialList").get('file')
        data = z.read(name)
        count = struct.unpack('<I', data[:4])[0]
        assert count == len(shape.Faces) and len(data) == 4+36*count
        for i in range(count):
            assert data[8+24*i:12+24*i] == (b'\xff'*4 if i in indices else b'\xff\x00\x00\x00')
    report = dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                  build_sha256=hashlib.sha256((ROOT/'build.FCMacro').read_bytes()).hexdigest(),
                  white_mark_size_mm=[.7, 2.2, .6], white_faces_zero_based=indices,
                  saved_gui_material_array_verified=True, gui_reopen_verified=False,
                  materials={'1': 'PLA Basic Black #000000', '2': 'PLA Lite White #FFFFFF'},
                  orientation='Disk on bed; index face up', overlap_mm3=body.common(mark).Volume,
                  assembled_single_connected_solid=True, printer_contacted=False,
                  physical_print_test=False, volumes=[])
    if args.previous:
        old = A.openDocument(str(args.previous.resolve()))
        same = {}
        for group in ('Shell', 'Controls', 'Carrier', 'Hardware'):
            for obj in doc.getObject(group).Group:
                if obj.Name == 'Knob':
                    continue
                same[obj.Name] = obj.Shape.exportBrepToString() == old.getObject(obj.Name).Shape.exportBrepToString()
        assert len(same) == 31 and all(same.values())
        before = old.Knob.Shape
        changes = [fused.cut(before), before.cut(fused)]
        outside = sum(delta.cut(mark).Volume for delta in changes if delta.Solids and delta.Volume>1e-9)
        assert outside < 1e-6, 'Knob changed outside the index region'
        report.update(previous_model_sha256=hashlib.sha256(args.previous.read_bytes()).hexdigest(),
                      unchanged_finished_shape_brep=same, change_outside_marker_mm3=outside)
        A.closeDocument(old.Name)
    # Match the existing knob print orientation; normal is outward from the slope.
    rotation = A.Rotation(A.Vector(0, -27, 38), A.Vector(0, 0, 1))
    shape.Placement = A.Placement(A.Vector(), rotation).multiply(shape.Placement)
    b = shape.BoundBox
    shape.translate(A.Vector(-b.Center.x, -b.Center.y, -b.ZMin))
    body, mark = shape.Solids
    b = mark.BoundBox
    for actual, expected in ((b.XLength, .7), (b.YLength, 2.2), (b.ZLength, .6), (b.ZMax, 13.9)):
        assert abs(actual-expected) < 1e-6, (actual, expected)
    model = ET.Element('model', unit='millimeter', attrib={'xmlns': NS})
    ET.SubElement(model, 'metadata', name='Application').text = 'Discora'
    resources = ET.SubElement(model, 'resources')
    build = ET.SubElement(model, 'build')
    config = ET.Element('config')
    cfg = ET.SubElement(config, 'object', id='3')
    ET.SubElement(cfg, 'metadata', key='name', value='Knob')
    ET.SubElement(cfg, 'metadata', key='extruder', value='1')
    for material, solid, label in ((1, body, 'Knob_Black'), (2, mark, 'Knob_WhiteIndex')):
        mesh = MeshPart.meshFromShape(Shape=solid, LinearDeflection=.025, AngularDeflection=.15, Relative=False)
        assert mesh.isSolid(), label
        obj = ET.SubElement(resources, 'object', id=str(material), type='model', name=label)
        node = ET.SubElement(obj, 'mesh')
        vertices = ET.SubElement(node, 'vertices')
        points, triangles = mesh.Topology
        for v in points:
            ET.SubElement(vertices, 'vertex', x=f'{v.x:.9f}', y=f'{v.y:.9f}', z=f'{v.z:.9f}')
        faces = ET.SubElement(node, 'triangles')
        for a, b, c in triangles:
            ET.SubElement(faces, 'triangle', v1=str(a), v2=str(b), v3=str(c))
        part = ET.SubElement(cfg, 'part', id=str(material), subtype='normal_part')
        ET.SubElement(part, 'metadata', key='name', value=label)
        ET.SubElement(part, 'metadata', key='extruder', value=str(material))
        mesh.write(str(args.output/(label+'.stl')))
        report['volumes'].append(dict(name=label, material=material, closed_mesh=True,
                                      facets=mesh.CountFacets, volume_mm3=solid.Volume))
    assembly = ET.SubElement(resources, 'object', id='3', type='model', name='Knob')
    components = ET.SubElement(assembly, 'components')
    for material in (1, 2):
        ET.SubElement(components, 'component', objectid=str(material))
    ET.SubElement(build, 'item', objectid='3', transform='1 0 0 0 1 0 0 0 1 128 128 0')
    types = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'
    rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'
    target = args.output/'Discora-knob-black-white.3mf'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', types)
        z.writestr('_rels/.rels', rels)
        z.writestr('3D/3dmodel.model', ET.tostring(model, encoding='utf-8', xml_declaration=True))
        z.writestr('Metadata/model_settings.config', ET.tostring(config, encoding='utf-8', xml_declaration=True))
    report.update(file=target.name, file_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), all_pass=True)
    (args.output/'mesh-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    A.closeDocument(doc.Name)
    print('DUAL_COLOR_KNOB_OK', target, flush=True)


if __name__ == '__main__':
    main()
