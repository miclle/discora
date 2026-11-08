"""Read back the four-key geometry and check the provisional cap travel allowance.

The actuator diameter and lead footprint are not measured. This checks the CAD
allowances only, and cannot establish real switch actuation or soldered fit.
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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,default=ROOT/'Discora.FCStd')
    parser.add_argument('--output',type=Path,default=ROOT/'button-checks.json')
    parser.add_argument('--baseline',type=Path,help='Pre-four-button model, for unchanged screen and volume control checks')
    args=parser.parse_args()
    doc=A.openDocument(str(args.model.resolve()))
    edge=doc.FoldSection.Geometry[1]
    slope=(edge.EndPoint.y-edge.StartPoint.y)/(edge.EndPoint.x-edge.StartPoint.x)
    outward=V(0,-slope,1);outward.normalize()
    objects=[o for g in ('Shell','Controls','Carrier','Hardware') for o in doc.getObject(g).Group]
    specs=[('PlayPause',-59,9),('Eject',-41,9),('Prev',-59,26),('Next',-41,26)]
    report=dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                user_dimensions_mm=dict(width=12,length=12,total_height=6,actuator_height=2.8,body_height=3.2,pin_length=3.7),
                head_diameter_measured=False,pin_footprint_verified=False,actual_stroke_verified=False,
                physical_fit_verified=False,cap_travel_sample_mm=[0,.2,.4,.6,.8],buttons={})
    for key,x,y in specs:
        origin=V(x,y,edge.StartPoint.y+y*slope)
        pose=A.Placement(origin,A.Rotation(V(0,1,0),-outward))
        cap=doc.getObject(key+'Key').Shape
        switch=doc.getObject(key+'Switch').Shape
        local=[]
        for shape in (cap,switch):
            shape=shape.copy();shape.Placement=pose.inverse().multiply(shape.Placement)
            b=shape.BoundBox
            local.append(dict(min=[b.XMin,b.YMin,b.ZMin],max=[b.XMax,b.YMax,b.ZMax],size=[b.XLength,b.YLength,b.ZLength]))
        assert all(abs(a-b)<1e-6 for a,b in zip(local[0]['size'],[12.8,7.2,12.8])),local
        assert all(abs(a-b)<1e-6 for a,b in zip(local[1]['size'],[12,6,12])),local
        assert abs(local[0]['min'][1]+1.2)<1e-6 and abs(local[0]['max'][1]-6)<1e-6
        assert abs(local[1]['min'][1]-6)<1e-6 and abs(local[1]['max'][1]-12)<1e-6
        assert cap.distToShape(switch)[0]<1e-6
        aperture=[s for s in doc.CowlTool.Shape.Solids if abs(s.BoundBox.Center.x-x)<1e-6 and abs((s.CenterOfMass-origin).dot(pose.Rotation.multVec(V(0,0,1))))<1e-6]
        assert len(aperture)==1,(key,len(aperture))
        radius=max(e.Curve.Radius for e in aperture[0].Edges if hasattr(e.Curve,'Radius'))
        assert abs(radius-5.25)<1e-6,radius
        hits=[]
        for travel in report['cap_travel_sample_mm']:
            moving=cap.copy();moving.translate(-outward*travel);a=moving.BoundBox
            for obj in objects:
                # The uncompressed actuator envelope is intentionally displaced
                # by pressing; no unsupported claim about its real stroke is made.
                if obj.Name in (key+'Key',key+'Switch'):continue
                b=obj.Shape.BoundBox
                if any(min(getattr(a,k+'Max'),getattr(b,k+'Max'))-max(getattr(a,k+'Min'),getattr(b,k+'Min'))<1e-7 for k in 'XYZ'):continue
                volume=moving.common(obj.Shape).Volume
                if volume>.001:hits.append(dict(travel_mm=travel,object=obj.Name,volume_mm3=volume))
        assert not hits,(key,hits)
        report['buttons'][key]=dict(exterior_center_xyz_mm=list(origin),local_cap=local[0],local_switch_envelope=local[1],
                                    aperture_diameter_mm=radius*2,nominal_cap_radial_gap_mm=radius-5,
                                    travel_clashes=hits)
    if args.baseline:
        previous=A.openDocument(str(args.baseline.resolve()))
        differences={}
        for name in ('Window','StatusArt','Knob','Encoder','VolumePot','DisplayPCB','DisplayHeader','DisplayCarrier'):
            a=previous.getObject(name).Shape;b=doc.getObject(name).Shape
            differences[name]=a.cut(b).Volume+b.cut(a).Volume
        assert all(v<.001 for v in differences.values()),differences
        report['preserved_controls_difference_mm3']=differences
        report['baseline_sha256']=hashlib.sha256(args.baseline.read_bytes()).hexdigest()
        A.closeDocument(previous.Name)
    report['retainer']=dict(connected_solids=len(doc.ButtonRetainer.Shape.Solids),
        panel_depth_mm=[16.5,18.5],support_depth_mm=[12,16.5],pin_tip_depth_allowance_mm=15.7,
        nominal_pin_tip_to_plate_mm=.8,center_support_diameter_mm=4,
        center_support_clear_of_actual_pins_verified=False)
    assert report['retainer']['connected_solids']==1
    report['limits']=['Round head uses an intentionally conservative diameter 12 mm envelope, not a measurement.',
                      '3.7 mm leads are reserved behind the 3.2 mm body; lead datum and footprint require confirmation.',
                      'Center supports require a pin-free bearing surface; no pin locations or solder joints are invented.',
                      '0.8 mm cap movement is sampled CAD clearance, not measured actuator stroke or a tolerance stack acceptance.']
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    A.closeDocument(doc.Name)
    print('BUTTON_CHECKS_OK',args.output)


if __name__=='__main__':main()
