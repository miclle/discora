# 光驱实测 CAD 适配交接

- **状态：complete**，仅指本轮 CAD 适配与文档交付；实物装配未验收。
- **更新时间：**2026-11-12T09:12:17+08:00。
- **仓库：**[miclle/discora](https://github.com/miclle/discora)，分支与目标分支均为 `main`。
- **CAD 交付 HEAD：**`c36ea18858fe6f32cbb7d4a73a8b31238f89ed01`（`feat(enclosure): fit measured rear-wall drive mount`）。
- **上游／最近已推送：**记录时 `origin/main` 和实际远端 `refs/heads/main` 均为上述提交，ahead/behind 为 0/0。
- **本文所在文档提交：**用 `git log -1 --format=%H -- docs/current-work-handoff.md` 解析；它在上述 CAD 提交之后，只刷新相关文档。不要将 CAD 基线 SHA 当成文档提交 SHA。
- **当前整理者／下一接手者：**本轮文档整理者／未指定。
- **传递方式：**`origin/main`；接收者需有仓库读取权限，并取得包含本文的文档提交。CAD、测量照片、检查报告及图册已在远端 CAD 提交及其历史中，可独立获取；临时切片产物不作为交接依赖。

## 目标与完成范围

按 UJ-898 的照片及实测数据调整光驱安装，保持光驱和碟口居中、外壳左右对称，以后壁保护垫、中央底托和两螺钉压条减少安装零件。用户最终选择外宽 170 mm；当前整机为 170 × 93 × 243.263 mm，包含脚垫和提手，不含脚垫高 240.263 mm。

已提交的测量记录为 `0c3a117`，CAD、关联图册和检查报告为 `c36ea18`。本轮文档刷新校正图册摘要、背锁工具长度、历史证据归属及复查命令，并将实物待验项接入现有路线图；没有重新建模或修改固件。

本范围没有进行中的实现或技术阻塞。后续实物打印、配合、走线、供电、载板集成、声学和整机验收属于[路线图 M5](roadmap.md)，本交接不将 M5 标为完成，也不自动启动打印或设备测试。

## 工作区与交付边界

文档整理开始时，暂存、已修改、未跟踪和未推送项均为空。本文对应提交仅涉及以下文件：

- `README.md`、`README.en.md`：同步光驱安装结构及打印网格导出入口。
- `hardware/enclosure/README.md`：区分当前／历史证据，补充光驱复查及交接入口。
- `docs/enclosure-drawings.md`、`docs/enclosure-printing.md`：修正版本、工具长度与基线复核方法。
- `docs/roadmap.md`：补充本版实物试装的完成条件。
- `docs/current-work-handoff.md`：本记录。

本地 `tmp/` 中 STL、3MF、G-code 和基准模型被 Git 忽略，接收端不保证存在；按[打印说明](enclosure-printing.md#重现)重建。未发现需随交接另传的未提交源文件。接手时重新检查工作区和远端状态，保护此后其他任务产生的修改。

## 已定取舍

| 项目 | 当前决定及保留边界 |
| --- | --- |
| 方向与外宽 | 竖装、碟口向上、铭牌底面朝后壁；170 mm 外宽、两侧壁各 5 mm。光驱居中后每侧 16 mm，实测线缆外伸 14.5 mm 后余 1.5 mm，不采用压缩到 12.5 mm 的方案。 |
| 固定 | 后壁留 1 mm 保护垫空间，中央底托承重，压条两枚名义 M2×10；不在光驱钻孔。保护垫压缩、压条保持力和薄盖变形须试装。 |
| 测量解释 | 平放碟口朝人、盘面朝上时左深 130、右深 95，右后斜边；竖装后测量左侧映射至机箱 +X。主体碰撞和维护检查使用填满的 128×10.8×130 最大包络。 |
| SATA | 外壳 37.7×7 mm、后伸 20.4 mm；边缘定位给出的跨度为 38.8 mm，两者差 1.1 mm，保留原始读数并用 38.8 mm 净空覆盖。上下偏置未测，显示居中只是示意，独立净空覆盖后端完整 9.5 mm 厚度。 |
| 维护 | 先取前壳、P3、压条和电池，释放线缆，再进入接头维护位置并侧转取出光驱；两螺钉固定不等于无需拆其它部件。具体位移见 ADR-0035。 |
| 关联布局 | DAC 左移 12 mm；20 个既有硬件／操控对象保持。侧孔居后壳侧视轴 Y=49，声腔深度增至 57.5 mm，旧声学判断不直接继承。洞洞板候选尚未针对当前版本闭合。 |

## 验证证据

当前 FCStd SHA-256：`fb24c86b81e000e9f2db58d3b2802ead2c5aad04e26171616b4c4fc6266ced1e`。

以下几何及切片结果来自已提交报告，本次只复核报告内容、源码入口和摘要关联，未重新运行 FreeCAD 或切片器。

| 检查／证据 | 结果与限制 |
| --- | --- |
| `hardware/enclosure/validation.json` | 33 个成品有效，三主体连续；8 项镜像差集为零。报告单列旋钮压配筋的设计过盈；不是实物验收。 |
| `hardware/enclosure/drive-mount-checks.json` | `all_pass=true`；最大包络、压条、接头与线缆净空通过，20 个对象差集为零，四键与旋钮面序保持。 |
| `hardware/enclosure/assembly-paths.json` | `all_pass=true`；平移段保守连续扫掠，光驱抬升 31 姿态、侧转 61 姿态，前壳 1 mm 步长；离散采样不是连续运动证明。 |
| `hardware/enclosure/print-checks.json` | 11 件闭合包络网格；四盘单色切片返回码均为 0，四键和旋钮另有双色证据。未发送打印，未试装。 |
| 模型和基线摘要复核 | 本次用 Python `hashlib.sha256` 读取 FCStd；9 份当前检查报告的模型摘要一致，图册 `geometry.json`／`color-render.json` 的模型与建模脚本摘要也一致。`git show 0c3a117:hardware/enclosure/Discora.FCStd` 的摘要匹配光驱报告的基线。 |
| FreeCAD GUI 读回 | 本版未完成；`drive-model-metadata-checks.json` 的资源与元数据检查不代替 GUI 关闭、重开后的几何与颜色读回。 |
| 本次文档验证 | 290 个本地 Markdown 链接有效，引用脚本／提交核对通过，`git diff --check` 通过；未运行与纯文档修改无关的固件构建、几何重算、切片或硬件测试。 |

9 份当前报告为 `validation.json`、`assembly-paths.json`、`drive-mount-checks.json`、`drive-side-port-checks.json`、`fastener-checks.json`、`print-checks.json`、`button-checks.json`、`oled-checks.json` 和 `drive-model-metadata-checks.json`，均在 `hardware/enclosure/`。历史 `rear-thickness-checks.json` 等应保留原模型摘要，不能批量改成当前摘要。

## 风险与未测项

- 底面台阶的纵向范围、前端加厚长度、接头上下偏置和完整三维线缆弯曲路径未测；不得借近似斜边、台阶或显示位置缩小实际净空。
- D/E/F 与接头定位存在原始测量差值，见测量记录；不得静默改写原始数据。
- 实际保护垫、螺钉、打印补偿、长刀杆操作、薄盖受压、维护动作、进退碟和热性能未验；CAD 中最小间隙不代表打印后保证间隙。
- 未完成本版 GUI 读回，未做实物装配和声学验收；本轮没有复测固件播放或电源系统。
- `check-drive-mount.py` 默认输出会覆盖受版本管理的报告；不带 `--baseline` 时会丢失图册追溯所需的比较字段。日常复查指定 `--output tmp/drive-mount-current-checks.json`，完整比较按打印说明恢复真正的旧模型。

## 优先阅读与接手

1. [实测照片和 A–F／SATA 原始记录](../hardware/MATSHITA-UJ-898/README.md)：测量基准、矛盾值和未测项。
2. [ADR-0035](decisions/0035-measured-drive-rear-wall-mount.md)：安装、净空和拆装取舍。
3. [外壳说明](../hardware/enclosure/README.md)、[打印与装配](enclosure-printing.md)、[图册说明](enclosure-drawings.md)：当前尺寸、流程和证据链。
4. [工程状态](status.md)与[路线图](roadmap.md)：整机有效待办与验证顺序。

本 CAD 范围已完成，没有待恢复的建模步骤。接收端首先在仓库根目录执行以下只读核对，确认包含本文的提交位于当前历史中、CAD 提交可达且模型摘要匹配；如果后续提交已改变模型或范围，先更新交接结论，再选择路线图上的下一项。

```bash
git status --short --branch
git log -1 --format='%H %s' -- docs/current-work-handoff.md
git merge-base --is-ancestor c36ea18858fe6f32cbb7d4a73a8b31238f89ed01 HEAD
git rev-list --left-right --count 'HEAD...@{upstream}'
git ls-remote origin refs/heads/main
python3 -c 'from pathlib import Path; import hashlib; print(hashlib.sha256(Path("hardware/enclosure/Discora.FCStd").read_bytes()).hexdigest())'
```

`origin/main` 是本地跟踪引用，判断远端交付状态还须对照 `git ls-remote`，不能只看本地 ahead/behind。上述检查不自动拉取、重置或覆盖接收端的改动。

## 环境与历史

已记录的建模环境为 FreeCAD 1.1.4；重算需要可导入 `FreeCAD`、`Part`、`TechDraw`、`MeshPart` 的 Python，通过 `DISCORA_FREECAD_PYTHON` 指定。彩色投影另需 `numpy`、`Pillow`；排版需 `reportlab`、`svglib`、通过 `DISCORA_DRAWING_FONT` 指定中文字体，逐页渲染使用 Poppler 的 `pdftoppm`。工具安装路径和字体需在接收机器配置，未将个人路径或凭证写入仓库。

切片证据来自 Bambu Studio 02.09.01.70 的 P2S / 0.4 mm 配置；用户设备为 P2SC，未连接设备验证。切片器及配置可用 `--bambu`、`--profiles` 指定。固件工具链和实体硬件不属于本次文档接收的前置条件。

此前无仓库内交接文件。本记录以已推送 CAD 提交为基线；关闭条件为相关文档提交可从 `origin/main` 获取且文档检查通过。后续实施与验收继续维护现有路线图，不在此另建第二份项目待办。
