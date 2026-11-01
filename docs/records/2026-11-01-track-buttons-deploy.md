# 换轨播放器固件部署（保留 GPIO7 退盘）

2026-11-01，用户授权烧录支持上一曲／下一曲按键且保留退盘的播放器。部署 `0.9.1-track-buttons`、ESP-IDF v5.4 的 **software-clock** 配置：真实 CD 源、软件定时消费，不输出 I²S／声音。GPIO8 上一曲、GPIO9 下一曲、GPIO7 退盘均启用；故障注入、自动读盘 bench 和读取恢复关闭，上电 stopped。

## 目标、备份与写入

仅操作唯一匹配 `1a86:55d3`、序列号 `5CF9109063` 的 Discora COM；未操作另一原生 USB JTAG 串口。芯片为 ESP32-S3 rev v0.2，Secure Boot／Flash Encryption 均关闭。烧录前读回 `[0x0, 0x110000)` 共 1114112 字节，原应用与此前部署的 `0.9.0-button-eject` 镜像逐字节一致，镜像校验有效。

本地证据目录：`.local/bench/2026-11-01-track-buttons-deploy/`（已忽略）。保存完整备份、单独 1 MiB 应用备份、分区表、安全信息、写入／校验日志、启动日志、启动检查及 SHA-256 清单。

- 备份 `before-first-0x110000.bin` SHA-256：`f027a248d2bc7ffe5d27a3d4b5bcab5566d9d33b9a4df87e87b3ee4d8b277d77`。
- 新应用 `flashed-discora.bin`：342752 字节，SHA-256：`ee3445950c1ce81ef5978c5cd620e95180865fec31aba189d2afdac95db1d94a`。
- 新应用 ELF SHA-256：`3926f846e959f0838d4ac24ead5021eba3ed7e4ed7ccc6202305f6fa68692c6a`，与启动日志一致。

板上分区表与候选镜像逐字节相同：factory 位于 `0x10000`、大小 1 MiB。只写入应用，擦除范围 `0x10000–0x63fff`；写入摘要校验和独立 `verify_flash` 均通过。未重写 bootloader、分区表或 NVS，未修改 eFuse。

## 启动证据

复位后采集 30.001 秒 UART0／115200 日志：

- 运行版本 `0.9.1-track-buttons`、IDF v5.4、完整 ELF 摘要匹配。
- GPIO7／8／9 均为输入、输出关闭、内部上拉；换轨与退盘初始化日志均为 30 ms 消抖、先释放再按下。
- 播放器 `boot=stopped sink=software-clock-no-I2S`；目录发布后仍为 stopped。
- 识别 `MATSHITA / DVD-R UJ-898 / HC10`、桥接 `13fd:0840`、Full-Speed BOT。
- 当前音乐 CD：13 条音频轨，lead-out LBA 252645；6 次 TUR 就绪成功。
- READ CD、退盘完成、device closed、transport error、panic 均为 0；窗口内仅一次应用启动。
- 保留已有 16 MiB 实体 Flash 与 2 MiB 镜像头配置提示；本次未改变布局，应用位于已核对的 1 MiB 分区内。

串口已关闭释放，设备保持新播放器固件，不恢复查询版。本轮未提交或推送。

## 验收边界

烧录、读回校验、三路 GPIO 初始化和正常启动／目录查询为 bench-tested。未按实体键、未发送播放／换轨命令、未执行本版本机械退盘，不能把此次启动验证当成按键换轨或声音验收。0.9.0 查询配置的用户退盘成功反馈保留为历史证据，不自动覆盖新播放器的播放中退盘场景。

现在可按[换轨接线说明](../track-buttons.md)测试：GPIO8／9 分别经常开按键接 GND，GPIO7 退盘原接线保留。首轨按上一曲无相邻目标；可先按下一曲，再按上一曲。软件时钟模式只读盘与消费，不会出声；实体按键、长按／双键、播放中退盘和重插盘仍待验收，DAC 输出须另行完成硬件接入。
