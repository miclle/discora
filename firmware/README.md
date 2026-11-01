# Discora firmware

这是 **USB 光驱、CD 控制与独立 I²S 诊断固件**（`0.7.3-transfer-wait`），ESP-IDF 基线为 v5.4。默认执行基础查询和 READ TOC；可显式启用有界 READ CD 实验。单/8 扇区已与电脑参考摘要一致，600 秒顺序读取及软件缓冲已与电脑完整摘要一致；寻道仍有失败记录，完整重连/冷启动、I²S 和刻录尚待验收，见 [当前状态](../docs/status.md)。

## 构建

```bash
# 先安装并加载 ESP-IDF v5.4 环境
cd firmware
idf.py set-target esp32s3
idf.py build
```

原始实测日志、烧录前备份和构建快照须保存到仓库根目录的 `.local/bench/`（已忽略），不要放入 `build/`：`set-target` 可能触发 fullclean。

默认启用外部/多级 USB Hub，使用 UART0 115200 日志，并关闭主、次 USB console；原生 USB PHY 用于 Host。`sdkconfig.defaults` 只对新生成的配置提供默认值，旧 `sdkconfig` 应在 `menuconfig` 中核对这些设置。

## 连接与烧录（用户准备好后执行）

先读 [组装文档](../docs/assembly.md)，核对具体开发板与电源路径。运行 Host 时原生 USB 串口不能同时用于电脑日志，优先使用板载 USB-UART 或外接 3.3V 逻辑 USB-UART。只选择本项目串口，不使用其它项目已连接的设备。

```bash
idf.py -p <DISCORA_UART_PORT> flash monitor
```

端口是占位符；macOS 可能为 `/dev/cu.usbserial*`，Linux 可能为 `/dev/ttyUSB*`，以实际 USB-UART 枚举为准。若只通过原生 USB 下载，应用启动后该设备口可能消失，需从 UART0 查看日志。

## 当前行为

1. 启动输出 `Discora M2 CD-DA read-only probe`、应用版本、IDF 版本和 ELF SHA-256，便于关联实测日志。
2. 记录 USB VID:PID、速度、接口 class/subclass/protocol；只选 Full-Speed BOT（`0x50`），subclass `0x02` / `0x05` / `0x06`、alternate setting 0。
3. 记录 Bulk IN/OUT 端点与 MPS；固定 LUN 0，通过 INQUIRY 确认可用 CD/DVD 设备（PDT `0x05`）。不以 VID:PID 单独推断型号。
4. 每 5 秒执行 TEST UNIT READY，命令失败时发送 REQUEST SENSE；输出真实数据、CSW status/residue、耗时和 sense。无盘是可记录的设备状态，不是假装成功。
5. 介质就绪后执行两阶段 READ TOC（格式 0、MSF=0），输出曲目数、类型、起止 LBA 与 `MM:SS:FF` 时长。最多 99 条曲目；同一就绪周期最多尝试三次，失败不会发布部分目录。边界见 [ADR-0003](../docs/decisions/0003-formatted-toc-probe.md)。
6. Bulk 超时后 halt/flush；STALL、无效 CSW、phase error 按 [ADR-0002](../docs/decisions/0002-read-only-native-bot-probe.md) 处理。传输故障后停止查询，重新连接才再次探测。
7. 断连后等待 transfer 回调，释放接口并关闭 device handle；打印剩余内部 heap，供重复插拔时观察趋势。

普通查询、CBW、CSW 和控制传输截止为 3 秒，READ CD 数据阶段为 30 秒；取消后最多再等待 2 秒。IDF 的 EP0 控制传输没有公开取消接口；控制超时或取消未归还时保留缓冲并隔离设备，须拔下设备。它不是完整的自动恢复驱动。

固件没有写入/擦除/退盘命令，不查询多 LUN，不切换配置或 alternate setting。`medium ready` 只代表就绪；`TOC validated` 只代表本次目录通过解析，均不代表 PCM 读取或播放通过。

## 受限 READ CD 实验

默认关闭。先核对供电、桥接器和测试盘，再运行 `idf.py menuconfig`，选择 `Discora bench probes → Run one bounded READ CD probe per MCU boot`（`CONFIG_DISCORA_CDDA_PROBE=y`），重新构建/烧录。启动会输出 `CDDA probe enabled=0/1`，须核对配置。

