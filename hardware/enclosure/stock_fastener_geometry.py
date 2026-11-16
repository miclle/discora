"""Adapt unprinted parts to measured stock screws without changing printed P3."""
import FreeCAD as A
import Part
import rear_setback_geometry as rear
import charging_port_geometry as charging
V=A.Vector
Y=V(0,1,0)
# x magnitude, z, post root, post end, blind bottom, screw head front plane.
LOCKS=((79.4,31.5,4.,15.,6.,37.),(29.,181.5,28.2,40.,29.5,60.5))
LOCK_PILOT=2.8
LOCK_CLEARANCE=3.9
LOCK_HEAD_WELL=7.4
LOCK_HEAD=6.8
LOCK_TOTAL_LENGTH=30.


def cyl(r,h,x,y,z):return Part.makeCylinder(r,h,V(x,y,z),Y)
def box(x,y,z,w,d,h):return Part.makeBox(w,d,h,V(x,y,z))
def posed(s,p):
    s=s.copy();s.Placement=p.multiply(s.Placement);return s


def apply(doc):
    assert not hasattr(doc.FrontShell,'StockFasteners'), 'Stock fasteners already applied'
    printed=doc.SpeakerCarrier.Shape.copy()
    old_posts=doc.FrontFastenerPosts.Shape.copy()
    front=doc.FrontShell.Shape.cut(old_posts.cut(doc.FrontCowl.Shape))
    posts=[];wells=[];cuts=[];pilots=[]
    profile=[(e.StartPoint.x,e.StartPoint.y) for e in doc.FoldSection.Geometry]
    envelope=rear.prism(profile[:7]+[(rear.DEPTH,1)],-85,170)
    for sign in (-1,1):
        for ax,z,root,end,bottom,head in LOCKS:
            x=sign*ax
            pilot=cyl(LOCK_PILOT/2,end-bottom+.1,x,bottom,z)
            post=cyl(3.5,end-root,x,root,z).cut(pilot)
            posts.append(post);pilots.append(pilot)
            wells.append(cyl(5.2,rear.DEPTH-end-.4,x,end+.4,z).common(envelope))
            # A 90-degree nominal countersink accepts the measured 6.8 mm head.
            cone_depth=(LOCK_HEAD_WELL-LOCK_CLEARANCE)/2
            cuts.extend([cyl(LOCK_CLEARANCE/2,head-cone_depth-end+.2,x,end+.3,z),
                         Part.makeCone(LOCK_CLEARANCE/2,LOCK_HEAD_WELL/2,cone_depth,V(x,head-cone_depth,z),Y),
                         cyl(LOCK_HEAD_WELL/2,rear.DEPTH-head+1,x,head,z),
                         cyl(3.8,end-root+.5,x,root-.1,z)])
        # Reuse the roof-side rib location; the enlarged well overlaps it.
        wells.append(rear.prism([(44,181.3),(56,181.3),(56,188.3)],sign*29-2,4))
        for z in (27,124):
            x=sign*64
            seat=box(-80 if sign<0 else 62,7,23 if z==27 else 120.5,18,7,8 if z==27 else 7.5)
            seat=seat.cut(cyl(1,8,x,6.5,z))
            p=[V(sign*xx,y,z-2) for xx,y in ((81,13),(71,13),(81,23))]
            rib=Part.Face(Part.makePolygon(p+p[:1])).extrude(V(0,0,4))
            wells.extend([rear.shifted(seat),rear.shifted(rib)])
    doc.FrontFastenerPosts.Shape=Part.makeCompound(posts)
    doc.FrontShell.Shape=front.multiFuse(posts).cut(Part.makeCompound(pilots)).removeSplitter()
    doc.RearFastenerCuts.Shape=Part.makeCompound(cuts)
    # Optical-drive retainer: stock 2.5 x 10, preserve its original seating plane.
    front_y=doc.DriveCarrier.Shape.BoundBox.YMin
    shelf=box(-20,front_y,doc.Drive.Shape.BoundBox.ZMin-2,40,89.7-front_y,2)
    bosses=[]
    for sign in (-1,1):
        xmin=64.3 if sign>0 else -69.2
        body=box(xmin,front_y,115,4.9,89.7-front_y,4).fuse(
            box(xmin,front_y+5,111,4.9,89.7-front_y-5,8))
        bosses.append(body.cut(cyl(1,9,sign*66.75,front_y-.1,117)))
    doc.DriveCarrier.Shape=shelf.multiFuse(bosses).removeSplitter()
    bar=box(-64,front_y-3,110,128,3,10)
    ears=[box(x,front_y-3,115,6,3,4) for x in (-70,64)]
    holes=[cyl(1.4,4,x,front_y-3.5,117) for x in (-66.75,66.75)]
    doc.DriveRetainer.Shape=bar.multiFuse(ears).cut(Part.makeCompound(holes)).removeSplitter()
    doc.DriveRetainer.Label='光驱可拆压条 · Ø2.5×10平底头／加宽螺柱'
    # Flat-head screws must bear on a flat washer, never on P3's conical mouth.
    washers=[];reliefs=[]
    for x in (-64,64):
        for z in (27,124):
            washers.append(cyl(2.9,1.2,x,5.5,z).cut(cyl(1.4,1.4,x,5.4,z)))
            reliefs.append(cyl(3.2,2,x,3.2,z))
    part=doc.addObject('PartDesign::Feature','CarrierWashers')
    part.Label='P3 平底螺帽垫圈 · 4件／Ø5.8×Ø2.8×1.2'
    part.Shape=Part.makeCompound(washers);doc.Carrier.addObject(part)
    doc.FrontShell.Shape=doc.FrontShell.Shape.cut(Part.makeCompound(reliefs)).removeSplitter()

    # Four-button bracket: 2.8 x 7.8 flat head, 2 mm clamp, 5.8 mm engagement.
    edge=doc.FoldSection.Geometry[1]
    slope=(edge.EndPoint.y-edge.StartPoint.y)/(edge.EndPoint.x-edge.StartPoint.x)
    rotation=A.Rotation(Y,V(0,slope,-1))
    button_pose=A.Placement(V(-54,17.5,edge.StartPoint.y+17.5*slope),rotation)
    additions=[];bores=[];old=doc.ButtonMounts.Shape.copy()
    for x in (-14,14):
        additions.append(posed(cyl(3.5,11.8,x,4.7,0),button_pose))
        bores.append(posed(cyl(1.15,9.6,x,7,0),button_pose))
        pad=posed(cyl(3.5,2,x,16.5,0),button_pose)
        hole=posed(cyl(1.5,2.2,x,16.4,0),button_pose)
        doc.ButtonRetainer.Shape=doc.ButtonRetainer.Shape.fuse(pad).cut(hole).removeSplitter()
    doc.ButtonMounts.Shape=old.multiFuse(additions).cut(Part.makeCompound(bores)).removeSplitter()
    doc.FrontShell.Shape=doc.FrontShell.Shape.multiFuse(additions).cut(Part.makeCompound(bores)).removeSplitter()

    # OLED: keep its position and contact lands; thicken only the screw pads.
    display_pose=A.Placement(V(0,18,edge.StartPoint.y+18*slope),rotation)
    oled_bores=[]
    for x in (-20.5,20.5):
        oled_bores.append(posed(cyl(1.15,4.5,x,2,-7),display_pose))
        pad=posed(cyl(3.5,3.8,x,6.4,-7),display_pose)
        hole=posed(cyl(1.5,4,x,6.3,-7),display_pose)
        doc.DisplayRetainer.Shape=doc.DisplayRetainer.Shape.fuse(pad).cut(hole).removeSplitter()
    doc.DisplayMountPilots.Shape=Part.makeCompound(oled_bores)
    doc.FrontShell.Shape=doc.FrontShell.Shape.cut(doc.DisplayMountPilots.Shape).removeSplitter()

    names=('RearRoof','SlotGuide','LPanel','RPanel','Back','Base','BatteryCradle','DriveCarrier','LPort','RPort')
    shell=doc.getObject(names[0]).Shape.copy().multiFuse([doc.getObject(n).Shape for n in names[1:]]+wells)
    shell=shell.cut(doc.RearFastenerCuts.Shape)
    shell=rear.shifted(charging.apply(rear.shifted(shell,-rear.SETBACK)))
    # Charging sleeves are added after the main union; keep the entire tool bore open.
    shell=shell.cut(doc.RearFastenerCuts.Shape)
    bottom=box(-85,0,1,170,rear.DEPTH,profile[3][1])
    edges=[e for e in bottom.Edges if abs(e.CenterOfMass.z-1)<1e-7 and abs(abs(e.CenterOfMass.x)-85)<1e-7]
    bottom=bottom.makeFillet(4,edges)
    doc.RearShell.Shape=shell.common(bottom).removeSplitter()
    doc.FrontShell.addProperty('App::PropertyString','StockFasteners','Fasteners')
    doc.FrontShell.StockFasteners='M3.5 countersunk, total 30, head diameter 6.8; 90-degree cone provisional'
    doc.recompute()
    assert printed.cut(doc.SpeakerCarrier.Shape).Volume+doc.SpeakerCarrier.Shape.cut(printed).Volume<.001
    for n in ('FrontShell','RearShell','DriveRetainer','ButtonRetainer','DisplayRetainer'):
        s=doc.getObject(n).Shape
        assert s.isValid() and len(s.Solids)==1,(n,len(s.Solids))
