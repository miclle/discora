# 2026-11-01：寻道空闲间隔与单次恢复对照

用户要求保持连接，优先尝试软件侧寻道等待及有界恢复。本轮不要求拔插、更换电源或线材；通过明确匹配的 Discora COM 做应用烧录及 RTS 复位。此前电脑初始化后的光驱供电状态延续，不代表冷启动验收。

## 软件及设备

源码 `0.5.2-seek-recovery`，ESP-IDF v5.4 (`67c1de1eeb`)，ESP32-S3 rev v0.2、16 MB Flash / 8 MB PSRAM；COM VID:PID `1a86:55d3`、序列号 `5CF9109063`。新 OTG 转接头直连 UJ-898 / HC10，桥接器 `13fd:0840`，Full-Speed BOT `08/02/50`，IN 0x81 / OUT 0x02、MPS 64、LUN 0。辅助 USB-A 继续由充电宝供电，无 Hub；同一张 13 轨音乐 CD，lead-out LBA 252645。

仅新增两个默认关闭的实验条件，完整策略见 [ADR-0007](../decisions/0007-bounded-seek-recovery.md)：

- 寻道位置之前可空闲 1000 ms，等待期间处理 USB 事件；不是 SEEK 命令，也不是机械完成信号。重复读取两次之间不等待，read 延迟不含这段预等待。
- 有效 `03/02/00` 且连接健康时，每次 MCU 启动最多预留一次恢复；再等 1000 ms、一次 TUR 成功才允许同位置重放。原始失败单独记录；断连、传输故障、无 sense、介质变化或 TUR 不成功均不重放，重连不重新给予预算。

三组主机 ASan/UBSan 测试通过，新增准入判断覆盖缺失 sense、已用预算、不健康连接及其它错误。默认、等待、等待加恢复、无等待恢复对照分别在独立 sdkconfig / build 目录完成 `idf.py set-target esp32s3 && idf.py build`。构建和准入测试不代替实机恢复时序验收。

每轮保持 30 秒 REQUEST SENSE 数据截止、相同短探测、12 位置寻道、完整首轨及 60 秒缓冲。烧录前用 `esptool verify_flash` 核对当前 0.4.3 应用，复用先前 `sense-control` 的 `0x0–0x110000` 备份，并核对 bootloader / 分区 / 应用。复用文件不是新读出的备份，也不是完整 16 MB Flash。仅写应用 `0x10000`，写入校验通过；每轮结束恢复已保存的 0.4.3 默认关闭读取实验配置，另采集约 25 秒。

## 仅等待，不恢复

配置 [seek-wait.defaults](../../firmware/bench/seek-wait.defaults)。短探测通过，256 扇区突发 749061 bytes/s；12 个位置全部完成，24 次读取的逐位置摘要匹配，最长单次 read 699518 μs。

首轨 LBA `[0, 19373)`：45565296 字节、2422 条命令，49035314 μs，929234 bytes/s。SHA-256 为 `73ad449e02aa5513ffb632bfd632a2bf6bc048dabb675b4ba958b26e9a54a38f`，与此前成功 MCU 轮次一致；仍无电脑该整轨的独立完整参考。

缓冲 LBA `[150, 4650)`：60 秒，生产/消费各 10584000 字节，欠载 0、缺失 0、joined 1，生产期低水位 109112 字节，最长 read 261278 μs。两端 SHA-256 均为 `7c144eb3ebb64f754f73e979f839ac4938b016047fa4244807b10bc7ad87407b`。该阶段仅软件时钟消费，不是 I²S。

实验窗口 140.994 秒，一次枚举、零关闭，`failures=0 recovery_reserved=0 recovered=0`。默认恢复窗口 25.038 秒，目录有效、5 次 TUR 成功、READ CD 数 0。

## 等待加恢复

配置 [seek-recovery.defaults](../../firmware/bench/seek-recovery.defaults)，仅在前轮基础上开启一次恢复预算。12 个位置、24 次重复读取通过，最长单次 read 689600 μs；首轨仍为 45565296 字节、2422 条命令，48673698 μs，936137 bytes/s，整轨摘要与上一轮完全相同。

60 秒缓冲生产/消费各 10584000 字节，欠载 0、缺失 0、joined 1，低水位 109196 字节，最长 read 238844 μs；两端摘要也与上一轮相同。实验窗口 138.389 秒，一次枚举、零关闭，`failures=0 recovery_reserved=0 recovered=0`，没有 REQUEST SENSE，**未触发恢复分支**。

