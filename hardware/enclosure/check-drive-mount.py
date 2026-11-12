"""Check measured-drive reservations and the two-screw removable rear-wall mount.

This verifies CAD geometry, not cable bending, pad compression or physical fit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import FreeCAD as A
import Part

ROOT=Path(__file__).resolve().parent
V=A.Vector

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,default=ROOT/'Discora.FCStd')
    p.add_argument('--baseline',type=Path)
    p.add_argument('--output',type=Path,default=ROOT/'drive-mount-checks.json')
    args=p.parse_args()
    doc=A.openDocument(str(args.model.resolve()))
    body=doc.Drive.Shape;b=body.BoundBox
    report=dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                measured_body_maximum_mm=[128,10.8,130],physical_assembly_test=False,
                reservations_are_not_measurements=True)
    assert all(abs(a-v)<1e-6 for a,v in zip((b.XLength,b.YLength,b.ZLength),(128,10.8,130)))
    # Check a filled maximum envelope as well: clearance must not rely on the
    # approximate diagonal, unspecified recess length or internal disc cavity.
    envelope=Part.makeBox(128,10.8,130,V(b.XMin,b.YMin,b.ZMin))
    hits=[]
    for g in ('Shell','Controls','Carrier','Hardware'):
        for o in doc.getObject(g).Group:
            if o.Name=='Drive':continue
            volume=envelope.common(o.Shape).Volume
            if volume>.001:hits.append(dict(object=o.Name,volume_mm3=volume))
    assert not hits,hits
    report['filled_maximum_envelope_clashes']=hits
    report['rear_wall_pad_gap_mm']=doc.Back.Shape.BoundBox.YMin-b.YMax
    assert abs(report['rear_wall_pad_gap_mm']-1)<1e-6
    report['roof_gap_mm']=body.distToShape(doc.RearRoof.Shape)[0]
    report['adapter_battery_gap_mm']=doc.Bridge.Shape.distToShape(doc.Battery.Shape)[0]
    report['adapter_floor_gap_mm']=doc.Bridge.Shape.BoundBox.ZMin-doc.Base.Shape.BoundBox.ZMax
    assert report['roof_gap_mm']>.5
    assert report['adapter_battery_gap_mm']>=1-1e-6
    assert report['adapter_floor_gap_mm']>3
    report['adapter_envelope_xyz_mm']=[getattr(doc.Bridge.Shape.BoundBox,k+'Length') for k in 'XYZ']
    # Explicit downward displacement must meet the shelf, while the installed
    # body has no volumetric overlap with either shelf or retainer.
    lowered=body.copy();lowered.translate(V(0,0,-.1))
    report['lowered_0_1mm_shelf_intersection_mm3']=lowered.common(doc.DriveCarrier.Shape).Volume
    assert report['lowered_0_1mm_shelf_intersection_mm3']>1
    assert body.common(doc.RearShell.Shape).Volume<.001
    assert body.common(doc.DriveRetainer.Shape).Volume<.001
    report['retainer_screws']=[]
    for x in (-66.15,66.15):
        front=doc.DriveRetainer.Shape.BoundBox.YMin
        bore=Part.makeCylinder(1.09,3,V(x,front,117),V(0,1,0))
        assert bore.common(doc.DriveRetainer.Shape).Volume<.001
        pilot=Part.makeCylinder(.79,8.8,V(x,front+3,117),V(0,1,0))
        assert pilot.common(doc.RearShell.Shape).Volume<.001
        tool=Part.makeCylinder(1.7,front+1,V(x,-1,117),V(0,1,0))
        tool_hits=[]
        for name in ('RearShell','Drive','Bridge','Battery','DAC','DACChip'):
            volume=tool.common(doc.getObject(name).Shape).Volume
            if volume>.001:tool_hits.append(name)
        assert not tool_hits,tool_hits
        report['retainer_screws'].append(dict(center_xz_mm=[x,117],clearance_mm=2.2,pilot_mm=1.6,
            nominal_screw='M2 x 10',nominal_engagement_mm=7,head_and_tool_diameter_mm=3.4,
            prerequisites=['Front cover and speaker carrier removed'],tool_clashes=tool_hits))
    m=A.Matrix();m.A11=-1
    reflected=doc.DriveRetainer.Shape.copy();reflected.transformShape(m,True)
    diff=reflected.cut(doc.DriveRetainer.Shape).Volume+doc.DriveRetainer.Shape.cut(reflected).Volume
    assert diff<.001
    report['retainer_mirror_difference_mm3']=diff
    if args.baseline:
        old=A.openDocument(str(args.baseline.resolve()))
        report['baseline_sha256']=hashlib.sha256(args.baseline.read_bytes()).hexdigest()
        report['unchanged_parts_difference_mm3']={}
        names=['Battery','Amp','AmpChip','MCU','MCUChip','LDriver','RDriver',
               'Window','StatusArt','PlayPauseKey','EjectKey','PrevKey','NextKey','ButtonRetainer',
               'DisplayPCB','DisplayHeader','DisplayRetainer','Knob','Encoder','VolumePot']
        for name in names:
            a=doc.getObject(name).Shape;c=old.getObject(name).Shape
            delta=a.cut(c).Volume+c.cut(a).Volume
            assert delta<.001,(name,delta)
            report['unchanged_parts_difference_mm3'][name]=delta
        report['key_and_knob_face_order_preserved']={}
        for name in ('PlayPauseKey','EjectKey','PrevKey','NextKey','Knob'):
            a,c=doc.getObject(name).Shape.Faces,old.getObject(name).Shape.Faces
            same=len(a)==len(c) and all(abs(x.Area-y.Area)<1e-7 and (x.CenterOfMass-y.CenterOfMass).Length<1e-7 for x,y in zip(a,c))
            assert same,name
            report['key_and_knob_face_order_preserved'][name]=same
        A.closeDocument(old.Name)
    report['connector_clearances']={}
    objects=[o for g in ('Shell','Controls','Carrier','Hardware') for o in doc.getObject(g).Group]
    for name in ('SataPlugClearance','SataCableClearance'):
        shape=doc.getObject(name).Shape
        clashes=[]
        for o in objects:
            if o.Name=='Bridge':continue
            v=shape.common(o.Shape).Volume
            if v>.001:clashes.append(dict(object=o.Name,volume_mm3=v))
        assert not clashes,(name,clashes)
        report['connector_clearances'][name]=dict(clashes=clashes,physical_fit_verified=False)
    report['cable_side_extent_mm']=dict(measured_natural=14.5,reserved_extent=14.5,
        shell_clearance=(doc.Back.Shape.BoundBox.XLength-10)/2-(64+14.5))
    assert report['cable_side_extent_mm']['shell_clearance']>=1.5-1e-6
    report['limits']=['Maximum-thickness filled-envelope checks do not certify the exact measured surface.',
        'Protective pads and nominal M2 fasteners require physical fit and retention checks.',
        'Adapter 37.7 x 7 and rear projection 20.4 are measured; vertical centering and the three-dimensional cable bend remain physical-fit checks.',
        'Assembly path samples are documented separately; no physical insertion/ejection test performed.']
    report['all_pass']=True
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('DRIVE_MOUNT_OK',report['roof_gap_mm'],report['adapter_battery_gap_mm'],flush=True)

if __name__=='__main__':main()
