# CD 播放控制实验

0.6.0 已将真实 READ CD 源接入音频控制核心。默认构建仍为目录查询模式；播放器须显式配置，上电不读取音频、不自动出声。

## 构建模式

| 配置 | 数据源 / 消费端 | 验证状态 |
| --- | --- | --- |
| [cd-player-clock.defaults](../firmware/bench/cd-player-clock.defaults) | 真实光驱 → 软件时钟消费 | 13 轨软件时钟及控制已实测；没有声音 |
| [cd-player-i2s.defaults](../firmware/bench/cd-player-i2s.defaults) | 真实光驱 → I²S 输出适配器 | 13 轨空载整盘已上板；临时候选另完成接 DAC 的约 60 秒立体声试听，差异见下文 |
| [cd-player-psram.defaults](../firmware/bench/cd-player-psram.defaults)（叠加 I²S profile） | 2 MiB PSRAM、自动重缓冲、GPIO15/16/7、25% 数字幅度 | 0.11.0；结果见[缓冲实测记录](records/2026-11-07-buffered-playback.md) |

使用独立 sdkconfig / build 目录加载配置，避免已有缓存覆盖默认值。播放器与 CDDA bench、独立测试音分开运行；每次部署须确认本项目 COM，不根据端口顺序猜设备。

