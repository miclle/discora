# 正式打印文件与装配

## 剩余两盘：P1 与逐件操控件

用户已确认 **P3 和 P2 整合盘的 8 件零件打印完成**。剩余 6 件使用下列两盘，均为 **P2S、0.4 mm 喷嘴、纹理 PEI 板，首层与后续层热床 55°C**：

| 打印盘 | 正式 3MF | 层高／首层 | 配色 | 预计时间／耗材 |
| --- | --- | --- | --- | --- |
| P1 前壳 | [Discora-P1-FrontShell.3mf](../hardware/enclosure/print/Discora-P1-FrontShell.3mf) | 0.16／0.20 mm | 橙色 | 14h 21m 45s／177.39 g |
| 旋钮＋四键组 | [Discora-Controls-Sequential.3mf](../hardware/enclosure/print/Discora-Controls-Sequential.3mf) | 0.12／0.12 mm | 黑白旋钮、橙白按键 | 1h 0m 26s／13.13 g |

两盘合计约 **15h 22m 11s、190.52 g**。预设采用橙／白 Bambu PLA Lite、黑 Bambu PLA Basic；AMS 按实际槽位对应橙、白、黑。P1 不换色；操控件盘共 11 次换色。小件盘**先打印旋钮，再打印四键组**，四键在同一组内按层一起打印；这只是切片分组，仍得到四个独立按键。保持保存的摆放、分组和“逐件打印”顺序，不要自动重排。

P1 共 306 层，小件盘为旋钮 116 层＋四键组 60 层，已核对保存网格、孔网支撑、五处白色标记和实际低位轨迹。已完成旋钮及其底边到第二组低位轨迹约 119.8 mm，超过 72 mm 打印头包络约 47.8 mm。旋钮轴孔顶面保留原约 5.3 mm 的双端短桥接，不添加孔内支撑。P1 支撑从孔网正面开放侧清理；实物表面质量、支撑拆除和装配仍待确认。

操控件盘替代下方的独立按键盘和独立旋钮盘，**不要重复打印**。CAD、零件几何及全部 STL 保持不变。

[两盘读回与逐层检查](../hardware/enclosure/remaining-print-checks.json) · [P1 关键层](../hardware/enclosure/remaining-front-toolpaths.png) · [逐件顺序与实际配色走线](../hardware/enclosure/remaining-controls-toolpaths.png)

复现：用 FreeCAD Python 执行 `slice-remaining-prints.py --work <工作目录>`，随后执行 `check-remaining-prints.py --work <工作目录>`；脚本位于 `hardware/enclosure/`，不发送打印任务。

## 配套设计背景

本轮按现有螺丝更新 P1、P2、四键压板、OLED 压框和光驱压条，新增 4 片 P3 平垫圈。已打印 P3 及其喇叭、整机 94.7 mm 深度、3 mm 振膜静态净距、电池下 1.5 mm 双面胶和封闭底板保持。见 [ADR-0052](decisions/0052-stock-fasteners.md)。

此前恢复用户已购、尺寸已确认的裸 B50K 带开关电位器，更新 P1 内侧辅助防转槽及引脚、焊点和出线预留。最新洞洞板布局、已打印 P3 的实体和位置、P2、电池落底及整机 94.7 mm 深度保持。当时只有 P3 已打印；该次只更新 P1 STL／3MF，其余 10 件 STL、5 盘 3MF 保持。见 [ADR-0051](decisions/0051-bare-b50k-solder-clearance.md)。

孔网沿用上一版下沉 1.5 mm 设计，仅两个喇叭投影区减薄至 1.2 mm，其余保留 2.5 mm，无新增背筋。已打印 P3 的实体及打印文件保持，此前整件后移 1.7 mm，P2 加深至 94.7 mm，安装座、出口、光驱和后壁接口同步后移，使振膜名义静态净距达到 3 mm。P1、P2 需要使用本轮配套文件，整机竖直高度和前部操控保持。见 [ADR-0049](decisions/0049-speaker-diaphragm-clearance.md)。

当前操控布局为 [ADR-0047](decisions/0047-control-spacing-and-knob.md)，前壳与28 mm旋钮已更新。主体版本：ADR-0046 P3 短渐扩口，配套 ADR-0048 P2 双充电口，保留圆角梯形开放侧口。正式文件统一在 [hardware/enclosure/print](../hardware/enclosure/print/README.md)，不再从历次 `tmp/` 目录选择零件。

这里的“正式版本”指本轮唯一配套交付版本，P1 和操控件打印、完整件支撑拆除、装配、强度、气密和声学仍待实测。**P3 已打印，喇叭已使用 Ø2.8×9.5 螺丝安装**，保留已通过的座面和孔位，不再要求打印试片。

