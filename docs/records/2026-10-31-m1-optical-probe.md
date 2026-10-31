# 2026-10-31：UJ-898 首次真实 BOT 查询

结论：**UJ-898 的 INQUIRY / TUR / REQUEST SENSE 已 bench-tested；第三轮连续 61.2 秒取得 13 次介质就绪，无光驱离线或额外 ESP32 启动记录。** 前两轮的离线与准备过程保留，不标为完整 M1 VERIFIED；TOC、音频和完整重连/冷启动验收尚未完成。

## 条件与范围

- 按用户指示暂缓线材内部隔离测量，沿用 ESP32-S3 COM→电脑、原生 USB→Hub、光驱数据→Hub、辅助供电→充电宝的接法。用户确认两路 USB 均接好，充电宝输出已开启。
- 固件为现有 ESP-IDF v5.4 / `61b8229-dirty`，未为本轮重新烧录；只运行 INQUIRY、TEST UNIT READY、REQUEST SENSE。
- 只匹配并打开此前确认的 Discora COM 桥接器；其它项目串口未打开。打开端口后出现一次启动日志，不算真实断电冷启动。
- 光盘已插入（用户报告），介质类型和内容尚未核对；本轮没有读取 TOC、音频或写入介质。

## 设备和接口事实

| 项目 | 真实返回 |
| --- | --- |
| Hub | `05e3:0610`，Full-Speed，class `0x09` |
| 光驱 USB 桥接器 | `13fd:0840`，Full-Speed，configuration 1 |
| 接口 | number 0，alternate setting 0，class `0x08`，subclass `0x02`，protocol `0x50`（BOT） |
| 端点 | Bulk IN `0x81`、Bulk OUT `0x02`，MPS 均为 64 |
| LUN | 0 |
| INQUIRY vendor | `MATSHITA` |
| INQUIRY product | `DVD-R   UJ-898  ` |
| 光驱固件 | `HC10` |
| peripheral type / qualifier | `0x05` / 0，可用 CD/DVD 设备 |

## 第一轮原始观察

90 秒采集窗口中：

