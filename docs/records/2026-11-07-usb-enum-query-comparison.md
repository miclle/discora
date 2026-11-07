# 2026-11-07：USB 仅枚举与查询的分阶段对照

## 目的与边界

[前序诊断](2026-11-07-usb-disconnect-diagnostics.md)已经确认：S3 在未播放时仍可能发生根端口 DISCONNECTION；Mac High-Speed 路径完整读盘通过。然而原 S3 程序上电后立即 INQUIRY，再每 5 秒 TUR，必要时 REQUEST SENSE／READ TOC；“未播放”并不等于未发送光驱命令。

本轮保持用户接回后的 S3 原生 USB、COM UART、充电宝 USB-A 直供及音频接线不变，只改变应用发出 BOT 命令的时机。不是 VBUS 电压、电流或 USB 波形测量，也不能单独区分命令兼容性与命令触发的光驱启动负载。

## 诊断实现

`0.11.2-usb-ab` 增加默认关闭的 `CONFIG_DISCORA_USB_ENUM_QUERY_TEST`，叠加文件为 `firmware/bench/usb-enum-query.defaults`。保留原 2 MiB PSRAM、GPIO15/16/7 和 USB 诊断日志配置。

- A 段：目标 `13fd:0840` 成功枚举并 claim BOT 接口后，观察 120 秒。应用不发送任何 BOT/SCSI 命令，包括 INQUIRY、TUR 和 REQUEST SENSE。Host 仍执行标准 USB 枚举、端口管理和 SOF；不是无 USB 总线活动。
- B 段：A 段满 120 秒且连接仍有效，自动在**同一设备句柄／连接代次**上执行原 INQUIRY 和每 5 秒就绪查询／必要的 sense、TOC，持续约 120 秒。结束点在查询调用边界，已经开始的查询／sense 链按原超时与所有权规则完成，不在窗口边界人为取消 USB transfer。
- `execute_command()` 使用共享策略的命令白名单：只有 B 段允许四种只读查询；READ CD、允许移除／退盘及未知命令一直禁止。播放器控制台只接受 `status`、`help`、`stop`，播放／换轨入口禁用。
- 掉线或 transport fault 锁定 FAILED，取消锁定 CANCELLED，完成锁定 COMPLETE；重枚举不能重新开始 A 段或绕过等待。只有重启 MCU 才开始新轮。掉线优先于同时到期的阶段切换。
- `stop` 通过原子标志请求结束，在 USB client 的命令边界处理；不是立即中断在途 transfer。日志记录阶段、失败所在阶段、时间、连接代次、地址、累计命令数、在途所有权及报告丢失。
- 不改变标准 USB 枚举、TUR 周期、BOT 格式和已有恢复策略。正常构建默认关闭该实验，不受阶段控制影响。

构建需依次叠加 `sdkconfig.defaults`、`bench/cd-player-i2s.defaults`、`bench/cd-player-psram.defaults`、`bench/usb-diagnostics.defaults`、`bench/usb-enum-query.defaults`。本诊断配置不是正常播放固件。

## 软件验证与部署

- ASan／UBSan 主机回归通过；新增测试覆盖 A/B 截止时间、四命令白名单、A 段零命令、禁止读盘／退盘、掉线优先、取消和重连不重启。
- ESP-IDF v5.4 默认查询配置与 A/B 配置均完成 `set-target esp32s3` 和 build。
- 目标 COM 序列号 `5C82128636`、VID:PID `1a86:55d3`，烧录器核实 MCU MAC `b8:1f:3f:d6:08:88`。仅写 app `0x10000`，写前核对旧应用，写后独立校验新应用及原 `0x0000～0xffff` 启动／配置区域。
- 新 app SHA-256：`90bfdfa503be9aece82b185eb55e6d87040f639e794d8b006d16df7b52d64196`。
- 原 app SHA-256：`8a9183c5d12e15eea669a137eb7320d03418be557bed8668a9eae7df0894ef75`，已保存在本轮目录 `previous-app.bin`，可恢复正常诊断播放配置。
- 本地证据目录：`.local/bench/8636-usb-ab-20261107/`，包含构建、主机测试、写前／写后验证、UART 日志和运行汇总；没有 CD PCM 文件。

## 实机结果

2026-11-07 17:54:41（Asia/Shanghai）开始捕获；最终自动到达 COMPLETE，两段使用同一枚举代次 1、地址 1、Full-Speed 根端口连接，身份在 B 段确认是 UJ-898 / HC10。没有在两段之间重启、烧录、改接或重新枚举。

