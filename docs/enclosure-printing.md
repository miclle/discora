# 三主体 PLA 打印与拆装检查

2026-11-10 左右导音孔与内凹饰片并入 P2，取消独立侧孔打印与装配；当前十一件网格与四盘单色切片见 `print-checks.json`，四键及旋钮另用双色记录。

本次采用用户提供的拓竹 P2SC、256 × 256 × 256 mm 成型空间及 0.4 / 0.2 mm 喷嘴信息。**已做 0.4 mm 喷嘴的本地切片；尚未实际打印或装配。** 采用本机 Bambu Studio 的 P2S 配置，未连接打印机；0.2 mm 喷嘴仅记录为可用设备，未验证其切片。

当前整机 170×93×243.263 mm，主体壁厚均为 5 mm；按 UJ-898 实测调整光驱底托、可拆压条、SATA 与线缆空间，详见 [ADR-0035](decisions/0035-measured-drive-rear-wall-mount.md)。

模型与图纸见[外壳说明](../hardware/enclosure/README.md)和[唯一彩色图册](../hardware/enclosure/drawings/Discora-V4-drawing-book-color.pdf)。三个主体均为单一连续实体；两侧孔已并入后壳，另有四键帽、按键支架、OLED 压框、光驱压条和旋钮，共 11 件刚性 PLA 零件，软脚垫与 OLED 自带玻璃另计；本版没有独立透明保护片。

## 橙白双色键帽（2026-11-10）

四个键帽已改为橙色键体和白色功能符号两个材料区域；白色符号深 0.6 mm、表面与键面齐平，最细笔画 0.8 mm。外包络、止退沿、按键孔和安装位置保持。用 FreeCAD Python 执行 `hardware/enclosure/export-dual-color-keys.py`，在 `tmp/dual-color-keys/` 生成四键一盘的 3MF 及同坐标 STL 分区；优先用 3MF 保持材料区域的相对位置。

在 Bambu Studio 中将材料 1 对应 PLA Lite 橙色、材料 2 对应 PLA Lite 白色，并映射实际 AMS 槽位；符号面朝上、止退沿贴板。已用本机 P2S 0.4 mm / 0.12 mm 配置切片，启用擦拭塔；每个按键生成 5 层白色路径，整盘 60 层，预估 34 分 20 秒、总耗材 7.42 g（含换色消耗）。本地原生项目在 `tmp/dual-color-keys/slicer/Discora-buttons-bambu.3mf`，不提交生成文件；复核配置后在自己的设备上打印。

[双色验收记录](../hardware/enclosure/dual-color-key-checks.json)记录实体、网格、材料分配及实际生成的双色路径。切片器返回成功，同时保留安装版本的 `T65535` 解析提示；没有发送打印或验证设备执行。白色遮盖、材料粘结、按压行程及实物装配仍待验证。下面为当前光驱实测适配版四盘单色记录，四个键帽沿用本节的双色记录；键帽外包络保持；P2 的后续侧孔一体化见 [ADR-0029](decisions/0029-integral-side-ports.md)。常规 `slice-print-parts.py` 已排除四键及旋钮，避免误用丢失双色信息的单色 STL。

## 当前单色件打印摆放和切片

| 零件 | 放置方向 | 旋转后的包络 X × Y × Z / mm | 注意事项 |
| --- | --- | --- | --- |
| P1 前壳 | 正面朝下，长边沿打印板 X | 240.263 × 170 × 49 | 保持导出姿态；护网、提手背面与安装座需支撑 |
| P2 一体后壳 | 后壁朝下 | 170 × 192.682 × 88 | 侧孔与导音通道的支撑清理需实物确认 |
| P3 喇叭支架 | 声腔背面朝下 | 134 × 125.7 × 57.5 | 托板突出声腔背面，需支撑；清理后检验气密与装配面 |
| 按键支架、OLED 压框、光驱压条；旋钮另用双色盘 | 按各自导出姿态 | 见切片报告 | 先核对承压、孔位、轴配合及实际支撑 |

提手加高后的 P1 将长边沿打印板 X 居中摆放，并关闭自动排版／自动定向。自动树支撑排版预留每边 12 mm，将可用宽度缩至 232 mm，拒绝 240.263 mm 长边；导出姿态保留 5 mm brim 空间，实际支撑及路径仍以本地切片检查为准。

三主体各一盘，按键支架、OLED 压框和光驱压条合为一个单色小件盘；四键和旋钮分别使用双色盘。十一件 STL 均为闭合网格，单件在 256³ 空间内留有 5 mm brim 余量；四键和旋钮的 STL 只是单色包络，实际打印优先用双色 3MF。参考工艺：Generic PLA、0.4 mm 喷嘴、0.20 mm 层高、3 层壁、15% gyroid 填充、自动树状支撑（仅从底板生成）、30° 阈值、0.2 mm 顶部接触间隙、5 mm 外侧 brim。

