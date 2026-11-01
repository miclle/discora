# ADR-0010：GPIO7 轻触按键与串行退盘

- 日期：2026-11-01
- 状态：Accepted；基本按键退盘 bench-tested（用户反馈，默认查询配置），其余场景未验收
- 补充 ADR-0002 / ADR-0008 / ADR-0009 中此前不含机械控制命令的边界；不改变历史实验结论

## 决策

使用 GPIO7 + 常开按键到 GND，内部上拉。供应商排针资料将 GPIO7 引到 J1-7，与现有默认音频、USB、串口和内存资源不冲突。固定引脚、可关闭功能；CD I²S 引脚冲突在编译阶段拒绝。默认查询和播放器可用；独立测试音没有 USB，长时 bench 不引入异步机械动作。

独立输入任务执行 30 ms 双向消抖，启动必须先稳定释放。原子单槽 mailbox 只接收健康光驱上的一次按下；断连/忙/故障禁用并清除请求。USB client 仍唯一拥有 transport，在当前命令完成后处理退盘。输出 owner 关闭 I²S 后才确认 quiescent；USB 任务等待时继续处理 USB 事件，超时或失联停止机械流程。目录失效、清空队列及代次变化阻止播放与退盘并发。

扩展固定白名单为 ALLOW MEDIUM REMOVAL（Prevent=0）和 START STOP UNIT（IMMED=0、LoEj=1、Start=0）。先允许移除，再退盘；任一步命令失败则读 sense 并退出，不重放。无数据阶段，SCSI subclass 0x06 使用 6 字节 CDB，ATAPI subclass 0x02/0x05 补零到 12 字节。机械操作非即时完成，每次 CSW 等待单独延长为 30 秒；保留既有一次 CSW STALL 恢复，其它所有权与隔离规则不变。

不新增写入/擦除/装盘/任意 CDB，也不承诺故障 USB 状态可退盘。成功 CSW 与实际光盘退出分开验收。已在途读取可延迟退盘，不声称按下即刻动作。

## 依据与验证

- [T10 PREVENT ALLOW MEDIUM REMOVAL / START STOP UNIT 行为说明](https://www.t10.org/ftp/t10/document.04/04-349r0.pdf)。
- [ESP-IDF v5.4 GPIO API](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-reference/peripherals/gpio.html)。
- [本项目板卡资料](../../hardware/ESP32-S3-N16R8/README.md)。
- 消抖/投递状态、精确 CBW/CDB、现有播放器与 USB 等待回归及配置构建见[验证记录](../records/2026-11-01-button-eject.md)；接线与硬件验收见[操作说明](../eject-button.md)。
