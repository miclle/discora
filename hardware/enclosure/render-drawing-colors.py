"""Render orthographic colour plates from saved CAD meshes for the drawing book.

Run in FreeCAD Python with numpy and Pillow. Source shapes are never saved.
A per-pixel depth buffer preserves occlusion and holes; PDF adds exact HLR edges.
"""
import ast
import hashlib
import json
import math
from pathlib import Path

import FreeCAD as A
import Part
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'drawings'
MODEL_SHA256 = 'b1e943face3860219c90706176f7a709497eb15f5b1de335028ce72c6ac2d5ad'


def palette_from_build():
    """Read the documented model palette without executing the GUI build macro."""
    palette={}
    for node in ast.parse((ROOT/'build.FCMacro').read_text()).body:
        if not isinstance(node,ast.Assign) or not isinstance(node.targets[0],ast.Tuple):
            continue
        names=[n.id for n in node.targets[0].elts]
        if names[0] in ('ORANGE','GLASS','KNOB_BLACK'):
            palette.update(zip(names,ast.literal_eval(node.value)))
    assert len(palette)==11
    return palette


def wire_points(wire):
    """Discretize ordered edges individually; OCC's compound-wire sampler can crash.

    Explicitly orient samples by shared endpoints so hole masks remain closed.
    """
    paths=[edge.discretize(Deflection=.05) for edge in wire.OrderedEdges]
    if len(paths)>1 and min((paths[0][-1]-p).Length for p in (paths[1][0],paths[1][-1]))>1e-6:
        paths[0].reverse()
    points=list(paths[0])
    for path in paths[1:]:
        if (points[-1]-path[-1]).Length<(points[-1]-path[0]).Length:path.reverse()
        assert (points[-1]-path[0]).Length<1e-5, 'Disconnected wire samples'
        points.extend(path[1:])
    assert (points[0]-points[-1]).Length<1e-5, 'Open face boundary'
    return np.array([[v.x,v.y,v.z] for v in points])


def surface_polygons(shape):
    """Keep planar faces and their holes intact; mesh only curved faces.

    Triangulating the grille's single face with thousands of hole boundaries
    is unnecessarily expensive. Its planar depth is exact without triangles.
    """
    surfaces=[]
    for face in shape.Faces:
        if isinstance(face.Surface,Part.Plane):
            outer=face.OuterWire
            # Boolean tangencies may retain open INTERNAL edges on a planar
            # face. They enclose no hole and crash OCC's wire sampler.
            holes=[w for w in face.Wires if not w.isSame(outer)
                   and any(e.Orientation not in ('Internal','External') for e in w.Edges)]
            wires=[outer]+holes
            loops=[wire_points(w) for w in wires]
            n=face.normalAt(0,0)
            surfaces.append((loops,np.array([n.x,n.y,n.z])))
        else:
            verts,faces=face.tessellate(.05)
            if not faces:continue
            mesh=np.array([[v.x,v.y,v.z] for v in verts])[np.array(faces)]
            for tri in mesh:
                normal=np.cross(tri[1]-tri[0],tri[2]-tri[0])
                surfaces.append(([tri],normal))
    return surfaces


def render(parts,rows,bounds,path):
    # 12 px per CAD mm: 305 dpi at 1:1 and >500 dpi on exploded pages.
    width,height=bounds['size'][:2]
    w,h=math.ceil(width*12),math.ceil(height*12)
    sx,sy=w/width,h/height
    matrix=np.asarray(rows)
    depth=np.full((h,w),-np.inf,dtype=np.float32)
    pixels=np.zeros((h,w,4),dtype=np.uint8)
    light=np.array([-.35,.55,.76]);light/=np.linalg.norm(light)
    for surfaces,color,offset in parts:
        for loops,normal in surfaces:
            normal=matrix@normal
            norm=np.linalg.norm(normal)
            if norm<1e-12 or abs(normal[2])/norm<1e-8:continue
            normal/=norm
            if normal[2]<0:normal=-normal
            shade=.69+.31*max(0,normal@light)
            shaded=np.clip((.12+.88*np.array(color))*shade*255,0,255).astype(np.uint8)
            projected=[(loop+offset)@matrix.T for loop in loops]
            base=projected[0][0]
            # Rasterized polygon borders can fall just outside a grazing face.
            # Reject extrapolated depths beyond its actual vertex range, which
            # otherwise lets distant cylinder edges leak through opaque panels.
            near=min(loop[:,2].min() for loop in projected)
            far=max(loop[:,2].max() for loop in projected)
            screen=[np.column_stack(((loop[:,0]-bounds['min'][0])*sx,
                                     (bounds['max'][1]-loop[:,1])*sy)) for loop in projected]
            outer=screen[0]
            left=max(0,int(math.floor(outer[:,0].min())))
            right=min(w,int(math.ceil(outer[:,0].max()))+1)
            top=max(0,int(math.floor(outer[:,1].min())))
            bottom=min(h,int(math.ceil(outer[:,1].max()))+1)
            if right<=left or bottom<=top:continue
            mask_image=Image.new('L',(right-left,bottom-top))
            draw=ImageDraw.Draw(mask_image)
            for j,loop in enumerate(screen):
                draw.polygon([tuple(v) for v in loop-np.array([left,top])],fill=255 if j==0 else 0)
            mask_pixels=np.asarray(mask_image)
            for ystart in range(top,bottom,128):
                yend=min(bottom,ystart+128)
                yy,xx=np.ogrid[ystart:yend,left:right]
                u=(xx+.5)/sx+bounds['min'][0]
                v=bounds['max'][1]-(yy+.5)/sy
                z=base[2]-normal[0]/normal[2]*(u-base[0])-normal[1]/normal[2]*(v-base[1])
                old=depth[ystart:yend,left:right]
                mask=(mask_pixels[ystart-top:yend-top]>0)&(z>=near-1e-5)&(z<=far+1e-5)&(z>old)
                old[mask]=z[mask]
                tile=pixels[ystart:yend,left:right]
                tile[mask,:3]=shaded;tile[mask,3]=255
    Image.fromarray(pixels).save(path,optimize=True)
    return [w,h]