| 指标 | 结果 |
| --- | --- |
| A 段实际长度 | 120.009990 秒，从 interface claim 后的 `phase_start_us=583749` 到 B 段 `phase_start_us=120593739` |
| A 段 BOT 命令 | 0；B 段切换日志 `commands_before=0` |
| B 段实际长度 | 120.000002 秒，COMPLETE 观察时间为 `240593741 μs` |
| B 段命令 | INQUIRY 1 次、TEST UNIT READY 24 次、READ TOC 2 次（头部与完整目录） |
| 命令结果 | 27 个 CSW 全为 0；无需 REQUEST SENSE，无 transport error 或 BOT reset |
| 连接 | root DISCONNECTION / ERROR / OVERCURRENT、client DEV_GONE 均为 0；地址和代次未变 |
| 音频路径 | READ CD 0 次，I²S opens=0、pcm_submitted=0，未测试播放 |
| 报告丢失 | 0 |
| 最终状态 | A/B COMPLETE 锁定，不再发查询；播放器 stopped、I²S closed、handle=0；串口已释放 |

日志 `ab-observe.log` 为 32722 字节，SHA-256 `4cfa08aa725f836de708a6ad1eea62a1f7b91b78b1bb51db2b27c38ad95a79d8`。`state.json` 保存阶段、播放器状态和 root 事件；`analysis.json` 独立统计查询类型、CSW、阶段长度和异常次数。结果不是依据控制器运行时间推测，而由 MCU 阶段时间和实际命令完成日志核对。

完成后控制器发了一次 stop 并确认输出关闭；COMPLETE 为终态，stop 没有重新启用或重置阶段。当前仍部署本轮 A/B 诊断配置，**播放命令禁用**；若恢复正常 CD 播放，须恢复原应用或关闭该配置重新构建。本轮变更未提交／推送。

## 解释与下一项假设

本轮证明当前连接状态下，S3 在零 BOT 命令的两分钟内可保持连接，随后现有查询在同一连接上也能成功运行两分钟；没有复现之前的故障，不能认定查询命令必然导致断开，也不能将稳定性标为已修复。

本轮之前光驱已在 Mac 上完成读盘，随后保持独立供电并接回 S3；没有要求光驱彻底断电。因此本轮不是冷启动证据。新增的 120 秒等待、光驱此前的初始化／运行状态以及前序转接变化，都可能影响复现；不能仅凭一次通过决定加入永久延迟。

下一项有区分力的对照是保持同一诊断固件与接线，**光驱与 S3 都完全断电后重新上电**，重复相同 A/B 流程，先确认这次通过是否依赖此前的运行状态。冷启动若也通过，再比较立即查询与延迟查询；若 A 段已掉线，停止进入 B 段，不用音频测试替代 USB 定位。


## 用户完全断电 10 秒后的重复观察

用户确认整套设备完全断电 10 秒后恢复供电。本轮没有烧录或发送显式复位命令，沿用同一 `0.11.2-usb-ab` 应用，2026-11-07 18:15:47（Asia/Shanghai）开始捕获。记录到完整 MCU 启动和 A/B 阶段日志；串口打开仍按既有方法预设 DTR/RTS 为 false。实际断电时长和电压归零来自用户说明，不是仪器测量，串口打开对主控的影响未作电气隔离验证。

- A 段 120.009989 秒，光驱命令数为 0，没有根端口断开或 client DEV_GONE。
- B 段 120.000002 秒，共 INQUIRY 1 次、TUR 24 次、REQUEST SENSE 1 次、READ TOC 2 次。
- 首次 TUR 返回 CSW=1，随后 sense 为 `06/29/00`；下次 TUR 已就绪，成功取得同一 13 轨目录。27 个 CSW=0、1 个 CSW=1，**不是 28 条查询全部成功**，也不是 transport error；正常的复位后状态处理完成。
- 全程同一连接代次／地址 1；root DISCONNECTION、ERROR、OVERCURRENT、client DEV_GONE、BOT reset、transport error、报告丢失全部为 0。
- READ CD=0、I²S opens=0，最终 COMPLETE、播放器 stopped、I²S closed；控制器确认停止后释放串口。

本地证据目录 `.local/bench/8636-usb-ab-20261107/cold-start/`：`setup.json` 保存用户断电说明；`ab-observe.log` 为 33459 字节，SHA-256 `fd953527b5eaed6231edc45812234d0650746f46e7d33440b5e85bce856c12c9`；`state.json`、`analysis.json` 保存阶段与命令统计。

本轮结果表明，“先等待 120 秒再查询”的通过并不只出现在此前 Mac 读盘后的状态下。但立即查询的同条件冷启动尚未对照，不能认定延迟就是修复，更不能据此加入永久两分钟等待或宣称整盘播放稳定。

## 0.11.3：准备零等待对照

将 A 段等待时间单独配置为 `CONFIG_DISCORA_USB_ENUM_WAIT_SECONDS`，范围 0～120，默认仍为 120。`bench/usb-query-immediate.defaults` 仅将它覆盖为 0；B 段仍为 120 秒，命令白名单、查询周期、超时、恢复、禁止音频和终态锁定规则均保留。0 秒表示 interface claim 后的下一次 client 循环开始查询，不是绕过标准 USB 枚举，也不是物理上零时延。

