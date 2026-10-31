# 研发路线图

状态说明：`TODO` 未开始、`IN PROGRESS` 进行中、`VERIFIED` 通过实机验证、`BLOCKED` 存在障碍。仅文档或构建成功不代表硬件 VERIFIED。

| 里程碑 | 目标 | 状态 | 完成条件 |
| --- | --- | --- | --- |
| M0 | ESP-IDF 工程 + Linux 侧光驱预验证 | IN PROGRESS | 初始化 CI 已通过；仍需串口启动、保存 USB 描述符/TOC/CD-DA 提取结果 |
| M1 | ESP32-S3 USB Host + MSC BOT | IN PROGRESS | 已实测 UJ-898 枚举、INQUIRY / TUR / sense 和 61.2 秒连续就绪；长时稳定、受控插拔/冷启动及异常恢复仍待验收 |
| M2 | SCSI/MMC CD-DA 读取 | IN PROGRESS | READ TOC 已在单张 CD 实测；READ CD 数据校验、连续吞吐仍待测 |
| M3 | I²S 立体声播放 | TODO | DAC L/R 正确、完整音轨和整张盘稳定播放 |
| M4 | CD-R/RW 刻录可行性 | TODO | 通过最低写速/吞吐/桥接兼容性安全门槛；成功刻录并校验测试盘 |
| M5 | 控制界面与硬件集成 | TODO | 按键/编码器、电源管理、BOM、可复现装配 |

## 推荐最小垂直切片

```
BOOT → USB ENUM → INQUIRY → READ TOC → READ CD
                                ↓
                         PCM BUFFER → I²S L/R
```

**刻录不应阻塞首版播放器的成功标准。** M4 不通过时仍可以作为低成本双声道 CD 播放器继续开发。

## 本轮初始化产物

- 项目范围、需求、架构、硬件候选、验证流程和决策记录。
- ESP-IDF v5.4 的最小启动日志工程。
- GitHub Actions 只编译固件（不等价于接入真实光驱测试）。
- 仓库 AGENTS.md 与贡献约定。

## 2026-10-31：M1 离线开发

- 实现原生 USB Host/BOT 只读探测，支持 INQUIRY、TEST UNIT READY、REQUEST SENSE；详见 [固件说明](../firmware/README.md)。
- 增加协议测试、[组装手册](assembly.md) 和 [ADR-0002](decisions/0002-read-only-native-bot-probe.md)；构建与验证证据统一记录在 [当前状态](status.md)。
- 按用户安排，设备连接与烧录留待软件和文档就绪后进行。M0/M1 尚未达到实机 VERIFIED；M2–M4 未提前启动。

## 2026-10-31：M2 曲目目录

- 用户确认介质为音乐 CD，已实现并烧录 `0.2.0-toc-probe`，在同一 UJ-898 / HC10 + `13fd:0840` 桥接器上读出 13 条音频轨和 lead-out；[实测记录](records/2026-10-31-m2-toc.md)。
- 当前只读取目录，尚无 PCM 扇区或 I²S 输出。下一步为受限 READ CD 小段读取、长度和参考数据核对，再测连续吞吐。M1 的受控插拔、冷启动与故障恢复验收仍开放。
