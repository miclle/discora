# Discora

> **Discora — Bring optical discs back to life.**  
> 基于 ESP32-S3 的低成本、独立运行、开源光盘播放器与刻录控制器探索项目。

[English summary](#english-summary) · [需求](docs/requirements.md) · [架构](docs/architecture.md) · [硬件](docs/hardware.md) · [组装](docs/assembly.md) · [验证计划](docs/validation.md) · [路线图](docs/roadmap.md)

## 为什么做 Discora

许多笔记本光驱依然可以工作，却依赖 PC 或操作系统。Discora 希望通过价格低廉的 ESP32-S3 MCU，以 USB Host + SCSI/MMC 命令直接控制光驱，让它成为独立的 CD 音乐播放器，并进一步探索 CD-R/CD-RW 刻录能力。

这是一个**独立项目**，不依赖树莓派、Linux 或其它既有产品方案。Linux 只允许作为开发阶段的测试工具；目标设备运行 ESP-IDF 裸机式嵌入式固件（FreeRTOS），**不需要 Linux**。

## 项目边界与状态

| 功能 | 目标 | 状态 |
| --- | --- | --- |
| ESP32-S3 启动与日志 | M0 基线 | 已完成一次烧录与 UART0 启动实验 |
| USB Host 识别光驱 | INQUIRY / TEST UNIT READY / REQUEST SENSE | 已识别 UJ-898 / HC10，61.2 秒连续 13 次 TUR 就绪；完整 M1 验收待完成 |
| 读取音乐 CD 曲目 | READ TOC | bench-tested：本张 CD 取得 13 条音频轨及 LBA；详见实测记录 |
| CD-DA 数字音频读取 | READ CD | bench-tested：600 秒顺序读取 / 105.84 MB 与电脑完整摘要一致、软件缓冲零欠载；寻道有成功与失败窗口，稳定性未验收，实验默认关闭 |
| 双声道模拟音频 | I²S → 立体声 DAC | bench-tested：当前 GPIO15/16/7、PCM5102A 与原功放完成约 60 秒原始立体声 CD，用户确认两边清晰；完整稳定性未验收 |
| 轻触按键播放／暂停 | 四键 profile GPIO1 → 状态切换 | bench-tested：0.12.5 用户确认实体播放、暂停正常；长按等专项场景待验收，见[四键控制](docs/playback-controls.md) |
| 轻触按键退盘 | 四键 profile GPIO41 → USB 退盘命令；旧查询默认 GPIO7 | bench-tested：0.12.5 用户确认实体退碟正常；退碟 CSW 未捕获，各状态及重插盘场景未完整覆盖，见[接线](docs/eject-button.md) |
| 轻触按键上一曲／下一曲 | 四键 profile GPIO2／GPIO42 → 播放器换轨 | bench-tested：0.12.5 用户确认实体前后换轨正常；暂停保持及首尾循环的实体按键场景待专项验收，见[接线与配置](docs/track-buttons.md) |
| OLED 曲目与播放状态 | GPIO10 SDA／GPIO11 SCL → SH1106 | bench-tested：当前四键有声版已启用，用户确认无介质画面清晰完整；动态显示待验收，见[显示说明](docs/oled-display.md) |
| CD-R/CD-RW 刻录 | 测速、写入、封盘、校验 | 研究目标；可行性待测 |
| DVD 读取/刻录 | 可选扩展 | 不在首版范围 |

**请勿把技术可行性推断、其它项目的成果或 Linux 测试结果当作 Discora 的实测结论。**

**2026-11-07：CD → ESP32-S3 → PCM5102A → TPA3118D2 → 双喇叭的基础立体声链路已调通（bench-tested）。** 当前主控 COM 尾号 8636，更换 GPIO7→DAC DIN 的连接后，右声道及双声道低音测试出声；随后第 1 轨原始立体声连续播放约 60 秒，用户确认左右都有清晰音乐、无明显杂音，日志写入错误与软件欠载均为 0。此前 USB 掉线的根因、整轨／整盘及冷启动、重复启停稳定性仍未验收。详见[对照与定位记录](docs/records/2026-11-07-cybertrack-audio-crosscheck.md)，早期失败保留在[无声排查记录](docs/records/2026-11-05-dac-no-sound.md)。

随后旧候选长时播放暴露软件欠载停播。`0.11.0-buffered` 新增可选 **2 MiB PSRAM 队列、3 秒预填、欠载自动恢复和读取耗时统计**，当前 GPIO15/16/7 与 25% 数字幅度已纳入可复现 profile；正常配置不包含故障注入。构建与命令见 [CD 播放说明](docs/cd-player.md)，失败窗口、受控恢复与持续播放证据见[缓冲记录](docs/records/2026-11-07-buffered-playback.md)。

成功实验使用 GPIO15→BCK、GPIO16→LCK、GPIO7→DIN、DAC 模拟输出三线直连功放；仓库默认接线仍是 GPIO4/5/6。PSRAM profile 已包含 25% 数字幅度和关闭按键／OLED 的配置，但不包含早期候选的 60 秒自动停止或 bench 命令。0.12.1 可在其后叠加[四键 profile](docs/playback-controls.md)启用 GPIO1／2／42／41 控制，GPIO7 仍只接 DIN。当前部署与运行状态见[状态记录](docs/status.md)，不能将无叠加配置的默认构建视为同一固件。配置差异见[音频输出说明](docs/audio-output.md#已通过的接法与默认配置差异)。借用的 CyberTrack 板原固件及配置已恢复并校验。

## 初始实验硬件

- **主控**：ESP32-S3（具有可用 USB OTG/Host 引脚的开发板）。
- **首个目标光驱**：MacBook Pro 13-inch (Mid 2010) 拆机 **MATSHITA DVD-R UJ-898**，SATA/ATAPI 接口。
- **桥接**：现有 SATA → USB 适配器。必须验证 USB Mass Storage BOT 与 MMC 命令透传。
- **音频**：PCM5102A I²S 双声道 DAC；已与 TPA3118D2 功放及双喇叭完成上述短时试听。
- **供电**：光驱独立、足额的 5V 供电支路；主控与光驱共地，不让开发板 GPIO 或微弱 USB 输出直接负担光驱电机电流。
- **刻录输入**：以后可选 SD 卡上的 ISO / PCM 数据；当前未定型。

这只是**实验选型**，不是已验证的 BOM。详见 [硬件清单与风险](docs/hardware.md)。机身外形与竖装光驱布局见 [V4 顶部进碟与中央双喇叭 FreeCAD 概念模型](hardware/enclosure/README.md)；外观尺寸、爆炸图和侧剖见 [彩色整机图册（5 页 A3 PDF）及说明](docs/enclosure-drawings.md)。

## 从哪里开始

1. 阅读 [需求及验收标准](docs/requirements.md)，明确首版只验证播放。
2. 按 [光驱验证手册](docs/validation.md) 测试 UJ-898 + USB 桥接器能否读取 CD-DA、查询刻录能力；保存设备日志。
3. 安装 ESP-IDF 5.4，进入 `firmware/`，执行：
   ```bash
   idf.py set-target esp32s3
   idf.py build
   ```
   默认查询配置自动执行四种只读查询命令，并默认支持 [GPIO7 轻触按键退盘](docs/eject-button.md)（仅按下触发，默认查询配置已获用户实测成功反馈）；受限 READ CD 实验须手动启用，每次主控启动最多执行一次。可另选独立 [I²S 测试音诊断](docs/audio-output.md) 或默认 stopped 的 [CD 播放控制模式](docs/cd-player.md)；真实 CD 软件消费和接 DAC 的短时立体声播放已实测，完整稳定性仍未验收，刻录未实现。详见 [读取实测](docs/records/2026-10-31-m2-cdda.md)。
4. 按 [组装说明](docs/assembly.md) 核对 OTG、独立 UART0 和 VBUS 电源；准备好后再选择本项目串口执行 `idf.py -p <DISCORA_UART_PORT> flash monitor`。原生 USB 用于 Host 时不能同时当电脑日志口。
5. 完成 M0/M1 实测后再进入 CD-DA 和 I²S；详见 [路线图](docs/roadmap.md)。离线协议检查：`python3 firmware/tests/run_host_tests.py`。

## 技术取舍

- ESP32-S3 原生 USB 为 **Full-Speed 12 Mb/s**；CD-DA 立体声 PCM（44.1 kHz、16-bit）为约 **1.4112 Mb/s**，读取方向带宽理论上足够，但传输时序与兼容性需要验证。
- **刻录不等于普通文件写入**：必须实现 MMC 写入状态机、缓冲、同步与封盘；且 USB Full-Speed 可能无法满足光驱与介质允许的最低刻录速率。
- 参考 [ESP32_CD_Player](https://github.com/julpage/ESP32_CD_Player) 等已有实践，但不直接复制第三方源码；具体适配与许可证审核留待实现阶段。
- 以**可重现的实验数据**驱动硬件选型，不为尚未验证的功能设计复杂 PCB。

## 仓库结构

```text
discora/
├── AGENTS.md                   # 协作/Agent 开发约定
├── README.md                   # 项目入口
├── CONTRIBUTING.md             # 开发与贡献约定
├── LICENSE                     # Apache License 2.0（保留原仓库许可证）
├── docs/
│   ├── requirements.md         # 目标、非目标、验收
│   ├── architecture.md         # USB/SCSI/MMC、CD-DA、I²S 设计
│   ├── hardware.md             # 供电、选型、BOM
│   ├── assembly.md             # Host / UART0 / Hub 接线与首次上电
│   ├── validation.md           # 实验步骤与证据要求
│   ├── roadmap.md              # 分阶段实施计划
│   ├── research.md             # 参考项目和资料
│   ├── status.md               # 当前验证状态
│   ├── records/                # 带日期的软件/硬件验证记录
│   └── decisions/              # 设计决策记录
└── firmware/                   # ESP-IDF 只读 BOT 探测与主机侧协议测试
```

## English summary

Discora explores a **low-cost standalone optical disc controller** built around ESP32-S3. The first goal is to read CD-DA from a USB-attached SATA/ATAPI drive and produce stereo I²S audio without a Linux computer. CD-R/CD-RW writing is a later **unverified research milestone**, subject to USB bridge compatibility and minimum write-speed constraints.

**Status:** flashing, UART0, Full-Speed hub/drive enumeration and read-only BOT queries have been bench-tested with MATSHITA UJ-898 firmware HC10. Thirteen consecutive TEST UNIT READY checks passed over 61.2 seconds; long-running, cold-start and reconnection qualification remain open. Formatted TOC was bench-tested on one music CD (13 audio tracks); A bounded READ CD probe (disabled by default) matched PC reference hashes for one/eight sectors and measured a 256-sector burst at 739,858 bytes/s. A 600-second paced software-buffer run transferred 105.84 MB with zero underruns and a full-window PC hash match. Random seeking failed; A standalone UART-controlled I²S tone diagnostic and playback-control core are implemented and build-tested; The actual CD source is integrated with UART controls and a software-clock sink, including a 60.47-second paced window; the I²S adapter is build-tested only and DAC output remains unverified. Writing is not implemented. See [current evidence](docs/status.md).

`0.12.1-buttons-row` adds an opt-in audio profile with play/pause (GPIO1), previous (GPIO2), next (GPIO42), and eject (GPIO41), preserving DAC DIN on GPIO7. Navigation arms continuous playback and preserves pause. Host checks and builds are separate from physical button acceptance; see [controls](docs/playback-controls.md) and [current deployment status](docs/status.md). The default build remains query mode.

## License

本仓库原有 [Apache License 2.0](LICENSE) 保持不变。外部项目、数据手册、第三方元件与音频资料分别遵循各自的许可或版权要求。
