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
    assert points == [[0,3],[0,150],[38,177],[38,202],[43,202],[43,177],[74,165]]
    feet = doc.Feet.Shape.BoundBox
    shell_bottom = min(doc.getObject(n).Shape.BoundBox.ZMin
                       for n in ('Cowl','LPanel','RPanel','Back','Base'))
    assert abs(feet.ZMin)<1e-6 and abs(feet.ZMax-shell_bottom)<1e-6
    return dict(sha256=source_hash, units='mm', outer_profile_yz=points,
                foot_bottom_z=feet.ZMin, shell_bottom_z=shell_bottom,
                foot_height=feet.ZLength,
                front_angle_deg=math.degrees(math.atan2(27,38)),
                rear_angle_deg=math.degrees(math.atan2(12,31)))


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
                                          for s in doc.CowlTool.Shape.Solids]
    data['features']['knob_radius'] = max(e.Curve.Radius for e in shapes['Knob'].Edges
                                         if hasattr(e.Curve,'Radius'))
    controls = Part.makeCompound([screen]+list(doc.CowlTool.Shape.Solids))
    controls.rotate(V(),V(1,0,0),90-angle)
    projection('control-cutouts',controls,'front')

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
        ('01','前壳与提手',['Cowl'],(0,-100,20)),
        ('02','左侧壳',['LPanel'],(-90,0,0)),
        ('03','右侧壳',['RPanel'],(90,0,0)),
        ('04','左导音孔与饰片',['LPort'],(-155,0,0)),
        ('05','右导音孔与饰片',['RPort'],(155,0,0)),
        ('06','格栅压圈',['FrontBezel'],(0,-240,0)),
        ('07','通孔护网',['FrontGrille'],(0,-180,0)),
        ('08','后盖',['Back'],(0,140,0)),
        ('09','底架',['Base'],(0,0,-70)),
        ('10','四个脚垫',['Feet'],(0,0,-115)),
        ('11','屏窗与操控件',['Window','StatusArt','Keycap','KeyLight','Knob'],(0,0,90)),
        ('12','内部组件（见下一页）',core,(0,0,0)),
    ],shapes)
    exploded('exploded-core',[
        ('A','前障板',['FrontBaffle'],(0,-110,0)),
        ('B','左喇叭及预留框',['LDriver','LDriverFrame'],(-55,-45,0)),
        ('C','右喇叭及预留框',['RDriver','RDriverFrame'],(55,-45,0)),
        ('D','左后腔',['LChamber'],(-110,35,0)),
        ('E','右后腔',['RChamber'],(110,35,0)),
        ('F','光驱、导轨与碟口导向',['Drive','DriveCarrier','SlotGuide'],(0,120,0)),
        ('G','功放及托板',['Amp','AmpChip','AmpPads','AmpShelf'],(0,0,65)),
        ('H','主控及托板',['MCU','MCUChip','MCUPads','ElectronicsSled'],(0,25,135)),
        ('I','DAC 与侧壁支撑',['DAC','DACChip','DACPads'],(-95,0,100)),
        ('J','屏幕 PCB、接头及安装座',['DisplayPCB','DisplayHeader','DisplayCarrier'],(-60,-50,140)),
        ('K','电位器与轴',['VolumePot','Encoder'],(70,-30,100)),
        ('L','旧电池占位与电池座',['Battery','BatteryCradle'],(0,-20,-65)),
        ('M','桥接器转向占位',['Bridge'],(100,0,-100)),
        ('N','后盖上部固定耳',['RearTopMount'],(0,145,80)),
    ],core)
    # Validate critical annotations against the saved B-rep snapshot.
    checks = {
        'overall_142_74_202': all(abs(a-b)<1e-5 for a,b in zip(data['overall']['size'],(142,74,202))),
        'handle_opening_90_16': abs(handle.BoundBox.XLength-90)<1e-5 and abs(handle.BoundBox.ZLength-16)<1e-5,
        'grille_opening_130': abs(grille.BoundBox.XLength-130)<1e-5,
        'slot_124_3_2': abs(slot.BoundBox.XLength-124)<1e-5 and abs(slot.BoundBox.YLength-3.2)<1e-5,
        'screen_opening_36_20': abs(local.BoundBox.XLength-36)<1e-5 and abs(local.BoundBox.ZLength-20)<1e-5,
        '45_finished_objects':len(objects)==45,
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
