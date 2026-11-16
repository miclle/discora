"""Extend P2 rearwards while rigidly relocating the already-printed P3.

The original construction coordinates remain the printed-P3 reference frame.
Only rear profile vertices, P2 attachment seats and outlets are rebuilt.
"""
import math
import FreeCAD as A
import Part
import perfboard_geometry as perfboard
import charging_port_geometry as charging
V=A.Vector
Y=V(0,1,0)
SETBACK=1.7
BASE_DEPTH=93.0
DEPTH=BASE_DEPTH+SETBACK
CORE_HARDWARE=('LDriver','Amp','AmpChip','Perfboard','MCU','MCUChip','MCUSockets',
               'DAC','DACChip','DACSockets','BuckA','BuckB','XHButtons','XHOLED',
               'XHVolumeSwitch','PerfboardScrew1','PerfboardScrew2','PerfboardScrew3')

def box(x,y,z,w,d,h):return Part.makeBox(w,d,h,V(x,y,z))
def cyl(r,h,x,y,z):return Part.makeCylinder(r,h,V(x,y,z),Y)
def prism(points,x,w):
    p=[V(x,y,z) for y,z in points]
    return Part.Face(Part.makePolygon(p+p[:1])).extrude(V(w,0,0))
def shifted(shape,dy=SETBACK):return shape.translated(V(0,dy,0))