新增主机测试覆盖零等待不跳过 attach、不缩短 B 段、取消／掉线仍优先。这个开关只用于启动时机的诊断，不改变默认正常播放行为。零等待候选必须再经用户完整断电后观察，烧录后或串口打开后的热机检查不能替代该对照。

### 零等待候选已准备并部署，冷启动对照待执行

- `0.11.3` 的 120 秒与 0 秒两个 profile 均通过 ESP-IDF v5.4 `set-target esp32s3` / build，主机 ASan／UBSan 回归通过。生成的两份 sdkconfig 逐项对比，唯一差异为 `CONFIG_DISCORA_USB_ENUM_WAIT_SECONDS=120 / 0`；见 `config-comparison.json`。
- 0 秒候选 app SHA-256：`431e484e9fd109b1ab128ecc1abb11bd47d1168a80eb22b2f89674dc22cb0fcc`；同版 120 秒候选为 `db29b940ad869f66a4e264a94a249e5a34c3905455ef4b1744e7340cbfa160ba`。
- 在已确认的 8636 / MAC `b8:1f:3f:d6:08:88` 上仅写 app，写前核对当前 `90bf…`，写后独立校验 app 及原启动／配置前缀。旧 120 秒 A/B 应用保存在本轮 `previous-app.bin`；它仍是禁用播放的诊断程序，不是正常播放应用。正常播放诊断程序 `8a9183…` 的备份保留在前序目录。
- 烧录后的热机启动检查观察到 `enum_seconds=0`，查询确已启动，未观察到根端口断开；约 8 秒后主动 stop，确认 CANCELLED、I²S closed、opens=0、pcm_submitted=0，串口释放。这个短窗口只验证配置生效和停止行为，不计入冷启动对照，也不视为两分钟立即查询通过。
- 当前运行的是 **0.11.3 零等待诊断版，已 CANCELLED、禁止播放**。需要用户再次完整断电后观察零等待的同条件冷启动；尚未验证“120 秒等待是否必要”，尚未修改正常播放策略。

本次候选、构建、测试、写前／写后校验及热机启动日志位于 `.local/bench/8636-usb-immediate-20261107/`。本轮无提交／推送。

## 零等待冷启动对照结果

用户再次确认整套设备完全断电 10 秒后恢复供电、接线保持不变。2026-11-07 18:30:08（Asia/Shanghai）开始捕获，沿用已校验的 `0.11.3-usb-ab` 零等待应用，本轮没有烧录或发送显式复位命令。捕获完整 MCU 启动、`enum_seconds=0` 和查询阶段；串口预设 DTR/RTS=false，但打开串口对主控的影响仍未作电气隔离验证，断电时长及电压归零仍仅据用户说明。

- interface claim 后下一次 client 循环开始查询，转换日志 `commands_before=0`，查询阶段持续 **120.009964 秒**后 COMPLETE。
- 共 28 条查询：INQUIRY 1、TUR 24、REQUEST SENSE 1、READ TOC 2。27 个 CSW=0；首次 TUR 的 CSW=1 随后获得 `06/29/00`，下一次 TUR 就绪，成功读取 13 轨目录，lead-out LBA=252645。
- 同一连接 epoch=1/address=1；根端口断开、ERROR、OVERCURRENT、client DEV_GONE、BOT reset 和 transport error 均未出现，报告丢失为 0。
- READ CD=0、I²S opens=0、PCM submitted=0。COMPLETE 后确认停止，串口已释放；当前仍是禁止播放的零等待诊断版，未恢复正常播放应用。

本地证据 `.local/bench/8636-usb-immediate-20261107/cold-start/` 含 `setup.json`、`observe.py`、`state.json`、`analysis.json` 和 `ab-observe.log`。日志 24827 字节，SHA-256 `67c4544f11dbf8bddd494936fd6e7a90d5a8b4053c9435958f65fbada6efa062`。

| 用户报告冷启动后的策略 | 查询观察时长 | 查询 / 成功 CSW | USB 断开 | 目录 |
| --- | --- | --- | --- | --- |
| 先等待 120 秒，0.11.2 | 120.000002 秒 | 28 / 27 | 0 | 13 轨 |
| 不额外等待，0.11.3 | 120.009964 秒 | 28 / 27 | 0 | 13 轨 |

两个窗口都通过，均有一次正常处理的复位后状态；**没有证据支持将固定 120 秒延迟作为修复**。跨轮固件版本不同，0.11.3 的同版 0 秒／120 秒构建配置已确认仅等待值不同，但并未在硬件上执行同版 120 秒轮次，因此不将本次描述成完全相同二进制的严格单变量实验。

查询阶段未复现既有掉线，不能排除偶发物理问题或宣称持续播放已稳定。下一项有信息增量的实验是带相同 USB 诊断的持续 READ CD 数据读取，优先关闭 I²S 输出以区分读取负载与音频输出；本轮尚未执行该实验，不继续重复接线检查，也不自动加入延迟或重试。文档核对通过，本轮无固件源码修改、无提交／推送。