2026-11-12 光驱实测适配版四个单色盘均重新切片；2026-11-14 PCB音量模块版仅重切前壳，下表采用新前壳结果；四键和旋钮的实体及分面顺序未变，沿用双色切片证据，关联检查见 [光驱安装检查](../hardware/enclosure/drive-mount-checks.json)。Bambu Studio 02.09.01.70 当前估计值（含支撑和 brim，不含试错）：

| 打印盘 | 估计总时间 | 耗材 / g | 层数 |
| --- | --- | --- | --- |
| P1 前壳 | 14h 7m 19s | 156.65 | 245 |
| P2 一体后壳 | 9h 33m 48s | 297.06 | 440 |
| P3 支架 | 5h 0m 55s | 149.65 | 287 |
| 3 个单色小件 | 26m 9s | 6.61 | 32 |

四盘单色合计估计 **609.97 g**；加上四键双色盘 7.42 g 和旋钮双色盘 9.50 g，共约 **626.89 g**。实际时间、耗材及支撑清理效果以打印结果为准。

2026-11-14 PCB 模块适配只改变前壳打印几何；新前壳切片及旧件复用依据见 [volume-pcb-print-checks.json](../hardware/enclosure/volume-pcb-print-checks.json)，文件位于 `tmp/cad-volume-pcb/print/`。[print-checks.json](../hardware/enclosure/print-checks.json)保留 2026-11-12 模型、网格、配置及 G-code 摘要。四盘返回码均为 0，保留安装版本对官方结束代码 `T65535` 的解析提示；未发送打印。本次旋钮双色文件位于被忽略的 `tmp/cad-volume-white/print/`，四个单色盘均位于 `tmp/cad-drive-measured/print/`。切片成功不代替侧孔窄筋、深孔和导音通道的支撑清理验证。

下方两处背锁通道深 78.8 mm，需细长螺丝刀；上方两处位于后斜面，轴向深约 30.5 mm。螺钉头径应不超过 4 mm，实际批头与刀杆须核对。详见 [ADR-0024](decisions/0024-rear-access-front-cover-fasteners.md)。

侧饰片现为四点连接，筋截面 2×3 mm、饰片厚 2 mm；仍需避免扭撬清理支撑，打印强度未实测。历史加强阶段单侧最窄采样通流面积约 3.84 cm²；当前声腔加深和短管延长见 ADR-0035，声学效果待测；声学分析及参数缺口见 [ADR-0030](decisions/0030-side-inset-support-and-port-sizing.md)。

## 装配顺序

1. 清理支撑、brim 和孔口，检查三个主体没有断筋、翘曲或薄壁破损；先用小样核对 0.3 mm 配合间隙和螺钉底孔。
2. 在 P2 装 DAC，并放置后壁保护垫；电池和 P3 尚未装入时，按下述拆卸路径逆序装光驱及 SATA 接头，落在中央底托上，装两螺钉压条，再装电池和绑带。实际导线和板卡固定方式尚需按实物补全。
3. 在 P3 安装两只喇叭、功放和主控；核对喇叭安装基准与密封材料后，从正面把总成推入后壳，固定四处前向连接。左右导音孔与饰片已和后壳一体，无需取下。
4. 连接线束，确认没有压线，保留前壳拆卸所需的可断开连接和维护余量。
5. P1 预装 OLED 模组和操控件（玻璃朝沉槽，四孔套入定位柱，再装可拆压框并锁紧两侧螺钉）；从内侧装入四个键帽、开关，固定可拆压板，确认回弹和引脚／焊点／线缆不受压后，向后合拢前壳，从后壁下方和后斜面四个深孔固定连接。实际线束必须另行检查。

拆卸按相反顺序。从背面深孔取出前壳四个螺钉、断开操控线，前壳向前移出；拆 P3 前断线并卸支架四螺钉，再向前抽出。光驱维护需取出 P3、压条和电池：先前移 12 mm，再前移 3 mm 并抬高 9.5 mm；接头向下退出 10 mm、向内移 14 mm 后从前方取出。光驱再前移 13 mm，绕 Z 旋转 -30°并同步前移 20 mm，最后向前抽出。压条使用两枚名义 M2×10；后壁留 1 mm 垫片空间，压条处软垫厚度按实际厚差试配，避免挤压薄盖。安装按反向顺序。电池断线松绑后可以保留 P3、光驱和接头直接向前取出。上述位移是检查用脱离行程，不是所有动作都必须移动完整 140 / 150 mm。

