# 2026-11-07：USB 自发掉线诊断

## 已知事实与代码检查

前一轮[完整日志](2026-11-07-buffered-continuous-log-review.md)在第 13 轨后段失联。用户确认没有动供电、USB 线或退盘；最后一次状态中的缓冲约够 10.24 秒，软件欠载为 0。日志没有 MCU 重启、panic、传输失败或 BOT reset recovery，随后同一光驱重新枚举。这些证据不能确定是供电、桥接器、光驱还是 Host 端异常。

检查当前 `usb_probe.c`、`transfer_wait.c` 及 ESP-IDF v5.4 的 `hub.c`、`hcd_dwc.c`、`usbh.c`：

- 运行中的设备关闭路径由匹配设备句柄的 `USB_HOST_CLIENT_EVENT_DEV_GONE` 触发；打开设备时的描述符、接口检查失败另有关闭路径。未发现播放器欠载会主动关闭 USB 设备的路径。
- 命令仍由单个 client 串行执行，CBW、DATA、CSW 共用的 transfer 仅在回调归还所有权后复用。超时后的迟到回调不会把超时改判成功。
- 应用的 BOT reset 只在符合条件的 transport error 后执行。旧故障窗口未记录此路径，不能将它认定为此次掉线原因。
- IDF 根端口的 `DISCONNECTION`、`ERROR`、`OVERCURRENT` 最终都能表现为上层 `DEV_GONE`。原应用没有保留这个区别；原慢读取统计也只有累计值，没有每次慢读取的阶段和位置。
- 重枚举后的 sense `06/29/00` 不能独立证明电源中断，枚举过程中的 USB reset 也会影响该状态。

以上是代码与日志审查结论，不是已排除软件缺陷或已定位物理故障。

## 新增诊断

`0.11.1-usb-diag` 增加默认关闭的 `CONFIG_DISCORA_USB_DIAGNOSTICS`。不改变读取批次、截止时间、TUR 周期、复位／重试策略、2 MiB 缓冲和故障后停止策略；不记录 CD 音频内容。

| 日志 | 定位用途 |
| --- | --- |
| `root_event` | 保留 IDF 根端口的 CONNECTION / DISCONNECTION / ERROR / OVERCURRENT |
| `action=open` | 记录设备地址、连接代次 `epoch`、VID:PID、是否经外部 Hub |
| `cmd reason=slow` | ≥100 ms 的命令记录 tag、曲目、LBA、扇区数、总耗时及 CBW / DATA / CSW / CONTROL 分段耗时；快速成功不逐条打印 |
| `cmd reason=failed` | 记录失败命令，即使失败很快；result 为通过 0、CSW 失败 1、transport error 2，CSW 未知时为 -1 |
| `client_event=DEV_GONE` | 记录接收事件时的代次、地址、在途所有权、命令、累计断开次数及事件服务间隔 |
| `gone_active` / `gone_last` / `gone_last_read` | 保存断开时在途命令、最近完成命令，以及最近 READ CD 尝试；后续 TUR 不会覆盖最后一次读取证据 |
| `transfer reason=gone_snapshot` | 当前／最近 transfer 的阶段、端点、申请与实际字节数、回调状态、提交／等待结果及时间；未回调的状态和字节数为 -1，不沿用旧值 |
| `player event=DEV_GONE` / `READ_TRANSPORT_ERROR` | 分别记录断开通知和 READ CD 传输失败时的播放器状态、曲目、generation、队列量、读取游标和 pending；传输失败快照在 complete() 清队列之前采样；同时记录事件时间与采样时间，取锁失败明确标为 unavailable |
| `wait_expired` / `late_callback` | 区分截止到期、取消排空和迟到归还；不改变既有资源所有权规则 |
| `action=BOT_RESET` / `action=close reason=…` | 区分应用发起恢复、已收到断开，以及打开阶段失败；保留调用先后 |

根端口观察通过链接器 `--wrap=hcd_port_handle_event` 实现：调用原函数一次，原样返回事件。只在 daemon 任务上下文、原 HCD 函数释放其锁之后记录，不改 SDK 源码、不在 ISR 打印。依赖 IDF 私有 API，编译期限制为 5.4 系列；升级 IDF 时必须重新审查调用上下文、枚举语义和最终链接。最终 ELF 已检查 `root_port_handle_events → __wrap_hcd_port_handle_event → hcd_port_handle_event` 调用链。

