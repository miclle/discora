# ADR-0042：P3 安装框斜边与永久承接筋

日期：2026-11-14。状态：已实现，CAD、网格、拆装和逐层切片检查通过；完整件打印与声学效果待实测。替代 ADR-0041 初版 P3 打印文件，保留其出线和封边设计。P2 不变，不再打印试片。

## 问题与改动

[原 18 条告警审计](../records/2026-11-14-p3-overhang-audit.md)定位了两处安装框后缘和 8 个螺柱底端；每个螺柱在切片器中计入两次。不能通过隐藏告警或在声腔内生成难拆支撑解决。

- 安装框后缘改为约 **39°** 的对称斜边：在 Y=52 mm、Z=34／118 mm 处从上下腔壁逐层长出，到 Y=18 mm、Z=76 mm 合拢。每 0.20 mm 层的横向推进约 0.247 mm。原前部入口和 Y≤13 mm 的安装界面不变，合拢发生在座板背面过渡之前。
- 每个螺柱增加一条 **45° 永久斜筋**。斜筋从已有框壁向螺柱后端逐层增长，Z 向包络 8 mm，Y=21.4～34.5 mm；按原盆架避让轮廓切除内侧，并保留原盲孔。它是零件本体，不需要拆除。
- 逐层复查发现原座板背面还有约 80.94 mm 的长桥接走线。座板背面改为沿盆架开口向外扩展的 45° 过渡，原座面、开口及盲孔保持不变。
- 两侧声腔翼部前端原有台阶也产生约 74.94 mm 的长桥接走线。在内部增加 45° 短过渡，长度 3 mm，取消突变。侧导音孔位置、形状、P2/P3 接口及外部包络保持不变。

不把整个安装框延长到背板。**Y=52～60 mm 的原后方 8 mm 导音通路保持原几何**，左右主腔与对应侧通道继续连通；左右腔体在封闭预期出口后仍互不连通。出线、封堵和拆卸工艺沿用 [ADR-0041](0041-p3-speaker-sealing-and-wire-exits.md)。

## 保留已通过试装的接口

- 安装座前部 Y≤13 mm、喇叭入口、盆架避让及喇叭占位保持。
- 8 个原 Ø8 mm 螺柱包络内的几何差集为零；36×70 mm 孔距、Ø2.3 mm 导孔、10.5 mm 孔深、1 mm 盲底不变。
- 原 0.5 mm 盆架避让空间没有被新增筋侵入，喇叭模型与 P3 无碰撞。
- 原双芯线预留路径无碰撞，两个出线孔及外侧封堵槽不变。
- 仅 `LDriverFrame`、`RDriverFrame`、`LChamber`、`RChamber` 和合并后的 `SpeakerCarrier` 改变；其余保存的形状不变。左右改动均镜像。

## 切片与逐层证据

Bambu Studio **02.09.01.70**，P2S 0.4 mm、Generic PLA、0.20 mm、3 层壁、15% gyroid，保持原有自动树支撑／仅底板／仅关键区域、30° 阈值、0.20 mm 顶部间隙和 5 mm 外侧 brim。没有支撑屏蔽体，也没有降低告警检测标准。

| 检查 | 结果 |
| --- | --- |
| 原 18 条未支撑提示 | 全部消失，切片器区域告警为空 |
| 01、02：两侧安装框后缘 | 第 54 层不再生成原 83.6 mm 悬空直边，改为逐层合拢 |
| 03～18：8 个螺柱，每个两条提示 | 第 206 层原底端占位被第 205 层材料覆盖，覆盖率均为 100% |
| 座板背面／翼部前端 | 第 249／271 层原长桥接消除 |
| 全层检查 | 287 层；无新增无支撑孤岛，无新增超过原 30° 判据的显著悬挑区域 |
| 安装框区域全层走线 | 无超过 1 mm 的无下层承接 `Bridge`／`Overhang wall` 线段 |
| 首层 | 左右背板各 285／286 条底面挤出移动，直接贴板 |
| 声腔及出线孔内支撑 | 均为 0 条；外侧支撑保留 |
| 网格与构件 | 7,244 个三角面、闭合网格；三个主体各为一个有效实体 |
| 碰撞与拆装 | 无非预期静态碰撞，既有七条拆装路径检查通过 |
| 时间与耗材 | **5h 4m 14s，161.60 g** |

逐层比较以网格截面和实际 G-code 为依据：采用接近层中面的截面，微量向下偏移避开共面三角形；以 0.35 mm 相邻层增长包络对应现有 0.20 mm／30° 判据，排除面积不超过 0.05 mm² 的几何噪声，再与修改前逐层比较。螺柱和安装框另外做明确的承接与走线检查，不仅依赖告警数量。

外侧支撑的部分走线次序／线段发生变化，不能声称支撑 G-code 完全相同；完整线段扫描确认没有进入声腔或出线孔。现存第 186 层约 3.51 mm² 的外侧独立起印区有支撑覆盖，与修改前相同。**侧孔原有约 44.6 mm 的顶缘跨距保留**，它不属于本次 18 条告警；实际桥接下垂、孔径、PLA 层间强度和声音仍须整件验证。没有发送打印任务。

结构化证据：

- [几何、接口和导音通路](../../hardware/enclosure/p3-self-support-geometry-checks.json)
- [287 层与原 18 条逐项对应](../../hardware/enclosure/p3-self-support-layer-checks.json)
- [首层、支撑与出线孔走线](../../hardware/enclosure/p3-self-support-print-checks.json)
- [网格](../../hardware/enclosure/p3-self-support-mesh-checks.json)、[侧口](../../hardware/enclosure/p3-self-support-port-checks.json)
- [整机几何](../../hardware/enclosure/validation.json)、[拆装路径](../../hardware/enclosure/assembly-paths.json)

## 正式模型和打印文件

- 正式 CAD：`hardware/enclosure/Discora.FCStd`。
- 重建入口：`hardware/enclosure/build.FCMacro`；本次几何集中在 `speaker_print_geometry.py`，接口及通路检查为 `check-p3-self-support.py`。
- STL：`tmp/cad-p3-self-support/print/SpeakerCarrier.stl`。
- 已切片 3MF：`tmp/cad-p3-self-support/SpeakerCarrier/Discora-P3-Self-Support.3mf`。内含本次核对的 G-code 和支撑参数覆盖标记。
- 切片日志、全层分析脚本和关键层叠图 `verified-layers.png` 均保存在 `tmp/cad-p3-self-support/`。
- P2 继续使用 `tmp/cad-wide-chambers/RearShell/RearShell.3mf`。旧 P3 文件仅保留为历史证据。

各 JSON 记录同一最终 CAD 的 SHA-256。现有图册未重绘这些内部斜面，当前结构和打印文件以本记录及正式 CAD 为准。
