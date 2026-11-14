"""Read saved FCStd with FreeCAD Python; export HLR views and measured geometry.

Run using FreeCAD's Python (FreeCAD/Part/TechDraw must be importable):
    python export-drawings.py [--output DIRECTORY]
The source document is never recomputed or saved. No GUI is required.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import FreeCAD as A
import Part
import TechDraw

ROOT = Path(__file__).resolve().parent
V = A.Vector


def bounds(shape):
    b = shape.BoundBox
    return {"min": [b.XMin, b.YMin, b.ZMin],
            "max": [b.XMax, b.YMax, b.ZMax],
            "size": [b.XLength, b.YLength, b.ZLength]}


def side_profile(doc, source_hash):
    points = [[edge.StartPoint.x, edge.StartPoint.y]
              for edge in doc.FoldSection.Geometry[:7]]
    front_run=points[2][0]-points[1][0]
    rear_run=points[6][0]-points[5][0]
    front_rise=points[2][1]-points[1][1]
    rear_rise=points[5][1]-points[6][1]
    assert abs(front_run-rear_run)<1e-7 and abs(front_rise-rear_rise)<1e-7
    feet = doc.Feet.Shape.BoundBox
    shell_bottom = min(doc.getObject(n).Shape.BoundBox.ZMin
                       for n in ('FrontShell','RearShell'))
    assert abs(feet.ZMin+2)<1e-6 and abs(feet.ZMax-shell_bottom)<1e-6
    return dict(sha256=source_hash, units='mm', outer_profile_yz=points,
                foot_bottom_z=feet.ZMin, shell_bottom_z=shell_bottom,
                foot_height=feet.ZLength,
                front_horizontal_width_mm=front_run,rear_horizontal_width_mm=rear_run,
                front_surface_width_mm=math.hypot(front_run,front_rise),
                rear_surface_width_mm=math.hypot(rear_run,rear_rise),
                front_angle_deg=math.degrees(math.atan2(front_rise,front_run)),
                rear_angle_deg=math.degrees(math.atan2(rear_rise,rear_run)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'drawings')
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'Discora.FCStd'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    doc = A.openDocument(str(source))
    objects = [o for g in ('Shell', 'Controls', 'Carrier', 'Hardware')
               for o in doc.getObject(g).Group]
    assert len({o.Name for o in objects}) == len(objects)
    for obj in objects:
        assert obj.Shape.isValid() and obj.Shape.Solids, obj.Name
    shapes = {o.Name: o.Shape for o in objects}
    groups = {g: [o.Name for o in doc.getObject(g).Group]
              for g in ('Shell', 'Controls', 'Carrier', 'Hardware')}
    data = dict(model=source.name, sha256=source_hash,
                build_sha256=hashlib.sha256((ROOT/'build.FCMacro').read_bytes()).hexdigest(),
                freecad_version=A.Version()[:3], units='mm',
                objects={o.Name: dict(label=o.Label, **bounds(o.Shape)) for o in objects},
                groups=groups, views={})
    compound = lambda names: Part.makeCompound([shapes[n] for n in names])
    data['overall'] = bounds(compound(shapes))
    # Rotation rows give drawing horizontal, vertical and viewer-facing axes.
    matrices = {
        'front': ((1,0,0),(0,0,1),(0,-1,0)),
        'right': ((0,1,0),(0,0,1),(1,0,0)),
        'top': ((1,0,0),(0,1,0),(0,0,1)),
        'rear': ((-1,0,0),(0,0,1),(0,1,0)),
        'iso': ((math.sqrt(3)/2,.5,0),(-.25,math.sqrt(3)/4,math.sqrt(3)/2),
                (math.sqrt(3)/4,-.75,.5)),
    }

    def projection(name, shape, direction, anchors=None):
        rows = matrices[direction]
        mat = A.Matrix()
        for i,row in enumerate(rows,1):
            for j,value in enumerate(row,1):
                setattr(mat, 'A%d%d' % (i,j), value)
        projected = shape.copy()
        projected.transformShape(mat)
        b = bounds(projected)
        x,y = b['min'][:2]
        w,h = b['size'][:2]
        raw = TechDraw.projectToSVG(projected,V(0,0,1))
        raw = raw.replace('stroke-width="1.0"','stroke-width="0.18"')
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" '
               f'viewBox="{x} {-y-h} {w} {h}">\n{raw}</svg>\n')
        (out/(name+'.svg')).write_text(svg)
        info = dict(file=name+'.svg', bounds=b, direction=direction)
        if anchors:
            info['anchors'] = {key:[sum(a*b for a,b in zip(row,point))
                                     for row in rows[:2]] for key,point in anchors.items()}
        data['views'][name] = info
        print('EXPORTED', name, flush=True)

    exterior = compound(groups['Shell']+groups['Controls'])
    for direction in ('front','right','top','rear'):
        projection(direction,exterior,direction)

    # A true section at X=-26, the left driver centre; keep the -X half.
    clip = Part.makeBox(174,400,500,V(-200,-100,-100))
    section = compound(shapes).common(clip)
    projection('section',section,'right')

    # Read the saved Boolean cutters, not pixels from the previews.
    cutters = doc.SymmetricCowlTool.Shape.Solids
    assert len(cutters) == 4
    handle, screen, grille, slot = cutters
    data['features'] = {'handle_cut':bounds(handle),'grille_cut':bounds(grille),
                        'slot_cut':bounds(slot)}
    # Obtain the front shoulder slope from its two outer sketch vertices.
    profile = doc.FoldSection.Geometry
    front_shoulder = profile[1]
    a,b = front_shoulder.StartPoint,front_shoulder.EndPoint
    slope = (b.y-a.y)/(b.x-a.x)
    angle = math.degrees(math.atan(slope))
    data['features']['deck_angle_deg'] = angle
    # The display's native local Y is inward normal; local Z follows the slope.
    local = screen.copy()
    local.rotate(V(),V(1,0,0),90-angle)
    data['features']['screen_cut_local'] = bounds(local)
    data['features']['controls_radii'] = [max(e.Curve.Radius for e in s.Edges
                                             if hasattr(e.Curve,'Radius'))
                                          for s in doc.CowlTool.Shape.Solids
                                          if any(hasattr(e.Curve,'Radius') for e in s.Edges)]
    data['features']['knob_radius'] = max(e.Curve.Radius for e in shapes['Knob'].Edges
                                         if hasattr(e.Curve,'Radius'))
    controls = Part.makeCompound([screen]+list(doc.CowlTool.Shape.Solids))
    controls.rotate(V(),V(1,0,0),90-angle)
    projection('control-cutouts',controls,'front')
    data['features']['control_cut_centers_xz']=[[s.CenterOfMass.x,s.CenterOfMass.z] for s in controls.Solids[1:]]

    # OLED details retain the saved parts at their real relative positions.
    pose=A.Placement(V(0,18,a.y+18*slope),A.Rotation(V(0,1,0),V(0,slope,-1)))
    module=compound(['DisplayPCB','Window','DisplayHeader'])
    module.Placement=pose.inverse().multiply(module.Placement)
    projection('oled-module',module,'front')
    installed=compound(['FrontShell','DisplayPCB','Window','DisplayHeader','DisplayRetainer'])
    installed.Placement=pose.inverse().multiply(installed.Placement)
    section=installed.common(Part.makeBox(.2,20,40,V(-.1,-1,-20)))
    projection('oled-side',section,'right')
    data['oled']={'pcb':bounds(doc.DisplayPCB.Shape),'mount_world_bounds':bounds(doc.DisplayCarrier.Shape),
                 'active_center_exterior_xyz_mm':list(pose.Base),
                 'local_frame':'X right; Y inward normal; Z up slope toward header'}

    # PCB module details use its own shaft datum, not its world-aligned bounds.
    volume_pose=A.Placement(V(48,18,a.y+18*slope),A.Rotation(V(0,1,0),V(0,slope,-1)))
    volume=doc.VolumePot.Shape.copy()
    volume.Placement=volume_pose.inverse().multiply(volume.Placement)
    unturned=volume.copy();unturned.rotate(V(),V(0,1,0),-90)
    projection('volume-module',unturned,'top')
    volume_parts=[]
    for name in ('FrontShell','VolumePot','Encoder','Knob'):
        shape=doc.getObject(name).Shape.copy()
        shape.Placement=volume_pose.inverse().multiply(shape.Placement)
        if name=='FrontShell':shape=shape.common(Part.makeBox(46,7,44,V(-23,-1,-22)))
        volume_parts.append(shape)
    installed=Part.makeCompound(volume_parts).common(Part.makeBox(30,60,50,V(-30,-16,-25)))
    projection('volume-installation',installed,'right')
    data['volume_module']={'installed_local_bounds':bounds(volume),'unturned_bounds':bounds(unturned),
        'pcb_unturned_size_mm':[35,26.2,1.5],'shaft_center_exterior_xyz_mm':list(volume_pose.Base),
        'rotation_about_shaft_deg':90,'local_frame':'X right; Y inward normal along shaft; Z up slope',
        'detail_section':'Keep local X <= 0; excludes unmeasured mounting holes and connector details'}
    data['volume_module']['clearances_mm']={n:doc.VolumePot.Shape.distToShape(doc.getObject(n).Shape)[0]
        for n in ('SpeakerCarrier','MCUChip','RearShell','Drive','Perfboard')}

    board_parts=['Perfboard','MCU','MCUChip','MCUSockets','DAC','DACChip','DACSockets',
                 'BuckA','BuckB','XHButtons','XHOLED','XHVolumeSwitch',
                 'PerfboardScrew1','PerfboardScrew2','PerfboardScrew3']
    projection('perfboard-outline',shapes['Perfboard'],'top')
    projection('perfboard-layout',compound(board_parts),'top')
    data['views']['perfboard-layout']['parts']=[dict(objects=board_parts,offset_mm=[0,0,0])]
    front_parts=['FrontShell','Window','DisplayPCB','DisplayHeader','VolumePot','Encoder','Knob',
                 'PlayPauseSwitch','EjectSwitch','PrevSwitch','NextSwitch','ButtonRetainer']
    for suffix,opening in [('Closed',0),('Open',60)]:
        pieces=[compound(board_parts)]
        defs=[dict(objects=board_parts,offset_mm=[0,0,0])]
        for name in front_parts:
            shape=shapes[name].copy()
            if name=='FrontShell':shape=shape.common(Part.makeBox(170,100,100,V(-85,-1,140)))
            shape.translate(V(0,-opening,0));pieces.append(shape)
        defs.append(dict(objects=front_parts,offset_mm=[0,-opening,0],clip_front_above_z=140))
        wires=[n+'Harness'+suffix for n in ('Buttons','OLED','VolumeSwitch')]
        pieces.extend(doc.getObject(n).Shape for n in wires)
        defs.append(dict(objects=wires,offset_mm=[0,0,0]))
        name='harness-'+suffix.lower()
        projection(name,Part.makeCompound(pieces),'top')
        data['views'][name]['parts']=defs
    data['perfboard']={'bounds':bounds(shapes['Perfboard']),
        'holes':[{ 'center_xy_mm':[e.CenterOfMass.x,e.CenterOfMass.y], 'radius_mm':e.Curve.Radius}
                 for e in shapes['Perfboard'].Edges if hasattr(e.Curve,'Radius')],
        'board_parts':board_parts,'service_translation_xyz_mm':[0,-60,0]}

    def exploded(name, definitions, expected):
        seen, pieces, anchors = [], [], {}
        for number,label,names,offset in definitions:
            seen.extend(names)
            shape = compound(names)
            shape.translate(V(*offset))
            pieces.append(shape)
            bb=shape.BoundBox
            anchors[number]=[bb.Center.x,bb.Center.y,bb.Center.z]
        assert len(seen)==len(set(seen)) and set(seen)==set(expected), name
        projection(name,Part.makeCompound(pieces),'iso',anchors)
        data['views'][name]['parts'] = [dict(number=n,label=l,objects=ns,offset_mm=ofs)
                                        for n,l,ns,ofs in definitions]

    core = groups['Carrier'] + groups['Hardware']
    exploded('exploded-shell',[
        ('01','P1 一体前壳／提手／护网',['FrontShell'],(0,-150,0)),
        ('02','P2 一体后壳／左右导音孔及饰片',['RearShell'],(0,160,0)),
        ('03','P3 双喇叭与电路板支架',['SpeakerCarrier'],(0,0,0)),
        ('04','光驱可拆压条',['DriveRetainer'],(0,70,0)),
        ('06','四个软质脚垫',['Feet'],(0,0,-65)),
        ('07','屏窗与操控件',['Window','StatusArt','PlayPauseKey','EjectKey','PrevKey','NextKey','ButtonRetainer','DisplayRetainer','Knob'],(0,-70,100)),
        ('08','硬件包络（见右图）',groups['Hardware'],(0,0,0)),
    ],shapes)
    exploded('exploded-core',[
        ('A','P3 一体支架／前障板',['SpeakerCarrier'],(0,0,0)),
        ('B','左喇叭包络',['LDriver'],(-50,-55,0)),
        ('C','右喇叭包络',['RDriver'],(50,-55,0)),
        ('D','光驱与可拆压条',['Drive','DriveRetainer'],(0,110,0)),
        ('E','功放 PCB 与元件预留',['Amp','AmpChip'],(0,0,70)),
        ('F','主控 PCB／元件／排母',['MCU','MCUChip','MCUSockets'],(0,25,100)),
        ('G','DAC PCB／元件／排母',['DAC','DACChip','DACSockets'],(-100,0,65)),
        ('H','屏幕 PCB 与接头',['DisplayPCB','DisplayHeader'],(-60,-40,130)),
        ('I','PCB 音量模块与轴',['VolumePot','Encoder'],(70,-30,90)),
        ('J','5600 mAh 平排电池',['Battery'],(0,-10,-50)),
        ('K','SATA 接头及护线环',['Bridge'],(180,-30,-140)),
        ('L','四个轻触按键包络',['PlayPauseSwitch','EjectSwitch','PrevSwitch','NextSwitch'],(-110,0,150)),
        ('M','洞洞板／双降压／接插件／螺钉',
         [n for n in board_parts if n not in ('MCU','MCUChip','MCUSockets','DAC','DACChip','DACSockets')],(100,-55,55)),
    ],core)
    # Validate critical annotations against the saved B-rep snapshot.
    checks = {
        'overall_170_93_243_263': all(abs(a-b)<1e-5 for a,b in zip(data['overall']['size'],(170,93,165+44*27/38+45+2))),
        'handle_opening_90_24': abs(handle.BoundBox.XLength-90)<1e-5 and abs(handle.BoundBox.ZLength-24)<1e-5,
        'hidden_grille_cut_130': abs(grille.BoundBox.XLength-130)<1e-5,
        'slot_124_5_5': abs(slot.BoundBox.XLength-124)<1e-5 and abs(slot.BoundBox.YLength-5.5)<1e-5,
        'screen_mouth_32_82_18_1': abs(local.BoundBox.XLength-32.82)<1e-5 and abs(local.BoundBox.ZLength-18.1)<1e-5,
        'battery_112_70_20': all(abs(a-b)<1e-5 for a,b in zip(data['objects']['Battery']['size'],(112,70,20))),
        'drive_y76_2_z29_5': abs(doc.Drive.Shape.BoundBox.YMin-76.2)<1e-5 and abs(doc.Drive.Shape.BoundBox.ZMin-29.5)<1e-5,
        'slot_center_y79_05': abs(slot.BoundBox.Center.y-79.05)<1e-5,
        'hidden_bezel_outer_136_5':abs(doc.FrontBezel.Shape.BoundBox.XLength-136.5)<1e-5,
        'oversized_grille_136':abs(doc.FrontGrille.Shape.BoundBox.XLength-136)<1e-5,
        'grille_thickness_2_5':abs(doc.FrontGrille.Shape.BoundBox.YLength-2.5)<1e-5,
        'grille_recess_2_5':abs(doc.FrontGrille.Shape.BoundBox.YMin-2.5)<1e-5,
        'circular_mouth_clear':doc.FrontShell.Shape.common(Part.makeCylinder(65,2.49998,A.Vector(0,.00001,76),A.Vector(0,1,0))).Volume<.001,
        'side_ports_rear_outline_y49':all(abs(doc.getObject(n).Shape.BoundBox.Center.y-49)<1e-5 for n in ('LPort','RPort','LPanelTool')),
        '44_finished_objects':len(objects)==44,
        'perfboard_bounds_111_55_1_6':all(abs(x-y)<1e-6 for x,y in zip(bounds(shapes['Perfboard'])['size'],(111,55,1.6))),
        'pcb_module_local_15_26_2_35':all(abs(x-y)<1e-6 for x,y in zip(bounds(volume)['size'],(15,26.2,35))),
        'pcb_module_unturned_35_26_2_15':all(abs(x-y)<1e-6 for x,y in zip(bounds(unturned)['size'],(35,26.2,15))),
        'three_connected_main_parts':all(len(doc.getObject(n).Shape.Solids)==1 for n in ('FrontShell','RearShell','SpeakerCarrier')),
        'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==source_hash,
    }
    data['checks']=checks
    assert all(checks.values()),checks
    (out/'geometry.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    (out/'side-profile.json').write_text(json.dumps(side_profile(doc,source_hash),ensure_ascii=False,indent=2)+'\n')
    A.closeDocument(doc.Name)
    print('DRAWING_GEOMETRY_OK',source_hash)


if __name__ == '__main__':
    main()
