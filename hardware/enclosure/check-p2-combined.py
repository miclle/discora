"""Read back the combined 3MF and audit all layers against its actual meshes."""
import argparse
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import FreeCAD
import Mesh
import numpy as np
from shapely import union_all
from shapely.geometry import LineString, Point, box
import slice_layer_geometry as geo
from stock_fastener_geometry import LOCKS

ROOT = Path(__file__).resolve().parent
NS = {'c': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
P = '{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transform(vertices, value):
    matrix = np.array(list(map(float, value.split()))).reshape(4, 3)
    return vertices @ matrix[:3] + matrix[3]


def check(work):
    project = work / 'slice/Discora-P2-Combined.3mf'
    gcode = work / 'slice/plate_1.gcode'
    layout = json.loads((work / 'meshes/layout.json').read_text())
    sliced = json.loads((work / 'slice-checks.json').read_text())
    assert sha(ROOT / 'Discora.FCStd') == layout['model_sha256']
    assert sha(ROOT / 'print/manifest.json') == layout['source_manifest_sha256']
    assert sha(project) == sliced['project_sha256']
    shapes = {}
    with zipfile.ZipFile(project) as archive:
        assert archive.read('Metadata/plate_1.gcode') == gcode.read_bytes()
        settings = json.loads(archive.read('Metadata/project_settings.config'))
        meta = ET.fromstring(archive.read('Metadata/model_settings.config'))
        model = ET.fromstring(archive.read('3D/3dmodel.model'))
        for item in model.findall('c:build/c:item', NS):
            object_id = item.get('objectid')
            obj = model.find("c:resources/c:object[@id='" + object_id + "']", NS)
            name = meta.find("object[@id='" + object_id + "']/metadata[@key='name']").get('value').removesuffix('.stl')
            component = obj.find('c:components/c:component', NS)
            source = ET.fromstring(archive.read(component.get(P + 'path').lstrip('/')))
            mesh = source.find('.//c:mesh', NS)
            vertices = np.array([[float(v.get(k)) for k in ('x', 'y', 'z')] for v in mesh.find('c:vertices', NS)])
            vertices = transform(transform(vertices, component.get('transform')), item.get('transform'))
            faces = np.array([[int(t.get(k)) for k in ('v1', 'v2', 'v3')] for t in mesh.find('c:triangles', NS)])
            shape = Mesh.Mesh([[tuple(vertices[i]) for i in face] for face in faces])
            expected = next(p for p in layout['parts'] if p['name'] == name)
            original = Mesh.Mesh(str(work / 'meshes' / expected['file']))
            # Compare every triangle after canonicalizing slicer vertex/facet ordering.
            source_vertices, source_faces = original.Topology
            source_vertices = np.array([tuple(v) for v in source_vertices])
            mapping = []
            error = 0.
            for start in range(0, len(vertices), 128):
                chunk = vertices[start:start + 128]
                distances = ((chunk[:, None, :] - source_vertices[None, :, :]) ** 2).sum(axis=2)
                nearest = distances.argmin(axis=1)
                error = max(error, float(np.sqrt(distances[np.arange(len(chunk)), nearest]).max()))
                mapping.extend(nearest.tolist())
            assert error < .0001, (name, error)
            mapped_faces = np.array(mapping)[faces]
            assert sorted(tuple(sorted(f)) for f in mapped_faces) == sorted(tuple(sorted(f)) for f in source_faces), name
            assert shape.isSolid() and len(shape.getSeparateComponents()) == 1
            assert abs(vertices[:, 2].min()) < .0001
            assert (vertices[:, :2].min(axis=0) >= 5).all() and (vertices[:, :2].max(axis=0) <= 251).all()
            shapes[name] = shape
            expected['saved_3mf_maximum_coordinate_error_mm'] = error
    assert len(shapes) == 8 and len(settings['filament_type']) == 1
    assert float(settings['nozzle_diameter'][0]) == .4
    assert settings['print_sequence'] == 'by layer'
    assert settings['curr_bed_type'] == 'Textured PEI Plate'
    assert float(settings['textured_plate_temp'][0]) == float(settings['textured_plate_temp_initial_layer'][0]) == 55
    text = gcode.read_text()
    assert re.search(r'^\s*M140 S55', text, re.M) and re.search(r'^\s*M190 S55', text, re.M)
    assert 'G29.1 Z0.01 ; for Textured PEI Plate' in text
    assert settings['support_on_build_plate_only'] == settings['support_critical_regions_only'] == '0'
    merged = Mesh.Mesh()
    for shape in shapes.values():
        merged.addMesh(shape)
    meshpath = work / 'actual-combined.stl'
    merged.write(str(meshpath))
    layers = geo.parse(gcode)
    assert abs(layers[0]['h'] - .2) < 1e-6
    assert all(abs(layer['h'] - .16) < 1e-5 for layer in layers[1:])
    polys = geo.sections(meshpath, layers, work / 'sections-Combined.json')
    audit = geo.audit('Combined', meshpath, gcode, work)
    raw = {}
    for path in audit['unbacked_paths']:
        raw.setdefault(path['layer'] - 1, []).append(path)
    residual = []
    for i, paths in raw.items():
        layer = layers[i]
        supports = []
        for lower in layers[max(0, i - 3):i]:
            if layer['z'] - lower['z'] > layer['h'] + .22:
                continue
            supports.extend(LineString((s['a'], s['b'])).buffer(s['width'] / 2 + .1) for s in lower['segments'] if s['feature'].startswith('Support'))
        backing = polys[i - 1].buffer(.35).union(union_all(supports))
        for path in paths:
            line = LineString((path['a'], path['b']))
            free = line.difference(backing)
            if free.length <= .5:
                continue
            count = max(1, int(line.length / .2))
            distance = max(line.interpolate(j / count, normalized=True).distance(backing) for j in range(count + 1))
            residual.append(dict(layer=i + 1, z=layer['z'], feature=path['feature'], maximum_distance_to_backing_mm=distance, free_length_mm=free.length))
    # Same charging/tool-well checks as the standalone P2, accounting for its +10 mm X shift.
    doc = FreeCAD.openDocument(str(ROOT / 'Discora.FCStd'))
    yoffset = 128 - doc.RearShell.Shape.BoundBox.Center.z
    rois = {'DC': Point(68, 12 + yoffset).buffer(5.1), 'TypeC': box(68 - 5.35, 24 + yoffset - 2.55, 68 + 5.35, 24 + yoffset + 2.55)}
    bores = {name: [] for name in rois}
    obstructions = []
    well_hits = []
    washer_support = []
    contacts = {name: 0 for name in shapes}
    first_regions = {}
    for name, shape in shapes.items():
        path = work / ('actual-' + name + '.stl')
        shape.write(str(path))
        first_regions[name] = geo.sections(path, layers[:1], work / ('first-' + name + '.json'))[0]
    wells = [(Point(sign * x + 138, z + yoffset).buffer(3.2), 94.7 - head) for sign in (-1, 1) for x, z, root, end, bottom, head in LOCKS]
    toolpath_bounds = [256., 256., 0., 0.]
    for i, layer in enumerate(layers):
        for seg in layer['segments']:
            line = LineString((seg['a'], seg['b']))
            feature = seg['feature']
            if feature in ('Custom', 'Skirt'):
                continue
            b = line.bounds
            toolpath_bounds = [min(toolpath_bounds[0], b[0] - seg['width']/2), min(toolpath_bounds[1], b[1] - seg['width']/2), max(toolpath_bounds[2], b[2] + seg['width']/2), max(toolpath_bounds[3], b[3] + seg['width']/2)]
            support = feature.startswith('Support')
            if i == 0 and not support and feature != 'Brim':
                for name, region in first_regions.items():
                    if line.intersection(region.buffer(.05)).length > .05:
                        contacts[name] += 1
            if layer['z'] <= 10:
                for name, roi in rois.items():
                    if line.intersection(roi).length < .05:
                        continue
                    if support:
                        bores[name].append(i + 1)
                    elif feature != 'Brim':
                        obstructions.append([name, i + 1, feature])
            for roi, maxz in wells:
                if layer['z'] <= maxz and feature != 'Brim' and line.intersection(roi).length > .05:
                    well_hits.append([i + 1, feature])
            if support:
                for name, roi in first_regions.items():
                    if name.startswith('CarrierWasher') and line.intersection(roi.buffer(.1)).length > .05:
                        washer_support.append([name, i + 1])
    duration = lambda value: sum(int(n) * {'h': 3600, 'm': 60, 's': 1}[unit] for n, unit in re.findall(r'(\d+)([hms])', value))
    manifest = json.loads((ROOT / 'print/manifest.json').read_text())
    original_seconds = sum(duration(manifest['plates'][name]['total_estimated_time']) for name in ('RearShell', 'SmallParts'))
    combined_seconds = duration(sliced['total_estimated_time'])
    report = dict(**sliced, source_manifest_sha256=layout['source_manifest_sha256'], parts=layout['parts'], all_layer_sections_checked=len(polys), new_islands=audit['new_islands'], remaining_spans_after_model_and_support=residual, first_layer_contacts=contacts, washer_support_layers=washer_support, bore_support_layers={k: sorted(set(v)) for k, v in bores.items()}, bore_model_obstructions=obstructions, tool_well_obstructions_or_support=well_hits, toolpath_bounds_mm=toolpath_bounds, physical_print_verified=False, acceptance={'maximum_local_distance_to_backing_mm': 2, 'island_support_ratio_minimum': .9, 'sample_spacing_mm': .2}, support_access='Original P2 open front/side mouths and accessible DC bore; retainers have open undersides; washers require no support.', replaces_plates=['RearShell', 'SmallParts'], original_two_plate_seconds=original_seconds, combined_seconds=combined_seconds, saved_seconds=original_seconds - combined_seconds)
    report['all_pass'] = (not report['warnings'] and all(contacts.values()) and not washer_support and not obstructions and not well_hits and all(p['support_ratio'] >= .9 for p in audit['new_islands']) and all(p['maximum_distance_to_backing_mm'] <= 2 for p in residual) and min(toolpath_bounds[:2]) >= 0 and max(toolpath_bounds[2:]) <= 256)
    (work / 'combined-print-checks.json').write_text(json.dumps(report, indent=2) + '\n')
    print('COMBINED_CHECK', report['all_pass'], 'layers', len(layers), 'bounds', toolpath_bounds, 'max residual', max((p['maximum_distance_to_backing_mm'] for p in residual), default=0), flush=True)
    assert report['all_pass']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    check(parser.parse_args().work)
