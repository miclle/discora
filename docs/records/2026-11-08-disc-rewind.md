# 2026-11-08：盘尾回首曲与手动首尾循环选曲

## 结果与边界

用户确认两条独立规则：连续播放自然结束后回首条可播放音轨并停止；手动首／末边界换轨循环，暂停状态保留。源码 **0.12.3-disc-rewind，implemented**；完整主机检查及两配置 ESP32-S3 构建通过。软件交付后用户授权烧录，已部署 0.12.3 并通过应用校验及启动检查；本次光驱 INQUIRY 超时，未播放或退碟，未提交／推送。详见文末部署记录。此前用户确认的 OLED 无介质画面不代表本次动态状态验收。

## 实现

- `cd_player_advance()` 在最后一条可播放音轨结束后选回第一条并保持 STOPPED。只有连续模式、有效目录、EOF、无在途请求、软件队列空、状态停止时允许进入；输出 owner 仍先等 I²S 排空并成功关闭，启用摘要校验时还要求末曲校验通过。
- 新选择清除当前曲游标／队列／消费量并更换代次，不开启连续模式、不产生 READ CD。再次按播放／暂停从首条可播放音轨起点开始整盘播放，OLED 读取相同快照显示实际首曲号和 STOPPED。第一条可播放轨不一定是物理轨 01。
- `next`／`prev` 与实体按键共同循环查找相邻可播放轨，最多遍历一圈；数据轨、四声道及不足 8 扇区的轨仍跳过。暂停时选曲后保持暂停，其余可用状态开始目标曲。只有一条可播放音轨时不重启当前曲、不清队列。
- 手动 stop、诊断单轨 `play`／`track N` 的 EOF、fault 和介质失效不触发盘尾回首曲。连续曲尾排空期间按暂停仍阻止自动推进；恢复后完成盘尾复位。
- 不改变自动序列的正向顺序，不增加自动循环重播，不改变 USB、供电或接线。

## 诊断保留

输出 owner 在复位前仍发布旧轨的 EOF 摘要（启用时）、排空时间与关闭输出状态。`sequence complete` 追加 `rewound=1`、`ended_generation`、`ended_lba`、`ended_bytes`，保存末轨代次、读取终点和软件消费字节数；最后一项不是声学播放位置。启动以来的读取、stale、欠载、恢复与 I²S 计数保持。

`player_bench.py sequence` 更新完成条件：须观察本次完整完成事件、末曲字节数和终点匹配、首曲 STOPPED、eof=0、queued=0、delivered=0、首曲 LBA 和新代次；I²S 模式须 handle=0。逐轨旧 EOF／输出关闭记录仍须完整；兼容历史末轨停止固件，不改写旧记录。

## 软件验证

- 完整 `python3 firmware/tests/run_host_tests.py` 通过（ASan／UBSan），含 77 组引脚检查、100 固定种子／500000 步独立 FIFO 检查。
- 新增／更新状态检查：末曲自然结束后首曲停止、再次播放首曲、盘尾排空暂停／恢复、实际首条可播放轨不为 01、首尾均有不可播轨、暂停／播放／停止状态的循环选曲、单可播轨无动作、换轨旧回复拒收、fault／失联／诊断单轨 EOF 不复位。OLED 快照与轨号检查同步新规则。
- `python3 firmware/tests/player_bench_test.py`：17 项通过，覆盖新盘尾状态、旧固件兼容、缺少末曲证据及错误回首曲状态拒绝。
- ESP-IDF v5.4，独立 sdkconfig 与 build 目录，均执行 `idf.py set-target esp32s3` 和 `idf.py build`：四键有声加 OLED／PSRAM／USB 诊断／单次恢复配置通过；四键软件时钟加 OLED／EOF 摘要配置通过。
- 未把离线合成 PCM、脚本化日志或构建结果当作实机音频／机械证据。

有声候选应用 402672 字节；应用 SHA-256 `01c90b3d87d34e48e3c303876710e7aba8384a2c191cc11e860325ae6b682afb`；ELF SHA-256 `6f4d7d1938fad3551e3d7e4bfcdb3f1fc10c020cf14d7cdfa6d0fe9ef488c15c`。构建脚本、配置、两配置日志与产物、主机测试日志和摘要保存在忽略目录 `.local/bench/2026-11-08-disc-rewind/`。

后续实机验收：确认末曲尾音完整、盘尾首曲 STOPPED、不自动读取，按播放从首曲开始；播放与暂停状态各检查首曲上一曲和末曲下一曲、OLED 曲号及声音对应，最后停止并释放设备。

## 后续授权部署（23:49，Asia/Shanghai）

用户要求烧录后，核对当前源码与构建摘要一致、串口无占用；目标 USB-UART `1a86:55d3`、序列号 `5CF9109063`、芯片 MAC `7c:4f:ad:1d:0e:18`。Secure Boot／Flash Encryption 均关闭。读取 `[0, 0x110000)` 备份，SHA-256 `b47d7df59bcf67b236b577a82f69b7c6b5dd73a116434236b38405c04f03ebc9`；板上原应用逐字节匹配 0.12.2 `2e4ea4cf…`，分区表一致。