默认恢复窗口 25.042 秒，目录有效、5 次 TUR 成功、READ CD 数 0。恢复开关开启且实验完成，仅证明该配置正常路径可运行，不能作为一次真实恢复成功的证据。

## 无预等待对照

配置 [seek-recovery-control.defaults](../../firmware/bench/seek-recovery-control.defaults)。与第二轮只差 `DISCORA_CDDA_SEEK_WAIT_MS=0`，保留相同一次恢复预算。12 个位置全部通过、24 次读取重复摘要一致，最长单次 read 1145978 μs。

首轨 45565296 字节、2422 条命令，48696422 μs，935701 bytes/s；整轨摘要与前两轮相同。60 秒缓冲生产/消费各 10584000 字节，欠载 0、缺失 0、joined 1，低水位 109704 字节，最长 read 238945 μs，两端摘要同前两轮。`failures=0 recovery_reserved=0 recovered=0`，恢复分支仍未触发。

实验窗口 126.264 秒，一次枚举、零关闭、零传输错误。最终恢复窗口 25.029 秒，0.4.3 日志明确 `CDDA probe enabled=0`，目录有效、5 次 TUR 成功、READ CD 数 0，未出现离线；串口采集已结束并释放。

## 结论与证据

| 配置 | 12 位置 / 24 次读取 | 首轨完整读取 | 60 秒软件缓冲 | 读取失败 / 恢复 |
| --- | --- | --- | --- | --- |
| 等待 1 秒，无恢复 | 通过，重复匹配 | 完成，摘要一致 | 零欠载，摘要一致 | 0 / 0 |
| 等待 1 秒，允许一次恢复 | 通过，重复匹配 | 完成，摘要一致 | 零欠载，摘要一致 | 0 / 0 |
| 不等待，允许一次恢复 | 通过，重复匹配 | 完成，摘要一致 | 零欠载，摘要一致 | 0 / 0 |

这三轮都没有有效失败 CSW、REQUEST SENSE 或实际重放，因此只能把恢复准入标为离线检查通过，把正常读取路径标为 bench-tested；不能声称错误后恢复已经实测成功。无等待对照也通过，**不能把连续成功归因于新增 1 秒间隔**。本轮无随机化、无冷启动，连续供电、之前的读取以及设备缓存/机械状态都是未隔离因素。

寻道间隔与有界恢复继续默认关闭。保留历史失败，M2 稳定性仍未验收；下一步优先增加有上限的寻道轮次，在相同软件条件下复现间歇性 `03/02/00`，观察“等待后仍连接并就绪”“等待中断连退出”“同位置仅重放一次”的真实路径，不以无限重试掩盖故障。无需因本轮成功提前判定硬件合格，也无需把未复现错误解读为必须换硬件。

原始日志、应用、配置、源码快照、备份来源、烧录记录和摘要分别保存在忽略目录 `.local/bench/2026-11-01-m2-seek-wait/`、`.local/bench/2026-11-01-m2-seek-recovery/`、`.local/bench/2026-11-01-m2-seek-recovery-control/`。没有保存音乐 PCM，未提交或推送。


| 原始证据 | SHA-256 |
| --- | --- |
| `seek-wait/direct.log` | `b5c141b7eb75d613ed80d33b16555b9c8a91cfe2d5e4d59b6c231fe68872c22e` |
| `seek-wait/direct-build/discora.bin` | `8c46a90592a934a43a378628d2acf1836e115f7f55278b0d360ebdffbe8abaa3` |
| `seek-recovery/direct.log` | `8e896fcdda1815560212540dd77c23f0d2c82222a4bd7aa07ef4ac4b9d9476ac` |
| `seek-recovery/direct-build/discora.bin` | `32589c35285c42696a93c6dbb70e998e35b570928205c8ab97b79ceaa82e8e41` |
| `seek-recovery-control/direct.log` | `86d606ad72308af3c20c73c3f54a1656f9d3c7871588a4f1403288b396f96deb` |
| `seek-recovery-control/direct-build/discora.bin` | `25c51145d1b7a5efa9977ff095b8159b9ded2e8da3636ccc8cfbdea5a9ae1baf` |
| 最终 `final-default.log` | `1461acfdbeaf055aa4de97bcef23c7bc086c0a2b2105b7bd9fca4bd73c94d3ae` |
