# 研发路线图

状态说明：`TODO` 未开始、`IN PROGRESS` 进行中、`VERIFIED` 通过实机验证、`BLOCKED` 存在障碍。仅文档或构建成功不代表硬件 VERIFIED。

| 里程碑 | 目标 | 状态 | 完成条件 |
| --- | --- | --- | --- |
| M0 | ESP-IDF 工程 + Linux 侧光驱预验证 | TODO | 构建成功、串口启动、保存 USB 描述符/TOC/CD-DA 提取结果 |
| M1 | ESP32-S3 USB Host + MSC BOT | TODO | 成功枚举 UJ-898、INQUIRY、TEST UNIT READY、REQUEST SENSE |
| M2 | SCSI/MMC CD-DA 读取 | TODO | READ TOC/READ CD 数据校验、连续吞吐实测 |
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
