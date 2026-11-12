# 研发路线图

本页记录里程碑状态与仍有效的待办。当前版本与证据见[工程状态](status.md)，历史阶段见[实验记录索引](records/README.md)。`TODO` 表示未开始，`IN PROGRESS` 表示仍有验收项，`VERIFIED` 表示对应功能已满足实机验收条件，`BLOCKED` 表示存在明确阻塞。

| 里程碑 | 状态 | 已有基础 | 剩余完成条件 |
| --- | --- | --- | --- |
| M0：环境、供电与电脑预验证 | IN PROGRESS | ESP-IDF 构建、UART 启动及电脑 TOC／CD-DA 对照已有记录 | 确认可复现的电脑数据连接；核对光驱负载供电与供电路径，按[验证计划](validation.md)补齐环境记录 |
| M1：USB Host／BOT | IN PROGRESS | 枚举、基础查询与连续就绪已实测 | 冷启动、受控插拔及异常清理验收，见 [#2](https://github.com/miclle/discora/issues/2) |
| M2：CD-DA 读取 | VERIFIED | 600 秒电脑摘要对照、整盘软件消费及重复有声播放通过，见 [#3](https://github.com/miclle/discora/issues/3) | 真实寻道失败、DATA STALL、CSW 超时与根端口断连的诊断及退出见 [#7](https://github.com/miclle/discora/issues/7) |
| M3：I²S 立体声播放 | VERIFIED（播放功能） | DAC 端时钟计数、三轮整盘 I²S 提交及用户反复实测完整有声链路通过，见 [#4](https://github.com/miclle/discora/issues/4) | 冷启动见 [#2](https://github.com/miclle/discora/issues/2)，真实故障退出见 [#7](https://github.com/miclle/discora/issues/7)，实体控制与整机集成见 M5 |
| M4：CD-R／CD-RW 刻录 | TODO | 仅研究目标 | 先通过最低写速／吞吐／桥接兼容性门槛，再对明确授权的测试介质写入、封盘和读回校验 |
| M5：控制界面与硬件集成 | IN PROGRESS | 四键五项基本操作获用户确认，OLED 静态画面和盘尾状态可用；170 mm 外壳已按光驱实测完成 CAD 与本地切片检查 | 按键专项手势与无盘场景、OLED 动态状态、双路 5V 供电／散热、洞洞板布局及实物装配验收 |

## 下一步验证顺序

1. **验证冷启动与受控重插**。记录枚举、旧目录失效、传输资源归还和异常复位。若出现真实读取故障或失联，保存失败窗口，按 [STALL 诊断](records/2026-11-09-usb-stall-diagnostic.md#后续如何形成修复结论)做单变量对照，并核对有界重读或退出。
2. **补齐控制和显示验收**：按[四键清单](playback-controls.md)与 [OLED 清单](oled-display.md)验证长按、上电按住、组合键、无盘／重插盘、暂停换曲及动态显示。
3. **整机验证**。完成[布局](perfboard-layout.md)、[供电](hardware.md)与[装配](../hardware/enclosure/README.md)后，记录实物尺寸、负载供电、散热、承载及入壳后的出声检查。光驱先按 [ADR-0035](decisions/0035-measured-drive-rear-wall-mount.md)核对后壁保护垫、两螺钉压条、接头上下偏置和自然外伸 14.5 mm 的实际走线，再验证拆装与进退碟；洞洞板候选仍须针对当前外壳重新闭合。

以上是规划，不自动授权烧录、播放、插拔、介质写入或改变供电。保留失败窗口，避免以新成功记录覆盖旧失败；各里程碑不因局部通过而整体标为 VERIFIED。
