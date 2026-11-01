# 2026-11-01：REQUEST SENSE 分阶段诊断与超时对照

目的：沿用电脑初始化后、辅助供电持续开启的新 OTG 直连路径，诊断此前 READ CD 返回失败 CSW 后 REQUEST SENSE 超时。用户要求保持接线，优先软件排查；本轮没有要求改变接线或电源，也没有把成品连接视为已经完成电气验收。

## 最小软件变更

源码版本 `0.5.1-sense-diag`。为 REQUEST SENSE 增加 CBW、DATA、CSW 日志，显示结果、累计耗时及适用的 transfer 所有权状态；诊断日志不读取尚未归还 transfer 的内容。

新增实验参数 `CONFIG_DISCORA_SENSE_DATA_TIMEOUT_MS`，默认 3000 ms，可选择至 30000 ms，仅影响 REQUEST SENSE 的 Bulk IN 数据阶段。READ CD 数据阶段仍为 30 秒，CBW / CSW / 控制传输仍为 3 秒；取消、等待归还、隔离以及无自动重放策略保留。新 [诊断配置](../../firmware/bench/sense-diagnostic.defaults) 采用与直连实验相同的短探测、12 位置寻道、完整首轨及 60 秒缓冲工作负载。

默认、30 秒诊断、3 秒对照各用独立 sdkconfig / build 目录执行 `idf.py set-target esp32s3 && idf.py build`。ESP-IDF v5.4 (`67c1de1eeb`)、Xtensa GCC 14.2.0；主机侧三组 ASan/UBSan 检查通过。主机测试不覆盖真实 USB 时序，新分阶段日志/超时分支仍须以实际调用为证。

## 硬件和部署边界

ESP32-S3 rev v0.2、目标 COM `1a86:55d3` / 序列号 `5CF9109063`；UJ-898 / HC10、桥接器 `13fd:0840`、Full-Speed BOT `08/02/50`、MPS 64、LUN 0；同一 13 轨音乐 CD，lead-out LBA 252645。OTG、辅助供电和盘未要求调整。沿用此前电脑初始化后的状态，不是独立冷启动。

前两轮分别备份 Flash `0x0–0x110000` 并与保存的默认 0.4.3 应用核对，仅烧录应用 `0x10000`，写入校验成功。后续复查复用第二轮备份，烧录前另用 `esptool verify_flash` 实时核对当前应用；不把复用文件称为新备份。备份不是完整 16 MB Flash。每轮结束恢复 0.4.3 默认关闭读取实验配置，记录独立 25 秒窗口；仅操作明确匹配的 Discora COM。实验启动为 RTS 复位。

## 30 秒配置：未复现错误

短探测通过，256 扇区突发 747811 bytes/s。12 个寻道位置全部完成，24 次读取的逐位置重复摘要一致；最慢单次 read 为 6854763 μs。此前失败的 LBA 223917 本次读取耗时约 388 ms，摘要仍与电脑参考一致。

完整首轨 LBA `[0, 19373)`：19373 扇区、45565296 字节、2422 条 READ CD，耗时 42881172 μs，约 1062594 bytes/s；SHA-256 为 `73ad449e02aa5513ffb632bfd632a2bf6bc048dabb675b4ba958b26e9a54a38f`。该整轨尚未取得独立电脑全区间参考，不称为独立内容校验完成。

60 秒缓冲 LBA `[150, 4650)`：生产/消费各 10584000 字节，欠载 0、缺失 0、joined 1，生产期低水位 110900 字节，最长 read 183620 μs；两端 SHA-256 均为 `7c144eb3ebb64f754f73e979f839ac4938b016047fa4244807b10bc7ad87407b`。这是软件时钟消费，不是 I²S 播放，也不是此前从 LBA 414 起的 600 秒窗口。

实验采集 137.897 秒，未触发 REQUEST SENSE。因延长截止的分支根本未调用，不能认定 30 秒等待解决了超时或寻道失败。此前失败日志保留。随后以同一代码、同一工作负载恢复 3 秒参数做对照，避免把运行状态变化误判为修复。

## 3 秒配置：定位到数据阶段

同一 0.5.1 代码、同一工作负载，仅把 sense 数据截止恢复为 3000 ms。短探测和寻道第 1 项通过；末轨 LBA 223917 再次返回失败。REQUEST SENSE 的 CBW 成功（累计 7 ms、owned=0），DATA 等待约 3 秒后超时，取消后 owned=0；未进入 CSW 阶段，没有有效 sense。实验采集 28.772 秒，完整首轨及缓冲没有运行。

