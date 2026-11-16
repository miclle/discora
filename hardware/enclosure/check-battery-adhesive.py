"""Check sealed strap slots, a 1.5 mm adhesive allowance and preserved printed P3."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
import FreeCAD as A
import Part

V=A.Vector
def difference(a,b):
    if a.exportBrepToString()==b.exportBrepToString():return 0.0
    return a.cut(b).Volume+b.cut(a).Volume


def check(model,baseline):
    d=A.openDocument(str(model.resolve()));old=A.openDocument(str(baseline.resolve()))
    fixed={}
    for o in old.Objects:
        if o.Name in ('Battery','RearShell') or hasattr(o,'Group') or not hasattr(o,'Shape') or o.Shape.isNull():continue
        fixed[o.Name]=difference(o.Shape,d.getObject(o.Name).Shape)
        assert fixed[o.Name]<.001,o.Name
    rear=d.RearShell.Shape
    assert rear.isValid() and len(rear.Solids)==1
    assert old.RearShell.Shape.cut(rear).Volume<.001
    added=rear.cut(old.RearShell.Shape)
    slots=[];expected=[]
    source=d.Base.Shape.fuse(d.BatteryCradle.Shape)
    for x in (-61,58):
        for y in (24,44):
            probe=Part.makeBox(3,8,20,V(x,y,.5))
            fill=source.common(probe);expected.append(fill)
            assert fill.cut(rear).Volume<.001
            floor=Part.makeBox(3,8,5,V(x,y,1))
            assert floor.cut(rear).Volume<.001
            slots.append(dict(origin_xy_mm=[x,y],floor_filled_mm3=floor.Volume,restored_material_mm3=fill.Volume))
    assert difference(added,Part.makeCompound(expected))<.001
    mirror=A.Matrix();mirror.A11=-1
    reflected=added.copy();reflected.transformShape(mirror,True)
    assert difference(reflected,added)<.001
    assert difference(d.Battery.Shape,old.Battery.Shape.translated(V(0,0,1.5)))<.001
    assert float(d.Battery.AdhesiveThickness)==1.5
    b=d.Battery.Shape.BoundBox
    assert abs(b.ZMin-7.5)<1e-7 and abs(b.ZMax-27.5)<1e-7
    # Full-footprint tape is a conservative clearance envelope, not a tape pattern.
    adhesive=Part.makeBox(112,70,1.5,V(-56,6,6))
    objects=[o for g in ('Shell','Controls','Carrier','Hardware') for o in d.getObject(g).Group]
    adhesive_clashes={o.Name:adhesive.common(o.Shape).Volume for o in objects if adhesive.BoundBox.intersect(o.Shape.BoundBox)}
    assert all(v<.001 for v in adhesive_clashes.values()),adhesive_clashes
    floor=Part.makeBox(112,70,.01,V(-56,6,5.99))
    assert floor.cut(rear).Volume<.001
    gap={n:d.Battery.Shape.distToShape(d.getObject(n).Shape)[0] for n in ('SpeakerCarrier','Drive','Bridge','SataPlugClearance','SataCableClearance','FrontShell','BatteryCradle')}
    assert min(gap.values())>=1-1e-7
    assert all(d.Battery.Shape.common(d.getObject(n).Shape).Volume<.001 for n in gap)
    assert abs(rear.BoundBox.YMax-94.7)<1e-7
    with zipfile.ZipFile(model) as new,zipfile.ZipFile(baseline) as previous:
        import xml.etree.ElementTree as E
        gui=previous.read('GuiDocument.xml');refs=[v for el in E.fromstring(gui).iter() for k,v in el.attrib.items() if k.lower()=='file' and v]
        assert all(new.read(n)==previous.read(n) for n in ['GuiDocument.xml']+refs)
    # Verify material face order for every unchanged two-colour part.
    colors={}
    for n in ('PlayPauseKey','EjectKey','PrevKey','NextKey','Knob'):
        a=old.getObject(n).Shape;bshape=d.getObject(n).Shape
        colors[n]=len(a.Faces)==len(bshape.Faces) and all(abs(x.Area-y.Area)<1e-7 and (x.CenterOfMass-y.CenterOfMass).Length<1e-7 for x,y in zip(a.Faces,bshape.Faces))
        assert colors[n]
    return dict(model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),unchanged_shapes_difference_mm3=fixed,changed_shapes=['RearShell','Battery'],added_rear_material_mm3=added.Volume,overall_depth_mm=94.7,battery_bounds_xyz_mm=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],adhesive_thickness_mm=1.5,adhesive_envelope_clashes_mm3=adhesive_clashes,floor_thickness_mm=5,side_stop_thickness_mm=2,side_clearance_mm=1,closed_strap_slots=slots,clearances_mm=gap,color_face_order_preserved=colors,gui_resources_preserved=len(refs),p3_world_geometry_unchanged=True,physical_fit_verified=False,adhesive_retention_and_release_verified=False,all_pass=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=check(a.model,a.baseline)
    a.output.write_text(json.dumps(r,indent=2)+'\n')
    print('BATTERY_ADHESIVE_OK',r['added_rear_material_mm3'],r['clearances_mm'],flush=True)
