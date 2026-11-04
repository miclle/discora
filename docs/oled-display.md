# OLED 曲目与播放状态

`0.10.0-oled`：**implemented，已部署；初始化超时，实屏未验收**。按仓库模块结构图和 SH1106 手册实现，不复制供应商例程或字体。实物如果是 SSD1306，不能直接使用此驱动；I²C ACK 也不能证明芯片型号或画面正确。

2026-11-05 已烧录软件时钟配置并独立校验，三个按键初始化和 UART 状态响应正常；0x3c 探测返回 `ESP_ERR_TIMEOUT`，未出现初始化成功日志。用户随后确认 OLED 尚未接线或未供电，完成接线和供电后需重启复测，详见 [部署记录](records/2026-11-05-oled-deploy.md)。

## 接线与配置

| ESP32-S3 | OLED |
| --- | --- |
| 3V3 | VCC（先确认模块适用 3.3V） |
| GND | GND |
| GPIO10 | SDA |
| GPIO11 | SCL |

断电后按实物丝印核对 VCC／GND 顺序。模块或外接电阻须将 SDA／SCL 上拉到 **3.3V**；固件不启用内部弱上拉，不接 5V 上拉，不从 DAC A3V3 取电。四针模块须自带上电复位电路。完整供电与连线见 [整机接线](wiring.md)。

- `CONFIG_DISCORA_OLED=y`：CD 播放器模式默认开启；查询、测试音和受限 READ CD bench 不开启。
- `CONFIG_DISCORA_OLED_ADDRESS=0x3c`：默认 7-bit 地址，可在 menuconfig 改为 `0x3d`。不要填写 `0x78`／`0x7a`；地址取决于模块 SA0，不自动扫描或改焊桥。
- 固定 GPIO10／11、100 kHz；I²S 改配到这些引脚时编译报错，需改回音频引脚或关闭 OLED。
- SH1106 132 列显存按 8 页写入，可见区假设为列 2–129。实屏须检查左右裁切、镜像及上下方向。

## 画面含义

显示 `DISCORA`、大字 `TRACK 01` 和以下状态；轨号来自实际 TOC，不是数组序号，不包含歌曲名称／CD-Text。

| 文字 | 含义 |
| --- | --- |
| STOPPED | 已停止，保留所选轨号；单轨 EOF 也显示停止 |
| BUFFERING | 正在预填音频缓冲 |
| PLAYING | 播放器正在消费 PCM |
| PAUSED | 已暂停 |
| UNDERRUN | 软件缓冲欠载，需显式恢复 |
| FAULT | 播放器故障；按已有 stop／play 流程处理 |
| NO MEDIA + TRACK -- | 无可用播放目录，包括启动、目录失效、退盘或断连；不据此诊断光驱内一定没有光盘 |

底行 `CLOCK - NO AUDIO` 表示软件时钟消费，不出声；`I2S OUTPUT` 表示选择 I²S 适配器，不是实际声音或 DAC 验收结果。

每 200 ms 采样一次，状态变化才刷屏；短于采样周期的瞬态可能不显示。取快照后释放播放器锁，再进行 I²C，音频任务不等待显示。缺屏、NACK、超时或初始化失败只关闭显示任务，播放／按键／USB 继续。失败会记录 `display disabled until reboot`，尝试一次灭屏；若总线已断，旧画面可能残留，须以日志为准。修复接线后重启，不在运行中无限重试。

## 构建

加载 ESP-IDF v5.4 后，从仓库根目录执行；使用独立配置，保留已有 sdkconfig 和实验产物：

```bash
mkdir -p .local/bench/oled
idf.py -C firmware -B "$PWD/.local/bench/oled/build" \
  -DSDKCONFIG="$PWD/.local/bench/oled/sdkconfig" \
  -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;bench/cd-player-clock.defaults" \
  set-target esp32s3
idf.py -C firmware -B "$PWD/.local/bench/oled/build" \
  -DSDKCONFIG="$PWD/.local/bench/oled/sdkconfig" build
```

该配置上电 stopped，保留 GPIO7 退盘、GPIO8／GPIO9 换轨，底行显示无声音。真实 I²S 模式将 defaults 后半部分改为 `bench/cd-player-i2s.defaults` 并使用另一套独立构建目录／sdkconfig。修改地址或关闭 OLED 时，使用同一 `-B` 和 `-DSDKCONFIG` 参数运行 `menuconfig`，再 build。以上命令不烧录。

## 实屏验收

1. 记录屏幕型号／控制器、SA0 地址、供电与上拉电压、ESP-IDF 和固件版本；光驱实验同时记录型号、桥接器 VID:PID 和光盘介质。
2. 核对目标设备并部署播放器配置后，启动日志应包含 GPIO10／11 和地址。检查全部文字清晰、无偏移、裁切或镜像；无有效 TOC 时不残留旧轨号。
3. 有效 TOC 发布后显示首个可播轨号和 STOPPED；使用 UART `play`、`pause`、`play`、`stop`，比对日志和画面。用 `next`／`prev` 及实体换轨键检查轨号、盘首／盘尾拒绝、换轨后播放状态。
4. 检查 EOF 停止、退盘和断连清除轨号、重新插盘保持停止；短暂 BUFFERING 可因采样未出现，持续缓冲应显示。
5. 使用已有故障注入配置时核对 UNDERRUN／FAULT；注入属于软件证据，不代表真实 USB 故障。另在屏幕不连接时冷启动，确认日志报告显示禁用且播放器仍可操作。
6. 正常接屏连续播放，对照欠载、读取错误、I²S 写入错误和供数事件，确认刷新没有引入音频回归。构建／离线渲染通过不代替该项实测。

本次软件证据见 [验证记录](records/2026-11-04-oled.md)。