连接孔见图册第 2 页：前壳改为背面 Ø4.4 深孔内的 Ø2.2 通孔配 Ø1.6 盲底孔，名义 2×8 mm 螺钉、头径不超过 4；支架仍为 Ø2.8 通孔配 Ø2.0 底孔；侧孔独立固定孔已取消。此处只是名义的螺杆、沉头和底孔预留，具体螺纹类型、螺钉长度、孔径补偿和扭矩未验收；不要把它当成已定型的紧固件 BOM。反复拆装寿命需试样；如后续改为嵌件，应另行增加足够安装柱体积并重新检查干涉。

OLED 玻璃前面内退 1.0 mm，沉槽前缘名义厚 0.8；外口经倒角收至内喉口。四个 Ø2.6 定位柱配 PCB Ø3 孔；可拆压框四点接触孔周，使用两枚名义 M2×6，Ø1.6 盲底孔深 4.4，头径不超过 4、高不超过 1.6。先打印局部沉槽、定位柱和压框试片，核对薄边强度、PCB 厚度、孔补偿和螺钉扭矩。针尖后 6 mm 为插线预留；拆屏前先拆 P1、断线、卸两枚压框螺钉并取下压框，再沿内法向取出模组。详见 [ADR-0028](decisions/0028-oled-mechanical-mount.md)。

## 检查范围

[assembly-paths.json](../hardware/enclosure/assembly-paths.json)记录以下条件和结果：

- P3 连同喇叭、功放、主控向前：按各构造件的包围盒连续保守扫掠；前壳和螺钉已取下，侧孔随 P2 固定。
- 光驱压条：拆前壳和 P3、卸两螺钉后向前取出，腰部及两耳分别连续保守扫掠。
- 光驱进入维护位置：移除压条和电池，先连续前移 12，再按 31 个姿态检查前移 3／抬高 9.5。
- SATA 拔出及向前取出：三个连续保守包络扫掠；10 mm 拔出行程是设计预留，线缆须释放。
- 光驱最终退出：先连续前移 13，再使用填满的最大主体包络，按 0.5° 步长检查 -30° 侧转并同步前移 20 的 61 个姿态，最后连续前移退出；抬升和转动都是离散采样，不是连续运动证明。
- 电池向前：连续保守扫掠，含 P3、光驱及 SATA 接头作为固定件；绑带和电池线缆已取下。
- 两侧孔与后壳为同一个实体；短管至声腔留隙 0.3，当前检查见 `drive-side-port-checks.json`，历史比较保留在 `side-port-checks.json`。
- OLED 维护：前壳取下并断线后，先卸压框再取模组；各按内法向 0…25 mm、0.5 mm 步长检查 51 个姿态。
- 前壳总成：取出四个背面螺钉后，真实 B-rep 以 1 mm 步长向前退出，所有采样无碰撞；这不是连续运动的严格证明。

四键改用镂空焊线支架：每键两个 2×3 mm 支承面，中央 5.6 mm 宽区域避让底面凹凸，两侧连续开口供直接焊线。按照片将两排引脚朝向斜面上下方向；引脚长度 3.7 按本体背面另计，脚端后预留 2 mm。上一曲键靠 DAC 一侧的导线须向机身中央引出，避免进入 DAC 接头区域。先焊线并检查绝缘，再安装支架；卸支架时导线可从开口退出，无须穿过封闭孔。先验证局部样件的承压、回弹、焊点、线径和弯折空间；精确脚距及底面高度仍待测。见 [ADR-0025](decisions/0025-open-button-wire-retainer.md)。

CAD 成品静态无干涉、网格闭合和切片成功，不代表喇叭安装孔已测、密封可靠、支撑必然容易拆除、PLA 提手承载足够或实物线材可装入。应先打印局部配合／护网／螺钉试片，再打印主体做装配样件；打印后核对提手层间受力、螺柱、喇叭振膜空间、温升与实际进退碟。电池标称尺寸不含已验证的线材和插头，外围电源模块也未完整建模。

## 重现

先运行外壳建模与静态检查，用可导入 FreeCAD、MeshPart 的 Python 导出十一件 STL，再用普通 Python 调用本机切片器：

```bash
mkdir -p tmp
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/check-side-ports.py --output tmp/side-port-current-checks.json
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/check-oled.py
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/check-fasteners.py
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/check-buttons.py
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/check-assembly.py
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/check-drive-mount.py --output tmp/drive-mount-current-checks.json
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/export-print-parts.py
python3 hardware/enclosure/slice-print-parts.py
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/export-dual-color-keys.py
```

