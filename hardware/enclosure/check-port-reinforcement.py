"""Measure the four inset connections and the stepped side-port free area.

This is a geometric assessment, not an acoustic tuning or strength simulation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import FreeCAD as A
import Part

ROOT = Path(__file__).resolve().parent
V = A.Vector


def aperture_face(x):
    center=V(x,40,80); along=V(0,0,1); across=V(0,1,0); radius=11
    a=center-along*22.5; b=center+along*22.5
    edges=[Part.makeLine(a+across*radius,b+across*radius),
           Part.Arc(b+across*radius,b+along*radius,b-across*radius).toShape(),
           Part.makeLine(b-across*radius,a-across*radius),
           Part.Arc(a-across*radius,a-along*radius,a+across*radius).toShape()]
    return Part.Face(Part.Wire(edges))


def free_areas(shape):
    # Each distinct depth interval of the rim, inset, tube and ribs is sampled.
    xs=[-70.9,-69.75,-69.25,-68.75,-68.25,-67.75,-67.25,-66.75,-65.31]
    rows=[]
    for x in xs:
        opening=aperture_face(x).cut(shape)
        rows.append(dict(x_mm=x,free_area_mm2=opening.Area,passages=len(opening.Faces)))
    area=min(r['free_area_mm2'] for r in rows)
    return dict(sections=rows,minimum_sampled_area_mm2=area,
                equal_area_circle_diameter_mm=math.sqrt(4*area/math.pi))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,default=ROOT/'Discora.FCStd')
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'port-reinforcement-checks.json')
    args=p.parse_args()
    doc=A.openDocument(str(args.model.resolve()))
    old=A.openDocument(str(args.baseline.resolve()))
    report=dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
                physical_strength_test=False,acoustic_test=False,connections={})
    for name,probe in {
        'middle_front':Part.makeBox(12,1,10,V(-72,32,75)),
        'middle_back':Part.makeBox(12,1,10,V(-72,47,75)),
        'bottom':Part.makeBox(12,4,1,V(-72,38,50)),
        'top':Part.makeBox(12,4,1,V(-72,38,110)),
    }.items():
        section=doc.LPort.Shape.common(probe)
        assert section.isValid() and len(section.Solids)==1,name
        assert abs(section.Volume-6)<1e-6,(name,section.Volume)
        report['connections'][name]={'cross_section_mm2':section.Volume,'continuous':True}
    # The inset face stays recessed 1.5 mm; thickness increases inward only.
    center=doc.LPort.Shape.common(Part.makeBox(12,1,1,V(-72,39.5,90)))
    assert abs(center.BoundBox.XLength-2)<1e-6
    assert abs(center.BoundBox.XMin+69.5)<1e-6
    report['inset']={'thickness_mm':center.BoundBox.XLength,'recess_mm':1.5}
    old_rear=old.RearShell.Shape;new_rear=doc.RearShell.Shape
    removed=old_rear.cut(new_rear).Volume
    addition=new_rear.cut(old_rear)
    assert removed<.001
    bounds=Part.makeBox(8,32,76,V(-72,24,42)).fuse(Part.makeBox(8,32,76,V(64,24,42)))
    outside=addition.cut(bounds).Volume
    assert outside<.001
    hits={}
    for group in ('Shell','Controls','Carrier','Hardware'):
        for obj in doc.getObject(group).Group:
            if obj.Name=='RearShell':continue
            volume=addition.common(obj.Shape).Volume
            if volume>.001:hits[obj.Name]=volume
    assert not hits,hits
    report['change_boundary']=dict(removed_mm3=removed,added_mm3=addition.Volume,
        added_outside_side_port_regions_mm3=outside,addition_collisions=hits)
    before=free_areas(old_rear);after=free_areas(new_rear)
    report['free_area_before']=before;report['free_area_after']=after
    report['free_area_reduction_percent']=100*(1-after['minimum_sampled_area_mm2']/before['minimum_sampled_area_mm2'])
    # Documented chamber inner envelope; the rectangular driver is NOT its displacement.
    cavity=Part.makeBox(61,50.5,84,V(-62.5,4,34))
    occupied=cavity.common(doc.LDriver.Shape).Volume
    report['chamber_volume_assessment']=dict(inner_envelope_liters=cavity.Volume/1e6,
        driver_rectangular_envelope_in_cavity_liters=occupied/1e6,
        remainder_after_full_driver_envelope_liters=(cavity.Volume-occupied)/1e6,
        actual_acoustic_net_volume_known=False)
    report['speaker']=dict(size_mm=[80,45,42],nominal_ohms=4,advertised_watts=10,
        missing_parameters=['Fs','Qts','Vas','Sd','Xmax','actual basket/magnet displacement'])
    report['decision']='Keep the 67 x 22 mm outer mouth and 63 x 18 mm short tube; only structural ribs reduce free area. No unsupported acoustic retuning.'
    report['limits']=[
        'Equal-area circle is an area comparison, not an acoustically equivalent circular port.',
        'The 0.3 mm chamber interface clearance and unmodeled driver seal prevent a validated sealed acoustic volume.',
        'No reliable driver T/S data or measured frequency/impedance response is available.',
        'Geometric continuity and 6 mm2 rib sections do not establish a load rating or printed fatigue strength.']
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('PORT_REINFORCEMENT_OK',json.dumps({k:report[k] for k in ['free_area_before','free_area_after','free_area_reduction_percent','chamber_volume_assessment']}),flush=True)
    A.closeDocument(old.Name);A.closeDocument(doc.Name)


if __name__=='__main__':main()
