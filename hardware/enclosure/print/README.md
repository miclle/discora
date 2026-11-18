# Discora 正式打印套件

## 剩余两盘：P1 与逐件操控件

用户已确认 **P3 和 P2 整合盘的 8 件零件打印完成**。剩余 6 件使用下列两盘，均为 **P2S、0.4 mm 喷嘴、纹理 PEI 板，首层与后续层热床 55°C**：

| 打印盘 | 正式 3MF | 层高／首层 | 配色 | 预计时间／耗材 |
| --- | --- | --- | --- | --- |
| P1 前壳 | [Discora-P1-FrontShell.3mf](Discora-P1-FrontShell.3mf) | 0.16／0.20 mm | 橙色 | 14h 21m 45s／177.39 g |
| 旋钮＋四键组 | [Discora-Controls-Sequential.3mf](Discora-Controls-Sequential.3mf) | 0.12／0.12 mm | 黑白旋钮、橙白按键 | 1h 0m 26s／13.13 g |

两盘合计约 **15h 22m 11s、190.52 g**。预设采用橙／白 Bambu PLA Lite、黑 Bambu PLA Basic；AMS 按实际槽位对应橙、白、黑。P1 不换色；操控件盘共 11 次换色。小件盘**先打印旋钮，再打印四键组**，四键在同一组内按层一起打印；这只是切片分组，仍得到四个独立按键。保持保存的摆放、分组和“逐件打印”顺序，不要自动重排。

P1 共 306 层，小件盘为旋钮 116 层＋四键组 60 层，已核对保存网格、孔网支撑、五处白色标记和实际低位轨迹。已完成旋钮及其底边到第二组低位轨迹约 119.8 mm，超过 72 mm 打印头包络约 47.8 mm。旋钮轴孔顶面保留原约 5.3 mm 的双端短桥接，不添加孔内支撑。P1 支撑从孔网正面开放侧清理；实物表面质量、支撑拆除和装配仍待确认。

操控件盘替代下方的独立按键盘和独立旋钮盘，**不要重复打印**。CAD、零件几何及全部 STL 保持不变。

[两盘读回与逐层检查](../remaining-print-checks.json) · [P1 关键层](../remaining-front-toolpaths.png) · [逐件顺序与实际配色走线](../remaining-controls-toolpaths.png)

复现：用 FreeCAD Python 执行 `slice-remaining-prints.py --work <工作目录>`，随后执行 `check-remaining-prints.py --work <工作目录>`；脚本位于上一级目录，不发送打印任务。

## P2 与小件整合盘

准备打印 P2 时，可直接打开 [Discora-P2-Combined.3mf](Discora-P2-Combined.3mf)：同盘包含 **P2 后壳 ×1、四键压板 ×1、OLED 压框 ×1、光驱压条 ×1、P3 平垫圈 ×4，共 8 件**。各件仍为独立对象，几何和原打印朝向保持，只调整板面位置。全部使用与 P2 相同的单色 PLA，保持 P2S／0.4 mm 喷嘴、0.16 mm 层高、首层 0.20 mm，按层打印。 已按实际使用的 **纹理 PEI 板（Textured PEI Plate）**重新切片，首层和后续层热床均为 **55°C**。

预计 **10h 30m 46s、298.24 g**；原 P2 与小件两盘合计 10h 35m 35s，整合后少约 5 分钟、少一次换盘。此盘**替代下表中的 P2 后壳盘和小件盘，不要重复打印**。双色键帽与旋钮不加入 P2 盘，当前使用上方的操控件逐件盘。

560 层切片检查及保存后网格读回通过；8 件均落板，无新增孤岛，四片垫圈无支撑。P2 的 DC 孔内树状支撑仍须清理，OLED 压框下方支撑从开放侧移除。用户已确认该整合盘打印完成；拆支撑与整机装配尚待确认。该次合盘保持正式 CAD、12 个 STL 和原独立盘不变；P1 随后按上方配置更新。

[整合盘检查及文件 SHA-256](../p2-combined-print-checks.json) · [实际走线关键层预览](../p2-combined-toolpaths.png)

复现：在 FreeCAD Python 环境运行 `export-p2-combined.py --output <工作目录>/meshes`，用系统 Python 运行 `slice-p2-combined.py --work <工作目录>`，再用 FreeCAD Python 运行 `check-p2-combined.py --work <工作目录>`。脚本位于上一级目录，切片结果包含 G-code，不向打印机发送任务。