报告通过现有非阻塞队列发送，丢失由 `report_dropped` 反映。断开回调仅保存固定尺寸快照，格式化及播放器采样在 client 事件处理返回后进行。持续 ≥100 ms 的串行慢命令最多约每秒 10 条；不启用整个 USB SDK 的逐包调试日志。

### 解读边界

- `observed_us` / `start_us` / `event_us` / `sampled_us` 来自 `esp_timer_get_time()`，属于任务处理／采样时间，不是电气边沿或 ISR 时间。根事件记录在 SDK 去抖／处理之后；异步输出顺序也可能滞后。比较明确记录的时间字段，不直接把它们与 `I (…ms)` 前缀混算。
- 当前在途阶段尚未结束时，其累计阶段耗时尚未计入；用 transfer 的 `start_us` 与事件时间判断已等待多久。`owned` 表示 USB 栈仍拥有 transfer，不等于设备正在传输有效数据。
- `service_gap_us` 是收到断开事件的那次 client 服务调用前的间隔；`service_gap_max_us`、`service_call_max_us` 为本次 MCU 启动以来最大值。服务调用时间含请求的等待时间，不能单凭最大值判定 CPU 卡死或 ISR 饥饿。
- `DISCONNECTION` 只说明 Host 检测到连接消失，不能区分拔线、供电波动或桥接器／光驱行为。`OVERCURRENT` 是控制器事件，不是独立电压／电流测量。
- 根端口钩子不能提供外部 Hub 下游端口的同等细节；须结合 `parent=root/hub` 判断覆盖范围。
- 正常连接、慢读取分段可以短测验证；自发掉线分支须等待实际复现。模拟测试不算物理故障验证。

## 构建与下一轮方法

对当前 N16R8、GPIO15/16/7 配置，在新的构建目录叠加：

```sh
cd firmware
idf.py -B build-usb-diag -DSDKCONFIG=sdkconfig.usb-diag \
  -DSDKCONFIG_DEFAULTS='sdkconfig.defaults;bench/cd-player-i2s.defaults;bench/cd-player-psram.defaults;bench/usb-diagnostics.defaults' \
  set-target esp32s3
idf.py -B build-usb-diag -DSDKCONFIG=sdkconfig.usb-diag build
```

保持已确认的接线、供电和同一张 CD。下一轮用一次 `play-disc` 顺序播放并完整保存日志，状态约每 5 秒查询一次；停止／盘尾结束后分析。发生 fault 时先留存根事件、命令和播放器快照，不自动复位或重播，以免覆盖第一现场。

按日志先后缩小范围：先发生 `BOT_RESET` 则追溯触发它的传输错误；先出现根端口 ERROR／OVERCURRENT 则沿对应 Host／电源路径调查；若仅见 DISCONNECTION 且无先行应用恢复，只能先定位到连接消失，仍不能直接判定电源故障。慢读取的 DATA 阶段增长而 CBW／CSW 正常，可将后续检查集中在设备提供数据及 USB Data-In 路径。已有电压／通断和左右声道接线不重复测量。

## 本轮验证

- ASan / UBSan 主机回归通过，包括阶段耗时、CSW 重试累计、最后 READ CD 保留、断开快照独立性、无回调状态、迟到归还不覆盖超时，以及实际端口包装函数的原样／单次转发。
- ESP-IDF v5.4 的默认查询、查询加诊断、PSRAM 播放加诊断三配置完成 `set-target esp32s3` 与 build；默认配置不启用私有钩子。
- 诊断初版应用 SHA-256：`89b19cb601523e0a49e7def053556d1303a8ddbe524be4b6e96f329f8fb4d228`；在原 8636 主控上 app-only 烧录并独立校验，0x0000～0xffff 的启动／配置区域与原备份一致。

### 短测实际复现了断开

同一 UJ-898 / HC10、`13fd:0840`、原 13 轨 CD、GPIO15/16/7 与 PCM5102A → TPA3118D2。仅发一次 `play`，未主动拔插光驱或触发 USB 复位；计划 30 秒播放被故障提前终止，不算短测通过。本轮未另行获得用户听感或手动操作反馈。