- 每次 MCU 启动最多一次，TUR 状态变化、换盘或重连不重新触发；失败后先检查日志，不反复复位试错。
- 要求有效 TOC，选择足够长的双声道音频轨，每次 1–8 扇区、每扇区 2352 字节；拒绝数据轨、跨轨、lead-out、零/超量请求。没有任意 CDB 或 Data-Out 入口。
- 先读单扇区，再读同位置 8 扇区并重复；内部 SHA-256 一致后，最多读 32 批 × 8 扇区。合计最多 273 扇区，包含重复区域。内部自比不等于独立参考对照。
- 只输出元数据、长度、耗时、摘要和统计，不打印 PCM，不存入 Flash。
- 18,816 字节共享响应位于静态内部 DRAM，USB transfer 另由原生 Host 分配；不放在 task stack，不默认依赖 PSRAM DMA。

边界及首轮失败修正见 [ADR-0004](../docs/decisions/0004-bounded-cdda-probe.md)。短突发速率不代表整张盘稳定播放；环形缓冲已有软件消费实测，I²S 已有独立诊断实现，CD 播放仍待接入。

## 长时读取、寻道和缓冲实验

`CONFIG_DISCORA_CDDA_SOAK` 默认关闭，依赖短探测开关；短探测成功才进入扩展阶段。`menuconfig → Discora bench probes` 中可单独选择 12 位置寻道、完整首轨读取，以及 60–1800 秒的软件时钟缓冲测试（默认 600 秒）。每次启动最多一轮，默认失败后不自动重试；0.5.2 增加单独选择的单次恢复实验，见下文。选择未运行的阶段不会获得该阶段验收。

- 寻道：首/末/中间音轨各四个位置，每位置读两次 8 扇区、比较摘要并记录定位耗时。
- 完整首轨：从 INDEX 01 到排他末地址，按轨道边界拆分 READ CD，记录总字节、耗时、吞吐及全区间摘要。
- 缓冲：64 扇区 / 150528 字节内部 RAM，先填 48 扇区，再由独立任务按实际单调时钟以 176400 bytes/s 消费真实 PCM。生产/消费端分别 SHA-256，检查完整字节数、欠载、缓冲水位、跨轨次数及调度迟到；这是软件定时丢弃端，不是 I²S。
- 同时关闭 `Include the 12-position seek experiment` 与 `Include a complete first-track read from INDEX 01` 时，从短探测末尾 LBA 顺序衔接缓冲阶段，不回跳。日志明确 `seeks=not_run full_track=not_run`，不能声称寻道或完整首轨通过。
- 扩展阶段只每 10 秒输出进度，失败 CSW 和传输错误始终输出。PCM 不打印、不保存。

设计与当前实测边界见 [ADR-0005](../docs/decisions/0005-stream-and-buffer-bench.md) 和 [长时实验记录](../docs/records/2026-10-31-m2-stream.md)。

负向测试开关 `CONFIG_DISCORA_CDDA_UNDERRUN_TEST` 默认关闭：启动消费两秒后计划暂停生产 1200 ms，检查原有欠载/退出路径；negative-control PASS 与正常流 PASS 分开报告。本次在注入前遇到设备离线，未完成欠载验证，见 [负向记录](../docs/records/2026-10-31-m2-underrun.md)。

[直连配置](bench/otg-direct.defaults) 开启寻道和完整首轨、60 秒软件缓冲，负向注入关闭；0.5.0 的直连曾复现末轨命令失败及 sense 超时，见 [实测](../docs/records/2026-11-01-m2-otg-after-pc.md)。加载 defaults 时须使用独立 sdkconfig，避免已有缓存配置覆盖目标值。

## REQUEST SENSE 超时诊断

`0.5.1` 为 REQUEST SENSE 记录 CBW、DATA、CSW 阶段的结果和累计耗时。实验参数 `CONFIG_DISCORA_SENSE_DATA_TIMEOUT_MS` 默认 3000，仅在 CD-DA 实验开启时可配置到 30000；普通默认固件继续使用 3 秒。超时后仍等待 transfer 归还，未归还时隔离，不增加命令重放。

[sense-diagnostic.defaults](bench/sense-diagnostic.defaults) 沿用直连的同一寻道/整轨/缓冲工作负载，仅把 REQUEST SENSE 数据阶段上限设为 30 秒。CBW、CSW、控制传输仍为 3 秒，READ CD 数据阶段仍为 30 秒。这是诊断参数，不是已证实的修复；若未调用 REQUEST SENSE，成功读取不能归因于该参数。

