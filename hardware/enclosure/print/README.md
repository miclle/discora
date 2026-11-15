# Discora 正式打印套件

本轮取消电池下方 2 mm 托台，电池直接落在原 5 mm 底板上，Z=6…26；左右挡板及四处绑带槽保留。P3 的实体和位置、整机 94.7 mm 深度保持。只更新 P2 打印文件，其余 10 个 STL／5 盘 3MF 保留，见 [ADR-0050](../../../docs/decisions/0050-battery-direct-floor.md)。

孔网沿用上一版下沉 1.5 mm 设计，仅两个喇叭投影区减薄至 1.2 mm，其余保留 2.5 mm，无新增背筋。已打印 P3 的实体及打印文件保持，此前整件后移 1.7 mm，P2 加深至 94.7 mm，安装座、出口、光驱和后壁接口同步后移，使振膜名义静态净距达到 3 mm。P1、P2 需要使用本轮配套文件，整机竖直高度和前部操控保持。见 [ADR-0049](../../../docs/decisions/0049-speaker-diaphragm-clearance.md)。

当前操控布局为 ADR-0047（四键外移、28 mm旋钮）。主体配套版本：ADR-0046 P3 + ADR-0049 P1 + ADR-0050 P2；保留 ADR-0048 P2 左下双充电口（从正面看：上 Type-C、下 DC；中心距 12 mm、距底边 23／11 mm；圆筒／矮矩形套座内伸 5 mm，连同后壁总支撑 10 mm），来源为上一级 `Discora.FCStd`。11 件刚性 PLA 零件、11 个单色包络 STL、6 个带切片的 Bambu Studio 3MF。完整件实物验收待完成；已通过喇叭安装座试片装配。

| 打印盘 | 推荐打开的项目 | 预计耗材 |
| --- | --- | --- |
| P1 前壳 | [Discora-P1-FrontShell.3mf](Discora-P1-FrontShell.3mf) | 145.33 g |
| P2 后壳 | [Discora-P2-RearShell.3mf](Discora-P2-RearShell.3mf) | 290.32 g |
| P3 喇叭支架 | [Discora-P3-SpeakerCarrier.3mf](Discora-P3-SpeakerCarrier.3mf) | 181.00 g |
| 三个压框／支架 | [Discora-Retainers.3mf](Discora-Retainers.3mf) | 6.61 g |
| 四个橙白双色按键 | [Discora-Keys-Orange-White.3mf](Discora-Keys-Orange-White.3mf) | 7.54 g |
| 黑白双色旋钮 | [Discora-Knob-Black-White.3mf](Discora-Knob-Black-White.3mf) | 9.82 g |

P1 开启“仅打印板支撑”、关闭“仅关键区域”；P2 两项均关闭，P3 两项均开启。P2 的 DC 孔内树状支撑须清理；Type-C 孔内未检测到支撑走线，两孔均检查贯通后再装母座。保持 3MF 保存姿态和支撑参数；四键与旋钮保留为双色对象，按实际 AMS 槽位映射材料。

STL 供其它切片器使用；四键和旋钮的单色 STL 不包含颜色分区。脚垫、电子模块、玻璃和紧固件另购。

[完整打印与装配说明](../../../docs/enclosure-printing.md) · [14 页装配图册](../drawings/Discora-V4-drawing-book-color.pdf) · [文件清单和 SHA-256](manifest.json) · [读回检查](../print-release-checks.json)
