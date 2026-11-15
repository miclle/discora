"""Check saved charging bores, bonded sockets and unchanged geometry against a baseline."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import FreeCAD as A
import Part
import charging_port_geometry as ports

ROOT = Path(__file__).resolve().parent
V = A.Vector


def difference(a, b):
    if a.exportBrepToString() == b.exportBrepToString():
        return 0.0
    return a.cut(b).Volume+b.cut(a).Volume


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, default=ROOT/'Discora.FCStd')
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'charging-port-checks.json')
    args = parser.parse_args()
    doc, old = (A.openDocument(str(p.resolve())) for p in (args.model, args.baseline))
    objects = [o for g in ('Shell','Controls','Carrier','Hardware') for o in doc.getObject(g).Group]
    rear = doc.RearShell.Shape
    assert rear.isValid() and len(rear.Solids)==1
    expected = ports.apply(old.RearShell.Shape)
    assert difference(rear, expected)<.001
    unchanged = {o.Name:difference(o.Shape,old.getObject(o.Name).Shape)
                 for o in objects if o.Name!='RearShell'}
    assert all(v<.001 for v in unchanged.values())
    # Tight boxes bound both user-selected lower-left mounting regions.
    zones = Part.makeCompound([Part.makeBox(14.8,10.2,14.8,V(x-7.4,82.9,z-7.4)) for x,z in ports.CENTERS_XZ])
    outside = difference(rear.cut(zones),old.RearShell.Shape.cut(zones))
    assert outside<.001
    report = dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                  baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
                  unchanged_finished_parts_difference_mm3=unchanged,
                  rear_outside_mount_zones_difference_mm3=outside,
                  centers_xyz_mm={'DC':[-70,93,12],'TypeC':[-70,93,24]},
                  openings_mm={'DC_diameter':10.8,'TypeC_width':11.3,'TypeC_height':5.7},
                  sleeve_outer_mm={'DC_diameter':14.8,'TypeC_xz':[14.8,9.7]},
                  sleeve_internal_depth_mm=5,total_support_length_mm=10,
                  face_flush_y_mm=93,dc_trim_required=False,ports={})
    for n, shape in {**ports.socket_shapes(),**ports.wire_shapes()}.items():
        saved = doc.getObject(n).Shape
        assert difference(saved,shape)<.001
        hits = {}
        for o in objects:
            if not shape.BoundBox.intersect(o.Shape.BoundBox):continue
            overlap=shape.common(o.Shape).Volume
            if overlap>.001:hits[o.Name]=overlap
        assert not hits,(n,hits)
        report['ports'][n]=dict(clashes=hits,body_depth_mm=shape.BoundBox.YLength,
                               drive_clearance_mm=shape.distToShape(doc.Drive.Shape)[0])
        if n.endswith('Socket'):
            # Enclose the housing along a rear-to-front insertion into its bore.
            b=shape.BoundBox
            sweep=(Part.makeCylinder(5.2,31.5+40,V(-70,61.5,12),V(0,1,0)) if n.startswith('DC')
                   else Part.makeBox(10.9,15.9+40,5.3,V(-75.45,77.1,21.35)))
            assert all(sweep.common(o.Shape).Volume<.001 for o in objects
                       if sweep.BoundBox.intersect(o.Shape.BoundBox)),n
            report['ports'][n]['rear_insertion_clear']=True
    # Measure free transverse size from saved bores at wall and sleeve depths.
    sections=[]
    for y in (83.01,85.5,88.01,92.99):
        for name,x,z,width,height in [('DC',-70,12,10.8,10.8),('TypeC',-70,24,11.3,5.7)]:
            probe=(Part.makeCylinder(width/2,.002,V(x,y,z),V(0,1,0)) if name=='DC'
                   else Part.makeBox(width,.002,height,V(x-width/2,y,z-height/2)))
            obstruction=probe.common(rear).Volume
            assert obstruction<.001
            sections.append(dict(port=name,y_mm=y,obstruction_mm3=obstruction))
    report['bore_sections']=sections
    # Independent combined cross-section: the compact sleeve roots join by 0.25 mm.
    window=Part.makeBox(15,.01,25,V(-77.5,86,4.5))
    dc_ring=Part.makeCylinder(7.4,.01,V(-70,86,12),V(0,1,0))
    usb_ring=Part.makeBox(14.8,.01,9.7,V(-77.4,86,19.15))
    expected=old.RearShell.Shape.common(window).multiFuse([dc_ring,usb_ring]).cut(doc.ChargingPortBores.Shape)
    error=difference(rear.common(window),expected)
    assert error<.001,error
    ahead=Part.makeBox(15,.01,25,V(-77.5,82.98,4.5))
    assert difference(rear.common(ahead),old.RearShell.Shape.common(ahead))<.001
    report['saved_sleeve_sections']={'combined_cross_section_difference_mm3':error,'inner_end_y_mm':83}
    sleeve=ports.sleeve_blanks().cut(ports.bores())
    screw_obstruction=sleeve.common(doc.RearFastenerCuts.Shape).Volume
    assert screw_obstruction<.001
    assert all(sleeve.common(o.Shape).Volume<.001 for o in objects if o.Name!='RearShell'
               and sleeve.BoundBox.intersect(o.Shape.BoundBox))
    report.update(rear_screw_access_obstruction_mm3=screw_obstruction,
                  center_spacing_mm=12,center_to_left_edge_mm=15,opening_edge_gap_mm=3.75,
                  center_above_shell_bottom_mm={'DC':11,'TypeC':23},
                  layout='Front-left lower corner; USB above DC; rear view lower right')
    # Preserve two-color face order and its GUI resource bytes.
    names=('PlayPauseKey','EjectKey','PrevKey','NextKey','Knob')
    face_order={n:all(abs(a.Area-b.Area)<1e-7 and (a.CenterOfMass-b.CenterOfMass).Length<1e-7
                     for a,b in zip(doc.getObject(n).Shape.Faces,old.getObject(n).Shape.Faces,strict=True)) for n in names}
    assert all(face_order.values())
    with zipfile.ZipFile(args.baseline) as before,zipfile.ZipFile(args.model) as after:
        gui_root=ET.fromstring(after.read('GuiDocument.xml'))
        resources=[v for e in gui_root.iter() for k,v in e.attrib.items() if k.lower()=='file' and v]
        assert len(resources)==len(set(resources)), 'Each GUI resource reference needs its own archive entry'
        assert after.namelist()[-len(resources)-1:]==['GuiDocument.xml',*resources], 'GUI archive order differs from registration order'
        a={e.get('name'):e for e in ET.fromstring(before.read('GuiDocument.xml')).iter('ViewProvider')}
        b={e.get('name'):e for e in ET.fromstring(after.read('GuiDocument.xml')).iter('ViewProvider')}
        for n in a:
            assert ET.tostring(a[n])==ET.tostring(b[n])
            for e in a[n].iter():
                for k,v in e.attrib.items():
                    if k.lower()=='file' and v:assert before.read(v)==after.read(v)
    report.update(color_face_order_preserved=face_order,gui_resource_order_verified=True,
                  gui_resource_references_unique=True,all_original_viewproviders_preserved=True,all_pass=True,
                  physical_fit_verified=False,adhesive_retention_verified=False,
                  electrical_charging_verified=False,
                  limits=['Socket housings use user maximum dimensions; terminal and cable shapes not measured.',
                          '8 mm tail reservation is not a verified wire bend radius.',
                          'Type-C charger board not selected or placed; no electrical charging claim.'])
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('CHARGING_PORTS_OK',report['ports'])


if __name__=='__main__':
    main()
