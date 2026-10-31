# ADR-0002：原生 USB Host 上的最小只读 BOT 探测

- 日期：2026-10-31
- 状态：Accepted（实现待硬件验证）

## 背景

M1 需要直接观察 USB 光驱的真实 SCSI 返回值。普通文件系统挂载和面向磁盘的块读写接口不能证明 MMC 兼容。首轮设备尚未接线；先完成固件与组装文档，再由用户连接、烧录。

## 决策

1. 使用 ESP-IDF v5.4 原生 `usb` 组件，不新增第三方驱动，也不复制参考播放器源码。
2. 在单一 client 任务串行执行 BOT，另设 Host daemon 处理底层事件；回调只更新状态，不阻塞、不发起下一条命令。
3. 仅允许 `INQUIRY`、`TEST UNIT READY`、`REQUEST SENSE`。只访问 LUN 0，不实现任意 CDB、Data-Out、退盘、写入或擦除入口。
4. 只选 Full-Speed、MSC class `0x08`、BOT protocol `0x50`、alternate setting 0。接受 subclass `0x02` / `0x05` / `0x06`；ATAPI 子类将六字节查询 CDB 补零为十二字节。INQUIRY 必须确认可用 CD/DVD 设备（PDT `0x05`、qualifier 0），才继续查询介质。
5. 精确发送 31 字节 CBW；Bulk IN 按端点 MPS 分配接收长度，仍以实际长度、13 字节 CSW、signature、tag、status、residue 约束结果。禁止 BOT OUT 追加 ZLP。
6. Data-In STALL 清除设备和 Host 两侧 halt 后继续读取 CSW；CSW STALL 最多重试一次。传输错误、无效 CSW 或 phase error 仅做一次 Reset Recovery，随后停止命令，等待重新连接。
7. 为每次 USB 传输设置应用层 3 秒截止时间；Bulk 超时后 halt/flush，最多再用 2 秒等待回调。未归还的 transfer 保持隔离，不复用或释放。IDF 未公开 EP0 取消 API，控制传输超时需要拔下设备以归还回调；不能声称所有超时均可自动恢复。
8. INQUIRY 仅在 sense 为 NOT READY / UNIT ATTENTION 时最多尝试三次；身份确认后每 5 秒查询一次就绪状态。这是正常监测，不是无限重试失败传输。
9. 使用 UART0 日志，关闭主、次 USB console，保留原生 PHY 给 Host。启用 IDF 外部 Hub 与多级 Hub 配置，但不据此认定现有 Type-C Hub 兼容。

## 代价与验证边界

- 只支持当前配置、首个满足条件的 BOT 接口和 LUN 0；UAS、多 LUN 搜索、切换配置/alternate setting 均未实现。
- 查询失败不会被转换为“无盘”或“读取成功”。REQUEST SENSE 也失败时停止探测，不递归请求 sense。
- 固件长期保留一个 transfer 供串行复用；每次断连需等待传输归还，释放接口并关闭 device handle。Host daemon/client 为常驻服务。
- 当前测试验证协议构造、解析与内存边界；USB 调度、Hub、STALL 恢复、断连、供电和真实 sense 仍须实机验收。
- 官方依据：[USB Host Library v5.4](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-reference/peripherals/usb_host.html)、[USB MSC BOT 1.0](https://www.usb.org/sites/default/files/usbmassbulk_10.pdf)。

## 重新评估条件

若实际桥接器必须使用其他配置、接口子类或 LUN，应保留描述符和命令日志后单独扩展；不得绕过身份确认或直接引入刻录命令。
