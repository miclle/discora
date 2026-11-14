# ADR-0046：P3 圆角梯形短渐扩口

日期：2026-11-14。状态：已实现，CAD、拆装和切片验证通过；完整件打印与声学待实测。

用户授权仅优化 P3 管口末端与口沿，使其与 ADR-0045 的 P2 圆角梯形外口更协调。P2 本体及其 STL／3MF 不变，P3 安装座和内部转弯通道保留。

## 几何边界

- 左侧口面仍为 X=−79.3，右侧镜像；只在最后 **4 mm**（左侧 X=−75.3 至 −79.3）增加渐扩切口。原 400 mm² 通路完整包含于新版气路，不存在为造型而缩小原通路的区域。
- 末端净口采用 P2 内口向内等距偏移 **1.8 mm** 的圆角梯形，圆角 **R2.2**、净面积约 **587.22 mm²**。17 个渐扩切口截面由内向外单调增大；完整转弯通道的既有截面检查仍不小于 400 mm²。
- 外侧一体实体口沿长 **5.8 mm**，比渐扩根部向内多 1.8 mm；末端横截面的名义口沿厚度为 **1.8 mm**。这是横截面尺寸，不是力学强度或任意方向最小壁厚的实测结论。原外壁与口沿融合，隐藏在 P2 后面的原背侧角部保留。
- 渐扩根部切割轮廓增加 **0.001 mm** 数值余量，避免重合接缝导致布尔内核错误分类；检查要求整个导管空腔为一个有效连通实体，并确认原通路无材料侵入。
- P3 在两侧末端 6 mm 检查邻域之外的实体差集为零；P2 整体差集为零。安装框、试装座面、8 个原螺柱及盲孔、出线孔保持，左右镜像差集为零。两声腔背面的 Y=62.5 贴板面保持，每侧接触面积仍为 6929 mm²。
- 新管口完整投影通过 P2，没有遮挡；P2/P3 最近间隙仍为 **0.7 mm**，七条原拆装路径全部通过。P2 不参与构成 P3 的导管壁，也不增加跨件粘接、倒扣或封闭盖板。

这是一段为接口和外观服务的短渐扩口，未宣称为优化后的号角、低风噪端口或声学调谐。主段参数仍沿用 ADR-0043；端部形状变化对实际声学表现的影响待完整件验证。

## 验证与打印

证据：[P3 末端检查](../../hardware/enclosure/p3-terminal-mouth-checks.json)、[整机检查](../../hardware/enclosure/validation.json)、[拆装路径](../../hardware/enclosure/assembly-paths.json)。

- 保存并重读的 P3 是有效单实体，导出 STL 闭合。封堵预期入口及出口后的左右独立性、开放出口连通外界，以及堵住导管入口后主腔与出口断开，均通过。
- 全部 **287 层**检查通过：没有新增无支撑孤岛，声腔、导管及末端范围内没有支撑走线；管口范围没有超过 1 mm 的无下层承接桥接／悬垂走线。
- 原 18 条悬空告警按原分组重查：两侧安装框无上述无承接长走线，8 个螺柱原第 206 层底部投影由第 205 层承接比例均达到既有要求。两块声腔背板首层 Z=0.20 mm 均有模型底面走线。
- 使用一致网格精度比较时，第 203 层在未修改的上部结构仍出现一条约 0.190 mm²、宽约 0.073 mm 的网格差异；对其实际三维邻域比较，保存 CAD 差集为零，归为网格离散差异并保留原记录。真实改动区域没有新增显著悬挑，0.05 mm² 面积与 0.35 mm 邻层增长判据保持。
- 使用 Bambu Studio 2.9.1.70、P2S 0.4 mm、Generic PLA、0.20 mm、3 层壁、15% gyroid、自动树支撑、30°、顶部间隙 0.20 mm；P3 仍开启“仅在打印板生成支撑”和“仅关键区域”。保存 3MF 区域告警为空，包内 G-code 与审核文件一致。预计 **5h 40m 46s／181.00 g**。
- 在 Bambu Studio 中重新打开并切片，查看首层及第 **162 层（32.4 mm）**；下限保持第 1 层、走线进度完整，声腔与末端未见内部支撑。GUI 显示约 5h41m／181.00 g，未覆盖审核过的 3MF，未发送打印任务。
- 装配侧视图 `tmp/cad-p3-trapezoid-mouth/assembled-mouth.png` 由保存的真实 P2/P3 实体正投影生成，灰色为 P2、青色为 P3，保留实际遮挡。孔内仍可看见深处过渡和转弯壁面，不是装饰假孔。

P2 沿用 ADR-0045 支撑设置，两项限制均关闭，其开放侧口支撑仍需清理。实际支撑拆除力、表面质量、装配公差、气密和声音仍待完整件实测；不再打印试片。

## 正式交付文件

本轮已将配套文件归一到 `hardware/enclosure/print/`；临时迭代导出不再作为打印入口。完整清单见[正式套件](../../hardware/enclosure/print/README.md)。历史日志、几何基线和审核摘要保留。

- CAD：`hardware/enclosure/Discora.FCStd`。
- P3 STL：`hardware/enclosure/print/SpeakerCarrier.stl`。
- P3 3MF：`hardware/enclosure/print/Discora-P3-SpeakerCarrier.3mf`。
- P2 仍用：`hardware/enclosure/print/Discora-P2-RearShell.3mf` 及同目录 `RearShell.stl`。
- 几何源：`speaker_duct_geometry.py`；整机重建入口：`build.FCMacro`；本轮基线、构建／切片／审计脚本、日志和截图保存在 `tmp/cad-p3-trapezoid-mouth/`。

使用 FreeCAD 所带 Python，在仓库根目录运行：

```sh
python hardware/enclosure/check-terminal-mouth.py \
  --model hardware/enclosure/Discora.FCStd \
  --baseline tmp/cad-p3-trapezoid-mouth/baseline.FCStd \
  --output tmp/cad-p3-trapezoid-mouth/duct-geometry.json
```
