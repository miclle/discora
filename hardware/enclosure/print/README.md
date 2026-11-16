# Discora 正式打印套件

本轮按现有螺丝更新 P1、P2、四键压板、OLED 压框和光驱压条，新增 4 片 P3 平垫圈。已打印 P3 及其喇叭、整机 94.7 mm 深度、3 mm 振膜静态净距、电池下 1.5 mm 双面胶和封闭底板保持。见 [ADR-0052](../../../docs/decisions/0052-stock-fasteners.md)。

P2 当前采用 **0.16 mm 层高／首层 0.20 mm／0.4 mm 喷嘴**，预计 **10h 3m 57s、290.77 g**，560 层支撑检查通过。P1 与小件盘也已更新；P3、双色键帽及旋钮三盘保持原文件。

此前恢复用户已购、尺寸已确认的裸 B50K 带开关电位器，更新 P1 内侧辅助防转槽及引脚、焊点和出线预留。最新洞洞板布局、已打印 P3 的实体和位置、P2、电池落底及整机 94.7 mm 深度保持。只有 P3 已打印；该次只更新 P1 STL／3MF，其余 10 件 STL、5 盘 3MF 保持。见 [ADR-0051](../../../docs/decisions/0051-bare-b50k-solder-clearance.md)。

孔网沿用上一版下沉 1.5 mm 设计，仅两个喇叭投影区减薄至 1.2 mm，其余保留 2.5 mm，无新增背筋。已打印 P3 的实体及打印文件保持，此前整件后移 1.7 mm，P2 加深至 94.7 mm，安装座、出口、光驱和后壁接口同步后移，使振膜名义静态净距达到 3 mm。P1、P2 需要使用本轮配套文件，整机竖直高度和前部操控保持。见 [ADR-0049](../../../docs/decisions/0049-speaker-diaphragm-clearance.md)。

当前操控布局为 ADR-0047（四键外移、28 mm旋钮）。主体配套版本：ADR-0046 P3 + ADR-0052 P1/P2/小件；保留 ADR-0048 P2 左下双充电口（从正面看：上 Type-C、下 DC；中心距 12 mm、距底边 23／11 mm；圆筒／矮矩形套座内伸 5 mm，连同后壁总支撑 10 mm），来源为上一级 `Discora.FCStd`。15 件刚性 PLA 零件、12 个单色包络 STL、6 个带切片的 Bambu Studio 3MF。P3 已打印且喇叭已固定，整机装配和强度待验收。

| 打印盘 | 推荐打开的项目 | 预计耗材 |
| --- | --- | --- |
| P1 前壳 | [Discora-P1-FrontShell.3mf](Discora-P1-FrontShell.3mf) | 147.36 g |
| P2 后壳 | [Discora-P2-RearShell.3mf](Discora-P2-RearShell.3mf) | 290.77 g |
| P3 喇叭支架 | [Discora-P3-SpeakerCarrier.3mf](Discora-P3-SpeakerCarrier.3mf) | 181.00 g |
| 三件压框／压条及四片垫圈 | [Discora-Retainers.3mf](Discora-Retainers.3mf) | 7.37 g |
| 四个橙白双色按键 | [Discora-Keys-Orange-White.3mf](Discora-Keys-Orange-White.3mf) | 7.54 g |
| 黑白双色旋钮 | [Discora-Knob-Black-White.3mf](Discora-Knob-Black-White.3mf) | 9.82 g |

P1 开启“仅打印板支撑”、关闭“仅关键区域”；P2 两项均关闭，P3 两项均开启。P2 的 DC 孔内树状支撑须清理；Type-C 孔内未检测到支撑走线，两孔均检查贯通后再装母座。保持 3MF 保存姿态和支撑参数；四键与旋钮保留为双色对象，按实际 AMS 槽位映射材料。

STL 供其它切片器使用；四键和旋钮的单色 STL 不包含颜色分区。脚垫、电子模块、玻璃和紧固件另购。

[完整打印与装配说明](../../../docs/enclosure-printing.md) · [14 页装配图册](../drawings/Discora-V4-drawing-book-color.pdf) · [文件清单和 SHA-256](manifest.json) · [读回检查](../print-release-checks.json)
