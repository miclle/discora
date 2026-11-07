# 架构初稿（待实验验证）

## 总体数据路径

```text
CD-DA disc
   ↓
MATSHITA UJ-898 (SATA/ATAPI optical drive)
   ↓
SATA ↔ USB bridge [必须验证 USB MSC BOT / MMC passthrough]
   ↓  USB Full-Speed (12 Mb/s theoretical line rate)
ESP32-S3 USB Host → BOT transport → SCSI/MMC command layer
   ↓
READ TOC → track metadata
READ CD  → 2352-byte audio sectors → ring buffer → I²S stereo
                                               ↓
                                         PCM5102A or similar DAC
                                               ↓
                                      L/R line out → amp / active speakers
```

主控和光驱需要安全的公共信号地；光驱 5V 电源不是来自 GPIO。SATA 光驱的低层电气接口由已存在的 USB 桥接器负责，ESP32-S3 不直接连接 SATA。

## 为什么不是普通 U 盘

- 数据盘可能暴露文件系统；**Audio CD 不等同于文件系统**。
- 需要 SCSI/MMC 指令：INQUIRY (0x12)、TEST UNIT READY (0x00)、REQUEST SENSE (0x03)、READ TOC/PMA/ATIP (0x43)、READ CD (0xBE)、START STOP UNIT (0x1B) 等。
- MSC Bulk-Only Transport 封装 CBW → data → CSW；必须正确处理端点、方向、residue、sense、stall、超时与重试。
- 不假设桥接器支持每一条 MMC 指令；首先用实际 USB 描述符与设备响应验证。
- 优先单一驱动访问任务，队列化命令，避免多个任务同时读写设备。

### 当前查询与退盘实现

`firmware/main/usb_probe.c` 使用一个常驻 Host daemon 和单个 client 任务，默认串行发送四种查询命令，可显式启用受限 READ CD 实验；按键任务通过原子单槽投递退盘意图，USB client 仍为唯一命令发送者。`probe_protocol.c` 独立承担描述符筛选、CBW 构造及 CSW/INQUIRY/sense 解析，可直接在主机上运行协议测试。

只访问当前配置、alternate setting 0、首个受支持 BOT 接口和 LUN 0。身份确认为可用 CD/DVD 后每 5 秒查询就绪状态；就绪后读取格式 0、MSF=0 的 TOC，先读 4 字节头再按校验长度取完整目录。最多 99 条轨道加 lead-out，共 804 字节；曲目边界和音频/数据标记全部校验后发布。一次介质就绪周期最多尝试三次；TUR 失败或断连后清除目录状态。READ CD 由默认关闭的实验开关控制；不发送写入/擦除命令；查询和播放器模式默认接受 GPIO7 显式退盘，先允许移除再发送 START STOP UNIT，基本退盘已获用户实测成功反馈，播放中等其余场景未验收，见 [ADR-0010](decisions/0010-gpio-eject-button.md)。开启外部和多级 Hub 配置，现有 UGREEN Hub `05e3:0610` 和光驱桥接器 `13fd:0840` 已完成基础枚举实验。TOC 边界见 [ADR-0003](decisions/0003-formatted-toc-probe.md)。

USB Bulk IN 长度按 MPS 向上对齐，CDB 请求与 CBW 数据长度仍保持精确值。普通查询/CBW/CSW/控制传输截止时间为 3 秒，READ CD 数据阶段为 30 秒；取消后等回调归还所有权。0.5.1 增加 REQUEST SENSE 分阶段日志，实验可将其数据等待单独设为 30 秒，默认仍为 3 秒；有效 sense 已观察到 03/02/00（寻道未完成），尚无稳定修复结论。0.7.3 将等待与取消排空控制提取到生产和离线测试共享的 `transfer_wait.c`，不改变原截止和协议策略。只有完成回调解除所有权；超时后的迟到回调仅归还资源，不把超时改判成功。未归还的 transfer 不复用，控制超时需要拔下设备。断连后释放接口并关闭 device handle，Host 服务继续等待新设备。恢复策略和限制见 [ADR-0002](decisions/0002-read-only-native-bot-probe.md)。0.5.2 新增默认关闭的寻道间隔与有界读取恢复实验：仅对有效 `03/02/00`、仍健康且再次 TUR 就绪的连接，允许每次启动最多一次相同 READ CD 重放。原始失败单独计数，重连不重新授权；详见 [ADR-0007](decisions/0007-bounded-seek-recovery.md)。