- Hub 于启动后约 9.6 秒枚举；光驱第一次枚举在 26.415 秒，最后一次为 89.045 秒。
- 光驱共有 **26 次枚举**，相邻枚举间隔 **1,470–2,810 ms**。用户随后明确报告期间有拔插、移动或开关供电，因此不能将这些事件全部归为自动故障。
- INQUIRY 成功 **26 次**，每次收到 36 字节，CSW status 0、residue 0，示例耗时 7 ms。
- TUR 返回 CSW status 1 共 **26 次**，没有记录到成功就绪。
- REQUEST SENSE 成功返回固定格式 18 字节，共 **26 次**；均为 key `0x06`、ASC `0x29`、ASCQ `0x00`。
- [T10 ASC/ASCQ 定义](https://www.t10.org/lists/asc-num.txt) 中，`29h/00h` 表示发生过上电、复位或总线设备复位。它不能单独证明电压不足；每次重新枚举后的复位状态也会影响观察。
- 没有记录到 BOT transport error、panic、brownout 或第二次 ESP32 启动。26 次 client 关闭（含 Hub）时内部 heap 均为 369,092 字节；这只是有限观察，没有证明完整无泄漏或长期稳定。

真实日志摘录：

```text
I (26415) usb_probe: USB address=2 VID:PID=13fd:0840 speed=Full-Speed config=1 device_class=0x00
I (26415) usb_probe: interface=0 alt=0 class=0x08 subclass=0x02 protocol=0x50
I (26415) usb_probe: BOT interface=0 IN=0x81 MPS=64 OUT=0x02 MPS=64 LUN=0
I (26435) usb_probe: command=INQUIRY CSW=0 received=36 residue=0 elapsed_ms=7
I (26455) usb_probe: INQUIRY vendor=[MATSHITA] product=[DVD-R   UJ-898  ] revision=[HC10] PDT=0x05 qualifier=0
I (26565) usb_probe: command=TEST UNIT READY CSW=1 received=0 residue=0 elapsed_ms=1
I (26565) usb_probe: command=REQUEST SENSE CSW=0 received=18 residue=0 elapsed_ms=7
I (26585) usb_probe: sense key=0x06 ASC=0x29 ASCQ=0x00
```

原始日志当时位于被忽略的 `firmware/build/bench-2026-10-31-9k2eyvtm/uart-optical-probe-202600.log`，35,216 字节，SHA-256 为 `be73889b787bb9c8bbfc31fc50ebf57a84b5c53cc9b76c08f5d0a556d3cd800b`。同目录 `optical-probe-summary.json` 是由原始日志统计的摘要，不提交原始个人端口信息。

## 下一轮对照

保持接头和电源不动，重新采集 90 秒，区分手动操作与实际自动离线；再决定是否进行介质就绪、无盘/有盘、重复插拔与冷启动验收。供电隔离仍是未验证项，M1 不因 INQUIRY 成功就标为 VERIFIED。

## 第二轮：按静置要求采集 90 秒

采集前要求保持连接和充电宝输出不变，不移动接头或按开关。没有自动仪器监测用户动作，因此记录为按静置要求进行的实验，不声称独立证明全过程无人操作。

- 一次 ESP32 启动记录；Hub 在启动后 725 ms 枚举。
- 光驱在 **1,285、4,545、23,075、37,985、50,565、62,175 ms** 枚举，共 6 次；前期离线原因尚未定位。
- INQUIRY 成功 6 次，均识别 UJ-898 / HC10；没有 BOT transport error、panic 或 brownout 记录。
- TUR 失败 19 次、成功 1 次；有效 sense 包括 `02/04/01`（正在就绪）、`06/29/00`（上电/复位/总线复位）、`06/28/00`（介质可能已变化）。解释依据同上 T10 ASC 表。
- 启动后 **82,825 ms** 报告 `06/28/00`，**87,925 ms** 的 TUR 成功，日志明确输出 `medium ready (TOC/audio not tested)`。

真实日志摘录：

```text
I (82825) usb_probe: sense key=0x06 ASC=0x28 ASCQ=0x00
I (87925) usb_probe: command=TEST UNIT READY CSW=0 received=0 residue=0 elapsed_ms=1
I (87925) usb_probe: medium ready (TOC/audio not tested)
```

原始日志 `firmware/build/bench-2026-10-31-9k2eyvtm/uart-optical-static-203050.log`，17,226 字节，SHA-256 `1524dda9e3e4a8644ec663893fd6fe22922093da9153bf8b5b8c6bb4f25911ab`。首次就绪只证明该时刻 TUR 成功，尚未读取曲目或音频；后续再观察连续就绪窗口，介质类型待用户确认。

## 第三轮：连续就绪窗口

保持原连接与供电进行后续观察，使用同一固件。串口打开后仍出现一次启动记录，因此以该次启动后的日志单独统计，不将多个采集窗口拼接成连续运行时长，也不计作真实断电冷启动。

| 项目 | 结果 |
| --- | --- |
| Hub 枚举 | 启动后 725 ms，`05e3:0610`，Full-Speed |
| 光驱枚举 | 启动后 1,285 ms，`13fd:0840`，本轮仅 1 次 |
| INQUIRY | 1 次成功，UJ-898 / HC10，36 字节、residue 0，耗时 7 ms |
| TUR | 13 次成功、0 次失败；从 1,425 ms 到 62,625 ms，跨度 61,200 ms，每次耗时 1 ms |
| REQUEST SENSE | 本轮 TUR 没有失败，因此未额外发送；前两轮已有真实返回证据 |
| 光驱离线 | 0 次；唯一 `device closed` 是枚举后 BOT client 正常关闭其 Hub handle |
| ESP32 额外重启 / panic / brownout | 未观察到；整个窗口仅初始 1 次启动 |
| BOT transport error | 0 次 |

首尾真实日志摘录：

```text
I (1425) usb_probe: command=TEST UNIT READY CSW=0 received=0 residue=0 elapsed_ms=1
I (1425) usb_probe: medium ready (TOC/audio not tested)
I (62625) usb_probe: command=TEST UNIT READY CSW=0 received=0 residue=0 elapsed_ms=1
I (62625) usb_probe: medium ready (TOC/audio not tested)
```

原始日志 `firmware/build/bench-2026-10-31-9k2eyvtm/uart-optical-ready-203417.log`，7,257 字节，SHA-256 `54268264ffe99af83e87346f9d5d5f9e6ddf66b3076fadaff2d066f149729be6`。统计摘要在同目录 `optical-ready-summary.json`。

这证明指定连接组合的基础查询和短窗口连续就绪可用，不等于独立验证线材隔离、带载电流/温升、完整音频吞吐、整盘播放或刻录。下一阶段读取 TOC 前需确认介质类型，并继续保留 M1 受控插拔和冷启动待办。

## 原始证据可用性更正（2026-10-31）

推进 M2 时，执行 `idf.py set-target esp32s3` 触发 fullclean，误删了放在 `firmware/build/` 内的 M1 原始串口/构建日志、统计文件及首次烧录前的备份。本文原有摘录、统计及校验值仍保留，但**不能再据原始文件复核这些历史窗口**；首次烧录前的原固件已无可用备份，不能声称仍可恢复。后续从设备重新读取的 M1 Flash 备份只用于回退到 Discora M1，不是首次烧录前固件的恢复。M1 应用从 Flash 提取后与本文历史 bin SHA-256 一致；原 M1 ELF 未恢复。

新的原始采集、烧录前备份、构建产物快照均放在被 Git 忽略的 `.local/bench/`，不再存放于会被构建清理的目录。详见 [M2 TOC 记录](2026-10-31-m2-toc.md)。
