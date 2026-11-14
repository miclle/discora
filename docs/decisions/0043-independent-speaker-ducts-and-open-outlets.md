# ADR-0043：P3 独立转弯导管与 P2 开放出口

日期：2026-11-14。状态：已实现；CAD、装配路径和切片检查通过，完整件打印、支撑拆除、气密与声学待实测。用户授权将布局研究继续落实为配套 P2/P3，不再打印试片。

> 后续更新：[ADR-0044](0044-rounded-exterior-outlets.md) 将 P2 外口改为圆角矩形，P3 及其打印文件保持。本页模型哈希、P2 尺寸和切片数据记录 ADR-0043 基线。

本版替代 ADR-0040 的宽侧空腔和侧饰片出口，保留 ADR-0041 的出线孔与可拆封堵，以及 ADR-0042 已试装座面和永久承接结构。P2、P3 必须使用本版配套文件。

## 结构与声道

原箱实测 20×20 mm 开口和两段约 50 mm 的转弯路径作为参考，未把未知的全程截面、箱体净容积和调谐照搬到 Discora。取舍过程见[布局研究](../records/2026-11-14-p3-channel-layout-study.md)。

- P3 每侧增加独立一次转弯导管。左侧中心 X=−65.5，入口 Z=98，转弯和侧出口中心 Z=65，右侧镜像。入口到内顶壁留 20 mm；路径从上方进入、向下、再转向外侧，封堵入口后主腔与出口断开，原底部直通旁路消除。
- 直段净截面 **400 mm²**，采用宽 20 mm 的斜顶截面；水平段深 25 mm。竖段顶脊沿长度渐变 1.5 mm，同时反向移动两肩，保持截面积并避免整条纵向屋脊同层长桥接。管壁名义 2.5 mm，和背板、腔体一体打印，无需装后封闭的盖板。
- 名义折线中心长度 **46.8 mm**，不含 P2 外壳厚度、端部修正或等效弯头长度。转弯连接处采用扩大的交汇空间；轴向和转角截面抽样均不小于 400 mm²。这不是经 CFD 优化的圆弧弯头，也不据此声称频响或调谐已优化。
- P2 出口随 P3 下移 15 mm 到 Z=65。取消原孔内饰片、连接筋和短管遮挡，换成贯穿 5 mm 侧壁的斜顶开放孔。入口沿管口轮廓法向放大 1 mm，净面积 **482.11 mm²**；外侧 1 mm 倒角再放大到 2 mm 偏置。沿壁厚七个截面检查，P3 的全部 400 mm² 投影均无遮挡。
- P2/P3 保持每侧 **0.7 mm** 滑动间隙。P3 自身围成完整导管，P2 是导管之后的外壳开口，不依靠 P2 拼成管壁；不新增胶粘、跨件倒扣或需先拆导管的装配步骤。

喇叭安装框整体、座面、8 个原螺柱包络及盲孔，与 ADR-0042 的实体差集均为零；其试装通过结论继续适用。顶部双 Ø1.8 mm 线材预留及封堵槽不变，通线走廊检查通过。喇叭后方 11 mm 名义间隙保留；**外侧原横向通路已改成导管，不再宣称整个后方 8 mm 区域不变**。

左侧扣除整个保守喇叭包络和导管后的主腔空间预算约 **159.37 cm³**。这一算法把盆架包络当作实心占位，不能当作实测净声学容积。缺少单元 Fs、Qts、Vas 和实际净容积，400 mm²／46.8 mm 是本版结构参数，不是已验证调谐。实物试听与频响验收仍需完整件完成。

## 验证与支撑

结构化证据：[p2-p3-duct-checks.json](../../hardware/enclosure/p2-p3-duct-checks.json)、[整机检查](../../hardware/enclosure/validation.json)、[拆装路径](../../hardware/enclosure/assembly-paths.json)。最终 CAD SHA-256：`5ba3b6c8d656ecfeb9e8c3cce01033df42622be426691f4662630de43c48bfca`。

- 三个主体各为一个有效实体；P2/P3 网格闭合，原导管之外的整机静态碰撞检查通过。七条既有拆装路径全部通过，包括 P3 整件向前抽出；连续保守包络与离散前壳姿态的限制仍按装配报告说明。
- 左右声腔、出口、P2 及 P3 下部镜像差集为零。关闭预期入口、线孔和出口后，左右腔和外界互相隔离；开启出口的反向检查确认连通。这里只验证几何气路，不代表打印件不漏气。
- P3 检查 287 层、P2 检查 440 层。逐层与修改前比较，未发现新增面积超过 0.05 mm² 的显著悬挑区或无承接孤岛；网格截面采用 0.35 mm 相邻层增长包络，对应现有 0.20 mm／30° 判据。
- 原 18 条 P3 告警重新逐项对应：两处安装框在全层没有超过 1 mm 的无下层承接桥接／悬垂走线；8 个螺柱在第 206 层的原底部投影均被第 205 层覆盖 100%。不是仅复用旧报告。
- P3 双背板首层直接贴板；逐段相交扫描确认声腔、独立导管和出线区域内 **0 条支撑挤出**。实际导管屋脊范围内无超过 1 mm 的无下层承接桥接／悬垂走线。
- P2 侧孔斜顶也未发现上述无承接长走线。出口附近存在树支撑分支，但仅经过开放孔和壳内开放区域，原饰片与内部连接筋已移除；5 mm 厚孔壁可从内外两侧接近。实际拆除力和表面质量仍需打印确认。