| `esp_timer` 时间 | 新日志事实 |
| --- | --- |
| 4.114536 s 开始 | LBA 0 首读共 2.297257 s，其中 DATA 2.296500 s，成功；慢读取分段日志有效 |
| 8.633710 s | 开始 tag 102、READ CD、第 1 轨、LBA 768、8 扇区 |
| 8.755719 s | 根端口 `DISCONNECTION`；不是 ERROR 或 OVERCURRENT |
| 8.756548 s | DATA 回调 status=1（USB_TRANSFER_STATUS_ERROR），actual=0；已归还所有权 |
| 8.757172 s | tag 102 失败：总计 123462 μs，CBW 95 μs、DATA 123011 μs，没有执行 CSW |
| 8.778999 s | 应用尝试 BOT reset，比根端口断开观察晚 23.280 ms；控制传输提交返回 ESP_ERR_INVALID_STATE，未取得回调 |
| 8.873788 s | client 才收到 DEV_GONE；此时读取失败路径已将播放器置 fault 并清队列 |
| 10.073751 s | 根端口重新 CONNECTION，距断开约 1.318032 s |
| 10.214313 s | 同一 VID:PID 以地址 2、epoch 2 打开，parent=root；INQUIRY 仍为同一光驱 |

当前 IDF 的 `_intr_hdlr_hprt()` 将 HAL DISCONN 转为 HCD DISCONNECTION；预期的端口 reset/disable 使用另外的事件路径。这进一步支持本轮是 Host 观察到连接消失，应用 BOT reset 是后续反应。**仍不能仅凭该事件确定电压波动、USB 信号完整性或桥接器／光驱内部复位，也不能据此断言前一轮 55 分钟故障与本次一定同因。**

本轮提交 PCM 301644 字节，约 1.710 秒；完成读取 96 次、失败 1 次。underruns、auto_recoveries、write_errors、bad_dma_sizes、event_overflows、report_dropped 全部为 0；没有 MCU 重启／panic。控制器看到 fault 后发 stop，确认 stopped、I²S closed、handle=0，串口释放。

- 日志：`.local/bench/8636-usb-diag-20261107/short-play.log`，SHA-256 `74ae15bf03e8ef8db5116eaaef005db21355d2f810e11c14d8cf5d753d60df5f`。
- 机器记录：同目录 `short-analysis.json`、`short-result.json`、`deploy-v1.json`；结果明确标为 failed，原日志保留不覆盖。
- 初版仅在 DEV_GONE 采样播放器，实测发现该通知可能晚于传输失败和清队列。因此补充 `READ_TRANSPORT_ERROR` 快照，放在 READ CD 失败返回和 complete() 之前；保留原 DEV_GONE 快照用于比较。此修改只增加诊断，不改变上述恢复行为。


### 当前部署

补齐提前采样后的应用 SHA-256 为 `8a9183c5d12e15eea669a137eb7320d03418be557bed8668a9eae7df0894ef75`，再次 app-only 写入并独立校验；启动／配置前缀保持一致。初版诊断应用、原 0.11.0 应用和原完整 app 分区备份均保留。

当前版本启动检查确认诊断已启用、光驱直连根端口、2 MiB 队列、stopped、I²S closed；这次启动检查未发送 play。新增 `READ_TRANSPORT_ERROR` 提前采样位置已通过编译，尚未在当前版本再次触发该硬件失败分支。诊断初版已复现的事件证据与当前版本的启动检查分别记录，不合并为稳定性通过。当前没有后台播放或串口占用，也未提交／推送本次变更。

## 更换光驱独立电源后的对照

用户报告已更换光驱独立供电。2026-11-07 17:15:34（Asia/Shanghai）开始一次整盘播放准备，使用上述最终诊断应用；未烧录、改配置或修改音频接线。用户随后确认：新电源为 PD 充电宝，使用 USB-A 口直接连接光驱供电线，没有 PD 诱骗板或降压板。本轮不以 USB-C PD 协商作为排查重点。型号、负载端实际电压／电流及是否连同供电线更换尚未明确，不能仅凭更换电源判定供电路径已经排除。

