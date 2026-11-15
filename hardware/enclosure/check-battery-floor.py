"""Verify removal of only the battery plinth, retaining stops, slots and printed P3."""
import argparse,hashlib,json,zipfile
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
        if o.Name in ('Battery','BatteryCradle','RearShell') or hasattr(o,'Group') or not hasattr(o,'Shape') or o.Shape.isNull():continue
        fixed[o.Name]=difference(o.Shape,d.getObject(o.Name).Shape)
        assert fixed[o.Name]<.001,o.Name
    rails=Part.makeCompound([Part.makeBox(2,50,14,V(x,6,6)) for x in (-59,57)])
    assert difference(d.BatteryCradle.Shape,rails)<.001
    removed=old.BatteryCradle.Shape.cut(rails)
    actual_removed=old.RearShell.Shape.cut(d.RearShell.Shape)
    assert difference(actual_removed,removed)<.001
    assert d.RearShell.Shape.cut(old.RearShell.Shape).Volume<.001
    assert d.RearShell.Shape.isValid() and len(d.RearShell.Shape.Solids)==1
    assert difference(d.Battery.Shape,old.Battery.Shape.translated(V(0,0,-2)))<.001
    b=d.Battery.Shape.BoundBox
    assert abs(b.ZMin-6)<1e-7 and abs(b.ZMax-26)<1e-7
    # Full pack footprint meets the existing floor; strap slots remain outside it.
    footprint=Part.makeBox(112,70,.01,V(-56,6,5.99))
    assert abs(footprint.common(d.RearShell.Shape).Volume-112*70*.01)<.001
    slots=[]
    for x in (-61,58):
        for y in (24,44):
            probe=Part.makeBox(3,8,20,V(x,y,.5))
            v=probe.common(d.RearShell.Shape).Volume
            assert v<.001
            slots.append(dict(origin_xyz_mm=[x,y,.5],size_xyz_mm=[3,8,20],obstruction_mm3=v))
    mirror=A.Matrix();mirror.A11=-1
    reflected=actual_removed.copy();reflected.transformShape(mirror,True)
    assert difference(reflected,actual_removed)<.001
    gap={n:d.Battery.Shape.distToShape(d.getObject(n).Shape)[0] for n in ('SpeakerCarrier','Drive','Bridge','SataPlugClearance','SataCableClearance','FrontShell')}
    assert min(gap.values())>=1-1e-7,gap
    assert abs(d.RearShell.Shape.BoundBox.YMax-94.7)<1e-7
    with zipfile.ZipFile(model) as new,zipfile.ZipFile(baseline) as previous:
        import xml.etree.ElementTree as E
        gui=previous.read('GuiDocument.xml');refs=[v for el in E.fromstring(gui).iter() for k,v in el.attrib.items() if k.lower()=='file' and v]
        assert all(new.read(n)==previous.read(n) for n in ['GuiDocument.xml']+refs)
        assert new.namelist()[-len(refs)-1:]==['GuiDocument.xml']+refs
    return dict(model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),unchanged_shapes_difference_mm3=fixed,changed_objects=['RearShell','BatteryCradle','Battery'],removed_plinth_volume_mm3=actual_removed.Volume,added_rear_material_mm3=0,overall_depth_mm=94.7,battery_bounds_xyz_mm=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],battery_down_mm=2,floor_thickness_mm=5,floor_contact_area_mm2=7840,side_stop_thickness_mm=2,side_clearance_mm=1,side_stop_top_z_mm=20,strap_slots=slots,clearances_mm=gap,gui_resources_preserved=len(refs),p3_world_geometry_unchanged=True,physical_fit_verified=False,all_pass=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=check(a.model,a.baseline);a.output.write_text(json.dumps(r,indent=2)+'\n');print('BATTERY_FLOOR_OK',r['removed_plinth_volume_mm3'],r['clearances_mm'],flush=True)
