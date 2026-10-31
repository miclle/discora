# Discora firmware

这是 **M2 CD-DA 只读探测固件**（`0.3.1-cdda-probe`），ESP-IDF 基线为 v5.4。默认执行基础查询和 READ TOC；可显式启用有界 READ CD 实验。单/8 扇区已与电脑参考摘要一致，256 扇区短突发为 739,858 bytes/s。尚无长时读取、完整重连/冷启动、I²S 或刻录验收，见 [实测记录](../docs/records/2026-10-31-m2-cdda.md)。

## 构建

```bash
# 先安装并加载 ESP-IDF v5.4 环境
cd firmware
idf.py set-target esp32s3
idf.py build
```

原始实测日志、烧录前备份和构建快照须保存到仓库根目录的 `.local/bench/`（已忽略），不要放入 `build/`：`set-target` 可能触发 fullclean。

默认启用外部/多级 USB Hub，使用 UART0 115200 日志，并关闭主、次 USB console；原生 USB PHY 用于 Host。`sdkconfig.defaults` 只对新生成的配置提供默认值，旧 `sdkconfig` 应在 `menuconfig` 中核对这些设置。

## 连接与烧录（用户准备好后执行）

先读 [组装文档](../docs/assembly.md)，核对具体开发板与电源路径。运行 Host 时原生 USB 串口不能同时用于电脑日志，优先使用板载 USB-UART 或外接 3.3V 逻辑 USB-UART。只选择本项目串口，不使用其它项目已连接的设备。

```bash
idf.py -p <DISCORA_UART_PORT> flash monitor
```

端口是占位符；macOS 可能为 `/dev/cu.usbserial*`，Linux 可能为 `/dev/ttyUSB*`，以实际 USB-UART 枚举为准。若只通过原生 USB 下载，应用启动后该设备口可能消失，需从 UART0 查看日志。

## 当前行为

1. 启动输出 `Discora M2 CD-DA read-only probe`、应用版本、IDF 版本和 ELF SHA-256，便于关联实测日志。
2. 记录 USB VID:PID、速度、接口 class/subclass/protocol；只选 Full-Speed BOT（`0x50`），subclass `0x02` / `0x05` / `0x06`、alternate setting 0。
3. 记录 Bulk IN/OUT 端点与 MPS；固定 LUN 0，通过 INQUIRY 确认可用 CD/DVD 设备（PDT `0x05`）。不以 VID:PID 单独推断型号。
4. 每 5 秒执行 TEST UNIT READY，命令失败时发送 REQUEST SENSE；输出真实数据、CSW status/residue、耗时和 sense。无盘是可记录的设备状态，不是假装成功。
5. 介质就绪后执行两阶段 READ TOC（格式 0、MSF=0），输出曲目数、类型、起止 LBA 与 `MM:SS:FF` 时长。最多 99 条曲目；同一就绪周期最多尝试三次，失败不会发布部分目录。边界见 [ADR-0003](../docs/decisions/0003-formatted-toc-probe.md)。
6. Bulk 超时后 halt/flush；STALL、无效 CSW、phase error 按 [ADR-0002](../docs/decisions/0002-read-only-native-bot-probe.md) 处理。传输故障后停止查询，重新连接才再次探测。
7. 断连后等待 transfer 回调，释放接口并关闭 device handle；打印剩余内部 heap，供重复插拔时观察趋势。

普通查询、CBW、CSW 和控制传输截止为 3 秒，READ CD 数据阶段为 30 秒；取消后最多再等待 2 秒。IDF 的 EP0 控制传输没有公开取消接口；控制超时或取消未归还时保留缓冲并隔离设备，须拔下设备。它不是完整的自动恢复驱动。

固件没有写入/擦除/退盘命令，不查询多 LUN，不切换配置或 alternate setting。`medium ready` 只代表就绪；`TOC validated` 只代表本次目录通过解析，均不代表 PCM 读取或播放通过。

## 受限 READ CD 实验

默认关闭。先核对供电、桥接器和测试盘，再运行 `idf.py menuconfig`，选择 `Discora bench probes → Run one bounded READ CD probe per MCU boot`（`CONFIG_DISCORA_CDDA_PROBE=y`），重新构建/烧录。启动会输出 `CDDA probe enabled=0/1`，须核对配置。

- 每次 MCU 启动最多一次，TUR 状态变化、换盘或重连不重新触发；失败后先检查日志，不反复复位试错。
- 要求有效 TOC，选择足够长的双声道音频轨，每次 1–8 扇区、每扇区 2352 字节；拒绝数据轨、跨轨、lead-out、零/超量请求。没有任意 CDB 或 Data-Out 入口。
- 先读单扇区，再读同位置 8 扇区并重复；内部 SHA-256 一致后，最多读 32 批 × 8 扇区。合计最多 273 扇区，包含重复区域。内部自比不等于独立参考对照。
- 只输出元数据、长度、耗时、摘要和统计，不打印 PCM，不存入 Flash。
- 18,816 字节共享响应位于静态内部 DRAM，USB transfer 另由原生 Host 分配；不放在 task stack，不默认依赖 PSRAM DMA。

边界及首轮失败修正见 [ADR-0004](../docs/decisions/0004-bounded-cdda-probe.md)。短突发速率不代表整张盘稳定播放；环形缓冲和 I²S 尚未实现。

## 不连接设备的协议检查

从仓库根目录执行，需要 Python 3 及支持 ASan/UBSan 的 C 编译器（Clang/GCC）：

```bash
python3 firmware/tests/run_host_tests.py
```

测试直接编译固件使用的 `probe_protocol.c`，检查 BOT 字节布局、描述符筛选、CSW 长度/signature/tag/status/residue、INQUIRY、固定/描述符 sense、TOC 命令/长度/曲目/lead-out、READ CD CDB/范围/整数边界和异常输入。输入为合成 fixtures，不是设备日志，不能验证 USB Host 调度或供电。CI 同时运行该测试和 ESP32-S3 构建。

## 当前模块

- `main.c`：启动探测服务。
- `usb_probe.c`：原生 Host client/daemon、串行 BOT、恢复与设备生命周期。
- `probe_protocol.c`：不依赖 ESP-IDF 的只读 CDB/CBW 构造和响应解析。

后续音频工作按实测结果引入 `mmc`、`cdda`、`audio` 的实际接口；本轮不添加 writer 空壳。