def apply(doc):
    assert not hasattr(doc.SpeakerCarrier,'InstalledSetback'), 'Setback already applied'
    old_front_cowl=doc.FrontCowl.Shape.copy()
    old_core=doc.SpeakerCarrier.Shape.copy()
    profile=[(g.StartPoint.x,g.StartPoint.y) for g in doc.FoldSection.Geometry]
    # Move only the two back-wall vertices; front shoulder and handle stay put.
    for i in (6,7):profile[i]=(profile[i][0]+SETBACK,profile[i][1])
    doc.FoldSection.Geometry=[Part.LineSegment(V(*a,0),V(*b,0))
                              for a,b in zip(profile,profile[1:]+profile[:1])]
    doc.RearRoofRegion.Shape=doc.RearRoofRegion.Shape.fuse(box(-86,93,0,172,SETBACK+1,243)).removeSplitter()
    tools=[]
    for s in doc.SymmetricCowlTool.Shape.Solids:
        b=s.BoundBox
        is_slot=abs(b.XLength-124)<1e-6 and abs(b.YLength-5.5)<1e-6
        tools.append(shifted(s) if is_slot else s)
    doc.SymmetricCowlTool.Shape=Part.makeCompound(tools)
    panel=[(5,1),(88+SETBACK,1),(88+SETBACK,profile[7][1]),profile[8],profile[9],profile[10]]
    doc.LPanelBlank.Shape=prism(panel,-85,5)
    doc.LPanelTool.Shape=shifted(doc.LPanelTool.Shape)
    doc.LPort.Shape=shifted(doc.LPort.Shape)
    for n in ('Back','DriveCarrier','SlotGuide','DriveBlank','DriveTool','Bridge','DriveRetainer',
              'SataPlugClearance','SataCableClearance','DiscReference','ChargingSleeveBlanks','ChargingPortBores'):
        doc.getObject(n).Shape=shifted(doc.getObject(n).Shape)
    doc.Base.Shape=doc.Base.Shape.fuse(box(-80,88-.001,1,160,SETBACK+.001,5)).removeSplitter()
    # Recompute the dependent mirrors and roof cut before rebuilding P2.
    doc.recompute()
    new_front_cowl=doc.FrontCowl.Shape
    removed=old_front_cowl.cut(new_front_cowl);added=new_front_cowl.cut(old_front_cowl)
    front=doc.FrontShell.Shape
    if removed.Solids:front=front.cut(removed)
    if added.Solids:front=front.fuse(added)
    doc.FrontShell.Shape=front.removeSplitter()
    envelope=prism(profile[:7]+[(DEPTH,1)],-85,170)
    bosses=[];cuts=[]
    for sign in (-1,1):
        for x,z,start,end,radius in ((sign*79.4,33,4,11,2.8),(sign*29,179,24.5,36,3.5)):
            bosses.append(cyl(radius,DEPTH-end-.4,x,end+.4,z).common(envelope))
            cuts.extend((cyl(1.1,3,x,end+.3,z),cyl(2.2,DEPTH-end-3.1,x,end+3.2,z),
                         cyl(2.55,end-start+.5,x,start-.1,z)))
        bosses.append(prism([(44,181.3),(56,181.3),(56,188.3)],sign*29-2,4))
        for z in (27,124):
            x=sign*64
            seat=box(-80 if sign<0 else 62,7,23 if z==27 else 120.5,18,7,8 if z==27 else 7.5)
            seat=seat.cut(cyl(1,8,x,6.5,z))
            p=[V(sign*xx,y,z-2) for xx,y in ((81,13),(71,13),(81,23))]
            rib=Part.Face(Part.makePolygon(p+p[:1])).extrude(V(0,0,4))
            bosses.extend((shifted(seat),shifted(rib)))
    doc.RearFastenerCuts.Shape=Part.makeCompound(cuts)
    names=('RearRoof','SlotGuide','LPanel','RPanel','Back','Base','BatteryCradle','DriveCarrier','LPort','RPort')
    rear=doc.getObject(names[0]).Shape.copy().multiFuse([doc.getObject(n).Shape for n in names[1:]]+bosses).removeSplitter()
    rear=rear.cut(doc.RearFastenerCuts.Shape)
    rear=rear.cut(Part.makeCompound([box(x,y,.5,3,8,20) for x in (-61,58) for y in (24,44)]))
    rear=shifted(charging.apply(shifted(rear,-SETBACK)))
    # Preserve the original four bottom XZ radii across the extended depth.
    bottom=box(-85,0,1,170,DEPTH,profile[3][1])
    edges=[e for e in bottom.Edges if abs(e.CenterOfMass.z-1)<1e-7 and abs(abs(e.CenterOfMass.x)-85)<1e-7]
    assert len(edges)==2
    bottom=bottom.makeFillet(4,edges)
    doc.RearShell.Shape=rear.common(bottom).removeSplitter()
    for n in list(doc.SpeakerCarrier.ConstructionObjects)+['SpeakerCarrier']+list(CORE_HARDWARE):
        obj=doc.getObject(n)
        if obj.TypeId=='Part::Mirroring':continue
        obj.Shape=shifted(obj.Shape)
    for obj in doc.ChargingInterfaces.Group:obj.Shape=shifted(obj.Shape)
    for obj in doc.CableClearances.Group:
        if 'Harness' in obj.Name or obj.Name in ('VolumeSolderClearance','VolumeAudioLeadClearance'):continue
        obj.Shape=shifted(obj.Shape)
    for name in perfboard.HARNESS_ROUTES:
        for suffix,opening in (('Closed',0),('Open',perfboard.SERVICE_OPENING)):
            doc.getObject(name+'Harness'+suffix).Shape=perfboard.harness_shape(name,opening,SETBACK)
    feet=[shifted(s) if s.BoundBox.Center.y>40 else s for s in doc.Feet.Shape.Solids]
    doc.Feet.Shape=Part.makeCompound(feet)
    doc.SpeakerCarrier.addProperty('App::PropertyLength','InstalledSetback','Printed part')
    doc.SpeakerCarrier.InstalledSetback=SETBACK
    doc.RearShell.addProperty('App::PropertyLength','OverallDepth','Dimensions')
    doc.RearShell.OverallDepth=DEPTH
    doc.recompute()
    for n in ('FrontShell','RearShell','SpeakerCarrier'):
        s=doc.getObject(n).Shape
        assert s.isValid() and len(s.Solids)==1,(n,len(s.Solids))
    # Rigid relocation is the only permissible operation on the printed P3.
    back=shifted(doc.SpeakerCarrier.Shape,-SETBACK)
    assert old_core.cut(back).Volume+back.cut(old_core).Volume<.001