def main():
    data=json.loads((OUT/'geometry.json').read_text())
    source=ROOT/'Discora.FCStd'
    assert data['sha256']==MODEL_SHA256==hashlib.sha256(source.read_bytes()).hexdigest()
    assert data['build_sha256']==hashlib.sha256((ROOT/'build.FCMacro').read_bytes()).hexdigest()
    palette=palette_from_build()
    assignments={
        'ORANGE':'FrontShell PlayPauseKey EjectKey PrevKey NextKey',
        'TEAL':'SpeakerCarrier ButtonRetainer DisplayRetainer',
        'BLACK':'RearShell',
        'RUBBER':'Feet LDriver RDriver VolumePot DisplayHeader AmpChip DACChip PlayPauseSwitch EjectSwitch PrevSwitch NextSwitch',
        'GLASS':'Window','PIXEL':'StatusArt','KNOB_BLACK':'Knob',
        'SILVER':'Drive Encoder MCUChip','PCB':'Bridge DisplayPCB Amp MCU DAC','BLUE':'Battery',
    }
    colors={name:palette[key] for key,names in assignments.items() for name in names.split()}
    assert set(colors)==set(data['objects'])
    appearance=json.loads((ROOT/'appearance-checks.json').read_text())
    integration=json.loads((ROOT/'side-port-checks.json').read_text())
    assert integration['model_sha256']==MODEL_SHA256
    assert appearance['model_sha256']==integration['baseline_sha256']
    assert all(integration['unchanged_finished_parts_difference_mm3'][n]<.001
               for n in ('PlayPauseKey','EjectKey','PrevKey','NextKey'))
    white_marks=appearance['color_update']['white_mark_faces_zero_based']
    rows={
        'front':((1,0,0),(0,0,1),(0,-1,0)),
        'right':((0,1,0),(0,0,1),(1,0,0)),
        'top':((1,0,0),(0,1,0),(0,0,1)),
        'rear':((-1,0,0),(0,0,1),(0,1,0)),
        'iso':((math.sqrt(3)/2,.5,0),(-.25,math.sqrt(3)/4,math.sqrt(3)/2),(math.sqrt(3)/4,-.75,.5)),
    }
    doc=A.openDocument(str(source))
    meshes={}
    for name in colors:
        meshes[name]=surface_polygons(doc.getObject(name).Shape)
        print('SURFACES',name,len(meshes[name]),flush=True)
    outputs={}
    for name,view in data['views'].items():
        if name=='control-cutouts' or name.startswith('oled-'):continue  # Unfilled dimensional details.
        parts=[]
        if 'parts' in view:
            parts=[(n,p['offset_mm']) for p in view['parts'] for n in p['objects']]
        elif name=='section':parts=[(n,(0,0,0)) for n in colors]
        else:parts=[(n,(0,0,0)) for g in ('Shell','Controls') for n in data['groups'][g]]
        render_parts=[]
        for obj,offset in parts:
            mesh=meshes[obj]
            if name=='section':
                shape=doc.getObject(obj).Shape.common(Part.makeBox(174,400,500,A.Vector(-200,-100,-100)))
                if shape.isNull() or not shape.Faces:continue
                mesh=surface_polygons(shape)
            if obj in white_marks and name!='section':
                shape=doc.getObject(obj).Shape
                indices=set(white_marks[obj])
                # Render the white PLA regions recorded in the saved GUI model.
                for is_white in (False,True):
                    faces=[f for i,f in enumerate(shape.Faces) if (i in indices)==is_white]
                    render_parts.append((surface_polygons(Part.makeCompound(faces)),
                                         palette['WHITE'] if is_white else colors[obj],np.array(offset)))
            else:
                render_parts.append((mesh,colors[obj],np.array(offset)))
        size=render(render_parts,rows[view['direction']],view['bounds'],OUT/(name+'-color.png'))
        outputs[name]={'file':name+'-color.png','size_px':size}
        print('COLOUR_OK',name,size,flush=True)
    A.closeDocument(doc.Name)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==MODEL_SHA256
    (OUT/'color-render.json').write_text(json.dumps(dict(
        sha256=MODEL_SHA256,build_sha256=data['build_sha256'],
        geometry_sha256=hashlib.sha256((OUT/'geometry.json').read_bytes()).hexdigest(),
        palette=palette,objects=colors,white_mark_faces_zero_based=white_marks,
        tessellation_deflection_mm=.05,pixels_per_mm=12,
        method='Orthographic planar faces with hole masks and curved-face triangles, per-pixel depth and directional shading; exact HLR edges added in PDF',
        outputs=outputs),ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
