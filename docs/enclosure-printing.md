# 正式打印文件与装配

当前版本：ADR-0046 P3 短渐扩口，配套 ADR-0045 P2 圆角梯形开放侧口。正式文件统一在 [hardware/enclosure/print](../hardware/enclosure/print/README.md)，不再从历次 `tmp/` 目录选择零件。

这里的“正式版本”指本轮唯一配套交付版本，完整件打印、支撑拆除、装配、强度、气密和声学仍待实测。**P3 喇叭安装座试片已打印并确认装配无问题**，保留已通过的座面和孔位，不再要求打印试片。

## 六个打印盘

| 打印盘 | 3MF | 预计时间 | 耗材 / g | 层数 |
| --- | --- | --- | --- | --- |
| P1 前壳 | [Discora-P1-FrontShell.3mf](../hardware/enclosure/print/Discora-P1-FrontShell.3mf) | 14h 6m 53s | 156.65 | 245 |
| P2 后壳 | [Discora-P2-RearShell.3mf](../hardware/enclosure/print/Discora-P2-RearShell.3mf) | 9h 12m 0s | 286.84 | 440 |
| P3 喇叭支架 | [Discora-P3-SpeakerCarrier.3mf](../hardware/enclosure/print/Discora-P3-SpeakerCarrier.3mf) | 5h 40m 46s | 181.00 | 287 |
| 三个压框／支架 | [Discora-Retainers.3mf](../hardware/enclosure/print/Discora-Retainers.3mf) | 26m 9s | 6.61 | 32 |
| 四个橙白双色按键 | [Discora-Keys-Orange-White.3mf](../hardware/enclosure/print/Discora-Keys-Orange-White.3mf) | 34m 44s | 7.54 | 60 |
| 黑白双色旋钮 | [Discora-Knob-Black-White.3mf](../hardware/enclosure/print/Discora-Knob-Black-White.3mf) | 48m 44s | 9.50 | 116 |

合计约 **648.14 g**，包含支撑、brim 和双色换料耗材。时间和用量来自 Bambu Studio 2.9.1.70 本地切片，不是实际打印记录。配置为 P2S / 0.4 mm，按用户提供的 P2SC、256³ mm 空间映射；0.2 mm 喷嘴未验证。

11 件刚性 PLA 零件均有 STL。四键和旋钮的 STL 仅为单色包络，双色打印优先打开上述 3MF，保留同一对象内的两个材料区域。软脚垫、OLED 玻璃、电子模块、螺钉、绑带和导线另购，不计入打印件。

## 摆放与支撑

| 打印盘 | 姿态／层高 | 仅在打印板生成支撑 | 仅关键区域 |
| --- | --- | --- | --- |
| P1 | 正面朝下，长边沿板 X；0.20 mm | 开 | 开 |
| P2 | 后壁朝下；0.20 mm | **关** | **关** |
| P3 | 双声腔背面朝下；0.20 mm | **开** | **开** |
| 三个小件 | 保持项目中各件姿态；0.20 mm | 开 | 开 |
| 四键／旋钮 | 符号面朝上；0.12 mm | 开 | 以各自 3MF 保存设置为准 |

单色盘使用 Generic PLA、3 层壁、15% gyroid、30° 自动树状支撑、顶部接触间隙 0.20 mm、5 mm 外侧 brim。P1 长边 240.263 mm，已保留检查过的摆放；不要使用自动定向重新翻转。P2/P3 的支撑限制不同，不要互相套用。

P3 双背板首层直接贴板；287 层审核未发现声腔、导管或渐扩口内支撑，原 18 条悬空告警对应位置已核对。P2 440 层侧口及开放结构需要支撑，从敞开的正面与侧口清理，实际拆除力待验证。两件的正式包保留已审核 STL 和 G-code，仅整理 3MF 文件名及本机导入路径元数据。

P1、小件、四键和旋钮从同一正式 CAD 重新导出、切片。四键每键及旋钮标记各有 5 层白色走线，3MF 对象数、材料分配、网格修复计数和完整走线摘要已读回检查。官方结束代码仍有历史 `T65535` 解析提示，切片成功不代表已验证打印机执行。

四键材料 1 为 PLA Lite 橙色，材料 2 为 PLA Lite 白色；旋钮材料 1 为 PLA Basic 黑色，材料 2 为 PLA Lite 白色。打印前按实际耗材映射 AMS 槽位。单色盘的绿色预览是 Generic PLA 默认显示色，不是零件配色要求。

## 装配顺序