0.11.1 增加默认关闭的 USB 诊断 profile：保存慢／失败命令的 CBW、DATA、CSW 分段耗时，断开时的传输／播放器快照，以及打开、关闭和应用 BOT reset 的原因与时间。通过仅限 IDF 5.4 的只读链接包装保留根端口事件，原处理函数只调用一次、返回值不变；异步报告不改变重试、供数或故障停止策略。实测已区分一次根端口 DISCONNECTION 先于应用恢复的故障，物理根因仍未确定；覆盖边界与验证见[USB 诊断记录](records/2026-11-07-usb-disconnect-diagnostics.md)。

默认 console 为独立 UART0；主、次 USB console 均关闭，避免与 Host 共用内部 PHY。固件不负责外部 VBUS 开关或 USB-PD 协商。

## CD-DA 音频

默认短探测实现有界取样：每次启动最多一次，先读 1 扇区、8 扇区并重复校验，再读最多 32 批 × 8 扇区。要求完整有效 TOC，固定 CD-DA User Data，拒绝数据轨、跨轨、零或超量请求。完整响应暂存静态内部 DRAM，USB DMA 缓冲由原生 Host 单独分配；不打印 PCM。详见 [ADR-0004](decisions/0004-bounded-cdda-probe.md)。

本张盘的单/8 扇区 SHA-256 与电脑参考一致，256 扇区短突发取得约 740 KB/s。此结果不代替长时读取、跨轨、冷启动或播放验收；已增加内部 RAM 环形缓冲及软件定时消费实验；独立 I²S 测试音适配和真实 CD 源接入均已实现；软件时钟控制/持续消费与 I²S 空载 CD 首轨已实测；该次空载实验不包含 DAC。2026-11-07，独立候选使用同一 I²S 适配器、GPIO15/16/7、PCM5102A 和 TPA3118D2 完成约 60 秒原始立体声 CD 试听，见[对照记录](records/2026-11-07-cybertrack-audio-crosscheck.md)；完整播放稳定性与波形指标未验收。

扩展实验由 `cdda_bench.c` 编排，`cdda_cursor.c` 负责连续区间逐轨拆分，`pcm_buffer.c` 是由调用方串行保护的 4 字节帧对齐环形队列。USB client 是唯一命令生产者；独立软件消费任务只访问已复制的 PCM，不触碰 USB handle 或共享响应。64 扇区内部 RAM 缓冲经 48 扇区预填后启动 1× 软件时钟，生产/消费两端分别累计摘要。失败时等待消费端停止后才释放内存；未确认停止则隔离。见 [ADR-0005](decisions/0005-stream-and-buffer-bench.md)。此模型验证传输与缓冲，不替代真实 I²S DMA/时钟。可选 seek-only 模式跳过整轨和缓冲，支持最多 20 轮寻道及确定性轨内偏移变化；位置边界检查 600 秒软截止，每次启动的恢复预算不随轮次重置。正常路径通过不等于实际恢复分支验收，见 [多轮记录](records/2026-11-01-m2-seek-rounds.md)。

- 44,100 sample/s × 16 bit × 2 = **1,411,200 bit/s**（约 176.4 KB/s）。
- 一扇区音频为 **2352 字节**，每秒 75 扇区；留足环形缓冲以应对光驱抖动和 USB 调度。
- I²S 用主模式输出 BCLK/LRCK/DATA 给立体声 DAC；PCM 左右交织，必须明确左右采样与字节顺序。
- 对 USB DMA 使用符合内存能力要求的缓冲；在搬运、I²S DMA 与任务之间管理缓存所有权。
- 模块间以原始 PCM 帧、音轨元数据和显式错误码传递数据。

