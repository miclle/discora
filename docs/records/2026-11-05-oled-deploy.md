# 2026-11-05：OLED 固件部署与初始化超时

用户授权将新固件烧录到 Discora，保留软件时钟播放器及三个按键，并检查 OLED 初始化和启动日志。已部署 **0.10.0-oled / ESP-IDF v5.4 / software-clock**；写入与独立校验通过。**OLED 初始化失败：0x3c 探测返回 ESP_ERR_TIMEOUT**。软件显示功能仍为 implemented，不能标为实屏通过。

## 镜像、设备和备份

- 唯一目标 COM：USB VID:PID `1a86:55d3`、序列号 `5CF9109063`，ESP32-S3 rev v0.2。打开前检查串口未被占用；Secure Boot／Flash Encryption 均关闭。
- 备份 `[0x0, 0x110000)` 共 1114112 字节，包含 bootloader、分区、NVS 和完整 1 MiB factory 应用分区；另提取应用和分区表。原应用与此前 `0.9.1-track-buttons` 软件时钟镜像逐字节相同，镜像校验有效。
- 备份 SHA-256：`db5e9aac3dae4052557f9caa4f8ce4bdceb1eb15d4394c2c419b1b2e87c72b0b`。
- 使用 [上一轮已测试的 clock 镜像](2026-11-04-oled.md)，363552 字节，SHA-256：`c50e0c3d12614d18aec2657ebe38d082a844ada37a253ed0282a13660f66346a`。本次增量构建尝试因临时 ESP-IDF v5.4 目录已被清理而未执行；未重新构建，实际镜像摘要与已记录产物完全相同，image_info 校验有效。
- 配置确认：CD_PLAYER、EJECT_BUTTON、TRACK_BUTTONS、OLED 开启；I²S、测试音、受限 READ CD 自动实验、故障注入和寻道恢复关闭；OLED 地址 0x3c。
- 设备分区表与候选分区表逐字节相同，factory 位于 `0x10000`、大小 `0x100000`。仅写入应用，擦除范围 `0x10000–0x68fff`；未写 bootloader、分区表、NVS 或 eFuse。
- 写入摘要校验和独立 `verify_flash` 均通过。启动完整 ELF SHA-256 与候选匹配：`a92f298deea98befd9f2fb4aa1ed55372c350246a3ad473292279da91d494301`。

本地证据保存在忽略目录 `.local/bench/2026-11-05-oled-deploy/`：备份、候选镜像、设备信息、写入／校验日志、`boot.log`、`status.log`、`boot-checks.json`、`sha256.json`。这些文件不进入 Git。

## 启动与状态检查

烧录后复位，采集 UART0／115200 日志 **30.076 秒**：

- 运行版本为 0.10.0-oled、IDF v5.4，窗口内一次启动，无 panic。
- GPIO8／9 上一曲／下一曲、GPIO7 退盘均初始化为输入及内部上拉，30 ms 消抖、先释放再按下。
- `CD player boot=stopped sink=software-clock-no-I2S`，不输出 I²S 或声音。
- 481 ms：`I2C transaction timeout detected`、`probe device timeout`，随后 `display disabled until reboot: ESP_ERR_TIMEOUT; player continues`。没有 SH1106 initialized 日志；清理时的一次有界灭屏发送也失败，没有无限重试。
- USB Host 启动并等待光驱，本窗口没有光驱枚举、INQUIRY、有效 TOC 或 TUR 就绪。不把先前 13 轨目录作为本轮设备证据，也不根据等待状态推断光驱一定未接或损坏。
- READ CD、退盘动作、USB transport error、device closed 均为 0。未按实体键或发送播放／换轨／退盘命令。

之后重新打开 COM 进行 8 秒只读状态采集。打开串口再次引起启动，未另发复位脉冲；同样出现 OLED 超时。UART `status` 正常响应：`state=stopped`、`sink=software-clock-no-I2S`、`media=0`、`track=0`，queued／delivered／reads／underruns 均为 0，report_dropped=0。这证明显示失败后播放器控制任务仍响应，不等于实际光驱读取或按键动作验收。

原有 16 MiB 实体 Flash 与 2 MiB 镜像头提示仍在；本次未改变布局，应用位于已核对的 1 MiB 分区内。串口已关闭释放，设备保留 0.10.0 软件时钟播放器。

## 下一步与边界

用户随后确认 OLED「尚未接线或未供电」。因此本次是在屏幕未就绪条件下观察到探测超时，不能据此判断已接屏时的驱动兼容性或显示效果。接屏复测前需检查 VCC→3V3、GND→GND、GPIO10→SDA、GPIO11→SCL，以及模块上拉和实际芯片／地址。不要仅凭超时改焊桥或盲目更换地址。修复后需重启，显示任务才会再次初始化；若要验证曲目显示，还需光驱成功枚举和有效目录。

本次完成烧录、校验、按键初始化及日志检查；OLED 点亮、画面方向与曲目状态同步、实体按键、接屏播放并行稳定性均未通过。本轮未提交或推送。

## 用户补充的测试条件

2026-11-05，用户确认 OLED 尚未接线或未供电。该条件来自用户反馈，不是电压或接线测量；保留原始超时日志。固件已部署且播放器状态响应正常，下一步是完成 OLED 接线和供电后重启复测。本次补充记录未再次打开串口或烧录，也未获得光驱连接状态的新信息。
