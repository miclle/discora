# ADR-0044：P2 圆角矩形外口

日期：2026-11-14。状态：已实现，CAD／装配／切片检查通过；完整件打印与声学待实测。

> 后续更新：[ADR-0045](0045-trapezoid-exterior-outlets.md) 将 P2 改为圆角梯形及连续内斜面，并调整 P2 支撑设置。本页尺寸、打印文件与证据保留为 ADR-0044 历史阶段；P3 仍保持 ADR-0043。

用户认为 ADR-0043 的尖头五边形外口不协调，授权将 P2 外口改成圆角矩形，在壳壁内过渡回原内口。本版只调整 P2 出口；P3 继续使用 ADR-0043 的独立转弯导管及原打印文件。

## 结构

- 两侧外口镜像，外表面为 **25 mm（Z）× 34 mm（Y）、R3.5** 圆角矩形；范围 Z=52.5–77.5、Y=28.5–62.5，齐平于原 X=±85 侧壁，不增加外凸装饰圈。
- 外口向内 0.5 mm 收至 24×33 mm、R3，然后在原 5 mm 壁厚内逐渐过渡回五边形内口。内口仍沿 P3 管口法向放大 1 mm，面积约 **482.11 mm²**；外口约 **839.48 mm²**。过渡不侵入 P3 的 400 mm² 出口投影，不增加饰片、连接筋或倒扣。
- P2/P3 的 **0.7 mm** 滑动间隙保持。P3 整体及其构造源与修改前一致，因此安装座、盲孔、出线孔、后腔和内部斜顶导管均保持。
- 最初 25×31 mm 候选在圆角收口处出现两段约 1.5 mm、下层承接不足的走线。最终沿 Y 向前扩展 3 mm，使壁内过渡更缓；没有通过增加难拆支撑来掩盖该问题。外观正视仍能看到内侧五边形喉口，外表面的边界已为圆角矩形。

## 验证

证据：[圆角出口检查](../../hardware/enclosure/p2-rounded-outlet-checks.json)、[整机检查](../../hardware/enclosure/validation.json)、[拆装路径](../../hardware/enclosure/assembly-paths.json)。

- P2 为有效单实体，导出的 STL 闭合；左右镜像差集为零，出口邻域之外的 P2 几何保持，P3 整体与其他成品保持。构造源在出口区域与保存的合并后壳一致。
- 沿 5 mm 壁厚检查实际开口面积与完整内口投影，并检查连续投影体积，确认没有缩颈遮挡；内口至外口面积逐渐增加。整机静态碰撞与七条拆装路径检查通过。
- P2 共 **440 层**。相对 ADR-0043，未发现新增面积超过 0.05 mm² 的显著悬挑区或无承接孤岛；出口范围内没有超过 1 mm 的无下层承接桥接／悬垂走线。相邻层增长包络仍为 0.35 mm，未放宽判据。
- Bambu Studio 2.9.1.70、P2S 0.4 mm、Generic PLA、0.20 mm，自动树支撑、30°、“仅关键区域”，允许支撑落在后壳内侧，沿用原设置。保存的切片区域告警为空，预计 **8h 36m 25s／281.62 g**。
- 解锁后展示圆角外口；最后一次间隙修正后，重新打开最终 3MF 并在 GUI 切片，核对第 319–322 层及内侧开放支撑，界面没有出现未支撑区域告警。最终停在第 322 层的内侧斜视图。GUI 显示约 8h36m／281.62 g，没有覆盖已审计的 3MF，也未发送打印任务。
- 过渡的两个内角以独立贯通切除修正，切除轮廓使用 1.001 mm 偏移（名义间隙 1 mm，额外 0.001 mm 避免重合面布尔残留）；11 个局部薄片及连续投影均复核名义 482.11 mm² 内口无侵入。外口尺寸不变。

支撑仍存在于开放后壳区域，实际拆除力与表面质量待完整件验证。此次调整不构成声学调谐或频响验证；P3 的相关边界沿用 ADR-0043。现有图册尚未重绘本版外口。

## 文件与复现

- 正式模型：`hardware/enclosure/Discora.FCStd`。
- P2 STL：`tmp/cad-p2-rounded-outlet/print/RearShell.stl`。
- P2 3MF：`tmp/cad-p2-rounded-outlet/RearShell/Discora-P2-Rounded-Outlet.3mf`。
- P3 保持：`tmp/cad-p3-duct-outlet/SpeakerCarrier/Discora-P3-Duct.3mf` 及对应 `print/SpeakerCarrier.stl`。
- 几何源：`speaker_duct_geometry.py`，重建入口仍为 `build.FCMacro`。
- 新检查器：`check-rounded-outlet.py`；逐层检查器：`slice_layer_geometry.py`。本轮基线、构建／切片／全层审计调用与日志保存在 `tmp/cad-p2-rounded-outlet/`。

使用 FreeCAD 所带 Python，在仓库根目录运行：

```sh
python hardware/enclosure/check-rounded-outlet.py \
  --model hardware/enclosure/Discora.FCStd \
  --baseline tmp/cad-p2-rounded-outlet/baseline.FCStd \
  --output tmp/cad-p2-rounded-outlet/geometry-checks.json
```