## 六个独立打印盘（备用拆分方案）

| 打印盘 | 3MF | 预计时间 | 耗材 / g | 层数 |
| --- | --- | --- | --- | --- |
| P1 前壳 | [Discora-P1-FrontShell.3mf](../hardware/enclosure/print/Discora-P1-FrontShell.3mf) | 14h 21m 45s | 177.39 | 306 |
| P2 后壳 | [Discora-P2-RearShell.3mf](../hardware/enclosure/print/Discora-P2-RearShell.3mf) | 10h 3m 57s | 290.77 | 560 |
| P3 喇叭支架 | [Discora-P3-SpeakerCarrier.3mf](../hardware/enclosure/print/Discora-P3-SpeakerCarrier.3mf) | 5h 40m 46s | 181.00 | 287 |
| 三件压框／压条及四片垫圈 | [Discora-Retainers.3mf](../hardware/enclosure/print/Discora-Retainers.3mf) | 31m 38s | 7.37 | 33 |
| 四个橙白双色按键 | [Discora-Keys-Orange-White.3mf](../hardware/enclosure/print/Discora-Keys-Orange-White.3mf) | 34m 44s | 7.54 | 60 |
| 黑白双色旋钮 | [Discora-Knob-Black-White.3mf](../hardware/enclosure/print/Discora-Knob-Black-White.3mf) | 49m 28s | 9.82 | 116 |

合计约 **673.89 g**，包含支撑、brim 和双色换料耗材。时间和用量来自 Bambu Studio 2.9.1.70 本地切片，不是实际打印记录。配置为 P2S / 0.4 mm，按用户提供的 P2SC、256³ mm 空间映射；0.2 mm 喷嘴未验证。

15 件刚性 PLA 零件共用 12 个 STL，四片垫圈合在一个 STL 中。四键和旋钮的 STL 仅为单色包络，双色打印优先打开上述 3MF，保留同一对象内的两个材料区域。软脚垫、OLED 玻璃、电子模块、螺钉、双面胶和导线另购，不计入打印件。

## 摆放与支撑

| 打印盘 | 姿态／层高 | 仅在打印板生成支撑 | 仅关键区域 |
| --- | --- | --- | --- |
| P1 | 孔网朝下，长边沿板 X；0.16 mm，首层 0.20 mm | 开 | 关 |
| P2 | 后壁朝下；0.16 mm，首层 0.20 mm | **关** | **关** |
| P3 | 双声腔背面朝下；0.20 mm | **开** | **开** |
| 三件压框／压条及四片垫圈 | 保持项目中各件姿态；0.20 mm | 开 | 开 |
| 四键／旋钮 | 符号面朝上；0.12 mm | 开 | 以各自 3MF 保存设置为准 |

P1 使用橙色 Bambu PLA Lite，其余原单色盘使用 Generic PLA；主体采用 3 层壁、15% gyroid、30° 自动树状支撑、顶部接触间隙 0.20 mm、5 mm 外侧 brim。P1 包络 240.263×170×49 mm，孔网朝下，已保留检查过的摆放；不要使用自动定向重新翻转。P1/P2/P3 的支撑限制不同，不要互相套用。

P3 双背板首层直接贴板；287 层审核未发现声腔、导管或渐扩口内支撑，原 18 条悬空告警对应位置已核对。P2 560 层侧口及开放结构需要支撑，从敞开的正面与侧口清理，实际拆除力待验证。P2 合壳孔座和光驱座适配后重新导出 STL，以 0.16 mm 层高审核全部 560 层；四条合壳工具井内无支撑走线；P3 保留不变实体对应的已审核文件。DC 充电孔内存在可拆树状支撑，Type-C 孔内未检测到支撑走线，须从后侧孔口和敞开内侧清理，10 mm 通道全部贯通后再安装母座。

本轮更新 P1、P2 和三件压框／压条，新增四片垫圈；重新切片 P1、P2、小件三盘。P3、四键和旋钮的 6 个 STL、3 个 3MF 保持原文件。四键每键及旋钮标记各有 5 层白色走线，3MF 对象数、材料分配、网格修复计数和完整走线摘要已读回检查。官方结束代码仍有历史 `T65535` 解析提示，切片成功不代表已验证打印机执行。

四键材料 1 为 PLA Lite 橙色，材料 2 为 PLA Lite 白色；旋钮材料 1 为 PLA Basic 黑色，材料 2 为 PLA Lite 白色。打印前按实际耗材映射 AMS 槽位。单色盘的绿色预览是 Generic PLA 默认显示色，不是零件配色要求。