## 有界多轮寻道

0.5.3 增加 `CONFIG_DISCORA_CDDA_SEEK_ROUNDS`（1–20，默认 1）和 `CONFIG_DISCORA_CDDA_SEEK_ONLY`（默认关闭）。[seek-rounds.defaults](bench/seek-rounds.defaults) 在短探测后最多执行 20 轮，每轮 12 个原有位置，每位置两次 8 扇区读取；不开启完整首轨或缓冲阶段，日志明确 `full_track=not_run buffer=not_run`。它不改变只读命令白名单，最多 480 次逻辑读取，另有短探测和全启动共享的至多一次恢复重放。

每个位置开始前检查 600 秒软截止；正在执行的读取仍按原有 USB / SCSI 截止结束。未完成全部位置即退出时记为失败，不把已通过的部分算作整轮完成。首次无法恢复的错误立即停止，重连不重新开始，恢复预算不会随轮次重置。每个位置记录 round / step / track / LBA；保留重复读取摘要和累计最长耗时。无错误时只能证明该工作负载正常路径，不能宣称错误恢复分支通过。

0.5.4 的 [seek-offsets.defaults](bench/seek-offsets.defaults) 额外启用默认关闭的 `CONFIG_DISCORA_CDDA_SEEK_VARY_OFFSET`。首轮保持原位置，后续轮次把轨内起始偏移加上 `997 × (round - 1)`，对有效 8 扇区起点数量 `span - 7` 取模；结果始终在该轨内。其目的是扩大取样范围，不能据此认定已绕过设备缓存。固定位置和变化位置结果见 [多轮记录](../docs/records/2026-11-01-m2-seek-rounds.md)。

## 寻道等待与单次恢复实验

[seek-wait.defaults](bench/seek-wait.defaults) 在 sense 诊断工作负载上增加每个寻道位置之前 1000 ms 的空闲间隔，不发送 SEEK，不重放失败读取。[seek-recovery.defaults](bench/seek-recovery.defaults) 保留这一间隔，再启用每次 MCU 启动最多一次的恢复机会。两个配置均使用 30 秒 sense 数据截止、12 个寻道位置、完整首轨及 60 秒软件缓冲。[seek-recovery-control.defaults](bench/seek-recovery-control.defaults) 仅取消预先间隔，保留相同恢复预算作为对照。各配置须使用独立 sdkconfig。

`CONFIG_DISCORA_CDDA_SEEK_WAIT_MS` 默认 0；`CONFIG_DISCORA_CDDA_SEEK_RECOVERY` 默认关闭。恢复要求有效失败 CSW、有效 sense `03/02/00`、连接和 transfer 状态正常、目录有效；预留一次预算后等待 1000 ms 并处理 USB 事件，再用一次 TUR 确认就绪，才重放相同 READ CD。断连、传输故障、就绪失败或其它 sense 都不会触发读取重放，重连不重新给予预算。该预算由所有 READ CD 阶段共享。

日志保留首次失败和 `recovery_reserved` / `recovered`，不能把恢复后完成当作首次无失败通过。先等待再读取的耗时分开记录，预等待不计入 read 延迟。主机测试覆盖准入和共享恢复编排，真实等待/恢复及阶段上板状态见 [实验记录](../docs/records/2026-11-01-m2-seek-recovery.md)，策略边界见 [ADR-0007](../docs/decisions/0007-bounded-seek-recovery.md)。

## 不连接设备的协议检查

从仓库根目录执行，需要 Python 3 及支持 ASan/UBSan 的 C 编译器（Clang/GCC）：

```bash
python3 firmware/tests/run_host_tests.py
```

测试直接编译固件使用的 `probe_protocol.c`，检查 BOT 字节布局、描述符筛选、CSW 长度/signature/tag/status/residue、INQUIRY、固定/描述符 sense、TOC 命令/长度/曲目/lead-out、READ CD CDB/范围/整数边界和异常输入。另验证 20,000 次 PCM 队列操作的回绕、数据顺序及满空边界，以及跨轨游标。输入为合成 fixtures，不是设备日志，不能验证 USB Host 调度或供电。CI 同时运行该测试和 ESP32-S3 构建。

## 独立 I²S 测试音诊断

默认关闭的 `CONFIG_DISCORA_AUDIO_DIAGNOSTIC` 选择独立测试音服务，入口不启动 USB 光驱任务；USB bench 开关在此模式不可选。已准备 [i2s-tone.defaults](bench/i2s-tone.defaults)，须用独立 sdkconfig 构建，避免已有配置覆盖 defaults。

