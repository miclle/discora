# 四键播放控制

`0.12.5-usb-recovery-guard` 已部署，用户于 2026-11-09 确认四个实体按键的播放、暂停、上一曲、下一曲和退碟均正常，五项基本操作为 **bench-tested（用户实测通过）**，见[部署与验收记录](records/2026-11-09-usb-offline-recovery.md#四键基本操作验收2026-11-09用户实测反馈)。长按、组合按键及故障恢复等专项场景尚未完整验收。

四键接线沿用[连续排针方案](records/2026-11-08-buttons-row.md)，OLED 配置见[显示记录](records/2026-11-08-buttons-oled.md)。UART 共用控制核心的循环换轨、暂停保持、盘尾回首曲与再次播放已 bench-tested，见[首轮检查](records/2026-11-08-disc-rewind.md)和[重连后盘尾验收](records/2026-11-09-disc-rewind-reconnect.md)；本次基本操作反馈不扩大为这些边界场景的实体按键验收。

## 接线与配置

本方案保留当前有声接法：GPIO15 → BCK、GPIO16 → LRCK、GPIO7 → DIN。四个按键均为常开、非自锁轻触开关，一端接下表 GPIO，另一端接 GND；使用内部上拉，按下为低，不接 5V。

| 功能 | GPIO | 供应商排针位置 | 配置 |
| --- | --- | --- | --- |
| 播放／暂停 | GPIO1 | J2-4 | `DISCORA_PLAY_PAUSE_BUTTON=y`、`DISCORA_PLAY_PAUSE_GPIO=1` |
| 上一曲 | GPIO2 | J2-5 | `DISCORA_TRACK_BUTTONS=y`、`DISCORA_PREV_GPIO=2` |
| 下一曲 | GPIO42 | J2-6 | `DISCORA_NEXT_GPIO=42` |
| 退碟 | GPIO41 | J2-7 | `DISCORA_EJECT_BUTTON=y`、`DISCORA_EJECT_GPIO=41` |

四根信号线占据 **J2 连续第 4～7 针**，另从 J2-1 引一根 GND，共五芯。元件面朝向观察者、天线向上、USB 向下时，J2 是右排，由上向下计数。位置来自[板卡资料](../hardware/ESP32-S3-N16R8/board-data.json)，不是实物逐网验收；以 GPIO 丝印和通断测量确认。先断电，四脚按键须确认所选两端“松开断路、按下导通”。

GPIO41／42 有外部 JTAG 复用功能，本方案通过 `gpio_config()` 选择普通输入和内部上拉，不可同时接外部 JTAG 调试器；不需要改变 eFuse 或 USB-OTG 焊桥。当前 COM 使用 GPIO43／44，USB Host 使用 GPIO19／20，OLED 保留 GPIO10／11，音频仍是 GPIO15／16／7。依据 [ESP-IDF GPIO 文档](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-reference/peripherals/gpio.html)与本地 v5.4 的 `gpio_config()` 实现。

**GPIO7 只接 DAC DIN，不能接退碟键。** 旧查询配置默认退碟仍为 GPIO7，旧播放器默认换轨仍为 GPIO8／9；四键 overlay 明确覆盖四个引脚。所有控制引脚仅允许 GPIO1／2／4～18／41／42，并检查 I²S、OLED 和任意两个按键之间的冲突。旧的 GPIO4／5／8／9 四键方案已由本连续排针方案替代。

洞洞板候选的引出孔为：播放（M，A）、上一曲（N，A）、下一曲（O，A）、退碟（P，A），GND（J，A）。从已有排母底部焊脚引出短线，板外 P3 五芯可拔接头统一定义为 **1=GND、2=播放、3=上一曲、4=下一曲、5=退碟**。这是项目线序，不是商品接头默认针号；两侧按标记逐线核对。接头壳体、固定和实际弯线空间待试装。见[孔位总图与线束放大](diagrams/discora-wiring.html#button-harness)及[载板说明](perfboard-layout.md#四键线束引出)。

以全新 sdkconfig 和 build 目录，依次叠加有声、PSRAM、四键配置：

```sh
cd firmware
idf.py -B build-buttons -DSDKCONFIG=sdkconfig.buttons \
  -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;bench/cd-player-i2s.defaults;bench/cd-player-psram.defaults;bench/cd-player-buttons.defaults;bench/cd-player-oled.defaults" set-target esp32s3
idf.py -B build-buttons -DSDKCONFIG=sdkconfig.buttons build
```

继承 2 MiB PSRAM、3 秒预填、25% 数字幅度和自动重缓冲；在最后叠加 `cd-player-oled.defaults` 启用 GPIO10／11、0x3c 的 SH1106，显示曲号与播放状态。`cd-player-buttons.defaults` 只启用四键，不自行开启 USB 诊断、单次寻道恢复或故障注入。本次候选额外保留上一部署的 `usb-diagnostics.defaults`、`cd-player-seek-recovery.defaults`，准确构建配置见验证记录。原 PSRAM profile 本身仍关闭按键；必须在它之后叠加四键文件。

## 操作语义

| 当前状态／操作 | 结果 |
| --- | --- |
| 停止、有有效目录 → 播放／暂停 | 从当前曲起点开始，顺序播放至盘尾 |
| 播放、首次预填、欠载或自动重缓冲 → 播放／暂停 | 暂停，保留软件队列、源位置及连续模式；不在补足缓冲后自动出声 |
| 暂停 → 播放／暂停 | 恢复当前位置，必要时先预填，不重新跳到曲首 |
| 播放／停止 → 上一曲或下一曲 | 从相邻受支持音轨起点开始，顺序播放至盘尾 |
| 暂停 → 上一曲或下一曲 | 选择目标曲起点，清空旧音频，保持暂停；再次播放后顺序播至盘尾 |
| 首轨上一曲／末轨下一曲 | 循环选到末条／首条可播放音轨；暂停时保持暂停，其余可用状态从目标曲起点播放 |
| 连续播放到末条可播放音轨自然结束 | 排空并关闭输出后选回首条可播放音轨，保持 STOPPED；再次播放从盘首开始，不自动重播 |
| 只有一条可播放音轨时换轨 | 不重启本曲，不改变状态或位置 |
| 无有效目录／播放器 fault → 前三个键 | 拒绝，不积压动作；故障不通过按键自动重播 |
| 健康且已识别光驱 → 退碟 | USB client 等待当前命令结束，停止输出并使目录失效，再执行允许移除和退碟 |
| 重插盘／重连 | 刷新目录后保持停止，不执行旧手势 |

上一曲始终选择前一条受支持音频轨，不根据播放时长改成重播本曲。跳过数据轨、四声道轨及不足 8 扇区的轨；单音轨盘也能用播放键启动。连续模式末轨自然结束后，选回第一条可播放音轨并停止，OLED 显示对应实际曲号和 STOPPED；首次可播放轨不一定是 01。诊断用 `play`／`track N` 的单曲 EOF 仍保留该曲，手动 stop 也保留选择，故障／断连不走盘尾复位。连续模式轨尾排空期间按播放／暂停会暂停跨曲，恢复后再推进。

前三键由输出 owner 轮询，复用 30 ms 双向消抖、长按单次和上电先释放规则。检测两个及以上播放／换轨键同时按下后，抑制后续操作，直到三个键均稳定释放；此前已经处理的动作不撤销。退碟是独立输入任务和 USB 单槽请求，不参与前三键组合；退碟使目录失效后播放操作不再接受。

USB client 仍独占 SCSI；I²S 仍由输出 owner 独占。已在途 USB 命令不会被强制取消：暂停可接受该次回复但不消费；换轨、停止、退碟和失联以代次拒收旧音频。30 ms 是消抖门槛，不是声音切换或机械退出的最大延迟。

## 串口与已知边界

新增 `toggle` 与实体播放／暂停共用同一核心。`next`／`prev` 与按键一致：保留暂停并开启连续模式。保留原诊断入口：`play` 是开始／恢复单轨（已有连续模式时保留），`play-disc` 从当前曲起点启动连续播放，`track N` 选定曲并开始单轨，`stop` 停止并清空队列。`track N` 与 `stop` 仍取消连续模式。fault 须排查后显式 `stop`／播放，未增加 UART 退碟入口。

暂停关闭 I²S 会丢弃最多约 40 ms 已提交 DMA 音频；软件队列保留不代表采样级无损暂停。恢复低于预填门槛时需等待补缓冲，EOF 短尾使用既有特殊处理。换轨重新预填，存在间隔；新四键不改变 50 ms EOF 排空策略、USB 超时或读取恢复预算。

## 实机验收

记录主控、固件／IDF／ELF、光驱型号／版本、桥接 VID:PID、介质与日志，并区分软件状态、真实声音和机械观察。

1. 启动确认 GPIO1／2／42／41 初始化、有有效 TOC、stopped、READ CD 为 0；上电按住任一键不触发，释放再按才有效。
2. 播放键启动；再次按暂停，核对消费量停止且 I²S 关闭；再按恢复，核对源位置／代次未被重置，并听音确认两声道。首次预填和自动重缓冲中暂停也应保持停止输出。
3. 播放中前后换轨后 `continuous=1`；暂停中换轨仍 paused 且不读取新曲，恢复从目标曲起点开始。核对旧代次回复被拒收。
4. 播放和暂停状态分别验证首曲上一曲／末曲下一曲循环；只有一条可播放音轨时保持原状态。末曲自然结束等待输出排空，再确认首曲 STOPPED、无新增读取；按播放从首曲开始。短尾暂停恢复及连续轨尾排空暂停分别验证。
5. 长按 2 秒一次动作；释放再按、前三键重叠、释放抖动、无盘按住再插盘分别检查无额外动作。
6. 空闲和播放中退碟：核对先关闭输出，再有真实退碟返回，肉眼确认退出；重插盘不自动播放。成功 CSW 不等于机械退出成功。
7. 最终停止并确认 I²S 已关闭，保存失败日志及未验收项。未发生真实故障时，不把合成测试记为实机错误恢复通过。