P1 周围面板贴板，孔网下沉 1.5 mm，其下支撑从正面清理，两处背面减薄区不增加筋或遮挡原孔型；上部结构仍有外部可拆支撑。局部 1.2 mm 孔网的刚度、孔口毛刺和翘曲须在打印后检查；支撑拆除时托住周围实心框，勿按压孔网，不将切片成功等同于强度或外观验收。

## 装配顺序

1. 清理支撑、brim 和孔口，检查三个主体没有断筋、翘曲或薄壁破损。本轮按用户选择直接装配完整件，不再打印试片；P2/P3 侧口装配间隙为 0.7 mm，保持不加接口密封圈。
2. 从正面看过去的左下角为上 Type-C、下 DC（从后面看为右下角），中心距 12 mm，Type-C／DC 中心距底边为 23／11 mm。先试装 DC 与 Type-C 母座，口面与后壁齐平，在内伸 5 mm 的套座胶接并固化（连同 5 mm 后壁，总支撑长度 10 mm），保留可断开的充电线束。DC 原长 31.5 mm 无需裁剪。再在 P2 放置光驱后壁保护垫；电池和 P3 尚未装入时，按下述拆卸路径逆序装光驱及 SATA 接头，落在中央底托上，装两螺钉压条，再将电池用 1–1.5 mm 双面胶固定在底板左右挡板之间（CAD 按 1.5 mm 预留）。实际导线和板卡固定方式尚需按实物补全。
3. 两只喇叭端子朝上，从 P3 正面装入，金属固定边直接贴原硬质座面，每只用四枚用户提供的 Ø2.8 螺钉均匀锁紧。按 ADR-0041 在固定框外周做可移除封边；两根各 Ø1.8 mm 的线绕过安装框后方，从对应顶部通孔穿出，留维护余量并封堵孔周及双线凹缝。先完成穿线封堵，再安装功放和集成洞洞板。总成从正面推入 P2，固定四处前向连接；线束留在 P3 上，不粘接到 P2。
4. 连接线束，确认没有压线，保留前壳拆卸所需的可断开连接和维护余量。
5. 裸 B50K 先焊线并做独立绝缘，放入 P1 辅助防转槽并锁螺母，再按关断止挡对准旋钮指示条并支撑主体压入；检查焊点及出线不受压。P1 预装 OLED 模组和操控件（玻璃朝沉槽，四孔套入定位柱，再装可拆压框并锁紧两侧螺钉）；从内侧装入四个键帽、开关，固定可拆压板，确认回弹和引脚／焊点／线缆不受压后，向后合拢前壳，从后壁下方和后斜面四个深孔固定连接。实际线束必须另行检查。

拆卸按相反顺序。从背面深孔取出前壳四个螺钉；托住前壳向前拉开 60 mm，拔开三组 XH2.54 及其它连接后移走前壳；拆 P3 前断线并卸支架四螺钉，再向前抽出。光驱维护需取出 P3、压条和电池：先前移 12 mm，再前移 3 mm 并抬高 9.5 mm；接头向下退出 10 mm、向内移 14 mm 后从前方取出。光驱再前移 13 mm，绕 Z 旋转 -30°并同步前移 20 mm，最后向前抽出。压条使用两枚 Ø2.5×10 平底头螺丝；后壁留 1 mm 垫片空间，压条处软垫厚度按实际厚差试配，避免挤压薄盖。安装按反向顺序。电池断线并解除胶层粘接后，可以保留 P3、光驱和接头直接向前取出；胶层拆除操作和保持力尚未实测。上述位移是检查用脱离行程，不是所有动作都必须移动完整 140 / 150 mm。

当前螺丝分配：合壳 4 枚 M3.5（含头总长 30 mm）；P3 4 枚、光驱压条 2 枚 Ø2.5×10；四键 2 枚、OLED 2 枚 Ø2.8×7.8，后两类都是平底头。洞洞板仍另需 3 枚 M2×4，不能以现有粗长螺丝代替。已装喇叭和 6 枚备用 Ø2.8×9.5 保持。

合壳工具井 Ø7.4、通孔 Ø3.9、P1 盲孔 Ø2.8；下方工具井约 58 mm，预留 Ø6 刀杆。M3.5 头径 6.8，沉头暂按 90°设计，实际锥角尚未测量。P3 原孔不改，每耳放一片 Ø5.8×Ø2.8×1.2 平垫圈，螺帽朝 P1；P1 内避让后净距 1 mm。拆 P3 时一并取下四片垫圈。螺丝入柱、盲底余量及库存详见 [ADR-0052](decisions/0052-stock-fasteners.md)。