上电为 stopped。通过 COM / UART0 115200 发送回车结束的 `left`、`right`、`stereo`、`silence`、`play`、`pause`、`stop`、`status`、`help`。数据为明确标记的合成 PCM，不是光驱响应；没有自动出声。默认 GPIO4 / 5 / 6 分别为 BCLK / LRCK / DATA，目标 44.1 kHz、16-bit stereo、Philips I²S，无 MCLK 输出。

暂停保留尚未提交的软件队列，并关闭/重建 DMA；最多约 40 ms 已排队 DMA 数据会被丢弃，不是采样级无损暂停。该独立诊断不使用 CD-DA 源；精确播放位置和硬件 DMA 欠载计数尚未实现。接线与验收见 [音频输出草案](../docs/audio-output.md)；源码、离线测试及构建证据见 [M3 准备记录](../docs/records/2026-10-31-m3-audio-prep.md)。独立 I²S 模式仍未烧录验收。

## 当前模块

- `main.c`：启动探测服务。
- `usb_probe.c`：原生 Host client/daemon、串行 BOT、恢复与设备生命周期。
- `probe_protocol.c`：不依赖 ESP-IDF 的只读 CDB/CBW 构造和响应解析。
- `cdda_bench.c`：寻道、完整首轨和软件时钟缓冲实验。
- `cdda_cursor.c` / `pcm_buffer.c`：跨轨区间拆分、帧对齐环形队列，直接在主机侧测试。
- `audio_core.c` / `test_tone.c`：可离线验证的控制状态机和诊断 PCM。
- `audio_i2s.c` / `audio_diag.c`：原生 I²S TX 适配、单所有者 UART 测试音服务。

后续音频工作按实测结果引入 `mmc`、`cdda`、`audio` 的实际接口；本轮不添加 writer 空壳。

恢复编排由 `cdda_recovery.c` 供 USB 适配和离线测试共用；等待失联、TUR 失败、重读失败/成功及预算不退款的脚本化测试见 [记录](../docs/records/2026-11-01-m2-recovery-flow.md)，不替代真实光驱恢复验收。

## CD 源与音频控制层接入

默认关闭的 CD player 模式把真实 READ CD 接入已有音频状态机；上电 stopped，由 UART 控制 play / pause / stop / next / prev / track N。USB 和输出任务分开，停止/换轨的旧代次回复拒绝入队。软件时钟模式已完成完整首轨 / EOF、10 轮控制及受控欠载/源故障，I²S 适配器完成离线检查及构建；见 [使用说明](../docs/cd-player.md)、[设计边界](../docs/decisions/0008-cd-player-control.md) 与 [实测](../docs/records/2026-11-01-m3-cd-player.md)。

## 可复用 bench 工具

[tools/player_bench.py](tools/player_bench.py) 提供只核对串口身份的 inspect、整轨 EOF、有限轮控制 stress 和一次性 faults 场景。默认不烧录、不主动发送复位脉冲；端口 / VID / PID / 序列号必须一致，输出目录拒绝覆盖，失败也保存报告并释放串口。仅适用于显式部署的 software-clock 播放器；当前板上默认查询固件不能直接运行这些场景。使用和边界见 [工具说明](tools/README.md)。

`python3 firmware/tests/run_host_tests.py` 现在包含八组共享 C 代码的 ASan/UBSan 检查（含 I²S API 替身）；`python3 firmware/tests/player_bench_test.py` 包含串口身份、解析/命令边界、超时、EOF 报告和本会话 TOC 完整性规则的离线检查，不访问设备。硬件接受情况以 [当前状态](../docs/status.md) 为准。

I²S 空载外设的测试音、CD 首轨及日志调度对照见 [记录](../docs/records/2026-11-01-m3-i2s-empty.md)。没有接 DAC，不等于模拟输出验收。

USB 等待/取消编排由生产 Host 和主机测试共享；长等待、迟到回调及 EP0 隔离覆盖见 [记录](../docs/records/2026-11-01-m2-wait-flow.md)，不等于真实设备故障恢复验收。

CI 现在分别构建默认查询、独立测试音、CD 软件时钟、CD I²S、故障注入五种 profile；每个 job 使用独立 build-ci / sdkconfig.ci，禁用 fail-fast 以保留全部配置结果。本地 v5.4 五配置已通过，不代表已触发远端 CI。
