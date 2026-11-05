"""Saved-B-rep assembly checks; conservative continuous sweeps where possible.

The front-cover path is explicitly sampled, not claimed to be a continuous proof.
Fasteners, straps and cables are removed/disconnected as described in the report.
"""
import argparse
import hashlib
import json
from pathlib import Path
import FreeCAD as A
import Part

ROOT=Path(__file__).resolve().parent
V=A.Vector

def check(doc):
    objects={o.Name:o for g in ('Shell','Controls','Carrier','Hardware') for o in doc.getObject(g).Group}
    def collisions(shape,names):
        hits=[]
        a=shape.BoundBox
        for name in names:
            other=objects[name].Shape;b=other.BoundBox
            if any(min(getattr(a,k+'Max'),getattr(b,k+'Max'))-max(getattr(a,k+'Min'),getattr(b,k+'Min'))<1e-7 for k in 'XYZ'):continue
            volume=shape.common(other).Volume
            if volume>.001:hits.append({'object':name,'intersection_mm3':volume})
        return hits
    def box_sweep(shape,axis,distance):
        b=shape.BoundBox
        lo=[b.XMin,b.YMin,b.ZMin];hi=[b.XMax,b.YMax,b.ZMax]
        lo[axis]+=min(distance,0);hi[axis]+=max(distance,0)
        return Part.makeBox(*[h-l for l,h in zip(lo,hi)],V(*lo))
    report={'units':'mm','fasteners_and_straps_removed':True,'cables_disconnected':True,'physical_assembly_test':False,'paths':{}}
    core_hw=['LDriver','RDriver','Amp','AmpChip','Bridge','MCU','MCUChip']
    core_sources=list(doc.SpeakerCarrier.ConstructionObjects)+core_hw
    fixed=[n for n in objects if n not in core_hw+['SpeakerCarrier','FrontShell','LPort','RPort','Window','StatusArt','Keycap','KeyLight','Knob','Encoder','VolumePot','DisplayPCB','DisplayHeader']]
    hits=[]
    for name in core_sources:
        hit=collisions(box_sweep(doc.getObject(name).Shape,1,-140),fixed)
        if hit:hits.append({'moving_source':name,'hits':hit})
    report['paths']['speaker_carrier_front']={'method':'continuous conservative bounding-box sweep per construction component',
        'translation_xyz_mm':[0,-140,0],'moving':['SpeakerCarrier']+core_hw,'fixed':fixed,
        'prerequisites':['Front cover removed and its cables disconnected','Both side-port inserts removed','Four carrier screws removed'],
        'clashes':hits}
    print('PATH speaker_carrier_front',hits,flush=True)
    fixed=['RearShell','Battery','DAC','DACChip','Feet']
    hits=collisions(box_sweep(doc.Drive.Shape,2,180),fixed)
    report['paths']['drive_top']={'method':'continuous conservative bounding-box sweep',
        'translation_xyz_mm':[0,0,180],'moving':['Drive'],'fixed':fixed,
        'prerequisites':['Front cover removed','Speaker carrier removed (not included among fixed objects)','Bridge cables disconnected'], 'clashes':hits}
    print('PATH drive_top',hits,flush=True)
    fixed=['RearShell','SpeakerCarrier','LDriver','RDriver','Drive','DAC','DACChip','Feet']
    hits=collisions(box_sweep(doc.Battery.Shape,1,-150),fixed)
    report['paths']['battery_front']={'method':'continuous conservative bounding-box sweep',
        'translation_xyz_mm':[0,-150,0],'moving':['Battery'],'fixed':fixed,
        'prerequisites':['Front cover removed','Battery straps and cables removed'], 'clashes':hits}
    print('PATH battery_front',hits,flush=True)
    for name,sign in [('LPort',-1),('RPort',1)]:
        source=objects[name].Shape;direction=V(sign*25,0,0)
        volumes=[source.copy()]
        for face in source.Faces:
            # All curved port surfaces are coaxial with X; their axial normal sign is constant.
            if not isinstance(face.Surface,Part.Plane):
                assert hasattr(face.Surface,'Axis') and abs(abs(face.Surface.Axis.x)-1)<1e-7,(name,face.Surface)
            if face.normalAt(0,0).dot(direction)>1e-7:
                solid=face.extrude(direction)
                assert solid.isValid(),name
                if solid.Solids:volumes.append(solid)
        fixed=[n for n in objects if n!=name]
        hits=collisions(Part.makeCompound(volumes),fixed)
        report['paths'][name+'_outward']={'method':'continuous forward-facing surface extrusion along X',
            'translation_xyz_mm':[sign*25,0,0],'moving':[name],'fixed':fixed,
            'prerequisites':['Two side-port screws removed'], 'clashes':hits}
        print('PATH',name,hits,flush=True)
    moving=['FrontShell','Window','StatusArt','Keycap','KeyLight','Knob','Encoder','VolumePot','DisplayPCB','DisplayHeader']
    fixed=[n for n in objects if n not in moving]
    # The flat front face and grille lie at Y<=3 and have no positive-volume
    # overlap with the remaining assembly (whose min Y is 3). Clip only that exterior slab.
    clip=Part.makeBox(400,300,500,V(-200,3.00001,-100))
    body=Part.makeCompound([objects[n].Shape for n in moving]).common(clip)
    hits=[]
    for step in range(81):
        dz=step*.5;shape=body.copy();shape.translate(V(0,0,dz))
        found=collisions(shape,fixed)
        if found:hits.append({'lift_z_mm':dz,'hits':found})
    # Once lifted 40 mm, check horizontal separation, with the same exact geometry.
    for step in range(1,141):
        dy=-float(step);shape=body.copy();shape.translate(V(0,dy,40))
        found=collisions(shape,fixed)
        if found:hits.append({'front_y_mm':dy,'lift_z_mm':40,'hits':found})
    report['paths']['front_cover']={'method':'exact B-rep samples; 0.5 mm lift steps then 1 mm forward steps',
        'waypoints_xyz_mm':[[0,0,0],[0,0,40],[0,-140,40]],'moving':moving,'fixed':fixed,
        'prerequisites':['Four front-cover screws removed','Control/display cables disconnected'],
        'clashes':hits}
    print('PATH front_cover',hits,flush=True)
    report['all_pass']=all(not p['clashes'] for p in report['paths'].values())
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,default=ROOT/'Discora.FCStd')
    p.add_argument('--output',type=Path,default=ROOT/'assembly-paths.json')
    args=p.parse_args();doc=A.openDocument(str(args.model.resolve()))
    result=check(doc);result['model_sha256']=hashlib.sha256(args.model.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    A.closeDocument(doc.Name)
    assert result['all_pass'],'Assembly path collisions; see report'
    print('ASSEMBLY_PATHS_OK')

if __name__=='__main__':main()
