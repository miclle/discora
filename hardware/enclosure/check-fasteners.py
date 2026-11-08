"""Check rear tool access and closed front face on the saved enclosure.

Nominal M2 geometry only: thread form, screw head and driver require physical fit.
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
    p.add_argument('--output',type=Path,default=ROOT/'fastener-checks.json')
    args=p.parse_args();sha=hashlib.sha256(args.model.read_bytes()).hexdigest()
    doc=A.openDocument(str(args.model.resolve()))
    objects=[o for g in ('Shell','Controls','Carrier','Hardware') for o in doc.getObject(g).Group]
    sealed=[];access=[]
    for x in (-65,65):
        for z in (18,140):
            probe=Part.makeCylinder(1.4,5,V(x,0,z),V(0,1,0))
            missing=probe.cut(doc.FrontShell.Shape).Volume
            assert missing<.001,(x,z,missing)
            sealed.append(dict(former_center_xz_mm=[x,z],missing_front_material_mm3=missing))
    for x,z,start,end,entry in [(-67.4,18,4,11,80),(67.4,18,4,11,80),
                                (-29,179,24.5,36,80-(179-165)*38/27),(29,179,24.5,36,80-(179-165)*38/27)]:
        seat=end+3.2
        tool=Part.makeCylinder(2,80,V(x,seat+.01,z),V(0,1,0))
        hits=[]
        for o in objects:
            volume=tool.common(o.Shape).Volume
            if volume>.001:hits.append(dict(object=o.Name,volume_mm3=volume))
        assert not hits,(x,z,hits)
        wall=Part.makeCylinder(.8,end-5.5-start,V(x,start,z),V(0,1,0))
        assert wall.cut(doc.FrontShell.Shape).Volume<.001
        bore=Part.makeCylinder(.79,5.49,V(x,end-5.49,z),V(0,1,0))
        assert bore.common(doc.FrontShell.Shape).Volume<.001
        access.append(dict(rear_center_xyz_mm=[x,entry,z],tool_diameter_mm=4,
                           seat_y_mm=seat,well_depth_mm=entry-seat,clashes=hits))
    report=dict(model_sha256=sha,former_front_holes_sealed=sealed,rear_access=access,
                nominal_screw_diameter_mm=2,nominal_under_head_length_mm=8,
                clearance_bore_mm=2.2,head_well_diameter_mm=4.4,pilot_diameter_mm=1.6,
                post_engagement_mm=4.8,minimum_driver_reach_mm=65.8,
                physical_fit_verified=False,thread_strength_verified=False,
                limits=['Screw head diameter must not exceed 4 mm; select length, thread form and PLA pilot fit with a sample.',
                        'Use a slim driver with at least 66 mm usable reach; actual handle and bit geometry are not modeled.',
                        'Integral side-wall wells do not establish printed strength, repeated assembly life or wire clearance.'])
    assert hashlib.sha256(args.model.read_bytes()).hexdigest()==sha
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    A.closeDocument(doc.Name)
    print('FASTENER_CHECKS_OK')


if __name__=='__main__':main()
