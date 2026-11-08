# 2026-11-08：四键控制实现与软件验证

> 后续引脚集中到右排 J2-4～7，版本 0.12.1；新配置、图文及产物见[连续排针修订](2026-11-08-buttons-row.md)。下文保留 0.12.0 初版软件验证。

## 结果与设备边界

源码 `0.12.0-four-buttons` 已实现播放／暂停、上一曲、下一曲和可配置引脚的退碟。**implemented：主机检查与四配置 ESP32-S3 构建通过；本轮未部署，实体按键及有声控制未验收。** 用户确认按键尚未接线，GPIO7 只接 DAC。电脑串口清单未发现 Discora USB-UART，仅有系统／蓝牙端口，因此没有打开设备、烧录或执行播放／退碟。用户随后明确选择先完成软件交付，硬件接线与实测留待后续；本轮软件交付范围已完成。

最后有证据的板上应用仍是[单次恢复候选](2026-11-08-track13-followup.md)（0.11.3、ELF `f764a9ea…`）；这是历史部署证据，未在本轮重新连接核实。不将该版本的三轮整盘完成记录当作四键版验收。

## 实现范围

- 四键有声 overlay：GPIO4 播放／暂停、GPIO5 退碟、GPIO8 上一曲、GPIO9 下一曲，常开接地。保留 GPIO15／16／7 音频、2 MiB PSRAM、3 秒预填和 25% 幅度。
- `toggle` 与实体播放键共用核心：停止开始连续播放，播放／预填／欠载／自动重缓冲时暂停，暂停从保留位置恢复；连续 EOF 排空期间暂停跨曲，fault 不自动恢复。
- `next`／`prev` 及实体键开启连续模式，暂停中选轨仍暂停且不请求新曲数据；首尾不循环。`track N` 保留单轨诊断语义，`play` 保留原开始／恢复语义。
- 前三键复用原消抖核心，30 ms、长按单次、上电先释放，多键重叠后全部稳定释放。目录失效或 fault 不保留手势。
- 退碟保留原 USB client 流程和输出关闭确认，仅 GPIO 可配置；旧查询默认 GPIO7，四键有声明确覆盖为 GPIO5。
- 新增生产代码共用的引脚冲突检查，以及四键 CI 构建矩阵；未提交、推送或触发远端 CI。
- 接线与验收入口：[四键控制](../playback-controls.md)，决策：[ADR-0022](../decisions/0022-four-button-controls.md)。

## 软件验证

`python3 firmware/tests/run_host_tests.py` 完整通过（ASan／UBSan），包括新增按键／状态语义及既有 USB、缓冲、恢复、OLED、I²S fake driver 和 500000 步独立 FIFO 检查。新增控制测试覆盖：

- 播放／暂停键抖动、长按、上电按住、多键重叠和无盘／故障期间手势丢弃。
- 暂停时在途源回复保留但不消费、恢复字节顺序／代次／源位置不重置、恢复低于预填门槛时等待补缓冲。
- 暂停中换轨不派发读取、旧代次回复拒收、首尾拒绝不改变暂停、换轨保持连续模式。
- 连续 EOF 排空的暂停／恢复、单音轨播放到盘尾不循环，以及欠载和自动重缓冲期间暂停优先。
- 29 组编译期引脚配置：合法四键、功能关闭、I²S、OLED、换轨键、按键互相冲突及不允许的 GPIO。

`python3 firmware/tests/player_bench_test.py` 的 15 项离线检查通过。首次新增恢复测试在队列低于预填门槛时错误期待立即消费；修正测试为先补缓冲后检查连续字节，未改变生产预填行为。最终完整检查通过，不将失败的初次测试记为成功。

ESP-IDF v5.4 下，每种配置使用独立 sdkconfig 和 build 目录，均执行 `idf.py set-target esp32s3` 与 `idf.py build`：

| 配置 | 叠加 defaults | 结果 |
| --- | --- | --- |
| 四键有声候选 | sdkconfig → cd-player-i2s → cd-player-psram → usb-diagnostics → cd-player-seek-recovery → cd-player-buttons | PASS |
| 默认查询 | sdkconfig | PASS；旧 GPIO7 退碟默认保留 |
| 原 CD I²S | sdkconfig → cd-player-i2s | PASS；原 GPIO4/5/6 音频与 GPIO7/8/9 按键，播放键关闭 |
| 四键软件时钟 | sdkconfig → cd-player-clock → cd-player-buttons | PASS；无声音 |

候选与上一恢复候选的配置对照仅启用三个按键开关、加入 GPIO4／5 参数；USB A/B 开关因 Kconfig 互斥而不再输出（仍关闭）。I²S 引脚、增益、PSRAM、恢复、USB 诊断不变，OLED 和故障注入关闭。未修改 USB 命令、读取恢复预算、供电或 CAD。

候选应用大小：383056 字节。应用 SHA-256：`c009b164923b4742a937eafc86304b10bc7ec2d88db7ea64e4c547a1ac289dc4`；ELF SHA-256：`1c95b2f3caf7d7a4ec055f4089f000caf9c8e39edda7f2e881b1b035590fb04a`。

原始构建脚本、四配置日志、生成配置、产物、配置差异及主机测试日志保存于忽略目录 `.local/bench/2026-11-08-four-buttons/`；源码摘要见该目录 `source-manifest.json`。初次测试日志另存 `host-tests-initial.log`。产物未加入 Git。

## 后续硬件阶段（用户明确留待后续）

1. 用户按 GPIO4／5／8／9 接线并连接 COM／光驱后，重新确认主控、原固件及分区；备份后部署匹配的四键候选并独立校验。
2. 先检查上电 stopped、按键初始化和 TOC，再验证有声播放／暂停／恢复、前后换轨、暂停中换轨、边界及长按／重叠。
3. 播放中退碟的输出关闭顺序、真实 CSW 和实际退出分开确认；重插盘不自动播放。
4. 保留约 40 ms DMA 丢弃、换轨预填间隔和等待在途 USB 命令的已知限制；软件通过不代表无缝暂停或机械动作通过。
