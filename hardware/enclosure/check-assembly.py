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
    core_hw=['LDriver','RDriver','Amp','AmpChip','MCU','MCUChip','DAC','DACChip']
    if doc.getObject('Perfboard'):
        core_hw.extend(['Perfboard','MCUSockets','DACSockets','BuckA','BuckB','XHButtons','XHOLED',
                        'XHVolumeSwitch','PerfboardScrew1','PerfboardScrew2','PerfboardScrew3'])
    else:
        core_hw.remove('DAC')
        core_hw.remove('DACChip')
    core_sources=list(doc.SpeakerCarrier.ConstructionObjects)+core_hw
    stationary_dac=[n for n in ("DAC","DACChip") if n not in core_hw]
    fixed=[n for n in objects if n not in core_hw+['SpeakerCarrier','FrontShell','Window','StatusArt','PlayPauseKey','EjectKey','PrevKey','NextKey','ButtonRetainer','PlayPauseSwitch','EjectSwitch','PrevSwitch','NextSwitch','Knob','Encoder','VolumePot','DisplayPCB','DisplayHeader','DisplayRetainer']]
    hits=[]
    for name in core_sources:
        hit=collisions(box_sweep(doc.getObject(name).Shape,1,-140),fixed)
        if hit:hits.append({'moving_source':name,'hits':hit})
    report['paths']['speaker_carrier_front']={'method':'continuous conservative bounding-box sweep per construction component',
        'translation_xyz_mm':[0,-140,0],'moving':['SpeakerCarrier']+core_hw,'fixed':fixed,
        'prerequisites':['Front cover removed and its cables disconnected','Four carrier screws removed'],
        'clashes':hits}
    print('PATH speaker_carrier_front',hits,flush=True)
    fixed=[n for n in objects if n in ['RearShell','Battery','Drive','Bridge','Feet']+stationary_dac]
    hits=[]
    for x,width in [(-68,4),(-64,128),(64,4)]:
        piece=doc.DriveRetainer.Shape.common(Part.makeBox(width,200,300,V(x,-10,0)))
        hits.extend(collisions(box_sweep(piece,1,-140),fixed))
    report['paths']['drive_retainer_front']={'method':'continuous conservative bounding-box sweeps of waist and two ears',
        'translation_xyz_mm':[0,-140,0],'moving':['DriveRetainer'],'fixed':fixed,
        'prerequisites':['Front cover and speaker carrier removed','Two retainer screws removed'], 'clashes':hits}
    print('PATH drive_retainer_front',hits,flush=True)
    # Remove the battery before moving the drive/adapter into the rear service
    # channel. The last 20 mm of both cradle side rails are open for this path.
    fixed=['RearShell','Feet']+stationary_dac
    db=doc.Drive.Shape.BoundBox
    # Do not depend on the approximate notch or underside recess during service.
    drive=Part.makeBox(db.XLength,db.YLength,db.ZLength,V(db.XMin,db.YMin,db.ZMin))
    report['drive_service_envelope']='Filled maximum 128 x 10.8 x 130 mm box; connector retains modeled housing and strain relief'
    adapter=doc.Bridge.Shape
    hits=[]
    for source in (drive,adapter):
        hits.extend(collisions(box_sweep(source,1,-12),fixed))
    for step in range(31):
        fraction=step/30
        for name,source in [('Drive',drive),('Bridge',adapter)]:
            pose=source.copy();pose.translate(V(0,-12-3*fraction,9.5*fraction))
            found=collisions(pose,fixed)
            if found:hits.append({'moving_object':name,'fraction':fraction,'hits':found})
    report['paths']['drive_service_position']={'method':'continuous initial translation then 31 maximum-envelope B-rep lift/translation samples; not a continuous lift proof',
        'waypoints_xyz_mm':[[0,0,0],[0,-12,0],[0,-15,9.5]],'moving':['Drive','Bridge'],'fixed':fixed,
        'prerequisites':['Front cover and speaker carrier removed','Drive retainer removed','Battery removed','Cable slack released'],
        'clashes':hits}
    print('PATH drive_service_position',hits,flush=True)
    parked=drive.copy();parked.translate(V(0,-15,9.5))
    plug=adapter.copy();plug.translate(V(0,-15,9.5))
    # Ten mm disengagement allowance is a design reservation, not a measured
    # connector stroke. Move inboard before passing the remaining cradle rail.
    hits=[]
    for axis,distance in [(2,-10),(0,-14),(1,-140)]:
        sweep=box_sweep(plug,axis,distance)
        hits.extend(collisions(sweep,fixed))
        overlap=sweep.common(parked).Volume
        if overlap>.001:hits.append({'object':'parked Drive','intersection_mm3':overlap})
        delta=[0,0,0];delta[axis]=distance;plug.translate(V(*delta))
    report['paths']['sata_removal']={'method':'continuous conservative bounding-box sweeps',
        'relative_waypoints_xyz_mm':[[0,0,0],[0,0,-10],[-14,0,-10],[-14,-140,-10]],
        'start_offset_xyz_mm':[0,-15,9.5],'moving':['Bridge'],'fixed':fixed+['Drive at service position'],
        'prerequisites':['Drive held at service position','Cable released'],
        'connector_release_allowance_mm':10,'actual_cable_bend_verified':False,'clashes':hits}
    print('PATH sata_removal',hits,flush=True)
    drive=parked
    hits=collisions(box_sweep(drive,1,-13),fixed)
    pivot=drive.BoundBox.Center+V(0,-13,0)
    for step in range(61):
        fraction=step/60
        pose=drive.copy();pose.translate(V(0,-13,0))
        pose.rotate(pivot,V(0,0,1),-30*fraction)
        pose.translate(V(0,-20*fraction,0))
        found=collisions(pose,fixed)
        if found:hits.append({'yaw_deg':-30*fraction,'additional_front_mm':20*fraction,'hits':found})
    hits.extend(collisions(box_sweep(pose,1,-140),fixed))
    report['paths']['drive_front']={'method':'continuous conservative translation sweeps before/after 61 maximum-envelope B-rep yaw/translation samples; rotation is not a continuous proof',
        'start_offset_xyz_mm':[0,-15,9.5],'initial_translation_xyz_mm':[0,-13,0],
        'yaw_axis':'Z','yaw_deg':-30,'yaw_step_deg':.5,
        'yaw_pivot_xyz_mm':[pivot.x,pivot.y,pivot.z],
        'translation_during_yaw_xyz_mm':[0,-20,0],
        'final_translation_xyz_mm':[0,-140,0],'moving':['Drive'],'fixed':fixed,
        'prerequisites':['Drive at service position','SATA adapter removed','Speaker carrier, battery and drive retainer removed'], 'clashes':hits}
    print('PATH drive_front',hits,flush=True)
    fixed=['RearShell','SpeakerCarrier','LDriver','RDriver','Drive','Bridge','Feet']+stationary_dac
    hits=collisions(box_sweep(doc.Battery.Shape,1,-150),fixed)
    report['paths']['battery_front']={'method':'continuous conservative bounding-box sweep',
        'translation_xyz_mm':[0,-150,0],'moving':['Battery'],'fixed':fixed,
        'prerequisites':['Front cover removed','Battery straps and cables removed'], 'clashes':hits}
    print('PATH battery_front',hits,flush=True)
    moving=['FrontShell','Window','StatusArt','PlayPauseKey','EjectKey','PrevKey','NextKey','ButtonRetainer','PlayPauseSwitch','EjectSwitch','PrevSwitch','NextSwitch','Knob','Encoder','VolumePot','DisplayPCB','DisplayHeader','DisplayRetainer']
    fixed=[n for n in objects if n not in moving]
    # Fixed objects all start at Y>=5. The exterior slab at Y<=5 moves
    # monotonically away and cannot intersect them; retain all inward posts.
    assert all(objects[n].Shape.BoundBox.YMin>=5-1e-7 for n in fixed)
    clip=Part.makeBox(400,300,500,V(-200,5.00001,-100))
    # Clip and test each part separately. The assembled OLED frame bears on
    # the PCB; a compound boolean needlessly resolves these internal contacts.
    # Collision against fixed objects distributes over the moving parts.
    bodies={n:objects[n].Shape.common(clip) for n in moving}
    hits=[]
    for step in range(141):
        dy=-float(step)
        for name,body in bodies.items():
            if body.isNull() or not body.Solids:continue
            shape=body.copy();shape.translate(V(0,dy,0))
            found=collisions(shape,fixed)
            if found:hits.append({'front_y_mm':dy,'moving_object':name,'hits':found})
    report['paths']['front_cover']={'method':'exact per-part B-rep samples; 1 mm forward steps',
        'waypoints_xyz_mm':[[0,0,0],[0,-140,0]],'moving':moving,'fixed':fixed,
        'prerequisites':['Four recessed rear-access front-cover screws removed','Control/display cables disconnected'],
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