OLED 玻璃前面内退 1.0 mm，沉槽前缘名义厚 0.8；外口经倒角收至内喉口。四个 Ø2.6 定位柱配 PCB Ø3 孔；可拆压框四点接触孔周，使用两枚 Ø2.8×7.8 平底头螺丝，Ø2.3 盲底孔深 4.4，头径 5.9、高 2；压框锁紧垫厚 3.8，名义入柱 4 mm、距盲底 0.4 mm。完整件装配时核对薄边强度、PCB 厚度、孔补偿和螺钉扭矩。针尖后 6 mm 为插线预留；拆屏前先拆 P1、断线、卸两枚压框螺钉并取下压框，再沿内法向取出模组。详见 [ADR-0028](decisions/0028-oled-mechanical-mount.md)。

## 完整件验收

- P1/P3 间隙：完整装配后复量振膜静态净距，名义目标 3 mm；从低音量逐步检查无碰网或异响。
- P3：双喇叭贴合与锁紧、出线、可移除封边、通道畅通；P2/P3 保留 0.7 mm 滑配间隙，不跨件粘接。
- 双充电口：清理孔内支撑，试配母座，核对胶层固化、插拔保持力、外部插头胶壳间隙与尾线余量；Type-C 充电板与双入口电气方案仍待确定。
- P2 与 P1：支撑清理、翘曲、提手和螺柱强度、实际紧固件及工具路径。
- 操控件：四键回弹、OLED 夹持、旋钮压配与转动。压旋钮时支撑电位器主体，不让焊脚承受推力。
- 整机：线束不受压，前壳可拉开 60 mm 并按顺序断开；实际进退碟、供电负载、温升、左右声音、漏气与异响分别验收。

## 版本与验证

模型 SHA-256：`39c745a443f341767aa4a219102fdb1477acd508da073d469f57701f85173ab2`。详见 [孔网净距](../hardware/enclosure/grille-clearance-checks.json)、[P1 当前逐层检查](../hardware/enclosure/stock-front-print-checks.json)、[P2 当前逐层检查](../hardware/enclosure/p2-depth-print-checks.json)、[当前螺丝与工具通道](../hardware/enclosure/stock-fastener-checks.json)、[文件清单与摘要](../hardware/enclosure/print/manifest.json)、[正式包检查](../hardware/enclosure/print-release-checks.json)、[P3 声道检查](../hardware/enclosure/p3-terminal-mouth-checks.json)、[P2 侧口检查](../hardware/enclosure/p2-trapezoid-outlet-checks.json)、[整机静态检查](../hardware/enclosure/validation.json)、[拆装路径](../hardware/enclosure/assembly-paths.json)和[当前线束检查](../hardware/enclosure/current-perfboard-checks.json)。

历史阶段的 `*-checks.json` 和 ADR 只证明其对应模型。本轮由 stock-fastener-checks.json 记录五件改动、四片垫圈及其余成品不变，三盘新切片分别记录在 stock-front-print-checks.json、p2-depth-print-checks.json、retainer-print-checks.json。最终 GUI 资源独立化只改变显示封装，全部几何存档逐字节相同；证据传递记录在 stock-gui-checks.json。P3 等原打印文件摘要保持。图册见[尺寸与装配图纸](enclosure-drawings.md)。

## 重现

设置 `DISCORA_FREECAD_PYTHON` 为可导入 FreeCAD、Part、MeshPart 的 Python；若库目录独立，设置相应 `PYTHONPATH`。先检查已交付包：

```sh
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/check-print-release.py
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/check-perfboard.py --output tmp/perfboard-current-checks.json
```

以下命令生成新的临时网格及 6 盘切片，不覆盖正式包，也不发送打印。新模型或新切片器产生的 P2/P3 必须重新审核关键层与支撑后，才能替换本次已审核文件。

```sh
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/export-print-parts.py --output tmp/pla-print
python3 hardware/enclosure/slice-print-parts.py --meshes tmp/pla-print --output tmp/pla-print/checks.json
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/export-dual-color-keys.py --output tmp/dual-color-keys
python3 hardware/enclosure/slice-dual-color-keys.py --meshes tmp/dual-color-keys --output tmp/dual-color-keys/checks.json
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/export-dual-color-knob.py --output tmp/dual-color-knob
python3 hardware/enclosure/slice-dual-color-knob.py --meshes tmp/dual-color-knob --output tmp/dual-color-knob/checks.json
```

历史光驱适配比较的基准 SHA-256 为 `e507a10f55fc1f1f7340c7df5203a91666335190cf97bc31325e94052f30bc4b`。生成文件历史清理后，当前 Git 不再保证包含旧 `0c3a117:hardware/enclosure/Discora.FCStd`；复查须使用摘要匹配的保留基线，或在独立目录恢复重写前 bundle 后提取。备份与恢复边界见[贡献约定](../CONTRIBUTING.md#git-中的生成文件历史)。历史比较不得使用当前模型冒充调整前基准；日常复查输出到 `tmp/`，保留已有历史证据。