1. 清理支撑、brim 和孔口，检查三个主体没有断筋、翘曲或薄壁破损。本轮按用户选择直接装配完整件，不再打印试片；P2/P3 侧口装配间隙为 0.7 mm，保持不加接口密封圈。
2. 在 P2 放置光驱后壁保护垫；电池和 P3 尚未装入时，按下述拆卸路径逆序装光驱及 SATA 接头，落在中央底托上，装两螺钉压条，再装电池和绑带。实际导线和板卡固定方式尚需按实物补全。
3. 两只喇叭端子朝上，从 P3 正面装入，金属固定边直接贴原硬质座面，每只用四枚用户提供的 Ø2.8 螺钉均匀锁紧。按 ADR-0041 在固定框外周做可移除封边；两根各 Ø1.8 mm 的线绕过安装框后方，从对应顶部通孔穿出，留维护余量并封堵孔周及双线凹缝。先完成穿线封堵，再安装功放和集成洞洞板。总成从正面推入 P2，固定四处前向连接；线束留在 P3 上，不粘接到 P2。
4. 连接线束，确认没有压线，保留前壳拆卸所需的可断开连接和维护余量。
5. P1 预装 OLED 模组和操控件（玻璃朝沉槽，四孔套入定位柱，再装可拆压框并锁紧两侧螺钉）；从内侧装入四个键帽、开关，固定可拆压板，确认回弹和引脚／焊点／线缆不受压后，向后合拢前壳，从后壁下方和后斜面四个深孔固定连接。实际线束必须另行检查。

拆卸按相反顺序。从背面深孔取出前壳四个螺钉；托住前壳向前拉开 60 mm，拔开三组 XH2.54 及其它连接后移走前壳；拆 P3 前断线并卸支架四螺钉，再向前抽出。光驱维护需取出 P3、压条和电池：先前移 12 mm，再前移 3 mm 并抬高 9.5 mm；接头向下退出 10 mm、向内移 14 mm 后从前方取出。光驱再前移 13 mm，绕 Z 旋转 -30°并同步前移 20 mm，最后向前抽出。压条使用两枚名义 M2×10；后壁留 1 mm 垫片空间，压条处软垫厚度按实际厚差试配，避免挤压薄盖。安装按反向顺序。电池断线松绑后可以保留 P3、光驱和接头直接向前取出。上述位移是检查用脱离行程，不是所有动作都必须移动完整 140 / 150 mm。

连接孔见图册第 2 页：前壳改为背面 Ø4.4 深孔内的 Ø2.2 通孔配 Ø1.6 盲底孔，名义 2×8 mm 螺钉、头径不超过 4；支架仍为 Ø2.8 通孔配 Ø2.0 底孔；侧孔独立固定孔已取消。此处只是名义的螺杆、沉头和底孔预留，具体螺纹类型、螺钉长度、孔径补偿和扭矩未验收；不要把它当成已定型的紧固件 BOM。反复拆装寿命需试样；如后续改为嵌件，应另行增加足够安装柱体积并重新检查干涉。

OLED 玻璃前面内退 1.0 mm，沉槽前缘名义厚 0.8；外口经倒角收至内喉口。四个 Ø2.6 定位柱配 PCB Ø3 孔；可拆压框四点接触孔周，使用两枚名义 M2×6，Ø1.6 盲底孔深 4.4，头径不超过 4、高不超过 1.6。完整件装配时核对薄边强度、PCB 厚度、孔补偿和螺钉扭矩。针尖后 6 mm 为插线预留；拆屏前先拆 P1、断线、卸两枚压框螺钉并取下压框，再沿内法向取出模组。详见 [ADR-0028](decisions/0028-oled-mechanical-mount.md)。


## 完整件验收

- P3：双喇叭贴合与锁紧、出线、可移除封边、通道畅通；P2/P3 保留 0.7 mm 滑配间隙，不跨件粘接。
- P2 与 P1：支撑清理、翘曲、提手和螺柱强度、实际紧固件及工具路径。
- 操控件：四键回弹、OLED 夹持、旋钮压配与转动。压旋钮时支撑电位器主体，不让 PCB 或焊脚承受推力。
- 整机：线束不受压，前壳可拉开 60 mm 并按顺序断开；实际进退碟、供电负载、温升、左右声音、漏气与异响分别验收。

## 版本与验证

模型 SHA-256：`80eede1e85eafe8aca6ba6702cb2e169b6f7b4d1c368eeca10f1e6647bacebe0`。详见 [文件清单与摘要](../hardware/enclosure/print/manifest.json)、[正式包检查](../hardware/enclosure/print-release-checks.json)、[P3 声道检查](../hardware/enclosure/p3-terminal-mouth-checks.json)、[P2 侧口检查](../hardware/enclosure/p2-trapezoid-outlet-checks.json)、[整机静态检查](../hardware/enclosure/validation.json)、[拆装路径](../hardware/enclosure/assembly-paths.json)和[当前线束检查](../hardware/enclosure/current-perfboard-checks.json)。

历史阶段的 `*-checks.json` 和 ADR 只证明其对应模型。当前 P2 通过与 ADR-0045 的实体零差集衔接，P3 直接对应当前模型；不把旧模型摘要改写成新版本。图册见[尺寸与装配图纸](enclosure-drawings.md)。

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

历史光驱适配比较仍可从 Git 的 `0c3a117:hardware/enclosure/Discora.FCStd` 恢复当时基准，其 SHA-256 为 `e507a10f55fc1f1f7340c7df5203a91666335190cf97bc31325e94052f30bc4b`。历史比较不得使用当前模型冒充调整前基准；日常复查输出到 `tmp/`，保留已有历史证据。