## 独立打印盘（备用拆分方案）

本轮按现有螺丝更新 P1、P2、四键压板、OLED 压框和光驱压条，新增 4 片 P3 平垫圈。已打印 P3 及其喇叭、整机 94.7 mm 深度、3 mm 振膜静态净距、电池下 1.5 mm 双面胶和封闭底板保持。见 [ADR-0052](../../../docs/decisions/0052-stock-fasteners.md)。

P2 当前采用 **0.16 mm 层高／首层 0.20 mm／0.4 mm 喷嘴**，预计 **10h 3m 57s、290.77 g**，560 层支撑检查通过。P1 与小件盘也已更新；P3、双色键帽及旋钮三盘保持原文件。

此前恢复用户已购、尺寸已确认的裸 B50K 带开关电位器，更新 P1 内侧辅助防转槽及引脚、焊点和出线预留。最新洞洞板布局、已打印 P3 的实体和位置、P2、电池落底及整机 94.7 mm 深度保持。当时只有 P3 已打印；该次只更新 P1 STL／3MF，其余 10 件 STL、5 盘 3MF 保持。见 [ADR-0051](../../../docs/decisions/0051-bare-b50k-solder-clearance.md)。

孔网沿用上一版下沉 1.5 mm 设计，仅两个喇叭投影区减薄至 1.2 mm，其余保留 2.5 mm，无新增背筋。已打印 P3 的实体及打印文件保持，此前整件后移 1.7 mm，P2 加深至 94.7 mm，安装座、出口、光驱和后壁接口同步后移，使振膜名义静态净距达到 3 mm。P1、P2 需要使用本轮配套文件，整机竖直高度和前部操控保持。见 [ADR-0049](../../../docs/decisions/0049-speaker-diaphragm-clearance.md)。

当前操控布局为 ADR-0047（四键外移、28 mm旋钮）。主体配套版本：ADR-0046 P3 + ADR-0052 P1/P2/小件；保留 ADR-0048 P2 左下双充电口（从正面看：上 Type-C、下 DC；中心距 12 mm、距底边 23／11 mm；圆筒／矮矩形套座内伸 5 mm，连同后壁总支撑 10 mm），来源为上一级 `Discora.FCStd`。15 件刚性 PLA 零件、12 个单色包络 STL、6 个带切片的 Bambu Studio 3MF。P3 已打印且喇叭已固定，整机装配和强度待验收。

| 打印盘 | 推荐打开的项目 | 预计耗材 |
| --- | --- | --- |
| P1 前壳 | [Discora-P1-FrontShell.3mf](Discora-P1-FrontShell.3mf) | 177.39 g |
| P2 后壳 | [Discora-P2-RearShell.3mf](Discora-P2-RearShell.3mf) | 290.77 g |
| P3 喇叭支架 | [Discora-P3-SpeakerCarrier.3mf](Discora-P3-SpeakerCarrier.3mf) | 181.00 g |
| 三件压框／压条及四片垫圈 | [Discora-Retainers.3mf](Discora-Retainers.3mf) | 7.37 g |
| 四个橙白双色按键 | [Discora-Keys-Orange-White.3mf](Discora-Keys-Orange-White.3mf) | 7.54 g |
| 黑白双色旋钮 | [Discora-Knob-Black-White.3mf](Discora-Knob-Black-White.3mf) | 9.82 g |

P1 开启“仅打印板支撑”、关闭“仅关键区域”；P2 两项均关闭，P3 两项均开启。P2 的 DC 孔内树状支撑须清理；Type-C 孔内未检测到支撑走线，两孔均检查贯通后再装母座。保持 3MF 保存姿态和支撑参数；四键与旋钮保留为双色对象，按实际 AMS 槽位映射材料。

STL 供其它切片器使用；四键和旋钮的单色 STL 不包含颜色分区。脚垫、电子模块、玻璃和紧固件另购。

[完整打印与装配说明](../../../docs/enclosure-printing.md) · [14 页装配图册](../drawings/Discora-V4-drawing-book-color.pdf) · [文件清单和 SHA-256](manifest.json) · [读回检查](../print-release-checks.json)