`drive-mount-checks.json` 含图册复用双色件所需的基线摘要、20 个不变对象和分面顺序证据；不带 `--baseline` 的检查不会生成这些字段，因此日常复查另存 `tmp/`。完整复核本版光驱适配比较时，从已提交的调整前版本恢复基准，并将新结果另存以供对照：

```bash
mkdir -p tmp/drive-baseline
git show 0c3a117:hardware/enclosure/Discora.FCStd > tmp/drive-baseline/Discora.FCStd
"$DISCORA_FREECAD_PYTHON" hardware/enclosure/check-drive-mount.py \
  --baseline tmp/drive-baseline/Discora.FCStd \
  --output tmp/drive-mount-baseline-checks.json
```

基准 SHA-256 应为 `e507a10f55fc1f1f7340c7df5203a91666335190cf97bc31325e94052f30bc4b`，当前模型摘要见[图册版本与证据](enclosure-drawings.md#版本与证据)。浅克隆若缺少 `0c3a117`，先获取相应历史；确认 `git show` 成功和摘要匹配后再检查。不要以当前模型充当调整前基准。未来修改模型时，应另存真正的修改前版本，并同步审查图册追溯链。

切片器和配置目录可用 `--bambu`、`--profiles` 指定，临时网格目录可用 `--meshes` 指定。脚本核对模型与网格摘要、返回码及 G-code 统计；不会发起打印。

## B50K 十字旋钮与安装试片

2026-11-10 旋钮更新见 [ADR-0032](decisions/0032-b50k-cross-knob.md)。底盘 Ø24、总高 13.9，底面朝下；十字跨度 24、臂宽 6.8。Ø12 螺母腔和六筋压配孔需清理支撑，保留筋尖形状。侧面无螺钉孔，直接压入 Ø5.8 花轴；顶部指示条为 0.7×2.2×0.6 mm 白色实体，与黑色顶面齐平。

使用 FreeCAD Python 运行 `hardware/enclosure/export-dual-color-knob.py --output tmp/dual-color-knob`，生成 `Discora-knob-black-white.3mf`；在 Bambu Studio 中保留为一个对象、两个部件，黑色主体指定材料 1，白色标记指定材料 2，不要将白色部件单独落板。底盘朝下、标记朝上。`hardware/enclosure/slice-dual-color-knob.py --meshes tmp/dual-color-knob` 可重现本机切片，另外生成带材料配置的 `slicer/Discora-knob-bambu.3mf`。

双色旋钮使用 PLA Basic 黑色／PLA Lite 白色，P2S 0.4 mm 喷嘴、0.12 mm 层高、Arachne、3 层壁、15% gyroid、树状支撑、5 mm brim 和擦拭塔。切片为 116 层，标记在 Z=13.44／13.56／13.68／13.80／13.92 mm 生成 5 层白色路径；预估 48 分 42 秒、黑色 6.58 g／白色 2.92 g，包含支撑与换色消耗。见 [双色旋钮检查](../hardware/enclosure/dual-color-knob-checks.json)。未发送打印，白色遮盖、材料粘结、支撑清理与实际压配仍待确认。

先用 `hardware/enclosure/export-volume-fit-samples.py --output tmp/volume-fit` 导出三档松紧试片（筋尖内切直径 5.5／5.6／5.7，需 FreeCAD Python）。三档已完成本地切片，见 [试片报告](../hardware/enclosure/volume-fit-checks.json)。默认旋钮为 5.6，不代表已知打印机与耗材的最终尺寸；选择能手压装入、转动开关不打滑的一档后再试印完整旋钮，检查拔出力和重复使用。压入时支撑电位器主体，不让焊脚或 PCB 承受装配推力。

局部前壳试片需核对 Ø7.2 壳孔、2 mm 夹持面、9.8 对边螺母锁紧、底盘下沉 1 mm、距凹位底 0.6 mm 和径向 0.4 mm 间隙；还需检查偏心主体、焊点和引线余量及整个旋转／开关行程。CAD 中六条筋与花轴圆柱包络的过盈是设计预留，不能当作碰撞遗漏或实物保持力验收。

拆卸 PCB 音量模块时先取下整个前壳，再拆旋钮、螺母并沿轴退出模块；机内直接后拔约6 mm后会碰支架。

安装试片可用 `hardware/enclosure/export-volume-coupon.py --output tmp/pla-print/VolumeMountCoupon.stl` 从当前保存模型重新导出（需 FreeCAD Python）；PCB 模块版试片为 32×44×5 mm，外表面朝打印板，验证沉槽与螺母夹紧，不计入整机 11 件清单。
