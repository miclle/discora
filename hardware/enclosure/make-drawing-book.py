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
ANNOTATED_MODEL_SHA256 = '150eeae75876a5ee5902df73d2a976904b093a151b048de0ccc697d6eaba24ad'
INK = HexColor('#182c35')
TEAL = HexColor('#087f82')
MUTED = HexColor('#536972')
LIGHT = HexColor('#d5e1e4')
TOTAL_PAGES = 5


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
        text(408,10,f'DC-V4-GA-{num:02d}  ·  2026-11-05  ·  {num}/{TOTAL_PAGES}',8,MUTED,'right')

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
    view('front',35,36)
    view('right',222,36)
    text(106,258,'正视 · 沿 +Y 观察',10,MUTED,'center')
    text(259,258,'右视 · 沿 -X 观察',10,MUTED,'center')
    dh(35,177,36,25,'142')
    dv(36,238,35,23,'202（含脚垫和提手）')
    dh(222,296,36,25,'74')
    dh(61,151,233.5,247,'90 净开口')
    dv(217.5,233.5,151,164,'16')
    dv(36,112,177,191,'76 格栅中心高')
    line(106,42,106,241,LIGHT,.15,[5,2,1,2])
    line(39,112,173,112,LIGHT,.15,[5,2,1,2])
    c.setFillColor(white); c.rect(86*mm,107*mm,40*mm,10*mm,fill=1,stroke=0)
    text(106,110,'Ø130 壳体开口',10,TEAL,'center')
    dv(79,153,281,286,'74 侧开口')
    dh(251.5,280.5,116,169,'29')
    # Side dimensions use foot-bottom Z=0; paired body-bottom values are adjacent.
    for z,edge,x,label in [(150,222,211,'150'),(177,260,200,'177'),(165,296,308,'165')]:
        dv(36,36+z,edge,x,label)
    dh(222,260,213,247,'38')
    dh(265,296,213,247,'31')
    line(218,36,312,36,MUTED,.15,[4,2])
    line(218,39,298,39,LIGHT,.15,[2,2])
    for letter,u,z,dx,dy in [('A',0,150,3,-7),('B',38,177,-5,3),
                              ('C',43,177,4,3),('D',74,165,-5,-7)]:
        text(222+u+dx,36+z+dy,letter,8,TEAL,'center',background=True)
    text(319,257,'高度对照 / mm',11,TEAL)
    text(319,248,'测点',8,MUTED)
    text(374,248,'含脚垫',8,MUTED,'center')
    text(398,248,'不含脚垫',8,MUTED,'center')
    for i,(label,z) in enumerate([('A 前斜面起点',150),('B/C 肩部最高处',177),
                                ('D 后斜面端点',165),('提手顶 / 整机总高',202)]):
        yy=244-i*10
        if i%2==0:
            c.setFillColor(HexColor('#f1f6f6'));c.rect(317*mm,(yy-8)*mm,91*mm,10*mm,fill=1,stroke=0)
        text(319,yy-4,label,8)
        text(374,yy-4,f"{z-side['foot_bottom_z']:g}",9,TEAL,'center')
        text(398,yy-4,f"{z-side['shell_bottom_z']:g}",9,TEAL,'center')
    table(317,199,91,[
        ('整机宽 / 深','142 / 74'),
        ('提手净开口 / 厚','90 × 16 / 5'),
        ('格栅中心 X / Z','0 / 76'),
        ('压圈 / 护网外径','Ø129.6 / Ø126.4'),
        ('护网厚 / 孔径','1.2 / Ø1.88'),
        ('侧开口中心 Y / Z','44 / 80'),
        ('侧饰片宽 / 高','12 / 56'),
        ('脚垫','4 × Ø8 × 3'),
        ('前斜面水平 / 高差','38 / 27'),
        ('前斜面与水平夹角',f"{side['front_angle_deg']:.2f}°"),
        ('后斜面水平 / 高差','31 / 12'),
        ('后斜面与水平夹角',f"{side['rear_angle_deg']:.2f}°"),
        ('提手高于肩部','25'),
        ('提手顶外角 / 前棱','R4 / R1.6'),
    ],split=44,height=8)
    notes(319,78,[
        '尺寸线以脚垫底面 Z=0 为基准。',
        '不含脚垫高度从外壳底面 Z=3 量起。',
        '两种总高均包含提手；未计脚垫受压。',
        'X 向右、Y 向后、Z 向上；中心面 X=0。',
        '外壳及声学结构左右镜像，',
        '既有按钮、旋钮布局为例外。',
        '尺寸为 CAD 名义值，未定义制造公差。',
        '请勿按图量取或直接投产。',
    ],gap=7,size=8)
    c.showPage()

    page(2,'顶面、背面与操控开孔','碟口尺寸按水平投影；操控开孔按前斜面真形','顶 / 背视图 1:1；开孔详图 1:1')
    view('top',34,168)
    text(105,259,'顶视 · 沿 -Z 观察',10,MUTED,'center')
    dh(34,176,242,251,'142')
    dv(168,242,176,190,'74')
    # Slot extremes are X=-62...62, Y=62.4...65.6.
    dh(43,167,233.6,224,'124 碟口水平长度')
    line(167,232,201,240,TEAL,.16); text(201,242,'宽 3.2',9,TEAL)
    line(105,168,105,242,LIGHT,.15,[5,2,1,2])
    text(34,156,'碟口中心 Y=64；提手后表面 Y=43。',10)
    text(34,148,'120 × 1.2 光盘扫掠距提手后表面 20.4。',9,MUTED)
    view('rear',247,36)
    text(318,259,'背视 · 沿 -Y 观察',10,MUTED,'center')
    dh(260,376,193,213,'116 孔中心距')
    dv(46,193,389,400,'147 孔中心距')
    text(247,27,'后盖 142 × 162 × 3；4 × Ø3.4 通孔',10,TEAL)
    for xx in (260,376):
        for yy in (46,193):
            line(xx-4,yy,xx+4,yy,LIGHT,.15,[2,1]);line(xx,yy-4,xx,yy+4,LIGHT,.15,[2,1])
    text(247,248,'孔中心：X=±58；Z=10 / 157',9,MUTED)
    # Drawing cutouts share the actual inclined-plane frame.
    p=view('control-cutouts',40,97)
    y0=data['views']['control-cutouts']['bounds']['min'][1]
    center_v=y0+11.25
    cx=lambda u:p(u,center_v)[0]
    text(34,134,'前斜面开孔真形 · 朝斜面法向观察',11,TEAL)
    for u in (-49,0,48):
        x,y=p(u,center_v)
        line(x,y-14,x,y+15,LIGHT,.15,[3,1])
    dh(cx(-49),cx(0),108.25,86,'49')
    dh(cx(0),cx(48),108.25,86,'48')
    notes(34,74,[
        '播放键孔 Ø22.5；键帽 Ø22，高 1.45（沿法向）。',
        '屏幕开窗 36 × 20，R3；窗片 35.6 × 19.6，R2.8。',
        '旋钮轴孔 Ø8.8；旋钮外径 Ø23.6，高 8.2（沿法向）。',
        '三处中心均位于 Y=18，Z=162.79；X=-49 / 0 / +48。',
        '背面底孔距机身中心线 ±58；孔位为模型设计，紧固件待定。',
        '操控孔与显示窗轮廓来自保存的布尔刀体；实体尺寸见第 5 页。',
    ],gap=8)
    c.showPage()

    page(3,'整机爆炸图 / 外壳与内部','两层展开并排对照 · 相同 CAD 几何与展示位移，编号对应第 5 页对象清单','爆炸图 NTS（非比例装配距离）')
    for i,(color,label) in enumerate([
        ('#16a9a4','外壳 / 支架'),('#4d5155','深色结构 / 单元'),
        ('#bac0c4','光驱 / 银色包络'),('#39775b','PCB'),('#3c6da9','旧电池占位')]):
        sx=14+i*80
        c.setFillColor(HexColor(color));c.rect(sx*mm,258*mm,3*mm,3*mm,fill=1,stroke=0)
        text(sx+5,258.1,label,8,MUTED)
    line(210,38,210,251,LIGHT,.15)
    for panel,name,title in [(12,'exploded-shell','外壳层 · 01–12'),(214,'exploded-core','内部层 · A–N')]:
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
        '左图覆盖 45 个成品对象，12 为内部总成；右图将其中 30 个内部对象分为 14 组。组内子件见第 5 页和 geometry.json。',
        '引线端点为组包络中心；爆炸位移不表示已验证的拆装路径或顺序。沿用 CAD 配色，不代表实物材料；硬件仍含占位与设计预留。',
    ],gap=7,size=8)
    c.showPage()

    page(4,'侧剖与内部空间','截面 X=-26：穿过左喇叭中心，保留 -X 半体，沿 -X 观察','剖视 1:1；表格为模型读数')
    view('section',38,36)
    text(75,258,'A-A 侧剖',11,TEAL,'center')
    dh(44,86,112,145,'42 喇叭总深度')
    dh(97.25,106.75,170,222,'9.5 光驱厚度')
    dv(72,152,38,25,'80 单元高度')
    text(130,253,'主要包络 / 关键净距',12,TEAL)
    table(128,246,280,[
        ('单只喇叭 X × Y × Z','45 × 42 × 80；中心 X=±26，Z=76；总包络，安装面待测'),
        ('双喇叭中心距','52；两只均朝 -Y，不代表声道分离或声学验收'),
        ('单侧后腔外包络','65 × 52 × 89；容积、调谐、气密及振膜行程待验证'),
        ('喇叭后方至腔体内壁','4.5（Y=48 至 Y=52.5）；不是插头或导线预留验证'),
        ('UJ-898 光驱','128 × 9.5 × 129；Y=59.25…68.75，Z=18…147'),
        ('光驱导轨 / 侧壁净距','左右各 1；光驱与现有桥接板的实际连接仍待核实'),
        ('桥接器占位','24 × 24 × 10；Y=38…62，Z=6…16；短转接线未建模'),
        ('功放 PCB / 元件预留','66 × 53 × 1.6 / 15；组件最高 Z=139.6'),
        ('主控 PCB / 元件预留','63.39 × 27.94 × 1.6 / 7；组件最高 Z=158.3'),
        ('DAC PCB / 元件预留','31 × 17 × 1.6 / 7；侧立，长边沿 Z'),
        ('显示 PCB 局部尺寸','38 × 30 × 1.6；并非已核实 OLED 实物安装尺寸'),
        ('旧电池包占位','82 × 21 × 22；Y=6…27，Z=8…30；所选电池不适配'),
        ('旧电池与后腔底部净距','1.5（Z=30 至 Z=31.5）'),
        ('脚垫中心','X=±55；Y=11 / 63；4 个脚垫为一个 CAD 复合对象'),
    ],split=69,height=9.5)
    notes(130,99,[
        '当前模型边界',
        '已选 5600mAh 电池：商家图示块状 58 × 41 × 67，或平排 112 × 70 × 20；',
        '两者均不能直接替代旧占位，充电及稳压板尚未纳入模型。本图不作为新电池装配依据。',
        '喇叭未建盆架、磁铁和安装孔；显示内容为示意，电子板元件与接头高度含设计预留。',
        '剖图使用实际实体裁切、隐藏线消除；未施加材料剖面线，不能由线型判断材质。',
        '尚缺：公差配合、螺钉规格、走线弯折、散热、打印分件、提手强度与实际进退碟验证。',
        '既有 validation.json 与本图使用同一模型摘要；历史静态通过不等于实物或生产验收。',
    ],gap=8,size=9)
    c.showPage()

    page(5,'模型对象清单与版本依据','45 个成品对象 · 尺寸为装配坐标系 X × Y × Z 的轴对齐包络，非展开尺寸','清单尺寸 mm；无制造数量承诺')
    labels={
        'Cowl':'前壳 / 提手','LPanel':'左侧壳','RPanel':'右侧壳','LPort':'左导音孔 / 饰片','RPort':'右导音孔 / 饰片',
        'FrontBezel':'中央格栅压圈','FrontGrille':'通孔护网','Back':'后盖','Base':'底架 / 下固定座','Feet':'脚垫复合件（4 个）',
        'Window':'斜面窗片','StatusArt':'显示内容示意','Keycap':'播放键帽','KeyLight':'键上指示灯','Knob':'音量旋钮',
        'LChamber':'左后腔','RChamber':'右后腔','LDriverFrame':'左喇叭预留框','RDriverFrame':'右喇叭预留框',
        'FrontBaffle':'双开口前障板','RearTopMount':'上固定耳（2 个）','DriveCarrier':'光驱底托 / 导轨','SlotGuide':'碟口导向框',
        'DisplayCarrier':'屏幕安装座','AmpShelf':'功放托板','ElectronicsSled':'主控托板','AmpPads':'功放支撑复合件',
        'MCUPads':'主控支撑复合件','DACPads':'DAC 支撑复合件','BatteryCradle':'旧电池座',
        'LDriver':'左喇叭总包络','RDriver':'右喇叭总包络','Encoder':'电位器轴预留','VolumePot':'电位器本体预留',
        'Drive':'UJ-898 包络','Bridge':'桥接器转向占位','DisplayPCB':'屏幕 PCB 占位','DisplayHeader':'屏幕接头占位',
        'Amp':'功放 PCB','AmpChip':'功放元件预留','MCU':'主控 PCB','MCUChip':'主控元件预留','DAC':'DAC PCB',
        'DACChip':'DAC 元件预留','Battery':'旧电池占位',
    }
    membership={n:part['number'] for key in ('exploded-shell','exploded-core')
                for part in data['views'][key]['parts'] if part['number']!='12' for n in part['objects']}
    items=list(data['objects'].items())
    def fmt(n): return f'{n:.2f}'.rstrip('0').rstrip('.')
    for col in range(2):
        x=12+201*col
        text(x,257,'图号 · 对象 ID / 名称',10,TEAL)
        text(x+195,257,'X × Y × Z',10,TEAL,'right')
        for i,(name,obj) in enumerate(items[col*23:(col+1)*23]):
            y=250-i*8.6
            if i%2==0:
                c.setFillColor(HexColor('#f1f6f6'));c.rect(x*mm,(y-7.8)*mm,195*mm,8.6*mm,fill=1,stroke=0)
            text(x+1,y-2,f'{membership[name]}  {name}',8)
            text(x+1,y-6,labels[name],7.5,MUTED)
            text(x+193,y-4,' × '.join(fmt(n) for n in obj['size']),8,INK,'right')
    text(12,43,'倾斜件的包络不等于自身尺寸：屏窗、屏幕 PCB、旋钮、电位器应结合第 2 / 4 页局部尺寸读取。',9)
    text(12,35,'成品对象数不等于 BOM 数量；Feet / Pads / Mount 等为复合对象，StatusArt 为显示示意，Chip 为高度预留。',9)
    text(12,27,'FCStd SHA-256: '+data['sha256'],8,MUTED)
    text(408,27,'来源：Discora.FCStd / build.FCMacro / drawings/geometry.json',8,MUTED,'right')
    c.showPage()

    c.save()
    print('PDF_OK',args.output)


if __name__=='__main__':
    main()
