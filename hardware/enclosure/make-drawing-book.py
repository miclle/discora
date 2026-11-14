"""Make an A3 PDF drawing book from export-drawings.py output.

Requires reportlab and svglib. Pass --font to a Chinese TrueType font/TTC.
Run after export-drawings.py; fails if the source model or build script changed.
"""
import argparse
import hashlib
import json
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

ROOT = Path(__file__).resolve().parent
# Dimensions and annotation positions below are reviewed for this CAD revision.
ANNOTATED_MODEL_SHA256 = '80eede1e85eafe8aca6ba6702cb2e169b6f7b4d1c368eeca10f1e6647bacebe0'
INK = HexColor('#182c35')
TEAL = HexColor('#087f82')
MUTED = HexColor('#536972')
LIGHT = HexColor('#d5e1e4')
TOTAL_PAGES = 12


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'drawings'/'Discora-V4-drawing-book-color.pdf')
    args=parser.parse_args()
    data=json.loads((ROOT/'drawings'/'geometry.json').read_text())
    if data['sha256'] != ANNOTATED_MODEL_SHA256:
        raise SystemExit('CAD revision changed: review dimension text and leader positions before updating ANNOTATED_MODEL_SHA256')
    for file,key in [('Discora.FCStd','sha256'),('build.FCMacro','build_sha256')]:
        if hashlib.sha256((ROOT/file).read_bytes()).hexdigest()!=data[key]:
            raise SystemExit('Source changed; rerun export-drawings.py: '+file)
    assert all(data['checks'].values())
    integration=json.loads((ROOT/'side-port-checks.json').read_text())
    handle=json.loads((ROOT/'handle-checks.json').read_text())
    volume=json.loads((ROOT/'volume-checks.json').read_text())
    seam=json.loads((ROOT/'side-seam-checks.json').read_text())
    bottom_check=json.loads((ROOT/'bottom-corner-checks.json').read_text())
    rear=json.loads((ROOT/'rear-thickness-checks.json').read_text())
    mount=json.loads((ROOT/'drive-mount-checks.json').read_text())
    pcb_volume=json.loads((ROOT/'volume-pcb-checks.json').read_text())
    perfboard=json.loads((ROOT/'perfboard-checks.json').read_text())
    speaker=json.loads((ROOT/'speaker-scope-checks.json').read_text())
    rib_check=json.loads((ROOT/'p3-seat-rib-checks.json').read_text())
    backlock=json.loads((ROOT/'backlock-rib-checks.json').read_text())
    fasteners=json.loads((ROOT/'fastener-checks.json').read_text())
    flat_back=json.loads((ROOT/'p3-flat-back-checks.json').read_text())
    current_perfboard=json.loads((ROOT/'current-perfboard-checks.json').read_text())
    drawing_baseline=json.loads((ROOT/'drawing-baseline-checks.json').read_text())
    assert drawing_baseline['all_pass'] and drawing_baseline['model_sha256']==data['sha256']
    assert current_perfboard['model_sha256']==data['sha256']
    assert drawing_baseline['baseline_sha256']==flat_back['model_sha256']
    assert flat_back['baseline_sha256']==backlock['model_sha256']
    assert backlock['model_sha256']==fasteners['model_sha256']
    assert {'FrontShell', 'RearShell'} <= set(flat_back['unchanged_finished_objects'])
    assert backlock['baseline_sha256']==rib_check['model_sha256']
    assert rib_check['baseline_sha256']==speaker['model_sha256']
    assert speaker['baseline_sha256']==perfboard['model_sha256']
    assert speaker['upper_p3_geometry_unchanged']
    assert not current_perfboard['harness_path_clashes'] and not current_perfboard['lead_reservation_clashes']
    assert current_perfboard['front_cover_opening_mm']==60
    assert all(not failures for checks in current_perfboard['unplug_access'].values() for failures in checks.values())
    validation=json.loads((ROOT/'validation.json').read_text())
    assembly=json.loads((ROOT/'assembly-paths.json').read_text())
    assert validation['sha256']==assembly['model_sha256']==data['sha256']
    assert validation['items']==44 and not validation['invalid'] and not validation['clashes']
    assert all(v<.001 for v in validation['mirror_difference_mm3'].values()) and assembly['all_pass']
    assert pcb_volume['model_sha256']==perfboard['baseline_sha256'] and pcb_volume['all_pass']
    assert pcb_volume['checker_sha256']==hashlib.sha256((ROOT/'check-volume.py').read_bytes()).hexdigest()
    assert mount['model_sha256']==pcb_volume['baseline_sha256'] and mount['all_pass']
    assert rear['model_sha256']==mount['baseline_sha256'] and rear['all_pass']
    assert bottom_check['model_sha256']==rear['baseline_sha256'] and bottom_check['all_pass']
    assert seam['model_sha256']==bottom_check['baseline_sha256'] and seam['all_pass']
    assert volume['model_sha256']==seam['baseline_sha256'] and volume['all_pass']
    assert volume['baseline_sha256']==handle['model_sha256']
    assert integration['model_sha256']==handle['baseline_sha256']
    def evidence_matches_geometry(report,owners):
        if report['model_sha256']==data['sha256']:return True
        if any(drawing_baseline['unchanged_finished_parts_difference_mm3'].get(n,1)>=.001 for n in owners):return False
        if report['model_sha256']==drawing_baseline['baseline_sha256']:return True
        if any(n not in flat_back['unchanged_finished_objects'] for n in owners):return False
        if report['model_sha256']==flat_back['baseline_sha256']:return True
        if any(n not in backlock['unchanged_finished_objects'] for n in owners):return False
        if report['model_sha256']==backlock['baseline_sha256']:return True
        if any(n not in rib_check['unchanged_finished_objects'] for n in owners):return False
        if report['model_sha256']==rib_check['baseline_sha256']:return True
        if any(speaker['finished_parts_difference_mm3'].get(n,1)>=.001 for n in owners):return False
        if report['model_sha256']==speaker['baseline_sha256']:return True
        if any(perfboard['unchanged_geometry_difference_mm3'].get(n,1)>=.001 for n in owners):return False
        if report['model_sha256']==perfboard['baseline_sha256']:return True
        if any(pcb_volume['unchanged_finished_parts_difference_mm3'].get(n,1)>=.001 for n in owners):return False
        if report['model_sha256']==pcb_volume['baseline_sha256']:return True
        if any(mount['unchanged_parts_difference_mm3'].get(n,1)>=.001 for n in owners):return False
        if report['model_sha256']==mount['baseline_sha256']:return True
        if any(rear['unchanged_finished_parts_difference_mm3'].get(n,1)>=.001 for n in owners):return False
        if report['model_sha256']==rear['baseline_sha256']:return True
        if any(bottom_check['unchanged_finished_parts_difference_mm3'].get(n,1)>=.001 for n in owners):return False
        if report['model_sha256']==bottom_check['baseline_sha256']:return True
        if any(seam['unchanged_finished_parts_difference_mm3'].get(n,1)>=.001 for n in owners):return False
        if report['model_sha256']==seam['baseline_sha256']:return True
        if any(volume['unchanged_finished_parts_difference_mm3'].get(n,1)>=.001 for n in owners):return False
        if report['model_sha256']==volume['baseline_sha256']:return True
        if any(handle['unchanged_finished_parts_difference_mm3'].get(n,1)>=.001 for n in owners):return False
        if report['model_sha256']==handle['baseline_sha256']:return True
        if (report['model_sha256']==integration.get('baseline_sha256')
                and all(integration.get('unchanged_finished_parts_difference_mm3',{}).get(n,1)<.001 for n in owners)):
            return True
        return False
    side=json.loads((ROOT/'drawings'/'side-profile.json').read_text())
    assert side['sha256']==data['sha256']
    color_data=json.loads((ROOT/'drawings'/'color-render.json').read_text())
    assert color_data['sha256']==data['sha256']
    assert color_data['geometry_sha256']==hashlib.sha256((ROOT/'drawings'/'geometry.json').read_bytes()).hexdigest()
    pdfmetrics.registerFont(TTFont('CN',str(args.font)))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(args.output),pagesize=(420*mm,297*mm),pageCompression=1)
    c.setTitle('Discora V4 整机尺寸与装配图册 · 彩色版')
    c.setAuthor('Discora project')
    c.setSubject('Saved CAD geometry; concept dimensions and exploded assembly; not a production release')

    def text(x,y,s,size=9,color=INK,align='left',background=False):
        # The bundled CJK font lacks subscript 2; keep the second letter block explicit.
        s=s.replace('₂','(2)')
        missing={ch for ch in s if ord(ch) not in pdfmetrics.getFont('CN').face.charToGlyph}
        assert not missing, f'Font lacks drawing characters: {missing}'
        if background:
            width=pdfmetrics.stringWidth(s,'CN',size)/mm
            left=x-({'left':0,'center':width/2,'right':width}[align])
            c.setFillColor(white)
            c.rect((left-.7)*mm,(y-.7)*mm,(width+1.4)*mm,(size/mm+1)*mm,fill=1,stroke=0)
        c.setFillColor(color); c.setFont('CN',size)
        getattr(c,{'left':'drawString','center':'drawCentredString','right':'drawRightString'}[align])(x*mm,y*mm,s)

    def line(x1,y1,x2,y2,color=INK,width=.2,dash=None):
        if color==TEAL and width<=.2 and not dash:
            c.setStrokeColor(white);c.setLineWidth((width+.35)*mm)
            c.line(x1*mm,y1*mm,x2*mm,y2*mm)
        c.setStrokeColor(color); c.setLineWidth(width*mm)
        c.setDash(dash or [])
        c.line(x1*mm,y1*mm,x2*mm,y2*mm)
        c.setDash([])

    def page(num,title,subtitle,scale):
        text(12,281,'DISCORA',23,TEAL)
        text(62,282,title,17)
        text(62,274,subtitle,9,MUTED)
        text(408,282,f'V4  /  {num:02d}  彩色版',14,TEAL,'right')
        line(12,269,408,269,LIGHT)
        line(12,16,408,16,LIGHT)
        text(12,10,'完整件试打 / CAD 静态几何 · 整机装配、声学与强度待实测',8,MUTED)
        text(245,10,'单位 mm  |  '+scale,8,MUTED)
        text(408,10,f'DC-V4-GA-{num:02d}  ·  2026-11-14  ·  {num}/{TOTAL_PAGES}',8,MUTED,'right')

    def view(name,x,y,scale=1,clip_bottom=0):
        info=data['views'][name]
        c.saveState()
        if clip_bottom:
            w,h=info['bounds']['size'][:2]
            clip=c.beginPath()
            clip.rect(x*mm,(y+clip_bottom*scale)*mm,w*scale*mm,(h-clip_bottom)*scale*mm)
            c.clipPath(clip,stroke=0,fill=0)
        if name in color_data['outputs']:
            color_file=ROOT/'drawings'/color_data['outputs'][name]['file']
            w,h=info['bounds']['size'][:2]
            c.drawImage(str(color_file),x*mm,y*mm,w*scale*mm,h*scale*mm,mask='auto')
        drawing=svg2rlg(str(ROOT/'drawings'/info['file']))
        drawing.scale(scale,scale)
        c.saveState()
        c.setStrokeAlpha(.65)
        renderPDF.draw(drawing,c,x*mm,y*mm)
        c.restoreState()
        c.restoreState()
        xmin,ymin=info['bounds']['min'][:2]
        return lambda u,v:(x+(u-xmin)*scale,y+(v-ymin)*scale)

    def arrow(x,y,dx,dy):
        # Two 30-degree strokes make a 1.6 mm arrowhead.
        line(x,y,x+1.6*dx+.6*dy,y+1.6*dy-.6*dx,TEAL,.16)
        line(x,y,x+1.6*dx-.6*dy,y+1.6*dy+.6*dx,TEAL,.16)

    def dh(x1,x2,edge,y,label):
        for x in (x1,x2): line(x,edge,x,y+(.9 if y>edge else -.9),LIGHT,.15)
        line(x1,y,x2,y,TEAL,.16)
        arrow(x1,y,1,0); arrow(x2,y,-1,0)
        text((x1+x2)/2,y+1.5,label,9,TEAL,'center',background=True)

    def dv(y1,y2,edge,x,label):
        for y in (y1,y2): line(edge,y,x+(.9 if x>edge else -.9),y,LIGHT,.15)
        line(x,y1,x,y2,TEAL,.16)
        arrow(x,y1,0,1); arrow(x,y2,0,-1)
        c.saveState(); c.translate((x-1.6)*mm,(y1+y2)/2*mm); c.rotate(90)
        text(0,0,label,9,TEAL,'center',background=True); c.restoreState()

    def notes(x,y,items,gap=7,size=9):
        for s in items:
            text(x,y,s,size); y-=gap

    def badge(x,y,s):
        c.setFillColor(white); c.setStrokeColor(TEAL); c.setLineWidth(.25*mm)
        c.circle(x*mm,y*mm,3*mm,fill=1,stroke=1)
        text(x,y-1,s,8,TEAL,'center')

    def table(x,y,width,rows,split=56,height=9):
        for i,(a,b) in enumerate(rows):
            if i%2==0:
                c.setFillColor(HexColor('#f1f6f6')); c.rect(x*mm,(y-height)*mm,width*mm,height*mm,fill=1,stroke=0)
            text(x+2,y-5.8,a,9)
            text(x+split,y-5.8,b,9)
            y-=height
        return y

    page(1,'整机外观尺寸','载板与线束维护见第 8 / 9 页，后壳加强筋见第 10 / 11 页','主视图 0.9:1')
    shoulder_z=side['outer_profile_yz'][2][1]
    handle_top=side['outer_profile_yz'][3][1]
    rear_peak_z=side['outer_profile_yz'][5][1]
    rear_eave_z=side['outer_profile_yz'][6][1]
    pf=view('front',25,30,.9)
    pr=view('right',205,30,.9)
    text(101.5,260,'正视 · 沿 +Y 观察',10,MUTED,'center')
    text(247,260,'右视 · 沿 -X 观察',10,MUTED,'center')
    dh(25,178,30,23,'170')
    dv(30,30+.9*(handle_top+2),25,17,f'{handle_top+2:.3f} 含脚垫和提手')
    dh(205,288.7,30,23,'93')
    x1,y1=pf(-45,shoulder_z+34.5);x2,_=pf(45,shoulder_z+34.5)
    dh(x1,x2,y1,252,'90 净开口')
    _,y0=pf(45,shoulder_z+10.5)
    dv(y0,y1,x2,x2+8,'24')
    x,y=pf(0,76)
    text(x,y,'Ø130 · 护网内凹 2.5',9,TEAL,'center',background=True)
    line(x,34,x,246,LIGHT,.15,[5,2,1,2])
    port=data['acoustics']['p2_outer_bounds']
    xa,ya=pr(port['min'][1],port['min'][2]);xb,yb=pr(port['max'][1],port['max'][2])
    dh(xa,xb,yb,yb+8,f"{port['size'][1]:.2f}")
    dv(ya,yb,xb,xb+10,f"{port['size'][2]:.2f}")
    axis,_=pr(49,0);line(axis,34,axis,235,TEAL,.15,[4,2])
    text(306,258,'主要尺寸 / mm',12,TEAL)
    table(304,249,104,[
        ('整机宽 / 深','170 / 93'),
        ('含脚垫总高',f'{handle_top+2:.3f}'),
        ('不含脚垫总高',f'{handle_top-1:.3f}'),
        ('提手净口 / 厚','90 × 24 / 5'),
        ('前 / 后壳主体','5 / 5'),
        ('侧口包络中心 Y / Z','44.861 / 65'),
        ('前后斜肩水平宽','44 / 44'),
        ('斜肩高差',f'{44*27/38:.3f}'),
        ('前 / 后斜角',f"{side['front_angle_deg']:.3f}°"),
        ('提手顶 Z',f'{handle_top:.3f}'),
        ('前斜肩顶 Z',f'{shoulder_z:.3f}'),
        ('后斜肩顶 Z',f'{rear_peak_z:.3f}'),
        ('后檐 Z',f'{rear_eave_z:.3f}'),
        ('底角 / 提手外角','R4 / R4'),
    ],split=49,height=9)
    notes(306,111,[
        'X 向右，Y 向后，Z 向上。',
        '机身左右对称面 X=0。',
        '脚垫底 Z=-2；外壳底 Z=1。',
        '后壳侧轮廓以 Y=49 对称。',
        '提手厚度中线 Y=46.5。',
        '壁厚以面法向测量。',
        '线缆侧向实测外伸 14.5。',
        '内宽 160，光驱宽 128。',
        '两侧各留 16，余量各 1.5。',
        '不得按预览图片量取尺寸。',
    ],gap=8,size=8)
    c.showPage()

    page(2,'顶面、背面与操控开孔','碟口按水平投影；操控开孔按前斜面真形','顶视 0.95:1；背视 0.85:1；开孔 1:1')
    pt=view('top',26,160,.95)
    text(107,259,'顶视 · 沿 -Z 观察',10,MUTED,'center')
    dh(26,187.5,248.35,253,'170')
    dv(160,248.35,187.5,197,'93')
    xa,ya=pt(-62,79.05);xb,_=pt(62,79.05)
    dh(xa,xb,ya,220,'124 碟口水平长度')
    line(xb,ya,204,241,TEAL,.16);text(204,243,'宽 5.5',9,TEAL)
    text(26,151,'碟口中心 X=0、Y=79.05；提手后表面 Y=49。',9)
    text(26,143,'120 × 1.2 光盘扫掠，至提手后表面净距 29.45。',8,MUTED)
    view('rear',245,22,.85)
    text(317,259,'背视 · 沿 -Y 观察',10,MUTED,'center')
    # Drawing cutouts share the actual inclined-plane frame.
    p=view('control-cutouts',40,97)
    centers=data['features']['control_cut_centers_xz']
    text(34,134,'前斜面开孔真形 · 朝斜面法向观察',11,TEAL)
    keys=[p(u,v) for u,v in centers if u<0]
    bottom=sorted(keys,key=lambda q:(q[1],q[0]))[:2]
    dh(bottom[0][0],bottom[1][0],bottom[0][1],86,'18 键距')
    left=sorted(keys,key=lambda q:q[0])[:2]
    dv(min(q[1] for q in left),max(q[1] for q in left),left[0][0],29,'20.85')
    text(146,94,'外圈：凹位 Ø25.6；内孔：Ø7.2',7,MUTED)
    notes(34,74,[
        '四键孔 Ø10.5；键帽 Ø10，露出 1.2；背面止退沿 Ø12.8。',
        '橙白双色键帽：白色符号深 0.6，与键面齐平；分别指定两种 PLA Lite。',
        'OLED 外口 32.82 × 18.1，倒角深 0.8；玻璃内退 1.0，详见第 6 页。',
        'B50K 壳孔 Ø7.2／局部壁厚 2；底盘 Ø24 下沉 1，十字 24×6.8，顶面高 12.9。',
        '键中心 X=-59 / -41、Y=9 / 26；屏与旋钮 Y=18、X=0 / 48。',
        '前壳背锁：后壁 X=±79.4、Z=33；后斜面 X=±29、Z=179。',
        'P3 支架：4 孔，X=±64、Z=27 / 124；Ø2.8，沉头 Ø4.8。',
        'P2 圆角梯形开放侧口；P3 独立导管末端留隙 0.7，详见第 12 页。',
        '背锁孔 Ø4.4／通孔 Ø2.2／盲底孔 Ø1.6；下孔深 78.8，名义螺钉 2×8。',
    ],gap=6.5,size=8.5)
    c.showPage()

    page(3,'整机爆炸图 / 外壳与内部','两层展开并排对照 · 相同 CAD 几何与展示位移，编号对应第 5 页对象清单','爆炸图 NTS（非比例装配距离）')
    for i,(color,label) in enumerate([
        ('#ff671f','前壳 / 橙色键帽'),('#000000','黑色旋钮'),('#16a9a4','内部支架'),('#4d5155','深色结构 / 单元'),
        ('#bac0c4','光驱 / 银色包络'),('#39775b','PCB'),('#3c6da9','5600 mAh 平排电池')]):
        sx=14+i*57
        c.setFillColor(HexColor(color));c.rect(sx*mm,258*mm,3*mm,3*mm,fill=1,stroke=0)
        text(sx+5,258.1,label,8,MUTED)
    line(210,38,210,251,LIGHT,.15)
    for panel,name,title in [(12,'exploded-shell','结构层 · 01–08'),(214,'exploded-core','内部层 · A–M')]:
        text(panel+97,250,title,10,TEAL,'center')
        info=data['views'][name]
        scale=min(150/info['bounds']['size'][0],147/info['bounds']['size'][1])
        w,h=[a*scale for a in info['bounds']['size'][:2]]
        px=panel+25+(150-w)/2;py=100+(147-h)/2
        p=view(name,px,py,scale)
        points=[(part,p(*info['anchors'][part['number']])) for part in info['parts']]
        midpoint=px+w/2
        for left in (True,False):
            entries=sorted([(part,pt) for part,pt in points if (pt[0]<midpoint)==left],key=lambda v:v[1][1])
            for i,(part,(x,y)) in enumerate(entries):
                by=109+i*(129/max(1,len(entries)-1)); bx=panel+7 if left else panel+186
                elbow=panel+16 if left else panel+177
                line(x,y,elbow,by,white,.65);line(elbow,by,bx,by,white,.65)
                line(x,y,elbow,by,TEAL,.15);line(elbow,by,bx,by,TEAL,.15)
                c.setFillColor(white);c.circle(x*mm,y*mm,1*mm,fill=1,stroke=0)
                c.setFillColor(TEAL);c.circle(x*mm,y*mm,.6*mm,fill=1,stroke=0)
                badge(bx,by,part['number'])
        for i,part in enumerate(info['parts']):
            col,row=divmod(i,7)
            x=panel+4+col*96;y=89-row*8
            badge(x,y+1,part['number']);text(x+5,y,part['label'].replace('见下一页','见右图'),8)
    notes(12,31,[
        '左图覆盖 44 个成品对象，08 为硬件总成；右图展开 P3、光驱压条和 30 个硬件对象，共 13 组。三个主体均为单一连续实体。',
        '引线端点为组包络中心；展示位移不是拆装路径。侧孔已并入后壳，拆装顺序及检查边界见第 5 页；颜色不代表实物材料。',
    ],gap=7,size=8)
    c.showPage()

    page(4,'侧剖与内部空间','截面 X=-26：穿过左喇叭中心，保留 -X 半体，沿 -X 观察','剖视 1:1；表格为模型读数')
    view('section',26,20)
    text(63,263,'A-A 侧剖',11,TEAL,'center')
    dh(34,75,98,131,'41 喇叭总深度')
    dh(102.2,113,156,208,'10.8 光驱最大厚度')
    dv(58,138,26,13,'80 单元高度')
    dh(32,102,30,18,'70 电池深度')
    dv(30,50,32,20,'20')
    text(65,38,'5600 mAh',8,white,'center')
    text(138,253,'主要包络 / 关键净距',12,TEAL)
    table(136,246,272,[
        ('单只喇叭 X × Y × Z','45 × 41 × 80 试装包络；中心 X=±26，Z=76；贴合面 Y=10'),
        ('P3 喇叭座','开口 71.5 × 39.3 / R12.5；每只四孔距 70 × 36，Ø2.3 底孔深 10.5'),
        ('单侧后腔外包络',' × '.join(f'{v:.1f}' for v in data['acoustics']['chamber_bounds']['size'])+'；含一体导管；净容积和调谐待实测'),
        ('喇叭前 / 后净距','格栅后面至喇叭 3，喇叭至后腔内壁 11；端子、走线及行程待试'),
        ('UJ-898 光驱','128 × 10.8 × 130；Y=76.2…87，Z=29.5…159.5'),
        ('光驱贴靠 / 固定','背面留 1 mm 保护垫；中央底托 + 可拆压条，两枚 M2×10'),
        ('SATA 接头 / 线缆','37.7 × 7，后伸 20.4；护线环 Ø6.5 × 3；侧伸 14.5'),
        ('功放 PCB / 元件预留','66 × 53 × 1.6 / 15；组件最高 Z=139.6'),
        ('主控 PCB / 元件预留','63.39 × 27.94 × 1.6 / 7；排母高8.5，组件最高Z=161.5'),
        ('DAC / 双路降压','DAC 水平装载板；两块 DCE001，载板底 Z=142.8，见第8页'),
        ('OLED PCB 局部尺寸','35.4 × 33.5 × 1.2；四孔 Ø3，孔距 30.4 × 28.5；图纸值'),
        ('5600 mAh 平排电池','112 × 70 × 20；X=±56，Y=6…76，Z=8…28'),
        ('电池周围名义净距','距后腔底 3.5；前 / 后内壁 1 / 12；托盘侧壁各 1'),
        ('脚垫中心','X=±55；Y=11 / 69；4 个脚垫为一个 CAD 复合对象'),
    ],split=69,height=9.5)
    notes(138,99,[
        '当前模型边界',
        '平排电池按商品标称包络；托盘并入后壳，预留 4 个绑带槽，绑带、线材及插头需实测。',
        '两块 DCE001 已纳入载板；充电电路未建模，整机电气与实物装配仍未验收。',
        '喇叭采用圆角盆架试装包络；喇叭静态前 / 后深 2 / 39；角部、螺丝及密封需实物试装。',
        '剖图使用实际实体裁切、隐藏线消除；未施加材料剖面线，不能由线型判断材质。',
        '喇叭安装座试片已通过；直接验证完整件的装配、支撑清理、强度和走线。',
        'P3 主通路 400 mm²，末端 4 mm 渐扩至约 587 mm²；气密和声学待实测。',
    ],gap=8,size=9)
    c.showPage()

    page(5,'对象清单、打印与拆装','44 个成品对象 · 尺寸为装配坐标系 X × Y × Z 的轴对齐包络，非展开尺寸','清单尺寸 mm；无制造数量承诺')
    labels={
        'FrontShell':'P1 前壳 / 提手 / 格栅 / 屏幕座',
        'RearShell':'P2 一体后壳 / 碟口 / 开放侧口 / 底架',
        'SpeakerCarrier':'P3 双声腔 / 前障板 / 电子托架',
        'Cowl':'前壳 / 提手','LPanel':'左侧壳','RPanel':'右侧壳','LPort':'左开放侧口','RPort':'右开放侧口',
        'FrontBezel':'中央格栅压圈','FrontGrille':'通孔护网','Back':'后盖','Base':'底架 / 下固定座','Feet':'脚垫复合件（4 个）',
        'Window':'OLED 玻璃面板','StatusArt':'显示内容示意','PlayPauseKey':'播放／暂停键帽','EjectKey':'退碟键帽','PrevKey':'上一曲键帽','NextKey':'下一曲键帽',
        'ButtonRetainer':'四键焊线支架（两侧敞开／双点支承）',
        'DisplayRetainer':'OLED 可拆压框（四点承压／两侧锁紧）',
        'DriveRetainer':'光驱可拆压条（两枚名义 M2×10）',
        'PlayPauseSwitch':'播放／暂停开关包络','EjectSwitch':'退碟开关包络','PrevSwitch':'上一曲开关包络','NextSwitch':'下一曲开关包络','Knob':'音量旋钮 · 黑白双色',
        'LChamber':'左后腔','RChamber':'右后腔','LDriverFrame':'左喇叭试装座','RDriverFrame':'右喇叭试装座',
        'FrontBaffle':'双开口前障板','RearTopMount':'上固定耳（2 个）','DriveCarrier':'光驱底托 / 导轨','SlotGuide':'碟口导向框',
        'DisplayCarrier':'屏幕安装座','AmpShelf':'功放 / 桥接器托板','ElectronicsSled':'主控托板','AmpPads':'功放支撑复合件',
        'MCUPads':'主控支撑复合件','DACPads':'DAC 支撑复合件','BatteryCradle':'平排电池托盘',
        'LDriver':'左喇叭总包络','RDriver':'右喇叭总包络','Encoder':'B50K 轴／六角螺母','VolumePot':'B50K PCB 插接模块 / 含插头包络',
        'Drive':'UJ-898 包络','Bridge':'SATA 接头 / 护线环','DisplayPCB':'OLED PCB／四孔与缺口','DisplayHeader':'OLED 弯针接头预留',
        'Amp':'功放 PCB','AmpChip':'功放元件预留','MCU':'主控 PCB','MCUChip':'主控元件预留','DAC':'DAC PCB',
        'DACChip':'DAC 元件预留','Battery':'5600 mAh 平排电池',
        'Perfboard':'洞洞板／右前缺口／左侧延伸',
        'MCUSockets':'主控排母高度包络','DACSockets':'DAC 排母高度包络',
        'BuckA':'DCE001 A／主控5Vin','BuckB':'DCE001 B／光驱及桥接器VBUS',
        'XHButtons':'四键5芯侧插包络','XHOLED':'OLED 4芯直插包络','XHVolumeSwitch':'音量开关2芯直插包络',
        'PerfboardScrew1':'M2×4／G₂-A','PerfboardScrew2':'M2×4／Q-N','PerfboardScrew3':'M2×4／A-O',
    }
    membership={n:part['number'] for key in ('exploded-shell','exploded-core')
                for part in data['views'][key]['parts'] if part['number']!='08' for n in part['objects']}
    items=list(data['objects'].items())
    def fmt(n): return f'{n:.2f}'.rstrip('0').rstrip('.')
    for col in range(2):
        x=12+201*col
        text(x,257,'图号 · 对象 ID / 名称',10,TEAL)
        text(x+195,257,'X × Y × Z',10,TEAL,'right')
        for i,(name,obj) in enumerate(items[col*22:(col+1)*22]):
            y=250-i*5.3
            if i%2==0:
                c.setFillColor(HexColor('#f1f6f6'));c.rect(x*mm,(y-5.0)*mm,195*mm,5.3*mm,fill=1,stroke=0)
            text(x+1,y-1.8,f'{membership[name]}  {name}',7)
            text(x+1,y-4.2,labels[name],6.3,MUTED)
            text(x+193,y-3.5,' × '.join(fmt(n) for n in obj['size']),7.5,INK,'right')
    text(12,127,'PLA 打印：3 主体 + 4 键帽 + 焊线支架 + 旋钮 + OLED 压框 + 光驱压条 = 11 件',11,TEAL)
    printing=json.loads((ROOT/'print'/'manifest.json').read_text())
    assert printing['model_sha256']==data['sha256'] and printing['all_pass']
    text(12,118,'P2SC / P2S配置 · 0.4喷嘴 / 0.20层高 / 3壁 / 15%填充 / 树状支撑；P3 双声腔背面直接贴板',8.5)
    for i,(name,label,pose) in enumerate([
        ('FrontShell','P1 前壳','正面朝下 / 板内转 90°'),('RearShell','P2 后壳','背面朝下'),
        ('SpeakerCarrier','P3 支架','声腔背面朝下')]):
        part=printing['parts'][name];plate=printing['plates'][name]
        size=' × '.join(fmt(n) for n in part['size_xyz_mm'])
        text(14,106-i*9,f"{label}  ·  {pose}  ·  打印包络 {size} mm  ·  切片估重 {plate['filament_g']:.1f} g（含支撑）",9)
    notes(14,72,[
        '前壳：断电卸4枚背锁螺钉，托住并前移60；按开关、OLED、四键次序拔线后移走，见第9页。',
        '光驱维护：拆 P3、两螺钉压条和电池；先前移 12，再前移 3 并抬高 9.5，进入接头拆卸位置。',
        'SATA 向下脱离、向内取出；光驱再前移 13，侧转 -30°并同步前移 20，最后抽出；安装逆序。',
        '光驱最大包络：抬升 31 姿态、侧转 61 姿态；前壳按 1 mm 抽样，其余直线段连续保守扫掠，实物未验收。',
        '四键双色：0.4 喷嘴 / 0.12 层高；白色 0.6 深；使用双色 3MF。实际色彩、配合与按压行程待测。',
        '音量模块：绕轴转 90°；拆卸先取下整个前壳，再拆旋钮和螺母，按第 7 页退出；旋钮保持原黑白双色 3MF。',
    ],gap=7,size=8.5)
    text(12,27,'FCStd SHA-256: '+data['sha256'],8,MUTED)
    text(408,27,'来源：Discora.FCStd / build.FCMacro / drawings/geometry.json',8,MUTED,'right')
    c.showPage()

    page(6,'OLED 沉槽与可拆压框','依据供应商结构图；玻璃面向外移 4.4；沉槽、倒角与压框来自保存 CAD；有效区虚线标注','模组正视 4:1；安装中剖 3:1')
    oled=json.loads((ROOT/'oled-checks.json').read_text())
    assert evidence_matches_geometry(oled,['Window','DisplayPCB','DisplayHeader','DisplayRetainer']) and oled['all_pass']
    # FrontShell changed only inside the checked shaft-centred X=35..61 zone.
    # The OLED mount is outside it; don't claim the entire shell is unchanged.
    assert pcb_volume['front_change_outside_mount_mm3']<.001
    assert data['oled']['mount_world_bounds']['max'][0]<35
    p=view('oled-module',38,86,4)
    text(109,243,'模组正面 · 排针朝斜面上方',11,TEAL,'center')
    lo,hi=p(-17.7,-18.8),p(17.7,14.7)
    dh(lo[0],hi[0],hi[1],233,'35.4 PCB')
    dv(lo[1],hi[1],lo[0],23,'33.5 PCB')
    h0,h1=p(-15.2,12.2),p(15.2,12.2)
    dh(h0[0],h1[0],h0[1],221,'30.4 孔距')
    b0=p(-15.2,-16.3)
    dv(b0[1],h0[1],h0[0],188,'28.5 孔距')
    aa0,aa1=p(-14.71,-7.35),p(14.71,7.35)
    c.setStrokeColor(TEAL);c.setLineWidth(.3*mm);c.setDash([3,2])
    c.rect(aa0[0]*mm,aa0[1]*mm,(aa1[0]-aa0[0])*mm,(aa1[1]-aa0[1])*mm,stroke=1,fill=0)
    c.setDash([])
    text(109,149,'有效区 29.42 × 14.7',10,TEAL,'center',True)
    text(109,140,'中心 X=0；高于 PCB 中心 2.05',8,MUTED,'center',True)
    text(38,75,'4 × Ø3 通孔；铜环外径图示 Ø4.5；底部缺口 14 × 4。',9)
    text(38,67,'有效区距 PCB 左边 2.99、顶边 7.35；玻璃距左边 0.45、顶边 5.25。',8.5)
    q=view('oled-side',214,101,3)
    text(237,243,'安装中剖（局部）',11,TEAL,'center')
    f,t=q(1,13.97),q(12.3,13.97)
    dh(f[0],t[0],f[1],233,'11.3 图纸总深度')
    text(214,94,'玻璃面距外斜面 1.0',8.5,TEAL)
    text(214,86,'玻璃 1.4 / PCB 1.2',8.5,TEAL)
    table(274,247,134,[
        ('外口 / 内喉口','32.82×18.1 / 30.42×15.7'),
        ('倒角 / 前缘厚度','深0.8；圆角R1.8→R0.6'),
        ('外斜面基准','X=0，Y=18，Z=177.789'),
        ('玻璃前面 / PCB 前面','法向向内 1.0 / 2.4'),
        ('PCB 背面 / 针尖','法向向内 3.6 / 12.3'),
        ('四孔定位柱','Ø2.6；PCB 孔 Ø3'),
        ('可拆压框','四点承压；背梁深6.4…8.4'),
        ('压框双侧固定','X=±20.5、局部Z=-7'),
        ('盲孔 / 名义螺钉','Ø1.6深4.4 / 2枚M2×6'),
        ('针尖后的插线预留','12.16 × 6 × 4.54'),
        ('工具通路预留','Ø4 × 20；两处无交叠'),
    ],split=51,height=10)
    notes(274,122,[
        '深度从外斜面沿内法向量取。',
        '玻璃与前缘间隙0.2；PCB 孔周四点承压。',
        '按第9页先拉开、拔线并卸前壳；取下压框，',
        '再沿内法向取出模组；两步均按0.5采样。',
    ],gap=7,size=8.5)
    notes(38,49,[
        '尺寸来源：oled-module-dimensions-wiring.webp。沉槽、倒角、定位柱和压框为外壳设计值。',
        '接头塑壳截面、插线和工具包络是设计预留；线材弯折、实际螺钉、打印孔补偿及装配配合仍须实测。',
        'Window 表示 OLED 自带玻璃面板；本版没有另设透明保护窗片。正前方及选定斜视方向无遮挡；不代表面板光学、密封或实物验收。',
    ],gap=7,size=8.5)
    c.showPage()

    page(7,'PCB 音量模块与安装槽','用户确认板尺寸及插接总厚度；插头 / 引脚为保守包络，未做实物验收','板面投影 3:1；安装剖视 2.6:1')
    text(100,258,'板面投影 · 转向前的尺寸基准',11,TEAL,'center')
    p=view('volume-module',42,153,3)
    a0,a1=p(-17.5,3.6),p(17.5,29.8)
    dh(a0[0],a1[0],a1[1],244,'35 PCB 宽')
    dv(a0[1],a1[1],a0[0],28,'26.2 沿轴深度')
    text(95,143,'板厚 1.5；轴线沿板宽居中；前边与安装面齐平',8.5,MUTED,'center')
    text(310,258,'安装局部剖视 · 保留轴线左半体',11,TEAL,'center')
    q=view('volume-installation',230,135,2.6)
    b0,b1=q(3.6,17.5),q(29.8,17.5)
    dh(b0[0],b1[0],b1[1],252,'26.2 伸入机内')
    table(12,130,190,[
        ('PCB 宽 / 深 / 板厚','35 / 26.2 / 1.5'),
        ('完整插接总厚度','15，已含引脚及插好的插头'),
        ('组件安装朝向','绕轴 90°，板宽沿斜面上下展开'),
        ('局部包络 X / Y / Z','15 / 26.2 / 35'),
        ('内槽 X / Y / Z','15.6 / 26.5 / 35.6'),
        ('夹持面 / 内槽底厚','2 / 3.6；横向与后端余量0.3'),
        ('轴总长 / 花轴长','15 / 10；轴径与螺纹沿用名义值'),
    ],split=66,height=10)
    table(218,120,190,[
        ('完整包络至支架',f"{data['volume_module']['clearances_mm']['SpeakerCarrier']:.3f}"),
        ('至主控元件预留',f"{data['volume_module']['clearances_mm']['MCUChip']:.3f}"),
        ('至后壳',f"{data['volume_module']['clearances_mm']['RearShell']:.3f}"),
        ('至光驱',f"{data['volume_module']['clearances_mm']['Drive']:.3f}"),
        ('至洞洞板',f"{data['volume_module']['clearances_mm']['Perfboard']:.3f}；外部旋钮与轴心保持"),
    ],split=75,height=10)
    notes(14,48,[
        '拆卸：按第9页拉开60并断开前壳线束，取下整个前壳；再拆旋钮、螺母，沿轴退出模块。',
        '安装：先锁螺母，再按实物关断止挡对准指示条并压入旋钮；插拔线束时托住 PCB。',
        '原主体、轴径、齿形、螺纹和 PCB 相对轴的高度仍为名义假设；模拟音量线束与开关额定值待确认。',
    ],gap=8,size=9)
    c.showPage()


    page(8,'洞洞板板形、布局与固定','从保存 CAD 读取 · 顶视沿 -Z；上方为机身后方 +Y，右方为 +X','板形与布局 1.5:1')
    text(105,258,'载板轮廓与三个固定孔',11,TEAL,'center')
    p=view('perfboard-outline',24,165,1.5)
    a0,a1=p(-43,75),p(57,75)
    dh(a0[0],a1[0],a0[1],253,'100 基准板宽；左耳另加11')
    lo,hi=p(-54,20),p(-54,75)
    dv(lo[1],hi[1],lo[0],16,'55 基准深度')
    for i,mount_info in enumerate(current_perfboard['mounts'],1):
        x,y=p(*mount_info['center_xy_mm'])
        badge(x+7,y+5,str(i));line(x,y,x+5,y+4,TEAL,.15)
    text(305,258,'装配布局 · 接插件为插合包络',11,TEAL,'center')
    q=view('perfboard-layout',226,165,1.5)
    for obj,label in [('MCU','ESP32-S3'),('DAC','PCM5102'),('BuckA','A'),('BuckB','B'),
                      ('XHButtons','5P'),('XHOLED','4P'),('XHVolumeSwitch','2P')]:
        ob=data['objects'][obj]
        x,y=q(*[(ob['min'][i]+ob['max'][i])/2 for i in (0,1)])
        text(x,y-1,label,8,TEAL,'center',True)
    table(12,150,190,[
        ('载板底面 / 厚度','Z=142.8 / 1.6'),
        ('右前避让缺口','X40.25…57，Y20…52；16.75×32'),
        ('左侧延伸耳','X-54…-43，Y40.86…50.86；11×10'),
        ('1 · G₂ / A','X=-27.28，Y=23.00'),
        ('2 · Q / N','X=13.36，Y=56.02'),
        ('3 · A / O','X=54.00，Y=58.56'),
        ('固定孔与螺钉','板Ø2.2／托架导孔Ø1.6；3枚M2×4'),
    ],split=53,height=10)
    table(218,150,190,[
        ('排母 / 模块PCB / 元件','8.5 / 1.6 / 7；顶部Z=161.5'),
        ('双路 DCE001 A / B','本体各17.5×12；含支承高7.5'),
        ('四键 5P','18×16×8；向机身左侧拔'),
        ('OLED 4P','13.5×8×11；向上拔'),
        ('开关 2P','8.5×8×11；向上拔'),
        ('板至光驱 / B50K','1.200 / 1.250'),
        ('板下走线至功放元件','1.200；板底走线深度预留2'),
    ],split=64,height=10)
    notes(14,68,[
        '孔名为原板元件面丝印：X向右A至Z再A至P，图中第二段加(2)；Y向下A至Z再1至4。',
        '布局水平转180°；原板毫米坐标换算 X=57-u、Y=20+v。三处支承留Ø5承压环，扩孔前核对铜皮与焊点。',
        '5P候选孔：J₂ / B…F；4P：H₂…K₂ / J；2P：O₂…P₂ / J。不是原板切割模板。',
        'XH类接插件按2.54孔位排布；实际针距、锁扣、脚位和插合尺寸须核对。DCE001绝缘固定、散热与短线待试装。',
        '主控USB／COM插座留空；桥接数据与供电按接线文档连接。板上孔位与电气线序见 docs/perfboard-layout.md。',
    ],gap=8,size=8.5)
    c.showPage()

    page(9,'前壳线束与 60 mm 维护位','当前 CAD 的隐藏线束预留 · 颜色用于区分回路；前壳只显示 Z≥140 的上部','顶视适配页面 NTS；位移按标注')
    wire_colors=[('#2054D1','四键'),('#9933B8','OLED'),('#FF660A','音量开关')]
    for i,(color,label) in enumerate(wire_colors):
        x=126+i*64;c.setFillColor(HexColor(color));c.rect(x*mm,258*mm,3*mm,3*mm,fill=1,stroke=0)
        text(x+5,258,label,9)
    for left,name,title in [(12,'harness-closed','合壳位置 · U形回环'),(218,'harness-open','前壳沿 -Y 拉开60 · 托住前壳')]:
        info=data['views'][name];w,h=info['bounds']['size'][:2]
        scale=min(180/w,152/h)
        x=left+(190-w*scale)/2;y=245-h*scale
        view(name,x,y,scale)
        text(left+95,250,title,10,TEAL,'center')
    notes(14,82,[
        '1  断电、卸4枚背锁螺钉；托住前壳向前平移60 mm，三组回环释放余量。',
        '2  先向上拔音量开关2P并移开线，再向上拔OLED 4P，最后向机身左侧拔四键5P；开关余线经过OLED入口。',
        '3  断开其余前壳线束后移走前壳。拆载板先断数据、供电及DAC音频，再卸3枚M2螺钉；也可随P3整体拆出。',
        '中心线路径：四键120.9、OLED 114.8、音量开关200.7 mm。制线另加端子压接、实际出口及固定余量。',
        '验证范围：0…60 mm每2 mm采样；按上述次序校核拔出包络及12×10 mm入口，不代表手指操作或弯曲应力验收。',
        'B50K双声道模拟线束、最终电源线与端子短尾未完整建模；同样须留服务余量，并检查合壳压线与实物卡扣。',
        '图中的圆柱／球形转角是占位包络，不表示实际线束弯曲半径；接口线序仍以接线文档和实物丝印为准。',
    ],gap=8,size=9)
    c.showPage()

    page(10,'后壳 P3 螺丝座加强筋','从机身正面看 P2 内侧 · 四处定位与右上座剖面详图','内侧正视 1:1 · 局部 4:1')
    ribs=data['p3_seat_ribs']
    text(117,253,'P2 内侧正视  /  沿 +Y 观察',11,TEAL,'center')
    inside=view('p2-interior',32,51,1)
    axis_x,_=inside(0,0)
    line(axis_x,46,axis_x,246,LIGHT,.2,[5,2,1,2])
    text(axis_x,42,'X=0 镜像基准',9,TEAL,'center')
    for i,rib in enumerate(ribs,1):
        x0,_,z0=rib['bounds']['min']
        x1,_,z1=rib['bounds']['max']
        x,y=inside(x0,z0)
        w,h=x1-x0,z1-z0
        c.setFillColor(TEAL); c.setStrokeColor(white); c.setLineWidth(.25*mm)
        c.rect(x*mm,y*mm,w*mm,h*mm,stroke=1,fill=1)
        badge_x=19 if x0<0 else 215
        center_y=y+h/2
        line(badge_x,center_y,x+w/2,center_y,TEAL,.16)
        badge(badge_x,center_y,str(i))

    line(228,37,228,250,LIGHT,.15)
    text(321,253,'右上座水平剖面  /  Z=124',11,TEAL,'center')
    top=view('p3-seat-section',271,145,4)
    rib=ribs[3]
    tri=c.beginPath()
    for i,(x,y) in enumerate(rib['plan_vertices']):
        tx,ty=top(x,y)
        (tri.moveTo if i==0 else tri.lineTo)(tx*mm,ty*mm)
    tri.close()
    c.setFillColor(HexColor('#c7e4e6')); c.setStrokeColor(TEAL); c.setLineWidth(.25*mm)
    c.drawPath(tri,stroke=1,fill=1)
    x0,y0,_=rib['bounds']['min']
    x1,y1,_=rib['bounds']['max']
    x,y=top(x0,y0)
    end_x,end_y=top(x1,y1)
    dh(x,end_x,y,237,fmt(x1-x0))
    dv(y,end_y,end_x,389,fmt(y1-y0))
    text(373,223,'侧壁',9,MUTED,'center')
    text(315,161,'螺丝座',9,MUTED,'center')
    text(302,140,'前方 -Y',9,MUTED,'center')
    text(281,219,'后方 +Y',9,MUTED,'center')

    _,leg,thickness=rib['bounds']['size']
    text(244,118,'筋条侧视',10,TEAL)
    c.setFillColor(HexColor('#c7e4e6')); c.setStrokeColor(TEAL); c.setLineWidth(.25*mm)
    c.rect(282*mm,110*mm,4*leg*mm,4*thickness*mm,stroke=1,fill=1)
    dv(110,110+4*thickness,282+4*leg,327,fmt(thickness))
    text(340,122,'四处相同',10,TEAL)
    text(340,113,'两直角边各外露 8',9)
    text(340,105,'Z 向厚 4',9)

    text(244,94,'四条筋坐标范围',10,TEAL)
    for i,rib in enumerate(ribs,1):
        lo,hi=rib['bounds']['min'],rib['bounds']['max']
        y=81-(i-1)*8
        badge(247,y+1,str(i))
        text(254,y,rib['location'],9)
        text(269,y,f'X {fmt(lo[0])} 至 {fmt(hi[0])}',9)
        text(324,y,f'Y {fmt(lo[1])} 至 {fmt(hi[1])}',9)
        text(365,y,f'Z {fmt(lo[2])} 至 {fmt(hi[2])}',9)
    carrier=assembly['paths']['speaker_carrier_front']
    assert not carrier['clashes'] and carrier['translation_xyz_mm']==[0,-140,0]
    text(12,29,'拆下前壳、断线并卸除四颗 P3 固定螺钉后，当前 P3 总成沿 -Y 前移 140 mm 连续保守扫掠无干涉。',9)
    text(12,21,'尺寸为 CAD 名义值。打印配合与锁紧强度待实物验证。',8.5,MUTED)
    c.showPage()

    page(11,'后斜面背锁深孔座加强筋','P2 内侧正视与右侧孔座轴向剖面 · 两条筋关于 X=0 镜像','内侧正视 1:1 · 轴向剖面 3:1')
    ribs=backlock['ribs']
    text(117,253,'P2 内侧正视  /  沿 +Y 观察',11,TEAL,'center')
    inside=view('p2-interior',32,51,1)
    axis_x,_=inside(0,0)
    line(axis_x,46,axis_x,246,LIGHT,.2,[5,2,1,2])
    text(axis_x,42,'X=0 镜像基准',9,TEAL,'center')
    for i,rib in enumerate(ribs,1):
        x0,_,z0,x1,_,z1=rib['bounds_xyz_mm']
        x,y=inside(x0,z0)
        c.setFillColor(TEAL); c.setStrokeColor(white); c.setLineWidth(.25*mm)
        c.rect(x*mm,y*mm,(x1-x0)*mm,(z1-z0)*mm,stroke=1,fill=1)
        badge_x=20 if x0<0 else 214
        center_y=y+(z1-z0)/2
        line(badge_x,center_y,x+(x1-x0)/2,center_y,TEAL,.16)
        badge(badge_x,center_y,str(i))

    line(228,37,228,250,LIGHT,.15)
    access=[item for item in fasteners['rear_access'] if item['rear_center_xyz_mm'][2]==179]
    assert len(access)==2 and all(not item['clashes'] for item in access)
    right=access[1]
    axis_x,entry,axis_z=right['rear_center_xyz_mm']
    seat=right['seat_y_mm']
    text(321,253,f'右侧孔座轴向剖面  /  X={fmt(axis_x)}',11,TEAL,'center')
    section=view('upper-backlock-section',255,152,3)
    tri=c.beginPath()
    for i,(y,z) in enumerate(data['upper_backlock_rib_section_yz']):
        sx,sy=section(y,z)
        (tri.moveTo if i==0 else tri.lineTo)(sx*mm,sy*mm)
    tri.close()
    c.setFillColor(HexColor('#c7e4e6')); c.setStrokeColor(TEAL); c.setLineWidth(.25*mm)
    c.drawPath(tri,stroke=1,fill=1)
    x0,y0,z0,x1,y1,z1=ribs[1]['bounds_xyz_mm']
    rib_start,rib_z=section(y0,z1)
    rib_end,_=section(y1,z1)
    dh(rib_start,rib_end,rib_z,234,fmt(y1-y0))
    text((rib_start+rib_end)/2,241,'新增材料 Y 向范围',8.5,MUTED,'center')
    seat_x,bore_y=section(seat,axis_z)
    entry_x,_=section(entry,axis_z)
    line(seat_x,bore_y,392,bore_y,TEAL,.2,[4,2])
    arrow(entry_x+3,bore_y,1,0)
    text(391,bore_y+4,'后方进刀',8.5,TEAL,'right')
    dh(seat_x,entry_x,bore_y,145,f"{right['well_depth_mm']:.2f}")
    text((seat_x+entry_x)/2,134,'螺钉承压面至斜面外表面轴心',8.5,MUTED,'center')

    text(242,123,'两条加强筋坐标与尺寸',10,TEAL)
    for i,rib in enumerate(ribs,1):
        x0,y0,z0,x1,y1,z1=rib['bounds_xyz_mm']
        row=111-(i-1)*8
        badge(246,row+1,str(i))
        text(254,row,f'X {fmt(x0)} 至 {fmt(x1)}',9)
        text(298,row,f'Y {fmt(y0)} 至 {fmt(y1)}',9)
        text(350,row,f'Z {fmt(z0)} 至 {fmt(z1)}',9)
    text(242,92,f'每条 X 向宽 {fmt(x1-x0)}，融合后新增材料的 Z 向包络高 {fmt(z1-z0)}。',9)
    driver_gap=min(r['minimum_distance_to_driver_mm'] for r in ribs)
    sampled_gap=min(r['minimum_sampled_front_clearance_mm'] for r in ribs)
    continuous_gap=min(r['continuous_front_clearance_lower_bound_mm'] for r in ribs)
    text(242,77,'螺丝刀通路',10,TEAL)
    text(242,69,f"Ø{fmt(right['tool_diameter_mm'])} 刀杆通过 Ø{fmt(fasteners['head_well_diameter_mm'])} 工具孔，距新增筋最近 {driver_gap:.2f} mm。",9)
    text(242,54,'前壳抽出净空',10,TEAL)
    text(242,46,f"断线并卸除四颗背锁螺钉后，沿 -Y 抽出 {backlock['front_cover_travel_mm']:g} mm。",9)
    text(242,38,f'距新增筋最小采样净距 {sampled_gap:.3f} mm，连续净距下界 {continuous_gap:.3f} mm。',9)
    text(12,23,'净空采用 CAD 刚体包络。实际批头配合、打印精度和锁紧强度待实物验证。',8.5,MUTED)
    c.showPage()

    page(12,'P2 开放侧口与 P3 独立导管','ADR-0045 / ADR-0046 · 左右按 X=0 镜像 · 已试装的喇叭安装座保留','侧视 1:1 · 导管剖视 2:1')
    text(67,255,'P2 / P3 实际装配侧视',11,TEAL,'center')
    view('port-assembly',22,48,1)
    text(185,255,'P3 导管截面 X=-70',11,TEAL,'center')
    view('duct-section',136,60,2)
    text(283,255,'声道与装配名义尺寸',11,TEAL)
    table(265,244,143,[
        ('P2 外口包络','38.48 × 28.20 mm'),
        ('P2 外圆角','R5.6；内圆角 R4'),
        ('P2 渐收段','4.85 mm + 0.15 mm 直段'),
        ('P3 主通路','400 mm²；一转弯回路'),
        ('P3 短渐扩段','长 4 mm；末端 R2.2'),
        ('P3 末端净面积',f"{data['acoustics']['outlet_area_mm2']:.2f} mm²"),
        ('P3 末端口沿','横截面名义厚 1.8 mm'),
        ('P2 / P3 间隙','0.7 mm；不跨件粘接'),
    ],split=48,height=12)
    notes(265,135,[
        'P3 背面朝下：双背板首层直接贴板。',
        'P3：仅底板支撑 ON，关键区域 ON。',
        'P2：仅底板支撑 OFF，关键区域 OFF。',
        'P2 支撑由敞开正面和侧口清理。',
        'P3 声腔、导管内未生成支撑走线。',
        '喇叭座外周与出线处采用可移除封堵。',
        'P2 为外壳，不承担 P3 导管密封。',
    ],gap=10,size=8.5)
    text(14,30,'左图保留真实遮挡；中图仅按标注剖切真实 P3 实体。没有为图示移动导管或扩大通道。',8.5,MUTED)
    text(14,22,'当前为完整件试打版本；喇叭安装座试片已通过。整机装配、拆撑、气密、承载与声学仍待实测。',8.5,MUTED)
    c.showPage()

    c.save()
    print('PDF_OK',args.output)


if __name__=='__main__':
    main()