## 音频诊断和控制准备

`audio_core.c` 在不调用设备的情况下管理预填充、播放、暂停、停止、欠载和 fault；停止/新源改变 generation 并清空队列，旧代次输入被拒收。由单一任务或外部串行保护其访问；独立测试音和新增 CD 播放器分别使用它，播放器由 mutex 保护 USB 生产和输出/控制任务的访问。

`test_tone.c` 生成明确标记的 PCM16LE 左右交织样本，`audio_i2s.c` 通过 IDF v5.4 原生 standard TX 输出，`audio_diag.c` 串行处理 COM 命令、生成和提交 PCM。默认模式仍为 USB probe；测试音模式不启动光驱任务，上电 stopped，显式命令后才开 I²S。

诊断软件队列为 14112 字节（80 ms），DMA 7056 字节（40 ms），与 M2 的 64 扇区缓冲实验是不同配置。暂停/停止删除输出通道以丢弃旧 DMA；暂停保留未提交软件数据，但不保证采样级无损位置，该独立诊断不处理 CD EOF；真实播放位置和 DMA 欠载统计尚未实现。0.7.2 增加完成回调、驱动完成事件队列溢出、提交字节及通道生命周期计数；完成回调可能包含 DMA 自动静音，不等于有效 PCM 已完整输出。详见 [ADR-0006](decisions/0006-i2s-tone-diagnostic.md)。独立测试音已有空载外设与接 DAC 试听记录；可选 PCNT 探针回读 MCU 时钟活动，不能替代独立波形与模拟性能测量，见[音频说明](audio-output.md)。状态格式化后投递到容量为 16 的报告队列（0.11.0 扩容，原为 8），由低优先级任务输出，队列满或截断显式计入丢弃；输出所有者不等待 UART 状态日志发送。其余命令/错误日志仍沿用原路径。

## 刻录通路（研究阶段）

```text
SD / flash ISO or PCM → source reader → buffer → USB BOT
   → MMC write/setup → WRITE(10) or suitable write mode
   → SYNCHRONIZE CACHE → CLOSE TRACK/SESSION → verify
```

刻录需要对介质能力、写入模式、缓存 underrun 和状态变化建模。数据 CD 1× 用户吞吐约 150 KB/s；音乐 CD 1× 原始音频吞吐约 176.4 KB/s。USB Full-Speed 理论 1.5 MB/s 并不是持续有效吞吐，不能推定 8× 刻录可用。**若最低允许写速超过实际吞吐，必须及时停止该方案而非冒险烧盘。**

## 待决策事项

1. `13fd:0840` 桥接器已透传基础查询和 READ TOC；READ CD 小片段和短突发已在本组合实测，600 秒 1× 顺序读取已与电脑完整摘要一致；随机寻道和回读 LBA 0 失败。新 OTG 绕过 Hub 后仍在末轨返回命令失败、REQUEST SENSE 超时，但该窗口没有 USB 断连；错误详情和桥接/Full-Speed/供电条件仍待隔离，见 [直连记录](records/2026-11-01-m2-otg-after-pc.md)。
2. 已采用原生 USB Host + 独立最小 BOT 层；是否需要扩展命令调度随音频读取结果再评估。
3. 缓冲空间与 SD 卡传输是否与 USB 带宽/任务调度冲突。
4. PCM5102A 不需要外部 MCLK 的具体模块接法与时钟精度验证。
5. 是否需要 PSRAM；初期先不用其承担 USB DMA。

## CD 播放控制接入

`cd_player_core.c` 将音轨选择、单轨读取光标、预填、暂停/停止/换轨及代次检查接到 `audio_core`；`cd_player.c` 独占 UART 和输出适配器，USB client 仍是唯一 SCSI 发送者。请求复制音轨边界及代次，USB 等待不持有播放器锁，完成后仅将当前代次的完整回复复制入队；旧代次返回不能污染新轨。

