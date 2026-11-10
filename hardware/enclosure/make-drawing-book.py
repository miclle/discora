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
ANNOTATED_MODEL_SHA256 = 'd7c2b89b240a10b2462816dccdbaa3489bcd6d2ade85581517a99eafa7ab16d5'
INK = HexColor('#182c35')
TEAL = HexColor('#087f82')
MUTED = HexColor('#536972')
LIGHT = HexColor('#d5e1e4')
TOTAL_PAGES = 6


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
    assert handle['model_sha256']==data['sha256']
    assert integration['model_sha256']==handle['baseline_sha256']
    def evidence_matches_geometry(report,owners):
        if report['model_sha256']==data['sha256']:return True
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
        text(12,10,'概念设计 / CAD 静态几何 · 未经实物装配、声学或生产验收',8,MUTED)
        text(245,10,'单位 mm  |  '+scale,8,MUTED)
        text(408,10,f'DC-V4-GA-{num:02d}  ·  2026-11-10  ·  {num}/{TOTAL_PAGES}',8,MUTED,'right')

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

    page(1,'整机外观尺寸','正视与右视 · 独立正投影，按视图名称读取；不按排列推断投影法','主视图 1:1')
    shoulder_z=side['outer_profile_yz'][2][1]
    handle_top=side['outer_profile_yz'][3][1]
    view('front',35,20)
    view('right',222,20)
    text(35,264,'正视 · 沿 +Y 观察',9,MUTED)
    text(259,264,'右视 · 沿 -X 观察',10,MUTED,'center')
    dh(35,177,20,18,'142')
    dv(20,20+handle_top,35,23,f'{handle_top:.2f}（含脚垫和提手）')
    dh(222,302,20,18,'80')
    dh(61,151,20+shoulder_z+34.5,259,'90 净开口')
    dv(20+shoulder_z+10.5,20+shoulder_z+34.5,151,164,'24')
    dv(20,96,177,191,'76 格栅中心高')
    line(106,26,106,253,LIGHT,.15,[5,2,1,2])
    line(39,96,173,96,LIGHT,.15,[5,2,1,2])
    c.setFillColor(white); c.rect(86*mm,91*mm,40*mm,10*mm,fill=1,stroke=0)
    text(106,94,'Ø130 圆孔 · 护网内凹 2.5',10,TEAL,'center')
    line(262,53,262,253,TEAL,.15,[4,2,1,2])
    dv(66.5,133.5,273,287,'67 导音口')
    dh(251,273,100,153,'22')
    # Side dimensions use foot-bottom Z=0; paired body-bottom values are adjacent.
    for z,edge,x,label in [(165,222,211,'165'),(shoulder_z,259.5,200,f'{shoulder_z:.2f}'),(165,302,310,'165')]:
        dv(20,20+z,edge,x,label)
    dh(222,259.5,20+shoulder_z,239,'37.5')
    dh(264.5,302,20+shoulder_z,239,'37.5')
    line(218,20,312,20,MUTED,.15,[4,2])
    line(218,23,302,23,LIGHT,.15,[2,2])
    for letter,u,z,dx,dy in [('A',0,165,3,-7),('B',37.5,shoulder_z,-5,3),
                              ('C',42.5,shoulder_z,4,3),('D',80,165,-5,-7)]:
        text(222+u+dx,20+z+dy,letter,8,TEAL,'center',background=True)
    text(319,257,'高度对照 / mm',11,TEAL)
    text(319,248,'测点',8,MUTED)
    text(374,248,'含脚垫',8,MUTED,'center')
    text(398,248,'不含脚垫',8,MUTED,'center')
    for i,(label,z) in enumerate([('A 前斜面起点',165),('B/C 肩部最高处',shoulder_z),
                                ('D 后斜面端点',165),('提手顶 / 整机总高',handle_top)]):
        yy=244-i*10
        if i%2==0:
            c.setFillColor(HexColor('#f1f6f6'));c.rect(317*mm,(yy-8)*mm,91*mm,10*mm,fill=1,stroke=0)
        text(319,yy-4,label,8)
        text(374,yy-4,f"{z-side['foot_bottom_z']:.2f}",9,TEAL,'center')
        text(398,yy-4,f"{z-side['shell_bottom_z']:.2f}",9,TEAL,'center')
    table(317,199,91,[
        ('整机宽 / 深','142 / 80'),
        ('提手净开口 / 厚','90 × 24 / 5'),
        ('格栅中心 X / Z','0 / 76'),
        ('圆孔 / 护网内凹','Ø130 / 2.5'),
        ('前板 / 斜板 / 护网厚','5 / 5 / 2.5'),
        ('侧开口中心 Y / Z','40 / 80'),
        ('侧饰片宽 / 高','12 / 56'),
        ('脚垫','4 × Ø8 × 3'),
        ('前斜面水平 / 高差','37.5 / 26.645'),
        ('前斜面与水平夹角',f"{side['front_angle_deg']:.2f}°"),
        ('后斜面水平 / 高差','37.5 / 26.645'),
        ('后斜面与水平夹角',f"{side['rear_angle_deg']:.2f}°"),
        ('提手高 / 上下横梁','45 / 10.5'),
        ('提手顶外角 / 前棱','R4 / R1.6'),
    ],split=44,height=8)
    notes(319,78,[
        '尺寸线以脚垫底面 Z=0 为基准。',
        '不含脚垫高度从外壳底面 Z=3 量起。',
        '两种总高均包含提手；未计脚垫受压。',
        'X 向右、Y 向后、Z 向上；中心面 X=0。',
        '侧孔竖直轴与提手中线同为 Y=40。',
        '底片 Ø136；圆口边缘自然遮挡孔阵。',
        '尺寸为 CAD 名义值，未定义制造公差。',
        '请勿按图量取或直接投产。',
    ],gap=7,size=8)
    c.showPage()

    page(2,'顶面、背面与操控开孔','碟口尺寸按水平投影；操控开孔按前斜面真形','顶 / 背视图 1:1；开孔详图 1:1')
    view('top',34,168)
    text(105,259,'顶视 · 沿 -Z 观察',10,MUTED,'center')
    dh(34,176,248,253,'142')
    dv(168,248,176,190,'80')
    # Slot extremes are X=-62...62, Y=66.15...69.35.
    dh(43,167,237.35,224,'124 碟口水平长度')
    line(167,235.75,201,240,TEAL,.16); text(201,242,'宽 3.2',9,TEAL)
    line(105,168,105,248,LIGHT,.15,[5,2,1,2])
    text(34,156,'碟口中心 Y=67.75；提手后表面 Y=42.5。',10)
    text(34,148,'120 × 1.2 光盘扫掠距提手后表面 24.65。',9,MUTED)
    view('rear',247,20)
    text(318,263,'背视 · 沿 -Y 观察',10,MUTED,'center')
    text(34,142,'背锁：后壁下方两孔与后斜面两孔，从背面锁紧前壳。',8,TEAL)
    # Drawing cutouts share the actual inclined-plane frame.
    p=view('control-cutouts',40,97)
    centers=data['features']['control_cut_centers_xz']
    text(34,134,'前斜面开孔真形 · 朝斜面法向观察',11,TEAL)
    keys=[p(u,v) for u,v in centers if u<0]
    bottom=sorted(keys,key=lambda q:(q[1],q[0]))[:2]
    dh(bottom[0][0],bottom[1][0],bottom[0][1],86,'18 键距')
    left=sorted(keys,key=lambda q:q[0])[:2]
    dv(min(q[1] for q in left),max(q[1] for q in left),left[0][0],29,'20.85')
    notes(34,74,[
        '四键孔 Ø10.5；键帽 Ø10，露出 1.2；背面止退沿 Ø12.8。',
        '橙白双色键帽：白色符号深 0.6，与键面齐平；分别指定两种 PLA Lite。',
        'OLED 外口 32.82 × 18.1，倒角深 0.8；玻璃内退 1.0，详见第 6 页。',
        '旋钮轴孔 Ø8.8；旋钮外径 Ø23.6，高 8.2（沿法向）。',
        '键中心 X=-59 / -41、Y=9 / 26；屏与旋钮 Y=18、X=0 / 48。',
        '前壳背锁：后壁 X=±67.4、Z=18；后斜面 X=±29、Z=179。',
        'P3 支架：4 孔，X=±64、Z=27 / 124；Ø2.8，沉头 Ø4.8。',
        '侧孔饰片四点连接：筋 2×3，饰片厚 2；短管与声腔轴向留隙 0.3。',
        '背锁孔 Ø4.4／通孔 Ø2.2／盲底孔 Ø1.6；下孔深 65.8，名义螺钉 2×8。',
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
    for panel,name,title in [(12,'exploded-shell','结构层 · 01–08'),(214,'exploded-core','内部层 · A–L')]:
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
        '左图覆盖 32 个成品对象，08 为硬件总成；右图展开 P3 支架和 19 个硬件对象，共 12 组。三个主体均为单一连续实体。',
        '引线端点为组包络中心；展示位移不是拆装路径。侧孔已并入后壳，拆装顺序及检查边界见第 5 页；颜色不代表实物材料。',
    ],gap=7,size=8)
    c.showPage()

    page(4,'侧剖与内部空间','截面 X=-26：穿过左喇叭中心，保留 -X 半体，沿 -X 观察','剖视 1:1；表格为模型读数')
    view('section',38,20)
    text(75,263,'A-A 侧剖',11,TEAL,'center')
    dh(46,88,96,129,'42 喇叭总深度')
    dh(101,110.5,154,206,'9.5 光驱厚度')
    dv(56,136,38,25,'80 单元高度')
    dh(44,114,28,18,'70 电池深度')
    dv(28,48,44,32,'20')
    text(77,36,'5600 mAh',8,white,'center')
    text(130,253,'主要包络 / 关键净距',12,TEAL)
    table(128,246,280,[
        ('单只喇叭 X × Y × Z','45 × 42 × 80；中心 X=±26，Z=76；总包络，安装面待测'),
        ('双喇叭中心距','52；两只均朝 -Y，不代表声道分离或声学验收'),
        ('单侧后腔外包络','65 × 52 × 89；容积、调谐、气密及振膜行程待验证'),
        ('喇叭后方至腔体内壁','4.5（Y=50 至 Y=54.5）；不是插头或导线预留验证'),
        ('UJ-898 光驱','128 × 9.5 × 129；Y=63…72.5，Z=32…161'),
        ('光驱 / 一体导轨侧隙','左右各 0.3；导轨并入 P2 后壳，光驱从前方侧转装入'),
        ('桥接器占位','10 × 24 × 24；X=-61…-51，Y=8…32，Z=124…148'),
        ('功放 PCB / 元件预留','66 × 53 × 1.6 / 15；组件最高 Z=139.6'),
        ('主控 PCB / 元件预留','63.39 × 27.94 × 1.6 / 7；组件最高 Z=157.3'),
        ('DAC PCB / 元件预留','31 × 17 × 1.6 / 7；侧立，长边沿 Z'),
        ('OLED PCB 局部尺寸','35.4 × 33.5 × 1.2；四孔 Ø3，孔距 30.4 × 28.5；图纸值'),
        ('5600 mAh 平排电池','112 × 70 × 20；X=±56，Y=6…76，Z=8…28'),
        ('电池周围名义净距','距后腔底 3.5；前 / 后内壁各 1；托盘侧壁各 1'),
        ('脚垫中心','X=±55；Y=11 / 69；4 个脚垫为一个 CAD 复合对象'),
    ],split=69,height=9.5)
    notes(130,99,[
        '当前模型边界',
        '平排电池按商品标称包络；托盘并入后壳，预留 4 个绑带槽，绑带、线材及插头需实测。',
        '电池名义包络已适配；充电及稳压板尚未纳入模型，整机电气与实物装配仍未验收。',
        '喇叭未建盆架、磁铁和安装孔；显示内容为示意，电子板元件与接头高度含设计预留。',
        '剖图使用实际实体裁切、隐藏线消除；未施加材料剖面线，不能由线型判断材质。',
        '三个主体及拆装路径已做 CAD 检查、PLA 切片；仍需配合试片、螺钉试装、强度和走线实测。',
        '侧饰片已加厚为 2 mm，四处 2×3 连接筋；净通流面积约 384 mm²，尚未完成声学调谐。',
    ],gap=8,size=9)
    c.showPage()

    page(5,'对象清单、打印与拆装','32 个成品对象 · 尺寸为装配坐标系 X × Y × Z 的轴对齐包络，非展开尺寸','清单尺寸 mm；无制造数量承诺')
    labels={
        'FrontShell':'P1 前壳 / 提手 / 格栅 / 屏幕座',
        'RearShell':'P2 一体后壳 / 碟口 / 导音孔及饰片 / 底架',
        'SpeakerCarrier':'P3 双声腔 / 前障板 / 电子托架',
        'Cowl':'前壳 / 提手','LPanel':'左侧壳','RPanel':'右侧壳','LPort':'左导音孔 / 饰片','RPort':'右导音孔 / 饰片',
        'FrontBezel':'中央格栅压圈','FrontGrille':'通孔护网','Back':'后盖','Base':'底架 / 下固定座','Feet':'脚垫复合件（4 个）',
        'Window':'OLED 玻璃面板','StatusArt':'显示内容示意','PlayPauseKey':'播放／暂停键帽','EjectKey':'退碟键帽','PrevKey':'上一曲键帽','NextKey':'下一曲键帽',
        'ButtonRetainer':'四键焊线支架（两侧敞开／双点支承）',
        'DisplayRetainer':'OLED 可拆压框（四点承压／两侧锁紧）',
        'PlayPauseSwitch':'播放／暂停开关包络','EjectSwitch':'退碟开关包络','PrevSwitch':'上一曲开关包络','NextSwitch':'下一曲开关包络','Knob':'音量旋钮',
        'LChamber':'左后腔','RChamber':'右后腔','LDriverFrame':'左喇叭预留框','RDriverFrame':'右喇叭预留框',
        'FrontBaffle':'双开口前障板','RearTopMount':'上固定耳（2 个）','DriveCarrier':'光驱底托 / 导轨','SlotGuide':'碟口导向框',
        'DisplayCarrier':'屏幕安装座','AmpShelf':'功放 / 桥接器托板','ElectronicsSled':'主控托板','AmpPads':'功放支撑复合件',
        'MCUPads':'主控支撑复合件','DACPads':'DAC 支撑复合件','BatteryCradle':'平排电池托盘',
        'LDriver':'左喇叭总包络','RDriver':'右喇叭总包络','Encoder':'电位器轴预留','VolumePot':'电位器本体预留',
        'Drive':'UJ-898 包络','Bridge':'桥接器转向占位','DisplayPCB':'OLED PCB／四孔与缺口','DisplayHeader':'OLED 弯针接头预留',
        'Amp':'功放 PCB','AmpChip':'功放元件预留','MCU':'主控 PCB','MCUChip':'主控元件预留','DAC':'DAC PCB',
        'DACChip':'DAC 元件预留','Battery':'5600 mAh 平排电池',
    }
    membership={n:part['number'] for key in ('exploded-shell','exploded-core')
                for part in data['views'][key]['parts'] if part['number']!='08' for n in part['objects']}
    items=list(data['objects'].items())
    def fmt(n): return f'{n:.2f}'.rstrip('0').rstrip('.')
    for col in range(2):
        x=12+201*col
        text(x,257,'图号 · 对象 ID / 名称',10,TEAL)
        text(x+195,257,'X × Y × Z',10,TEAL,'right')
        for i,(name,obj) in enumerate(items[col*17:(col+1)*17]):
            y=250-i*6.6
            if i%2==0:
                c.setFillColor(HexColor('#f1f6f6'));c.rect(x*mm,(y-6.2)*mm,195*mm,6.6*mm,fill=1,stroke=0)
            text(x+1,y-1.8,f'{membership[name]}  {name}',7)
            text(x+1,y-4.8,labels[name],7,MUTED)
            text(x+193,y-3.5,' × '.join(fmt(n) for n in obj['size']),7.5,INK,'right')
    text(12,127,'PLA 打印：3 主体（侧孔并入后壳）+ 4 键帽 + 焊线支架 + 旋钮 + OLED 压框 = 10 件',11,TEAL)
    printing=json.loads((ROOT/'print-checks.json').read_text())
    assert evidence_matches_geometry(printing,['FrontShell','RearShell','SpeakerCarrier']),'Main-body print geometry differs'
    keys=json.loads((ROOT/'dual-color-key-checks.json').read_text())
    assert evidence_matches_geometry(keys,['PlayPauseKey','EjectKey','PrevKey','NextKey']) and keys['slicing']['exit_code']==0
    text(12,118,'用户设备 P2SC · 按 P2S 配置 / 256³ 空间 / 0.4 喷嘴 / 0.20 层高 / 3 壁 / 15% 填充 / 树状支撑',9)
    for i,(name,label,pose) in enumerate([
        ('FrontShell','P1 前壳','正面朝下 / 板内转 90°'),('RearShell','P2 后壳','背面朝下'),
        ('SpeakerCarrier','P3 支架','声腔背面朝下')]):
        part=printing['parts'][name];plate=printing['plates'][name]
        size=' × '.join(fmt(n) for n in part['size_xyz_mm'])
        text(14,106-i*9,f"{label}  ·  {pose}  ·  打印包络 {size} mm  ·  切片估重 {plate['filament_g']:.1f} g（含支撑）",9)
    notes(14,72,[
        '拆卸：从后壁与后斜面深孔取出 4 螺钉，断开操控线，前壳向前退出。',
        '支架拆卸前断线并卸 4 螺钉；左右侧孔随后壳保持固定；支架向前抽出，光驱先前移 11.5，再侧转 -30°并前移 15.75 后抽出。',
        '电池松开绑带并断线后向前取出；装配按反向顺序，无独立侧孔装配步骤。',
        '前壳路径按 1 mm 抽样；光驱转动按 0.5° 抽样，平移及其余路径连续保守扫掠。实物未验收。',
        '四键双色：0.4 喷嘴 / 0.12 层高；白色 0.6 深；使用双色 3MF。实际色彩、配合与按压行程待测。',
    ],gap=7,size=8.5)
    text(12,27,'FCStd SHA-256: '+data['sha256'],8,MUTED)
    text(408,27,'来源：Discora.FCStd / build.FCMacro / drawings/geometry.json',8,MUTED,'right')
    c.showPage()

    page(6,'OLED 沉槽与可拆压框','依据供应商结构图；玻璃面向外移 4.4；沉槽、倒角与压框来自保存 CAD；有效区虚线标注','模组正视 4:1；安装中剖 3:1')
    oled=json.loads((ROOT/'oled-checks.json').read_text())
    assert evidence_matches_geometry(oled,['FrontShell','Window','DisplayPCB','DisplayHeader','DisplayRetainer']) and oled['all_pass']
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
        '先卸前壳、断线；取下两螺钉和压框，',
        '再沿内法向取出模组；两步均按0.5采样。',
    ],gap=7,size=8.5)
    notes(38,49,[
        '尺寸来源：oled-module-dimensions-wiring.webp。沉槽、倒角、定位柱和压框为外壳设计值。',
        '接头塑壳截面、插线和工具包络是设计预留；线材弯折、实际螺钉、打印孔补偿及装配配合仍须实测。',
        'Window 表示 OLED 自带玻璃面板；本版没有另设透明保护窗片。正前方及选定斜视方向无遮挡；不代表面板光学、密封或实物验收。',
    ],gap=7,size=8.5)
    c.showPage()

    c.save()
    print('PDF_OK',args.output)


if __name__=='__main__':
    main()
