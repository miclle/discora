# 2026-11-08：四键有声版本启用 OLED

## 结果与原因

用户接上 1.3 英寸 OLED 后无显示。核对已烧录的 `0.12.1-buttons-row`，其 PSRAM profile 显式设置 `CONFIG_DISCORA_OLED=n`，四键 overlay 没有覆盖，是本轮无显示的软件原因。用户确认模块是 SH1106 四针 I²C，接线为 3V3→VCC、GND→GND、GPIO10→SDA、GPIO11→SCL。

已部署 **0.12.2-buttons-oled**。启动日志确认 0x3c 探测、SH1106 初始化和首帧发送成功；用户随后确认 **DISCORA／TRACK --／NO MEDIA／I2S OUTPUT 文字清晰完整**。因此无介质画面的通信与用户目视结果为 bench-tested；播放、暂停、换轨等动态显示及显示刷新与有声播放并行的验收仍待有盘验证。

## 实现与软件验证

复用既有 SH1106 驱动、播放器快照及渲染逻辑，没有增加显示库、字体或模拟状态。独立 `bench/cd-player-oled.defaults` 在 PSRAM／四键配置之后启用 OLED，地址 0x3c。保留原无屏 profile，新增四键加 OLED 的 CI 构建配置，未提交、推送或运行远端 CI。

曲号来自有效 TOC；显示全部现有播放器状态：STOPPED、BUFFERING、PLAYING、PAUSED、UNDERRUN、FAULT；无有效目录时为 TRACK --／NO MEDIA。约每 200 ms 采样，仅在曲号／状态／介质可用性变化时刷新。底行 I2S OUTPUT 只表示输出模式。尚未实现歌曲名称、CD-Text、时间进度或音量显示。OLED 独立低优先级任务，不在播放器锁内进行 I²C；显示故障会退出显示任务，不停止播放器。

- SH1106 快照、状态标签、像素渲染、分页写入及传输失败检查通过（ASan／UBSan）。
- 77 组控制引脚检查通过；GPIO10／11 不与四键 1／2／42／41 或音频 15／16／7 冲突。
- ESP-IDF v5.4，全新 sdkconfig／build，`idf.py set-target esp32s3` 和 `idf.py build` 通过。
- 构建 defaults：sdkconfig → cd-player-i2s → cd-player-psram → usb-diagnostics → cd-player-seek-recovery → cd-player-buttons → cd-player-oled。
- 与刚部署四键版本对比，sdkconfig 唯一变化是 `DISCORA_OLED=n→y` 及新增 `DISCORA_OLED_ADDRESS=0x3c`。2 MiB PSRAM、3 秒预填、25% 幅度、欠载自动恢复、单次寻道恢复和所有按键／音频引脚均保持。

应用大小 402480 字节；应用 SHA-256 `2e4ea4cf9bee583890533cd9b0ea462ca6da67c91ed567938ee9afa16456a354`；ELF SHA-256 `00a3cda7df5cced8a9635195f62ae76d83e4f1ccf91eb5a9dc0a1c8a1d4fe956`。

## 部署与实屏证据

实时核对 USB-UART `1a86:55d3`、序列号 `5CF9109063`、芯片 MAC `7c:4f:ad:1d:0e:18`，Secure Boot／Flash Encryption 关闭，串口无其它占用。读取 `[0, 0x110000)` 备份，SHA-256 `ebbef3fdb97f6a8cb3e286756e4776b762398721de597e1061d1ccfedd6e8e89`。原应用逐字节匹配四键版 `6db61daa…`，分区表与候选一致。

仅写入 0x10000 factory app，写入摘要及独立 verify_flash 均通过；原前 65536 字节独立校验一致，未写 bootloader、分区表、NVS 或 eFuse。保留既有 2 MiB bootloader 映射及物理 16 MiB Flash 的容量提示，应用在原 factory 分区内。

2026-11-08 22:55:48（Asia/Shanghai）结束 25.080 秒启动采集，版本、IDF、完整 ELF 均匹配。四键输入、PSRAM 及 I²S 模式初始化正常，OLED 日志：

```text
SH1106 initialized SDA=GPIO10 SCL=GPIO11 address=0x3c; physical display unverified
```

光驱识别为 MATSHITA DVD-R UJ-898／HC10，桥接 VID:PID `13fd:0840`、Full-Speed。TEST UNIT READY 返回有效失败 CSW，REQUEST SENSE 为 `02/3a/02`，固件记录 medium not present；这是有效设备响应，不是 transport error。无 TOC，无 READ CD，没有播放或退碟命令。只发送 status：stopped、media=0、queued=0、pending=0、reads=0、continuous=0，I²S tx=closed、handle=0、pcm_submitted=0。无 panic 或显示任务退出，结束后串口已释放。

日志中的 physical display unverified 是驱动固定提示；其后用户明确回复“正常，文字清晰且完整”，补充了本次无介质画面的实屏证据。没有代替用户确认其它状态，也没有把 ACK 当成全屏验收。

本地忽略目录 `.local/bench/2026-11-08-buttons-oled/` 保存构建、配置差异、测试日志、产物及 `deploy/` 下备份、烧录、校验、启动日志。未保存 CD 音频。后续有盘时按[OLED 验收步骤](../oled-display.md#实屏验收)验证状态切换和声音并行，实体按键与机械退碟仍按各自清单验收。