切片使用 Bambu Studio 2.9.1.70，P2S 0.4 mm、Generic PLA、0.20 mm、3 层壁、15% gyroid、自动树支撑、30°、顶部间隙 0.20 mm、5 mm 外侧 brim。

**P2 与 P3 的支撑设置不同：** P3 保持“仅在打印板生成支撑”；P2 关闭此项，允许支撑从后壳内侧生成，两者都保留“仅关键区域”。P2 初次按旧设置有 5 处未覆盖提示，集中在原横梁、底部固定等开放结构；只关闭“仅关键区域”无效。允许支撑落在后壳上后告警清零，也未把支撑引入 P3 声腔。不能将 P3 的仅底板设置重新套到 P2。检查方法亦参考 [Bambu Studio 的未覆盖支撑检查实现](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/PrintObject.cpp)，最终结论以本机实际 G-code 和保存参数为准。

| 配套件 | 层数 | 最终切片区域告警 | 预计时间 | 预计耗材 |
| --- | ---: | --- | --- | ---: |
| P2 后壳 | 440 | 空 | 8h 36m 23s | 282.45 g |
| P3 喇叭支架 | 287 | 空 | 5h 36m 48s | 180.85 g |

3MF 已保存覆盖参数标记，压缩包内 G-code 与审核文件完全一致。原有外部支撑仍保留，不宣称整件无支撑，也没有发送打印任务。

## 模型、打印文件和复现

- 正式模型：`hardware/enclosure/Discora.FCStd`。
- 重建入口：`hardware/enclosure/build.FCMacro`；新增几何集中在 `speaker_duct_geometry.py`，气路与保留界面检查在 `check-speaker-duct.py`。
- P2：`tmp/cad-p3-duct-outlet/print/RearShell.stl`；`tmp/cad-p3-duct-outlet/RearShell/Discora-P2-Outlet.3mf`。
- P3：`tmp/cad-p3-duct-outlet/print/SpeakerCarrier.stl`；`tmp/cad-p3-duct-outlet/SpeakerCarrier/Discora-P3-Duct.3mf`。
- 临时目录同时保留修改前基线、生成脚本、切片脚本和日志、全层检查及真实 CAD 剖面图 `paired-channel-sections.png`。逐层几何工具为 `hardware/enclosure/slice_layer_geometry.py`，本轮调用与参数为该目录的 `audit.py`；原 18 条对应关系由 `finalize.py` 复核。

使用 FreeCAD 1.1.4 所带 Python（含 Part、MeshPart、Shapely），在仓库根目录运行检查：

```sh
python hardware/enclosure/check-speaker-duct.py \
  --model hardware/enclosure/Discora.FCStd \
  --baseline tmp/cad-p3-duct-outlet/baseline.FCStd \
  --output tmp/cad-p3-duct-outlet/duct-geometry.json
python hardware/enclosure/check-assembly.py \
  --model hardware/enclosure/Discora.FCStd \
  --output tmp/cad-p3-duct-outlet/assembly-paths.json
```

图册尚未重绘本版内腔和出口；本版结构与打印以正式 CAD、上述成套文件及本记录为准。

GUI 复核状态：解锁后已在 Bambu Studio 打开最终 P2／P3 3MF，核对两者不同的支撑设置并重新切片，界面均未出现未支撑区域告警。查看 P2 第 200、260 层附近的出口与斜顶，确认孔内没有原饰片和连接筋阻挡，树支撑可从后壳内侧接近；查看 P3 首层、第 90 层及第 137–138 层，确认双声腔背面直接贴板，导管斜顶收口和外侧支撑与逐层分析一致。窗口最终停在 P3 第 138 层（27.6 mm），下限第 1 层、完整走线、走线类型配色。截图保存于上述临时目录的 `bambu-p2-layer-*.png` 和 `bambu-p3-layer-*.png`。GUI 重切显示 P2 8h36m／282.42 g、P3 5h37m／180.86 g；未覆盖已经审计的 3MF，表中仍记录保存文件的 CLI 数据。原生 CAD 应用中的最终外观回读尚未完成；声道、装配和逐层检查证据仍以正式模型及报告为准。
