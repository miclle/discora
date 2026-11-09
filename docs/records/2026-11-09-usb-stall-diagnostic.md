# 2026-11-09：USB STALL 与状态超时分层排查

**实机新结果**：本轮在 LBA 243351 再次复现 DATA STALL，CSW 在 clear 成功后 **245 µs** 返回有效失败状态，sense 仍为 `03/02/00`。原有一次寻道恢复首次捕获到真实成功，随后恢复供数；发生一次欠载，未播放到末曲 EOF。此次并非 CSW 超时，不能用它证明或否定上一轮状态超时的根因；延长 CSW 截止不是本次恢复成功的原因。详细过程见下文。

## 范围与当前判断

用户要求继续定位偶发 STALL／超时。复查三份原始日志、应用 BOT 控制流，以及实际构建所用 ESP-IDF **v5.4** 的 Host／HCD／HAL 源码；没有把电脑另装的 v5.5.1 当作板上基线。当前不能确认盘片、光驱机械／光学、桥接器或供电中哪一项是根因，也未发现能直接解释原始 STALL 的确定应用代码缺陷。

用户补充：光驱由电量充足的 PD 充电宝供电，仍使用同一张新购 13 曲 CD，已反复测试多次。未提供充电宝输出档位／额定电流、线缆压降、光驱输入负载电压或另一张盘的对照。电量和盘片新旧均保留为用户报告，不等同于电气测量或介质全盘独立校验。

## 从原始日志重新核对

| 失败窗口 | 第 13 轨 LBA | DATA 提交至 STALL 回调 | 后续结果 |
| --- | --- | --- | --- |
| 11-08 整盘 | 233783 | 9.672403 秒 | 有效 CSW=1，sense `03/02/00` |
| 11-08 单独末曲 | 244135 | 9.677852 秒 | 有效 CSW=1，sense `03/02/00` |
| 11-08 循环选曲后末曲 | 242415 | 9.671937 秒 | clear 返回成功后 CSW 等待约 3.017 秒超时，未取得 sense |

三次均无根端口 DISCONNECTION；这与更早的根端口掉线另作分类。前两次明确是设备通过 BOT 返回命令失败；T10 将 `02h/00h` 定义为 **NO SEEK COMPLETE**。第三次只证明状态阶段未在截止前完成，不能借用前两次 sense 为它补写错误码。

三次等待都约 9.67 秒，与设备侧读取／寻道重试达到某种内部期限的假设相容，但没有桥接器内部日志或总线抓包，不能据此认定具体固件定时器。已成功读过这些位置，且失败 LBA 改变，不支持简单归因于一个固定永久坏扇区；也不能排除间歇性介质读取或机械问题。

最近一次在 DATA STALL **之后**才因供数等待耗尽缓冲，随后 CSW 超时。因此增加音频缓冲只能改变声音还能维持多久，不能修复首次 STALL。把所有 USB 等待直接改长或无限重试也不会提供根因证据。

原始日志 SHA-256 分别为：

- `64a003108be896f435b5e703f3d3ff3945f98797bbcbce70f346abb7732b7a1c`
- `bb66684b4f93fcc39864a3b7b617da25f15ef72b227634f7f39b36b9ab2ae521`
- `37a2f5fda4b974f0ca1cccb4a3105d4ee96b4683107f3c22f3459b8da2ec4b79`

本轮提取结果保存于忽略目录 `.local/bench/2026-11-09-usb-stall/history-analysis.json`；原失败文件不改写。

## 软件路径核对与诊断限制

- `execute_command()` 串行发送 CBW→DATA→CSW。DATA STALL 后清设备 halt，再清 Host pipe；CSW STALL 仅清除后再取一次状态。没有并发提交下一条 CBW、无限恢复或丢失 transfer 所有权后直接复用的路径。
- DATA 等待本来就是 30 秒，历史约 9.67 秒的 STALL 是回调错误，不是 3 秒 DATA 截止造成。最近一次的 **CSW** 使用 3 秒期限；只有它是否过短值得单独做有界对照，目前尚不能称为已确认软件缺陷。
- 对照 USB BOT 1.0 第 6.7 节，当前 Data-In STALL 后继续读取 CSW 的处理方向正确。Espressif MSC 参考也分别操作 Host pipe 和设备 CLEAR_FEATURE；不能用仅调用 `usb_host_endpoint_clear()` 替换设备控制请求。
- v5.4 的 `_buffer_parse_error()` 会把 `actual_num_bytes` 设为 0。因此失败日志 `actual=0` 是驱动报告值，不能仅据此断言线缆上没有传过任何数据；新增日志使用 `reported_actual` 命名。
- 已追踪 Host clear 到 HCD／HAL。仅从 clear 函数未显式设置 PID 不能认定是此次超时根因；没有总线 DATA0/DATA1 抓包，不加入寄存器写入、SDK 私有结构修改或未经验证的数据序号修补。

