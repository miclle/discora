"""Rear-down P3 transitions; keep the proven front interfaces and rear air path.

Coordinates are those of the measured 45 x 80 mm left driver, centred at
X=-26, Z=76. The build macro mirrors these two construction sources.
"""
import FreeCAD as App
import Part
V=App.Vector

def basket_clearance():
    blank=Part.makeBox(39.3,60,71.5,V(-45.65,9.9,40.25))
    return blank.makeFillet(12.5,[e for e in blank.Edges if e.BoundBox.YLength>50])

def make_left_frame_printable(frame):
    # Remove the long floating rear edge progressively from both ends.
    # The Y<=13 seat stays untouched. A 39-degree arch closes at Y=18,
    # before the 45-degree plate-back transition starts projecting inward.
    points=[V(-51,18,76),V(-51,60,76+42*42/34),V(-51,60,76-42*42/34)]
    rear_relief=Part.Face(Part.makePolygon(points+[points[0]])).extrude(V(50,0,0))
    result=frame.cut(rear_relief)
    ribs=[]
    for side in (-1,1):
        # Relative to driver centre -26: 24.5 mm outer frame, 18 mm screw.
        # 45-degree growth inward from Y=34.5; full disc supported before Y=21.5.
        def x(u):return -26+side*u
        for z in (41,111):
            points=[V(x(24.6),34.5,z-4),V(x(13.5),23.4,z-4),
                    V(x(13.5),21.4,z-4),V(x(24.6),21.4,z-4)]
            wedge=Part.Face(Part.makePolygon(points+[points[0]])).extrude(V(0,0,8))
            a,b=sorted((x(24.6),x(18)))
            root=Part.makeBox(b-a,13.1,8,V(a,21.4,z-4))
            disc=Part.makeCylinder(4,13.1,V(x(18),21.4,z),V(0,1,0))
            ribs.append(wedge.common(root.fuse(disc)))
    ribs=Part.makeCompound(ribs).cut(basket_clearance())
    # Enlarge the basket clearance outward one mm per rearward mm, so the
    # plate grows from its perimeter instead of printing an 81 mm bridge.
    wires=[]
    for y,delta in ((12.9,0),(13,0),(29,16)):
        blank=Part.makeBox(39.3+2*delta,1,71.5+2*delta,
                           V(-45.65-delta,y,40.25-delta))
        rounded=blank.makeFillet(12.5+delta,[e for e in blank.Edges if e.BoundBox.YLength>.9])
        face=next(f for f in rounded.Faces if f.BoundBox.YLength<1e-7 and abs(f.CenterOfMass.y-y)<1e-7)
        wires.append(face.OuterWire)
    clearance=Part.makeLoft(wires,True,True)
    plate_back=Part.makeBox(49,16.1,84,V(-50.5,12.9,34)).cut(clearance)
    pilots=[Part.makeCylinder(1.15,10.6,V(x,9.9,z),V(0,1,0))
            for x in (-44,-8) for z in (41,111)]
    return result.fuse([ribs,plate_back]).cut(Part.makeCompound(pilots)).removeSplitter()

def smooth_left_wing(chamber):
    """Replace the inner front-wall step by a 45-degree, permanent transition."""
    import math
    y=3+2.5*math.sqrt(5)
    points=[V(-66.5,y+3,40.5),V(-65.5,y+3,40.5),V(-62.5,y,40.5),
            V(-62.5,y-.1,40.5),V(-66.5,y-.1,40.5)]
    transition=Part.Face(Part.makePolygon(points+[points[0]])).extrude(V(0,0,75))
    return chamber.fuse(transition).removeSplitter()
