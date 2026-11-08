"""Restore FCStd GUI resource order without changing geometry or material data.

FreeCAD reads embedded resources sequentially, in XML registration order.
Run after a headless edit that appended GUI resources in a different order.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


def repair(model, output):
    with zipfile.ZipFile(model) as archive:
        entries = archive.infolist()
        payload = {item.filename: archive.read(item) for item in entries}
        assert len(payload) == len(entries), 'Duplicate archive entries'
        gui = ET.fromstring(payload['GuiDocument.xml'])
        resources = list(dict.fromkeys(
            value for element in gui.iter() for key, value in element.attrib.items()
            if key.lower() == 'file' and value))
        assert all(name in payload for name in resources), 'Missing GUI resource'
        gui_names = {'GuiDocument.xml', *resources}
        order = [item.filename for item in entries if item.filename not in gui_names]
        order += ['GuiDocument.xml', *resources]
        metadata = {item.filename: item for item in entries}
        with zipfile.ZipFile(output, 'w') as target:
            for name in order:
                target.writestr(metadata[name], payload[name])
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == order
        assert all(archive.read(name) == data for name, data in payload.items())
    return {
        'before_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
        'model_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'archive_entries': len(payload),
        'gui_resource_count': len(resources),
        'all_entry_contents_identical': True,
        'geometry_and_material_data_changed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.model.resolve() == args.output.resolve():
        parser.error('Use a separate output file to retain the original')
    print(json.dumps(repair(args.model, args.output), indent=2))