依据：[USB BOT 1.0](https://www.usb.org/sites/default/files/usbmassbulk_10.pdf)、[T10 ASC/ASCQ](https://www.t10.org/lists/asc-num.txt)、[Espressif MSC clear_feature](https://github.com/espressif/esp-usb/blob/master/host/class/msc/usb_host_msc/src/msc_host.c)。后者为参考实现，实际运行版本仍以 v5.4 本地源码和构建摘要为准。

## 诊断候选与离线验证

源码 `0.12.4-usb-stall-diag` 增加 `data_stall`、`clear_halt`、`csw_wait` 异常路径日志，区分 Host halt、设备 CLEAR_FEATURE、Host clear 失败；记录命令 tag、CSW 尝试次数、等待期限、结果及耗时。正常音频数据不输出逐次日志，不保存 PCM。

默认 READ CD CSW 仍为 3000 ms；独立 overlay 设为 30000 ms。两候选都执行 v5.4 `set-target esp32s3`／`build`，配置逐项比较只有该参数不同；四键、OLED、GPIO15/16/7、25% 幅度、PSRAM、自动重缓冲和原有单次寻道恢复保持。原有 sense DATA 已为 30000 ms，不重复改动。

完整主机 ASan／UBSan 检查通过。补充共享等待代码检查：同一 4 秒回调在 3 秒期限下仍为超时，即使清理期间归还也不冒充成功；在 30 秒期限下正常完成；等待期间断连仍退出。补充检查编译运行通过，属于合成时间与回调，不是实机故障复现。

| 候选 | app 字节数 | ELF SHA-256 |
| --- | --- | --- |
| baseline，CSW 3 秒 | 403232 | `a587ad9136d37655896d8706103217448851292bcadd67085651330e75827df0` |
| csw30，CSW 30 秒 | 403248 | `4e7c4e5982f3328c6f4341ecd053c8a59ed333b9366ee2e8af10ef3ee83b2da5` |

首次构建入口选到了系统 Python 3.14，因缺少对应 IDF 虚拟环境在编译前退出；改用已有 IDF 5.4 Python 3.9 环境后两配置成功。失败输出保留。构建、配置与摘要位于同一诊断证据目录。

另以默认查询配置执行 set-target／build 通过，确认关闭 USB diagnostics 时使用原来的 3 秒回退值；没有把查询配置烧入板子。

## 实机复现与一次恢复

核对 9063 USB-UART、MAC `7c:4f:ad:1d:0e:18`，备份 `[0, 0x110000)` 并确认原应用与 0.12.3 的 SHA-256 `01c90b3d87d34e48e3c303876710e7aba8384a2c191cc11e860325ae6b682afb` 一致。只临时写 factory app，独立 verify_flash 通过；未写 bootloader、分区表或 eFuse。诊断应用 SHA-256 为 `60b4318fac770a9e0f858d76c2ac5a021d2fe40a662d5e82b3282cb28398af88`。

00:32 首次采集脚本遗漏 bench 报告的 `actions` 字段，status 后抛出 KeyError，随后 stop 的记录也报同样错误。原始串口确认 stop 已接受、READ CD=0、STOPPED、I²S 关闭，故不算读盘失败。修正记录字段后另建 `live-run2/`，未再次修改或烧录固件，失败目录保留。

正式窗口于 **2026-11-09 00:33:18（Asia/Shanghai）** 开始，共 **279.247 秒**。重启 MCU 采集，核对完整 ELF、UJ-898／HC10、13fd:0840 Full-Speed、13 轨 TOC；没有对光驱断电，不称为冷启动。只发送一次 `prev` 从停止的首曲选到末曲，之后仅 status；观察到真实恢复成功后立即结束场景，追加一次 stop。主机没有重复播放命令，也没有跳到失败 LBA。

| 阶段 | 实测 |
| --- | --- |
| 首次失败 | 第 13 轨 LBA **243351**，8 扇区、18816 字节，tag=2503 |
| DATA | 提交到 STALL 回调 **9.673202 秒**，status=4 |
| clear | 设备 CLEAR_FEATURE 与 Host clear 均成功；合计 **626 µs**，owned=0、gone=0 |
| CSW | 第一次等待 **245 µs** 成功，CSW=1、residue=18816；未发生第二次 CSW 重试 |
| sense | 有效 `03/02/00`，整个 REQUEST SENSE **5.207289 秒**，其中 DATA 约 5.130 秒 |
| 恢复 | 原有预算 reserved=1/1；等待 1000 ms、TUR 成功、同 LBA／扇区数重放一次成功 |
| 整个读取调用 | 最大 **16.018562 秒**，包含失败、sense、等待和重读，不是单次 DATA 耗时 |
| 音频软件表现 | 1 次 underrun、1 次自动重缓冲恢复；I²S 重新打开并提交更多 PCM，无写入错误 |
| 传输与设备 | 无 transport error、根端口 DISCONNECTION、panic 或报告丢失；只观察到本轮一次 MCU 启动 |
| 最终 | track=13、STOPPED、media=1、queued=pending=0、I²S handle=0、opens=closes=2；2582 次成功供数、累计提交 46504332 字节 |

`read_timing failed=0` 只说明最终读取调用成功，**不代表没有原始 READ CD 失败**；原始 `CDDA first failure failures=1` 和恢复记录均保留。恢复后短暂恢复输出由日志确认，没有用户对本轮声音的独立确认，不宣称无缝或完整末曲通过。读取范围已覆盖旧 LBA 233783、242415，停止前供数亦越过 244135；这仍不能排除间歇性的盘片／光驱问题。

此结果把本轮停顿收窄到**设备返回的读取／寻道错误及随后较慢的错误查询**。STALL 清除与状态读取在这次正常工作；30 秒 CSW 参数未发挥作用。原有 30 秒 sense DATA 配置则确实容纳了超过 3 秒的实际返回，但不能据此把所有历史超时归为 sense 等待过短。

完整原始日志 SHA-256：`03385f6cce5249a167c1fde6b3dbf846f9f8f0ed11f9df1fca721e56d577584e`。`live-run2/independent-analysis.json` 独立核对一次原始错误、一次恢复预留／重放／成功、无主机重复播放及最终关闭状态。没有保存 CD 音频。

场景结束后核对板上仍是本次诊断镜像，从本轮备份恢复原 0.12.3 factory app，并独立校验完整备份范围一致。未将 30 秒 CSW 对照默认留在板上；源代码中的诊断日志和 opt-in 配置保留待审查，未提交／推送。

00:40:22 结束 **25.065 秒**恢复后启动检查：完整 ELF `6f4d7d1938fad3551e3d7e4bfcdb3f1fc10c020cf14d7cdfa6d0fe9ef488c15c`、光驱身份／TOC、四键与 OLED 初始化正常；第 1 曲 STOPPED、media=1、READ CD=0、I²S 关闭，无 transport error 或 panic。原始日志与检查在 `restore-boot/`，lsof 确认串口已释放。没有复播。

## 后续如何形成修复结论

1. **若复现 STALL，且 CSW 在 3～30 秒内返回**：证明原截止会丢失迟到状态；保留实际最大耗时与有效 sense，再决定生产截止。等待变长只修复过早放弃状态，原始读取失败还须按真实 sense 处理；不能直接无限重放 READ CD。
2. **若 clear 成功、CSW 等满 30 秒仍不返回**：没有证据继续加大截止。优先用 USB 总线抓包或同桥接器的可用电脑连接区分设备 NAK／数据序号／Host 调度；历史 Mac 转接路径三次未枚举，必须先验证数据连接，不能再次把未枚举记为读盘对照。
3. **若获得有效 `03/02/00`**：已有一次有界寻道恢复只改善容错，不诊断具体硬件。用另一张已知可读 CD 做同路径对照；若多盘出现相似错误，再用已知稳定 5V 供电并测光驱接口处的负载电压，之后才考虑更换桥接器或光驱。一次只改一项，保留供电与温度条件。
4. **若本轮未发生 STALL**：只记录未复现，恢复原应用，不把 30 秒对照配置发布为修复，也不继续同条件无限等待错误。