2026-11-07 早期 8636 板的成功试听使用临时诊断候选：GPIO15/16/7、左右各 25% 数字幅度、60 秒自动停止，关闭按键和 OLED。该历史候选的 bench 命令和限时控制仍未合入；0.11.0 已新增可复现的 PSRAM profile 和独立增益选项。默认 GPIO7 退盘键会与该 DIN 接法冲突。不要把本页标准命令／默认构建当作同一候选；差异见[音频输出说明](audio-output.md#已通过的接法与默认配置差异)，实测见[记录](records/2026-11-07-cybertrack-audio-crosscheck.md)。

## 四键控制（0.12.1）

四键 profile 使用 J2-4～7 连续排针：GPIO1 播放／暂停、GPIO2 上一曲、GPIO42 下一曲、GPIO41 退碟；保留 GPIO15／16／7 音频。通过独立 `cd-player-buttons.defaults` 在 PSRAM profile 后启用，原 PSRAM profile 本身仍关闭按键。接线、构建及验收见[四键控制](playback-controls.md)。

## UART0 命令

播放器保留 GPIO8 上一曲／GPIO9 下一曲的旧默认，四键 overlay 改为 GPIO2／42；当前行为与下表 `prev` / `next` 一致；接线、配置和待完成的实机验收见[换轨按键](track-buttons.md)。此前已部署 0.9.1 软件时钟播放器，保留 GPIO7 退盘；当时启动与目录查询通过，按键动作待验收，见[历史部署记录](records/2026-11-01-track-buttons-deploy.md)。

串口为 115200，命令以回车结束。首次有效目录到来后保持 stopped。

| 命令 | 行为 |
| --- | --- |
| `play` | 开始或恢复；欠载后显式重缓冲；fault 时先 stop |
| `play-disc` | 从当前轨起点依次播放到盘尾；自然结束回首条可播放音轨并停止，不自动重播 |
| `pause` | 暂停消费和后续读取，保留软件队列及连续模式 |
| `toggle` | 与播放／暂停键一致：停止时开始连续播放，播放／缓冲时暂停，暂停时恢复 |
| `stop` | 清空队列并回到当前轨起点，旧代次回复被丢弃 |
| `next` / `prev` | 选择下一/上一可用音频轨，开启连续模式；暂停中保持暂停，其余可用状态开始；首尾循环选曲，只有一条可播放轨时无动作 |
| `track 13` | 选择指定轨并开始；非法轨号不影响现有播放 |
| `status` / `help` | 查看当前状态、轨号、代次、队列、交付量、读取次数和欠载 |

普通 `play` 每次播放一轨，EOF 后停止；0.8.0 的 `play-disc` 显式开启有限连续播放。成功的 `track N`、stop、fault 或失联均取消连续模式；0.12.0 的 next／prev 则开启连续模式并保留暂停；欠载默认也取消，开启 0.11.0 自动恢复选项时保留；支持双声道音频轨，至少 8 扇区，不支持数据轨/四声道轨。`next_lba` 是下一次源读取位置，队列中已有预读数据，它不是听觉播放位置。`delivered` 是软件消费/输出提交字节数，停止或换轨后清零；`reads`、`stale`、`underruns` 是当前 MCU 启动累计值。`continuous` 表示连续播放是否仍被授权；`pending` 只描述当前代次，不能据此推断旧 USB 请求已取消。

暂停或停止会响应控制，但不会强制取消底层正在等待的 USB 命令；换轨后等待旧请求返回再发新请求，USB 截止仍适用。源失败或介质失效停止输出，重新枚举不自动开始音频。

源码 0.12.5 在单次寻道恢复前及恢复等待期间检查当前请求身份；一旦观察到停止、换轨、fault 或介质失效，便不再为旧请求启动额外恢复读取。已提交的 USB 命令仍等返回后按代次隔离；暂停保留当前逻辑请求，恢复预算已消耗则不退款。该控制边界目前仅离线验证，板上版本见[当前状态](status.md)。

## PCM5102 到货后的顺序

先按 [音频输出准备](audio-output.md) 确认实际模块及供电/跳线，使用独立测试音验证 L/R。通过后才上播放器 I²S 配置；检查真实 CD 声道、音调、噪声、长时播放、暂停/换轨和 EOF 尾部。软件时钟通过和 I²S 构建通过均不代替这些项目。

I²S 暂停会丢弃已提交 DMA 数据，可能产生约 40 ms 的跳过；当前没有硬件 DMA 欠载计数。EOF 的 50 ms 排空等待尚无硬件测量。不把此版本称为无缝播放器。设计边界见 [ADR-0008](decisions/0008-cd-player-control.md)。

## 整轨摘要诊断

0.6.1 增加默认关闭的 `DISCORA_CD_PLAYER_VERIFY`，software-clock bench profile 显式开启。接受当前代次的完整源数据后累计 SHA-256，消费端独立累计；单轨 EOF 后报告两端字节数、轨长、最后输出块和摘要。停止/换轨重新开始代次，不将中断区间标为整轨通过。摘要计算使用队列互斥锁，不保存 PCM，存在诊断开销。

`match=1` 只表示该代次源与软件消费顺序/长度相同，不等于独立电脑内容参考匹配，也不代表 I²S 已播放这些字节。

0.6.2 的 `resources` 状态行记录系统空闲/历史最低堆，以及输出任务最低剩余栈（字节）。它们是有限实验中的资源观测，不代表长期泄漏验收或所有任务栈已覆盖。

## 受控故障实验

`DISCORA_CD_PLAYER_FAULT_TEST` 默认关闭，`cd-player-faults.defaults` 显式开启；0.11.0 也允许单独叠加到 I²S 实验。播放时 `test delay` 按 `DISCORA_CD_PLAYER_TEST_DELAY_MS` 暂停新请求（默认 1200 ms，可设 100～30000 ms），`test fail` 在下一次请求处注入播放器源失败、不发送该次 USB。两项各每次 MCU 启动最多一次；命令和触发日志均有 TEST 标记，不代表真实光驱错误。未开启自动恢复时，欠载须显式 play；fault 始终须 stop 后 play。正常 PSRAM/I²S profile 不开放这些命令，详见 [负向实测](records/2026-11-01-m3-player-faults.md)。

## 轨尾暂停 / I²S 软件边界

0.6.4 修复 EOF 已读完但剩余队列低于预填门槛时，pause/play 永久停在 prefill 的问题。已知 EOF 的剩余数据可直接恢复消费；I²S 重新打开时允许 4 字节对齐的短预装，真实尾帧后补静音填满 DMA。补齐只用于 EOF 初始预装，不在普通欠载时伪造 PCM，也不计入 CD 字节摘要。

适配器的 50 ms EOF 排空截止已纳入生产代码的离线测试，重复 EOF 不延长截止，stop/关闭会清除截止。假的 IDF 调用验证开通失败、短写、关闭失败保留句柄、重开和尾块；不模拟真实时钟或证明 DMA 已播放完成。见 [轨尾回归与适配器记录](records/2026-11-01-m3-player-tail.md)。

## I²S 运行计数

0.7.2 的 I²S 状态行分别报告 `pcm_submitted`、`padding`、`dma_blocks`、`event_overflows`、`write_errors` 和 opens/closes。PCM 提交量与 DMA 完成量不是同一个计数，自动补零也会完成；事件队列溢出与软件队列 underrun 分开报告。计数跨通道重开累计，32 位回调计数按无符号回绕。

状态打印使用独立低优先级任务和 16 项有界快照队列（0.11.0 扩容，原为 8 项），音频 owner 不等待串口；`report_dropped` 记录队列满/过长报告。命令语义不变，频繁查询可能丢报告，不能因此宣称音频完整性通过。空载 profile 为 `cd-player-i2s-observe.defaults`，仅增加软件摘要观察，不自动播放。

0.7.5 将 EOF 摘要也交给报告任务；六个阶段的内存快照只在关闭后输出。首轨对照中，摘要窗口由 18.399 ms 降为 0.713 ms，收尾事件溢出由 3 变为 2，供数阶段为 0；固定 50 ms 排空没有改变。计数和物理边界见 [EOF 阶段记录](records/2026-11-01-m3-eof-phases.md)。

13 轨 I²S 空载整盘已完成，逐轨摘要与软件时钟整盘一致，供数阶段事件溢出为 0、收尾每轨 2 次；详见 [整盘记录](records/2026-11-01-m3-i2s-disc.md)。

连续播放在上一轨 I²S 排空并关闭后才启动下一轨，存在轨间间隔；EOF 排空期间暂停可阻止切换，play 恢复后再继续。目录发布/重新枚举不自动恢复连续模式。见 [ADR-0009](decisions/0009-explicit-disc-sequence.md) 与 [实测记录](records/2026-11-01-m3-autoplay.md)。

## 轻触按键退盘

退碟按键由 `DISCORA_EJECT_GPIO` 选择；默认查询保留旧 GPIO7，0.12.1 四键有声 profile 改为 GPIO41，GPIO7 只接 DAC DIN。接线见[按键说明](eject-button.md)。稳定按下后由 USB client 在当前命令结束时处理，先失效介质、清空队列和取消连续模式，等待输出 owner 成功关闭 I²S，再执行允许移除/退盘。重新检测目录后保持 stopped。长按不重复、上电按住不触发；默认查询配置的基本按键退盘已获用户实测成功反馈；本节的播放中停止输出与退盘流程仍未上板验收。

## 2 MiB 缓冲与欠载自动恢复（0.11.0）

在全新构建目录中按顺序叠加配置：

```sh
cd firmware
idf.py -B build-psram -DSDKCONFIG=sdkconfig.psram \
  -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;bench/cd-player-i2s.defaults;bench/cd-player-psram.defaults" set-target esp32s3
idf.py -B build-psram -DSDKCONFIG=sdkconfig.psram build
```

此 profile 面向已确认的 16 MiB Flash / 8 MiB Octal PSRAM 主控，启用 PSRAM 80 MHz 和启动内存测试，关闭按键及 OLED，保留当前 GPIO15→BCK、GPIO16→LRCK、GPIO7→DIN 接法。上电仍为 stopped；发送 `play-disc` 后开始，不自动循环整盘。

- `DISCORA_CD_PLAYER_PSRAM_BUFFER`：仅软件 PCM 队列使用 2097152 字节 PSRAM，约可容纳 11.89 秒 CD-DA；225 扇区／529200 字节（3 秒）预填后开始。分配失败明确拒绝启动，不悄悄降级。USB 响应、USB DMA、I²S DMA 和输出适配器保留内部 RAM。
- `DISCORA_CD_PLAYER_AUTO_RECOVER`：输出 owner 成功关闭 I²S 后，将 underrun 转为 prefill，保留 generation、源读取位置、队列和在途请求；达到预填量后自动继续。EOF 剩余数据不足门槛时直接输出尾部。显式暂停、停止、换轨，以及真实源失败、介质失效或 I²S 错误会阻止此次恢复。重连不自动播放。
- `DISCORA_CD_PLAYER_GAIN_PERCENT`：对左右 PCM16 样本分别缩放，默认 100，此 profile 为 25；不混音、不改变源端摘要。

自动恢复避免欠载后永久停住，不能补回已经发生的静音间隙。关闭通道可能丢弃最多约 40 ms 已提交 DMA 数据，不保证采样连续或无缝恢复；大缓冲也不能解决持续低于 176400 bytes/s 的供数或真实 USB 掉线。

`status` 新增以下累计观测（MCU 重启清零）：

| 字段 | 含义 |
| --- | --- |
| `buffer capacity/prefill/low` | 容量、预填门槛、非 EOF 消费后采样的最低软件队列字节数；不包含 DMA |
| `rebuffering/auto_recoveries` | 当前是否自动补缓冲；补足后进入 playing 的次数，不等于已经听到声音 |
| `read_timing count/last_us/max_us/avg_us` | 已完成 `read_audio` 调用的端到端耗时，含配置允许的恢复等待；不是单个 USB 传输阶段计时 |
| `last_lba/max_lba` | 最近／最长一次读取的起始 LBA |
| `ge100ms/ge500ms/ge1s` | 耗时达到对应阈值的次数，包含关系而非互斥分桶 |
| `failed/rejected` | 源调用失败次数／播放器拒收次数（包括旧代次）；两者可能重叠 |

未完成的在途读取尚不进入耗时统计。按状态快照汇总输出，不逐次打印 READ CD 时间；建议以数秒间隔查询。I²S `event_overflows` 是驱动完成事件队列溢出，与软件 PCM 欠载分别记录。设计见 [ADR-0017](decisions/0017-psram-rebuffer.md)。

## USB 读取负载对照（无音频输出）

定位 USB 掉线时，可在上述 PSRAM 播放配置后继续叠加 `bench/usb-diagnostics.defaults;bench/usb-read-clock.defaults`，使用新的构建目录与 sdkconfig。最后一个 overlay 关闭 I²S、查询 A/B 实验、摘要校验和故障注入，保留实际 READ CD、2 MiB 缓冲与软件时钟消费；上电仍为 stopped。`play-disc` 会读取到盘尾，短窗口须由控制器发送 `stop`，该 overlay 本身不提供 600 秒截止。

此模式不会输出测试音或音乐，也不代表音频链路通过。实机窗口、供电条件、构建与部署证据见[2026-11-07 读取对照](records/2026-11-07-usb-read-clock-comparison.md)。

## 单次寻道恢复实验

需要验证真实 `03/02/00` 读取失败后的行为时，可在 I²S／PSRAM／USB 诊断配置后叠加 [cd-player-seek-recovery.defaults](../firmware/bench/cd-player-seek-recovery.defaults)。该文件只启用 `DISCORA_CDDA_SEEK_RECOVERY`，不更改引脚、增益、缓冲或默认播放行为；使用独立 sdkconfig 和 build 目录。

只有有效失败 CSW、精确 `03/02/00`、目录有效且 USB 连接健康时才消耗每次 MCU 启动最多一次的恢复预算。等待 1000 ms 并继续处理 USB 事件，TUR 成功后仅重读相同 LBA／扇区数一次；断连、其它错误或再次失败仍停止。原始失败和 `seek recovery reserved / replay / succeeded` 日志必须保留，恢复后完成不计为无错误通过。策略详见 [ADR-0007](decisions/0007-bounded-seek-recovery.md)。

此开关与软件欠载自动重缓冲不同：后者处理供数间隙，不会自行重试失败的 SCSI 命令。恢复等待可能使队列耗尽，即使重读成功也可能产生声音间隙。构建或未触发错误的播放成功，不能替代真实恢复分支的实机验证。
