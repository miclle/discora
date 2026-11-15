"""Check the recessed locally relieved P1 grille against corrected drivers and the printed P3."""
import argparse,hashlib,json,zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from importlib.machinery import SourceFileLoader
import FreeCAD as A
import Part
ROOT=Path(__file__).resolve().parent
ac=SourceFileLoader('acoustics',str(ROOT/'check-speaker-acoustics.py')).load_module()
V=A.Vector

def check(model,baseline):
    doc=A.openDocument(str(model.resolve()));old=A.openDocument(str(baseline.resolve()))
    setback=float(doc.SpeakerCarrier.InstalledSetback)
    assert abs(setback-1.7)<1e-7
    changed={'FrontShell','FrontGrille','FrontBezel','LDriver','RDriver','RearShell','FoldSection','CowlBlank','FoldedSkin','CowlEdges','SymmetricCowl','Cowl','SymmetricCowlTool','FrontCowl','RearRoof','RearRoofRegion','LPanelBlank','LPanel','RPanel','Base','RearFastenerCuts','Feet'}
    changed.update(n+'Harness'+suffix for n in ('Buttons','OLED','VolumeSwitch') for suffix in ('Open','Closed'))
    preserved={};fixed={};relocated={}
    for o in old.Objects:
        if o.Name in changed or hasattr(o,'Group') or not hasattr(o,'Shape') or o.Shape.isNull():continue
        current=doc.getObject(o.Name).Shape
        delta=ac.difference(o.Shape,current)
        if delta<.001:fixed[o.Name]=delta
        else:
            delta=ac.difference(o.Shape,current.translated(V(0,-setback,0)))
            assert delta<.001,(o.Name,delta)
            relocated[o.Name]=delta
        preserved[o.Name]=delta
    assert abs(doc.RearShell.Shape.BoundBox.YMax-94.7)<1e-7
    front=doc.FrontShell.Shape
    assert front.isValid() and len(front.Solids)==1
    zone=Part.makeCylinder(68.251,5.02,V(0,-.01,76),V(0,1,0))
    zone=zone.fuse(Part.makeBox(172,4,20,V(-86,45.8,181)))
    outside=ac.difference(front.cut(zone),old.FrontShell.Shape.cut(zone));assert outside<.001,outside
    translated=old.FrontGrille.Shape.translated(V(0,-1,0))
    reliefs=[]
    for x in (-26,26):
        pocket=Part.makeBox(47,1.5,82,V(x-23.5,2.7,35))
        pocket=pocket.makeFillet(2,[e for e in pocket.Edges if e.BoundBox.YLength>1.4])
        reliefs.append(pocket)
    expected=translated.cut(Part.makeCompound(reliefs))
    mesh_delta=ac.difference(doc.FrontGrille.Shape,expected);assert mesh_delta<.001
    bb=doc.FrontGrille.Shape.BoundBox
    assert abs(bb.YMin-1.5)<1e-6 and abs(bb.YMax-4)<1e-6
    assert abs(front.BoundBox.YMin)<1e-6
    clearance={};driver_rear={}
    # Check the whole flange footprint in front of each measured apex. This
    # also covers moving-front contours wider than our rounded basket proxy.
    for n in ('LDriver','RDriver'):
        b=doc.getObject(n).Shape.BoundBox
        assert abs(b.YMin-5.7)<1e-6 and abs(b.YMax-50.7)<1e-6
        air=Part.makeBox(45,2.9999,80,V(b.XMin,2.7001,36))
        assert air.common(front).Volume<.001
        contact=Part.makeBox(45,.02,80,V(b.XMin,2.69,36)).common(front).Volume
        assert contact>.001,contact
        oldbody=doc.getObject(n).Shape.translated(V(0,-setback,0)).common(Part.makeBox(200,60,160,V(-100,8,0)))
        driver_rear[n]=ac.difference(oldbody,old.getObject(n).Shape)
        assert driver_rear[n]<.001
        clearance[n]={'grille_static_mm':b.YMin-2.7,'rear_wall_mm':61.7-b.YMax,
                      'full_flange_footprint_air_obstruction_mm3':0,'grille_negative_control_mm3':contact}
    matrix=A.Matrix();matrix.A11=-1
    symmetry={}
    for left,right in [('FrontGrille','FrontGrille'),('FrontBezel','FrontBezel'),('LDriver','RDriver')]:
        shape=doc.getObject(left).Shape.copy();shape.transformShape(matrix,True)
        symmetry[left]=ac.difference(shape,doc.getObject(right).Shape)
    assert max(symmetry.values())<.001
    assert doc.RDriver.TypeId=='Part::Mirroring'
    colors={}
    for n in ('PlayPauseKey','EjectKey','PrevKey','NextKey','Knob'):
        a=doc.getObject(n).Shape;b=old.getObject(n).Shape
        assert len(a.Faces)==len(b.Faces)
        assert all(x.cut(y).Area+y.cut(x).Area<.001 for x,y in zip(a.Faces,b.Faces));colors[n]=True
    with zipfile.ZipFile(model) as new,zipfile.ZipFile(baseline) as previous:
        gui=previous.read('GuiDocument.xml')
        resources=[v for el in ET.fromstring(gui).iter() for k,v in el.attrib.items() if k.lower()=='file' and v]
        assert len(resources)==len(set(resources))
        assert all(new.read(n)==previous.read(n) for n in ['GuiDocument.xml']+resources)
        assert new.namelist()[-len(resources)-1:]==['GuiDocument.xml']+resources
    finished=[o.Name for g in ('Shell','Controls','Carrier','Hardware') for o in doc.getObject(g).Group]
    return dict(model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
        unchanged_shapes_difference_mm3=fixed,preserved_shape_difference_mm3=preserved,rigidly_relocated_shapes_difference_mm3=relocated,installed_setback_mm=setback,p2_depth_mm=94.7,unchanged_finished_parts=[n for n in finished if n in fixed],
        changed_finished_parts=['FrontShell','RearShell','LDriver','RDriver'],p3_entire_shape_difference_mm3=preserved['SpeakerCarrier'],
        p1_outside_grille_zone_difference_mm3=outside,grille_expected_local_relief_difference_mm3=mesh_delta,
        driver_at_and_behind_flange_difference_mm3=driver_rear,seat_y_mm=11.7,front_envelope_depth_mm=6,
        grille_front_y_mm=1.5,grille_local_back_y_mm=2.7,grille_back_y_mm=4,grille_thickness_mm=2.5,grille_local_thickness_mm=1.2,grille_forward_shift_mm=1,
        visible_aperture_diameter_mm=130,connection_outer_diameter_mm=136.5,local_relief=dict(size_xz_mm=[47,82],corner_radius_mm=2,driver_projection_margin_mm=1,centers_xz_mm=[[-26,76],[26,76]],center_full_thickness_web_mm=5,added_ribs=False,physical_stiffness_verified=False),
        clearances=clearance,wire_corridor=ac.check_wire_corridor(doc),symmetry_difference_mm3=symmetry,
        color_face_order_preserved=colors,gui_resources=dict(count=len(resources),unique=True,registered_order=True,all_bytes_preserved=True),
        p3_printed_user_confirmed=True,p1_printed_user_confirmed=False,physical_full_assembly_verified=False,
        physical_excursion_verified=False,all_pass=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=check(a.model,a.baseline);a.output.write_text(json.dumps(r,indent=2)+'\n');print('GRILLE_CLEARANCE_OK',r['clearances'],flush=True)