仅写 factory app 0x10000，写入摘要及独立 verify_flash 均通过；原前 65536 字节校验保持一致，未写 bootloader、分区表、NVS 或 eFuse。保留既有 2 MiB bootloader 映射和物理 16 MiB Flash 的容量提示。

23:49:42 结束 25.043 秒启动采集，确认版本 0.12.3-disc-rewind、IDF v5.4、完整 ELF `6f4d7d1938fad3551e3d7e4bfcdb3f1fc10c020cf14d7cdfa6d0fe9ef488c15c`。四键 GPIO1／2／42／41、2 MiB PSRAM 初始化正常；SH1106 在 0x3c 初始化与首帧发送成功，没有 panic 或显示任务退出。只发送 status，最终 stopped、media=0、reads=0、continuous=0，I²S tx=closed、handle=0、pcm_submitted=0。串口关闭并由 lsof 确认释放。

本次有独立的 USB 异常：桥接器 `13fd:0840` Full-Speed 已枚举，首条 INQUIRY 的 DATA 阶段在约 3021 ms 后返回 ESP_ERR_TIMEOUT；一次 BOT reset recovery=ESP_OK 后停止命令探测，等待重连。未取得光驱型号返回或 TOC，无 READ CD、播放、换轨或退碟。不能将此称为无盘状态，也不能依据该窗口判断超时根因或新控制功能实测通过。后续需重连光驱，重新确认身份与目录再验收。

备份、写入、校验和原始启动日志位于 `.local/bench/2026-11-08-disc-rewind/deploy/`。成功烧录与 USB 查询异常分别保留，本次没有自动重试烧录或循环播放。

## 重连后实机检查：循环换轨通过，盘尾因读取失败未完成

用户确认光驱重连后，2026-11-08 23:54:38～23:59:18（Asia/Shanghai）使用同一 9063 主控、0.12.3 完整 ELF、UJ-898／HC10 和 13fd:0840 Full-Speed 桥接器。实时取得 13 条音频轨，lead-out 252645；末轨范围 223767～252645，共 28878 扇区，名义时长 385.040 秒。没有重新烧录，没有主机跳到曲尾或模拟 EOF。

通过 UART 调用与实体按键相同的控制核心，以下检查通过；不替代实体按钮、电气消抖或人工手势验收：

| 操作 | 实际结果 |
| --- | --- |
| 首曲暂停 → prev | 第 13 曲 PAUSED、continuous=1、I²S 关闭；读取／消费／代次在稳定窗口不变 |
| 末曲暂停 → next | 第 1 曲 PAUSED、continuous=1、I²S 关闭；读取／消费／代次在稳定窗口不变 |
| 首曲播放 → prev | 第 13 曲 PLAYING，I²S running |
| 末曲播放 → next | 第 1 曲 PLAYING，I²S running |
| 首曲停止 → prev | 第 13 曲开始连续播放，随后等待自然 EOF |

用户在末曲播放过程中确认 OLED 为 TRACK 13／PLAYING，声音正常。此为当时画面与声音反馈，不代表最后一曲全程或尾音验收。

本轮盘尾验证失败：第 13 曲 LBA **242415**、8 扇区 READ CD 的 DATA 阶段约 9.673 秒后收到 **STALL**（IDF v5.4 USB transfer status=4），随后 CSW 等待约 3.017 秒超时，总命令耗时 12.691 秒。不是有效失败 CSW／`03/02/00` sense，也没有触发单次寻道恢复重读。固件一次 BOT reset recovery=ESP_OK 后停止探测，要求重连；未观察到根端口 DISCONNECTION。

失败前末轨软件消费 43860096 字节，约 248.640 秒，尚未到 385.040 秒盘尾。缓冲耗尽发生 1 次 underrun，并进入自动重缓冲，随后读取失败使介质不可用。I²S write_errors、event_overflows、bad_dma_sizes 及 report_dropped 均为 0。前面主动换轨留下 3 次旧代次回复拒收，不能当作 USB 读取失败。

控制器发现 transport error 后停止，没有自动重播。最终 stopped、media=0、continuous=0、queued=0、pending=0、I²S tx=closed／handle=0，opens=closes=5，串口释放；共 2552 次成功读取、1 次读取失败。**未观察到 sequence complete，所以盘尾回首曲、停止后再次从首曲启动仍未实机验收。** 当前证据不能判定失败根因，也不能直接归因于新的选曲逻辑。

原始日志与状态在 `.local/bench/2026-11-08-disc-rewind-acceptance/run2/`，日志 SHA-256 `37a2f5fda4b974f0ca1cccb4a3105d4ee96b4683107f3c22f3459b8da2ec4b79`。首次控制脚本因 Python 辅助函数参数重名在任何播放开始前退出，stop 已发出、日志确认停止；修正脚本后另建 run2，未修改固件，初次日志保留在父目录。失败后已请求用户对光驱断电重连，再单独决定是否继续一次验证。

## 后续一次断电重连验证

2026-11-09 00:06～00:13 的独立窗口已完整播放末曲，回首曲停止 20 秒无新增读取，再次 toggle 从首曲启动成功；用户确认尾音完整和首曲 STOPPED 画面正确。详细证据见[重连验证记录](2026-11-09-disc-rewind-reconnect.md)。本记录的读取失败不被后续成功覆盖，间歇性故障仍无根因结论。