**本轮尚未进入播放，准备阶段就发生 3 次根端口 DISCONNECTION，整盘对照未能启动。** 共采集约 37.1 秒，根断开观察时间分别为 `esp_timer` 2.211845、13.013656、30.501867 秒，随后均出现 CONNECTION；同一 `13fd:0840` 光驱地址依次为 1、2、3、4。

三次 DEV_GONE 均为 `active=0 owned=0`，最后完成的命令是 REQUEST SENSE，最近 transfer 为已成功完成的 CSW。没有发送 play / play-disc，没有 READ CD，读取数和 I²S opens / pcm_submitted 均为 0；没有应用 BOT reset 或 transport error。状态查询取得 sense `06/29/00`，后续有 `02/04/01`（正在就绪）。未见 ERROR / OVERCURRENT 根事件、MCU 再次启动、panic 或报告丢失。

这进一步表明，**掉线无需 CD 音频读取或 I²S 输出负载即可发生**。更换电源后症状仍出现，不能据此排除供电路径、启动瞬态或 USB 信号问题，也不能认定原电源无问题或两种电源等效。日志尚不能区分桥接器／光驱内部复位与其他连接异常。

观察到重复断开后，由 agent 结束播放准备并发 stop，最终确认 stopped、I²S closed、handle=0，串口释放；没有自动重试播放。控制器的通用异常字符串 `User stop` 指停止文件触发，实际由 agent 为保留异常现场设置，不表示用户操作了设备，见 `stop-reason.json` 和 `analysis.json`。固件的既有只读状态轮询仍在运行，停止播放不等于关闭 Host。

证据位于 `.local/bench/8636-usb-diag-20261107/new-supply/`：

- `play.log`：32075 字节，SHA-256 `aaa88fb2b2b7aa09f5e2c84f5af5ab89f292756cd88ee0fe387b1b25fbe47804`。
- `state.json`、`analysis.json`、`stop-reason.json`：保存准备失败、3 次断开及停止原因，原始日志未改写。
- 本轮未改变固件，因此没有新增构建结果；当前提前采样 READ_TRANSPORT_ERROR 分支仍未触发，因为没有执行 READ CD。

## 光驱数据连接改接 Mac：尚未枚举，读取未开始

用户将光驱数据连接改接电脑，充电宝 USB-A 辅助供电保持不变。检查 IORegistry、`drutil list/status` 和磁盘列表：只识别到主控 COM `1a86:55d3` / `5C82128636`，未找到桥接器 `13fd:0840`、UJ-898 或可读取的音频 CD。

- 首轮约 60.668 秒、59 次约 1 秒间隔的 USB 采样，未捕捉到目标桥接器。
- 用户确认没有出现“允许配件连接”提示；随后按请求在保持辅助供电不变的情况下，重新插接 Mac 端数据连接。
- 覆盖这次重插的后续窗口约 180.959 秒、176 次采样，仍未捕捉到目标桥接器；窗口结束后的 `drutil` 仍无光驱。采样不能排除间隔内更短暂的出现，也不等于捕获了所有 USB 电气事件。
- 内核日志检索未返回匹配的 13fd／enumeration／overcurrent 信息；没有日志不证明没有底层故障。

没有执行任何 CD 音频读取，没有 PCM 文件产出；本轮只能记录为**电脑端枚举未完成，读取对照被阻塞**，不能称为电脑读盘失败，更不能据此认定是或不是 ESP32 固件问题。没有烧录、修改系统安全设置、退盘或操作其他磁盘。

已请求补充 Mac 端连接路径：沿用原 ESP32-S3 的 USB-C OTG 转接头，还是使用其他转接头／扩展坞；等待用户说明，不继续重复拔插。主机替换还会改变 USB 速率、VBUS 和接地条件，后续即使电脑成功也不能单独证明固件有缺陷。

证据保存在 `.local/bench/8636-usb-diag-20261107/mac-new-supply/`：`usb-observe.jsonl`、`usb-replug-observe.jsonl`、两份 summary、`drutil`／USB 树快照、`user-actions.json`。两轮监测均已结束，没有后台读取进程。

## Mac 识别恢复后的整盘只读对照

用户随后报告光驱已识别。实际重新取得 MATSHITA UJ-898 / HC10、桥接器 `13fd:0840`，USB 序列号 `554B33302020333530415A33`。恢复识别前的具体操作／转接路径未补充，不能把恢复归因于某一个动作。供电按用户说明保持充电宝 USB-A 直供，未改固件或音频接线。