0.9.1 在播放器模式默认开启 GPIO8／GPIO9 换轨按键。输出 owner 轮询两键，在播放器锁内消抖并执行原有 `cd_player_step`，成功后由同一 owner 关闭旧输出；按键不访问 USB。消抖提取为 `button_core` 与退盘共用，双键互斥、介质失效和 fault 丢弃手势，详见 [ADR-0011](decisions/0011-gpio-track-buttons.md)。

模式默认关闭、启动 stopped，与 bench/测试音互斥。软件时钟模式用真实 CD 数据验证控制和 1× 消费；I²S 模式复用已有适配器，短时接 DAC 试听已完成；主固件与成功实验的引脚、25% 增益和限时停止差异见[配置说明](audio-output.md#已通过的接法与默认配置差异)。单轨 EOF 停止，暂停可丢弃已提交 DMA，未实现无缝播放或独立硬件 DMA 欠载计数。详见 [ADR-0008](decisions/0008-cd-player-control.md)。

播放器 EOF 诊断可选地对已接受源数据与软件消费分别累计 SHA-256，仅在完整同代次结束时比较字节数/摘要。0.6.4 的轨尾恢复允许不足预填门槛的已知 EOF 队列继续消费；I²S 短预装只在尾帧之后补静音，EOF 50 ms 截止在适配器内管理。离线 fake driver 测试调用实际 `audio_i2s.c`，只替换 ESP-IDF API，不能充当电气/声音验收。

0.8.0 在控制核心增加显式连续模式，输出 owner 只有在旧轨队列耗尽、EOF 校验完成（启用时）及 I²S 通道成功关闭后，才选择下一受支持音轨并重新预填。play-disc 从当前轨起点到盘尾，不循环；暂停保留模式，停止、手动选择、fault 和介质失效取消模式。欠载默认取消；0.11.0 显式开启自动恢复时保留连续模式。存在轨间间隔，详见 [ADR-0009](decisions/0009-explicit-disc-sequence.md)。

## OLED 状态显示

`oled_display.c` 在播放器启动后运行独立优先级 1 任务，使用 ESP-IDF 原生 I²C master API（GPIO10 SDA／GPIO11 SCL，100 kHz）；默认 SH1106、7-bit 地址 0x3c。每 200 ms 尝试在播放器 mutex 内复制轨号、介质可用性与状态，锁等待最多 10 ms；释放锁后才渲染和通信，USB 与音频 owner 不等待 OLED。`oled_panel.c` 负责本地字形、1024 字节帧和 SH1106 分页／列偏移，不使用第三方显示库。仅变化时刷屏；I²C 单次等待最多 50 ms，失败后尝试灭屏并释放资源，直到重启才重试，播放继续。状态为核心逻辑状态，不代表 DAC 实际声音。查询／测试音模式不初始化 OLED；配置与硬件边界见 [显示说明](oled-display.md)、[ADR-0012](decisions/0012-sh1106-status-display.md)。

## PSRAM 播放队列与恢复

0.11.0 新增可选 2 MiB PSRAM PCM 队列和 3 秒预填，USB / I²S DMA 仍在内部 RAM。输出 owner 确认关闭通道后才对 underrun 执行重缓冲；保留源游标、generation 和在途读取，不重播当前轨。控制命令及真实故障优先，源失联不自动恢复。每次 read_audio 完成时累计端到端耗时及慢读取分布，状态任务异步报告，未完成请求不计入。内部 RAM 的 I²S 计数器允许 ESP-IDF v5.4 PSRAM 原子操作包装器，它对内部地址走硬件原子路径。配置、恢复边界见 [CD 播放说明](cd-player.md#2-mib-缓冲与欠载自动恢复0110) 和 [ADR-0017](decisions/0017-psram-rebuffer.md)。
