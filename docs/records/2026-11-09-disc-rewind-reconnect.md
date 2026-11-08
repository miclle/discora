# 2026-11-09：断电重连后盘尾回首曲验证通过

## 结果

**bench-tested（本次末曲与 UART 共用控制核心窗口）**：0.12.3-disc-rewind 完整播放第 13 曲后，排空并关闭 I²S，选回第 1 曲并保持停止；20 秒观察没有新增读取或自动重播。随后一次 `toggle` 从第 1 曲开始播放，短暂播放后停止。用户确认 **尾音完整，当前 OLED 显示 TRACK 01／STOPPED 正确**。

结合[上一轮](2026-11-08-disc-rewind.md)已通过的播放／暂停状态首尾双向循环换轨，两个控制规则均获得实机日志证据；命令通过 UART 调用与实体键相同核心，实体按键接触、消抖和手势仍未独立验收。本次成功不覆盖上一轮 LBA 242415 的 DATA STALL／CSW 超时，不表示间歇性 USB 问题已修复，也不是整盘稳定性测试。

## 条件与执行

用户明确确认按要求断开光驱 Host 数据与辅助供电约 10 秒，先恢复辅助供电、后接数据。此为用户报告，没有独立电压／温度测量，采集也未与电源上升沿同步；不能称为充分冷却或电气复位验收。

2026-11-09 **00:06:54～00:13:59（Asia/Shanghai）**，总窗口 424.810 秒。核对 USB-UART `1a86:55d3`、序列号 `5CF9109063`，0.12.3／IDF v5.4、完整 ELF `6f4d7d1938fad3551e3d7e4bfcdb3f1fc10c020cf14d7cdfa6d0fe9ef488c15c`，UJ-898／HC10、桥接器 `13fd:0840` Full-Speed 和与上一轮相同的完整 13 轨 TOC。GPIO1／2／42／41 与 SH1106 0x3c 初始化正常。打开 COM 后明确复位 MCU 采集启动；未烧录或改固件。

启动 stopped、首曲、READ CD=0、I²S 关闭。仅发一次 `prev`，按手动循环规则从首曲选到末曲并播放，随后等待真实 EOF；不重做上一轮四组换轨检查，没有主机跳到曲尾、伪造 EOF 或失败后自动重播。盘尾完成后等待 20 秒，再发一次 `toggle`，确认首曲 PLAYING 后短播并发一次 `stop`。

## 证据

| 项目 | 结果 |
| --- | --- |
| 末轨范围／名义时长 | 第 13 轨，LBA 223767～252645，28878 扇区，385.040 秒 |
| 末轨完整 I²S PCM 提交 | **67921056 字节**，等于 28878 × 2352；3610 次成功读取 |
| 自然完成事件 | `sequence complete from=13 to=1 generation=4 rewound=1 ended_generation=3 ended_lba=252645 ended_bytes=67921056` |
| 排空与关闭 | drain_start 到 before_close 为 **57700 µs**；完成事件前 I²S handle=0，opens=closes=1 |
| 盘尾新状态 | 首曲、stopped、continuous=0、next_lba=0、eof=0、queued=0、pending=0、delivered=0，代次由 3→4 |
| 20 秒不自动重播 | reads 保持 3610，消费／代次／LBA／opens／PCM 提交均不变 |
| 再次播放 | 一次 toggle 后第 1 曲 PLAYING、I²S running；新的代次，目标曲从首曲起点开始 |
| 失败／恢复／失联 | 无 READ CD 失败、transport error、寻道恢复重读、根端口掉线、panic 或 OLED 禁用 |
| 输出与队列 | underruns=0、write_errors=0、bad_dma_sizes=0、report_dropped=0 |
| I²S 完成事件溢出 | 2 次，均在末曲 EOF 排空阶段；最后 PCM 提交时为 0，关闭前为 2，供数阶段无溢出 |
| 最终状态 | 第 1 曲 STOPPED、media=1、continuous=0、queued=pending=0；I²S tx=closed、handle=0、opens=closes=2，串口已释放 |

末轨旧 EOF／输出关闭快照在回首曲前保留；独立核对完成事件、字节数、读取次数、代次转换、命令次数及关闭资源通过。此次实际读过上一轮失败位置，不据此推断故障根因或断电的因果效果。

本次累计读取 3745 次、PCM 提交 68369112 字节包含末曲完整播放及首曲短播，不作为整盘长度。用户目视和尾音确认分别补充日志证据，没有保存音频或声学测量。

证据保存于忽略目录 `.local/bench/2026-11-09-disc-rewind-reconnect/`：用户断电确认、控制器、原始串口、状态与独立分析。`serial.log` SHA-256：`16337a73025a56ced30b7538674d1f673c2f9bf799006ff9c683a7cdf001c168`。上一轮失败及初次脚本问题仍在原目录独立保留；本轮未提交或推送。
