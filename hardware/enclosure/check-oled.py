"""Read saved OLED geometry against the supplier drawing and assembly allowances.

The connector housing, plug, wire bends and screw dimensions are reservations;
this does not certify real hardware, optical panel performance or printed fit.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import FreeCAD as A
import Part

ROOT=Path(__file__).resolve().parent
V=A.Vector
TOL=.001


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,default=ROOT/'Discora.FCStd')
    p.add_argument('--output',type=Path,default=ROOT/'oled-checks.json')
    p.add_argument('--baseline',type=Path)
    args=p.parse_args()
    doc=A.openDocument(str(args.model.resolve()))
    objects={o.Name:o for g in ('Shell','Controls','Carrier','Hardware') for o in doc.getObject(g).Group}
    edge=doc.FoldSection.Geometry[1]
    slope=(edge.EndPoint.y-edge.StartPoint.y)/(edge.EndPoint.x-edge.StartPoint.x)
    pose=A.Placement(V(0,18,edge.StartPoint.y+18*slope),A.Rotation(V(0,1,0),V(0,slope,-1)))
    def local(shape):
        copy=shape.copy();copy.Placement=pose.inverse().multiply(copy.Placement);return copy
    def world(shape):
        copy=shape.copy();copy.Placement=pose.multiply(copy.Placement);return copy
    def bounds(shape):
        b=shape.BoundBox
        return dict(min=[b.XMin,b.YMin,b.ZMin],max=[b.XMax,b.YMax,b.ZMax],size=[b.XLength,b.YLength,b.ZLength])
    def equal(actual,expected):
        assert len(actual)==len(expected) and all(abs(a-b)<1e-6 for a,b in zip(actual,expected)),(actual,expected)
    def clashes(shape,exclude=()):
        hits=[]
        for name,o in objects.items():
            if name in exclude or not shape.BoundBox.intersect(o.Shape.BoundBox):continue
            volume=shape.common(o.Shape).Volume
            if volume>TOL:hits.append(dict(object=name,volume_mm3=volume))
        return hits
    pcb=local(doc.DisplayPCB.Shape);panel=local(doc.Window.Shape);header=local(doc.DisplayHeader.Shape)
    equal(bounds(pcb)['size'],[35.4,1.2,33.5]);equal(bounds(pcb)['min'],[-17.7,2.4,-18.8])
    equal(bounds(panel)['size'],[34.5,1.4,23]);equal(bounds(panel)['min'],[-17.25,1,-13.55])
    equal(bounds(header)['size'],[10.16,8.7,2.54]);equal(bounds(header)['min'],[-5.08,3.6,11.43])
    equal([header.BoundBox.YMax-panel.BoundBox.YMin],[11.3])
    # Hole walls must span the complete board thickness; not just decorative circles.
    holes=[]
    for face in pcb.Faces:
        if isinstance(face.Surface,Part.Cylinder) and abs(face.Surface.Radius-1.5)<1e-6:
            holes.append([face.Surface.Center.x,face.Surface.Center.z])
            equal([face.BoundBox.YLength],[1.2])
    expected=[[-15.2,-16.3],[-15.2,12.2],[15.2,-16.3],[15.2,12.2]]
    assert len(holes)==4,holes
    for a,b in zip(sorted(holes),expected):equal(a,b)
    notch=Part.makeBox(14,1.2,4,V(-7,2.4,-18.8))
    assert pcb.common(notch).Volume<TOL
    equal([pcb.Volume],[(35.4*33.5-14*4-4*3.141592653589793*1.5**2)*1.2])
    opening=local(doc.SymmetricCowlTool.Shape.Solids[1])
    equal([opening.BoundBox.XLength,opening.BoundBox.ZLength],[32.82,18.1])
    equal([opening.BoundBox.Center.x,opening.BoundBox.Center.z],[0,0])
    # A local shell crop keeps repeated optical/assembly booleans away from the grille.
    shell=local(doc.FrontShell.Shape).common(Part.makeBox(52,15,48,V(-26,-1,-22)))
    active=Part.makeBox(29.42,1.1,14.7,V(-14.71,-.1,-7.35))
    assert shell.common(active).Volume<TOL,'Active area is obstructed by shell'
    lip=Part.makeLine(V(0,-.1,10),V(0,3,10)).common(shell)
    equal([sum(e.Length for e in lip.Edges)],[2.2])
    # Glass pocket floor / exterior lip at a point outside the flared opening.
    lip_inner=Part.makeLine(V(16.8,-.1,0),V(16.8,3,0)).common(shell)
    equal([sum(e.Length for e in lip_inner.Edges)],[.8])
    # Read exact mouth/throat sections, independent of build constants.
    for depth,size in [(0,[32.82,18.1]),(.8,[30.42,15.7])]:
        plane=Part.Face(Part.makePolygon([V(-25,depth,-22),V(25,depth,-22),V(25,depth,22),V(-25,depth,22),V(-25,depth,-22)]))
        section=opening.common(plane).BoundBox
        equal([section.XLength,section.ZLength],size)
    rays=[]
    front_angle=90-math.degrees(math.atan(slope))
    angles=[(x,z) for x in (-45,0,45) for z in (-45,0,45)]
    angles.extend([(0,front_angle),(0,-front_angle),(0,55),(0,-55)])
    face=Part.Face(Part.makePolygon([V(-14.71,1,-7.35),V(14.71,1,-7.35),
                                    V(14.71,1,7.35),V(-14.71,1,7.35),V(-14.71,1,-7.35)]))
    for ax,az in angles:
        direction=V(2*math.tan(math.radians(ax)),-2,2*math.tan(math.radians(az)))
        sweep=face.extrude(direction)
        overlap=shell.common(sweep).Volume
        rays.append(dict(horizontal_deg=ax,vertical_deg=az,obstruction_mm3=overlap))
        assert overlap<TOL,(ax,az,overlap)
    art=local(doc.StatusArt.Shape)
    aa=Part.makeBox(29.42,.15,14.7,V(-14.71,.85,-7.35))
    assert art.cut(aa).Volume<TOL,'Display illustration outside active area'
    mirror=A.Matrix();mirror.A11=-1
    symmetry={}
    for name in ('DisplayCarrier','Window','DisplayPCB','DisplayRetainer'):
        a=doc.getObject(name).Shape;b=a.copy();b.transformShape(mirror,True)
        symmetry[name]=a.cut(b).Volume+b.cut(a).Volume
    assert all(v<TOL for v in symmetry.values()),symmetry
    assert doc.DisplayMountRight.TypeId=='Part::Mirroring' and doc.DisplayMountRight.Source==doc.DisplayMountLeft
    mounting=[]
    frame=local(doc.DisplayRetainer.Shape)
    assert frame.isValid() and len(frame.Solids)==1
    for x,z in expected:
        seat=Part.makeCylinder(2.25,.1,V(x,2.3,z),V(0,1,0))
        assert seat.cut(shell).Volume<TOL
        peg=Part.makeCylinder(1.3,1.5,V(x,2.4,z),V(0,1,0))
        assert peg.cut(shell).Volume<TOL
        pad=Part.makeCylinder(2.25,.1,V(x,3.6,z),V(0,1,0)).cut(
            Part.makeCylinder(1.6,.2,V(x,3.55,z),V(0,1,0)))
        assert pad.cut(frame).Volume<TOL
        mounting.append(dict(local_xz_mm=[x,z],world_seat_center_xyz_mm=list(pose.multVec(V(x,2.4,z))),
            pcb_hole_diameter_mm=3,seat_outer_diameter_mm=4.5,peg_diameter_mm=2.6,
            peg_height_mm=1.6,nominal_peg_radial_gap_mm=.2,retainer_contact_depth_mm=3.6))
    fasteners=[]
    for x in (-20.5,20.5):
        bore=Part.makeCylinder(.799,4.39,V(x,2.01,-7),V(0,1,0))
        assert shell.common(bore).Volume<TOL
        bottom=Part.makeCylinder(.7,.1,V(x,1.85,-7),V(0,1,0))
        assert bottom.cut(shell).Volume<TOL,'Pilot is not blind'
        clearance=Part.makeCylinder(1.099,2,V(x,6.4,-7),V(0,1,0))
        assert frame.common(clearance).Volume<TOL
        # Two nominal M2 x 6 screws secure the removable frame, not the PCB.
        head=world(Part.makeCylinder(2,1.6,V(x,8.4,-7),V(0,1,0)))
        tool=world(Part.makeCylinder(2,20,V(x,10,-7),V(0,1,0)))
        head_hits=clashes(head);tool_hits=clashes(tool)
        assert not head_hits and not tool_hits,(x,head_hits,tool_hits)
        fasteners.append(dict(local_xz_mm=[x,-7],pilot_diameter_mm=1.6,pilot_depth_mm=4.4,
                             clearance_diameter_mm=2.2,head_clashes=head_hits,tool_clashes=tool_hits))
    wire=world(Part.makeBox(12.16,6,4.54,V(-6.08,12.3,10.43)))
    wire_hits=clashes(wire)
    assert not wire_hits,wire_hits
    equal(list(doc.DisplayHeader.PinCentersX),[-3.81,-1.27,1.27,3.81])
    # P1 is detached. Remove frame first, then withdraw module from the pegs.
    module=Part.makeCompound([local(doc.getObject(n).Shape) for n in ('DisplayPCB','Window','DisplayHeader')])
    removals=[];frame_removals=[]
    fixed=Part.makeCompound([shell,module])
    for step in range(51):
        moving=frame.copy();moving.translate(V(0,step*.5,0))
        volume=moving.common(fixed).Volume
        if volume>TOL:frame_removals.append(dict(depth_mm=step*.5,volume_mm3=volume))
        moving=module.copy();moving.translate(V(0,step*.5,0))
        volume=moving.common(shell).Volume
        if volume>TOL:removals.append(dict(depth_mm=step*.5,volume_mm3=volume))
    assert not removals and not frame_removals,(removals,frame_removals)
    gaps={}
    for name in ('RearShell','SpeakerCarrier','MCUChip','Drive','ButtonRetainer','EjectSwitch','NextSwitch','VolumePot'):
        gaps[name]={n:doc.getObject(n).Shape.distToShape(objects[name].Shape)[0]
                    for n in ('DisplayPCB','DisplayHeader','Window')}
    report=dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
        build_sha256=hashlib.sha256((ROOT/'build.FCMacro').read_bytes()).hexdigest(),
        source='../OLED-1.3-128x64/oled-module-dimensions-wiring.webp',
        source_sha256=hashlib.sha256((ROOT.parent/'OLED-1.3-128x64/oled-module-dimensions-wiring.webp').read_bytes()).hexdigest(),
        freecad_version=A.Version()[:3],units='mm',pcb_local=bounds(pcb),panel_local=bounds(panel),header_reservation_local=bounds(header),
        active_area=dict(size_mm=[29.42,14.7],left_from_pcb_mm=2.99,top_from_pcb_mm=7.35,
                         center_above_pcb_center_mm=2.05,exterior_reference_xyz_mm=list(pose.Base)),
        aperture=dict(mouth_size_mm=[32.82,18.1],mouth_radius_mm=1.8,throat_size_mm=[30.42,15.7],
                      throat_radius_mm=.6,lip_depth_mm=.8,glass_setback_mm=1,panel_to_lip_gap_mm=.2,
                      moved_outward_mm=4.4,obstructed_volume_mm3=0,full_active_area_ray_sweeps=rays),
        board_notch_mm=[14,4],hole_pitch_mm=[30.4,28.5],mounts=mounting,retainer_fasteners=fasteners,
        retainer=dict(connected_solids=1,frame_depth_mm=[6.4,8.4],contact_depth_mm=3.6,
                      body_clearance_mm=2.8,removal_clashes=frame_removals),
        header=dict(pin_pitch_mm=2.54,pin_centers_local_x_mm=list(doc.DisplayHeader.PinCentersX),
                    pin_labels=list(doc.DisplayHeader.PinLabels),pin_center_local_z_mm=12.7,
                    panel_front_to_pin_tip_mm=11.3,housing_size_measured=False),
        plug_and_wire_reservation=dict(local_min_mm=[-6.08,12.3,10.43],size_mm=[12.16,6,4.54],clashes=wire_hits,
                                       physical_plug_and_bend_verified=False),
        screw_reservation=dict(nominal='2 x M2 x 6',max_head_diameter_mm=4,max_head_height_mm=1.6,
                               tool_diameter_mm=4,tool_length_mm=20,sku_and_print_fit_verified=False),
        symmetry_difference_mm3=symmetry,native_mount_mirror=True,nearest_object_gaps_mm=gaps,
        module_removal=dict(method='51 B-rep samples at 0.5 mm inward-normal steps',travel_mm=25,
                            prerequisites=['Front shell detached','OLED wires, two frame screws and retainer removed'],clashes=removals),
        physical_fit_verified=False,all_pass=True)
    if args.baseline:
        old=A.openDocument(str(args.baseline.resolve()))
        changes={};unchanged=[]
        allowed={'FrontShell','Window','StatusArt','DisplayPCB','DisplayHeader'}
        added=[]
        for name in objects:
            if old.getObject(name) is None:
                added.append(name);continue
            a=old.getObject(name).Shape;b=objects[name].Shape
            difference=a.cut(b).Volume+b.cut(a).Volume
            if difference>TOL:changes[name]=difference
            else:unchanged.append(name)
        assert set(changes)==allowed and added==['DisplayRetainer'],(changes,added)
        report['added_finished_objects']=added
        report['baseline_sha256']=hashlib.sha256(args.baseline.read_bytes()).hexdigest()
        report['changed_finished_objects_difference_mm3']=changes
        report['unchanged_finished_objects']=unchanged
        A.closeDocument(old.Name)
    report['limits']=['Supplier drawing dimensions are not physical measurements.',
        'Connector housing uses 10.16 x 2.54 conservative cross-section; only pitch and side extent are specified.',
        'The 6 mm plug/wire reservation and 20 mm tool reach are design allowances, not verified cable bends or actual tools.',
        'M2 x 6 screw heads and blind PLA pilots require SKU selection and a printed test coupon.',
        'Full-area ray sweeps check the nominal aperture at selected angles; panel optics, tolerance stack, lip strength and dust seal are not certified.']
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    A.closeDocument(doc.Name)
    print('OLED_CHECKS_OK',args.output)


if __name__=='__main__':main()