```text
I (15531) usb_probe: sense phase=CBW result=ESP_OK elapsed_ms=7 owned=0
I (15531) usb_probe: sense phase=DATA deadline_ms=3000
I (18561) usb_probe: sense phase=DATA result=ESP_ERR_TIMEOUT elapsed_ms=3037 owned=0
E (18561) usb_probe: command=REQUEST SENSE transport error=ESP_ERR_TIMEOUT elapsed_ms=3040
```

本轮证明失败点是 REQUEST SENSE 的 Bulk IN 数据等待，不是 CBW 发不出去或 CSW 解析失败。是否只是等待上限不足，仍须在 30 秒配置下实际触发此分支；第一轮的成功不能回答该问题。随后复用 30 秒镜像进行一次复查。

## 30 秒复查：取得真实 sense

复用第一轮完全相同的 30 秒应用镜像。寻道前 7 项通过，第 8 项（轨 13 / LBA 252637，靠近 lead-out 的最后 8 扇区）失败。REQUEST SENSE 的 CBW 成功，DATA 在累计 2930 ms 返回、CSW 成功，18 字节有效响应如下：

```text
70 00 03 00 00 00 00 0a 08 00 00 00 02 00 00 00 00 00
sense key=0x03 ASC=0x02 ASCQ=0x00
```

ASC/ASCQ `02/00` 在 [T10 官方分配表](https://www.t10.org/lists/asc-num.txt) 中定义为 `NO SEEK COMPLETE`（寻道未完成）。这是设备返回的具体错误，不能直接推定光盘损坏、机械损坏或供电问题。错误之后约 450 ms 出现 device closed，再重新枚举；本次 sense 成功之前没有执行超时导致的 BOT reset recovery，不能把该离线归因于这条恢复命令。

本轮共两个枚举实例、一次关闭，未重放 READ CD；完整首轨和缓冲未进入。其后就绪查询得到 `06/29/00` 和 `02/04/01`。实验采集 40.047 秒。最后恢复默认关闭实验的 0.4.3，25.044 秒内由准备中转为有效 13 轨目录，3 次 TUR 成功，READ CD 数 0。

**30 秒上限尚未被证明必要或足以修复原故障**：本次数据在约 2.93 秒就返回，且失败位置与 3 秒对照不同，不是同一错误的配对延时实验。已确认软件能取得真实 sense，原 3 秒对照的故障发生在 DATA 阶段；是否存在更慢响应或桥接器错误恢复兼容性仍开放。

三轮结果表明该组合既可完成 12 位置寻道、完整首轨和 60 秒缓冲，也可在远距离寻道时失败。成功窗口只能标为 bench-tested，不足以宣告稳定修复。下一步优先设计软件侧的寻道节奏和有界错误恢复对照；本轮没有引入自动重试或新的机械控制命令，也没有要求用户换硬件。

## 原始证据

30 秒配置及默认构建保存在忽略目录 `.local/bench/2026-11-01-m2-sense-diag/`；3 秒对照保存在 `.local/bench/2026-11-01-m2-sense-control/`；30 秒复查保存在 `.local/bench/2026-11-01-m2-sense-recheck/`。保存配置、源码、镜像、备份、原始日志和摘要；没有保存音乐 PCM。尚未提交或推送，保留已有 README / CAD 修改。

| 证据 | SHA-256 |
| --- | --- |
| 第一轮 `direct.log` | `e933e6d2dc3123a6c984f4945e8026eb92752d61b7ca97131c41836007e8b67f` |
| 3 秒对照 `direct.log` | `bad3e36c757a1a0a8608550486a7694ae74970dc8d4cba7d9563d888cbd1f4e2` |
| 30 秒复查 `direct.log` | `908c85e3ccf7c924763edb96edee0157dbf89d222a78f77c2dd58921f1255f56` |
| 最终 `final-default.log` | `dd7b65c450402f65ed078b4b9b6692a5eb0fb9dc01869401265ac86e153945d2` |
| 30 秒应用（两轮相同） | `e527353e789a0009d6c6760cd7cef6c28aae0f5d81ffc7baff2bb148caaa2a8d` |
| 3 秒对照应用 | `030d06cc732cf28e96896176073884fce231f49686f6dfa444930df5140dad4e` |