最终读取从 2026-11-07 17:38:17（Asia/Shanghai）开始，约 215.762 秒完成。这是 macOS `cddafs` 的 AIFF-C / `sowt` 顺序读取，逐文件成功申请 `F_NOCACHE`，每次最多读取 75 个音频扇区，仅计算摘要并记录耗时，不保存 PCM 内容。

| 项目 | 本轮结果 |
| --- | --- |
| 光驱／连接 | UJ-898 / HC10，`13fd:0840`，480 Mb/s High-Speed，直接位于 Mac 根端口；枚举实例 `4298919546` |
| 介质 | 同一组 13 轨目录，lead-out LBA 252645；每轨 AIFF 帧数与 TOC 扇区范围一致 |
| 完成数据 | 13 / 13 轨，3378 次音频文件读取，594221040 字节；逐轨 LBA 连续，无漏读／跨轨拼接错误 |
| 音频时长等价／实际用时 | 3368.6 秒（56 分 8.6 秒）／215.762 秒（约 3 分 36 秒） |
| 平均读取速率 | 2.754 MB/s，含本轮准备及日志开销 |
| 应用可见读取错误／短读 | 0 / 0 |
| USB 观察 | 400 次约 0.5 秒间隔采样，目标始终存在、同一枚举实例，未观察到掉线／重枚举；结束后再次确认实例仍相同 |
| 单次读取耗时 p50 / p95 / p99 | 57.157 / 93.713 / 104.414 ms |
| 最大耗时 | 3593.221 ms，在第 1 轨 LBA 0 的首次 176400 字节读取；仅这一次 ≥500 ms／≥1 s |
| 历史参考对照 | 轨 1 相对扇区 0、轨 1 相对 150、轨 13 相对 150，三段各 18816 字节，SHA-256 均匹配已有参考 |
| 整盘 PCM 摘要 | `6ef1cfe1624cc00be04882711caf4e4a45507a121ebdd318c0b1b4dd210b2ff7`，用于后续对照，不是独立第二次整盘校验 |

读取前的两次脚本尝试遇到目录匹配／文件打开失败，均未读到音频字节，保留在 `full-read/` 和 `full-read-v2/`。复查时发现 `drutil toc` 查询后文件访问会暂时失败，USB 枚举实例未变；具体文件系统原因未确定。最终使用已捕获的同实例 TOC，读取过程中不再运行 `drutil` 查询，每轨重新核对实际 AIFF 元数据。前两轮属于读取准备／文件访问失败，不把它们误计为 USB 传输错误，也不删除失败证据；成功结果仅覆盖 `full-read-v3/` 窗口。

这次证明光驱、桥接器和当前供电组合在 **Mac High-Speed 路径下能够完整读出本张 CD**。它不等同于 ESP32 的 56 分钟实时连续播放，也不证明供电瞬态、Host 栈或所有 USB 传输没有内部重试。操作系统和光驱可能有缓存／错误恢复，F_NOCACHE 请求不等于独立总线抓包。Mac 与 S3 的 USB 速率（480 / 12 Mb/s）、Host 实现、VBUS／接地条件均不同，故排查重点转向 S3 侧 USB 环境和 Full-Speed 兼容性，而非直接认定固件错误或供电已排除。

最终证据：`.local/bench/8636-usb-diag-20261107/mac-new-supply/full-read-v3/`。

- `result.json`：4947 字节，SHA-256 `695d5d6dddbfba6fd99fd484e87ec629312f4da738a7daa9426213cdb5149b8a`，包含逐轨长度／摘要及三个历史样本对照。
- `reads.jsonl`：3378 条读取耗时，SHA-256 `28cfcc51da73d1f64f55ecdfa565f8d33293a6189a9250b3a85beaa138dc3ddf`。
- `usb.jsonl`：400 条枚举采样，SHA-256 `215712d5f3d96889d1dfd778cc1d8765c9325b30dc3fa20842d7afdab59e8d65`。
- `analysis.json`：独立汇总字节数、逐轨连续性和耗时分位数。所有读取句柄与监测线程已关闭，没有后台读取，未退盘。
