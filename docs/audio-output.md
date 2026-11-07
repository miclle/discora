# PCM5102 音频输出与验证

状态（2026-11-07）：PCM5102A → TPA3118D2 → 双喇叭已完成独立声道测试音和约 60 秒原始立体声 CD 试听（bench-tested）；整轨／整盘、冷启动与重复稳定性未验收。下文 UART 测试音模式独立于 CD 播放器，不能互用命令。

## 当前软件模式

默认仍为 USB 光驱探测。显式选择 `menuconfig → Discora audio diagnostic → Run UART-controlled I2S test tones instead of the USB probe`，或使用 [i2s-tone.defaults](../firmware/bench/i2s-tone.defaults) 加独立 sdkconfig 构建，才进入音频诊断。不要用已有 sdkconfig 缓存的开关值推断新 defaults 已生效。

音频诊断上电为 stopped，无自动出声。COM 为 UART0 115200；原生 USB 光驱任务不启动，不发送 SCSI/MMC。代码只在接收明确的 play / 测试音命令后开 I²S。

| 命令（回车结束） | 行为 |
| --- | --- |
| `left` | 清空旧源/软件队列/DMA，开始左侧 441 Hz；右侧为零 |
| `right` | 开始右侧 882 Hz；左侧为零 |
| `stereo` | 左 441 Hz、右 882 Hz |
| `silence` | 输出零样本，便于检查时钟与底噪 |
| `pause` | 关闭 I²S，保留未提交的软件队列 |
| `play` | 从 stopped 开始，或从 paused / underrun 显式恢复；fault 时先 stop |
| `stop` | 关闭并释放 I²S，清空软件队列，改变 generation，重置测试音相位 |
| `status` / `help` | 查询状态或命令；dequeued 仅表示已交给输出适配器 |

所有测试音为项目自己生成的 PCM16LE，左右交织，幅度不超过 4096，约 −18 dBFS；不是提取的音乐。441 / 882 Hz 以目标 44.1 kHz 为基准，实际频率需实测。

## 64fs 诊断对照

`CONFIG_DISCORA_DIAG_I2S_64FS` 默认关闭且仅在独立测试音模式可选。使用全新的 sdkconfig，按顺序加载 `sdkconfig.defaults;bench/i2s-tone.defaults;bench/i2s-tone-64fs.defaults`，可把每声道 slot 和 WS 宽度改为 32 个 BCLK，目标 BCLK 为 2.8224 MHz。PCM 数据仍为 16-bit stereo / 44.1 kHz，查表音调、幅度和 DMA 大小保持不变；启动日志报告实际选择的 slot 宽度与名义 BCLK。CD 播放和默认测试音继续使用 16-bit slot / 1.4112 MHz。

TI PCM5102A 数据手册表 11 同时列出 44.1 kHz 下的 32fs、64fs 时钟组合。因此该选项用于无声排查对照，不代表原配置错误，也不是已经验收的修复。两种配置都需实际听音／模拟输出与波形验收，详见[本次记录](records/2026-11-05-dac-no-sound.md)。

## MCU 时钟脉冲计数

`CONFIG_DISCORA_DIAG_CLOCK_PROBE` 默认关闭，仅在独立诊断可用。新 sdkconfig 按顺序加载 `sdkconfig.defaults;bench/i2s-tone.defaults;bench/i2s-clock-probe.defaults` 后，可通过 UART 命令 `clocks` 启动约一秒的 BCLK／LRCK 上升沿计数，不自动开始播放。两个 PCNT 单元从 MCU 的原输出 GPIO 输入路径取样，无需额外连线；输入使能不会替换 I²S 输出路由，关闭 PCNT 添加的上拉，未启用脉冲滤波。

采集由音频 owner 轮询完成，供数继续运行，日志报告各 GPIO 的原始 `edges` 和 `elapsed_us`，频率估计为 `edges × 1000000 / elapsed_us`。stop／pause／换源／输出故障会取消未完成采集；重复 `clocks` 在忙时拒绝。两套计数资源在诊断期间保留复用，初始化或采集错误会禁用探针直到重启，不伪造结果或反复分配资源。

首次 I²S 尚未初始化时输入路径可能浮动，停止状态的非零计数不能直接解释为有效时钟。该检查只提供 MCU 引脚输入路径的脉冲计数，计数时间基准和 I²S 同属 MCU，且 API／时间戳开销未校准；不能替代独立频率精度、占空比、边沿、DAC 端波形、DIN 位序及声音验收。初始化依照 [ESP-IDF v5.4 PCNT 文档](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-reference/peripherals/pcnt.html)。

## 接线与焊桥

模块已到货，已保存正反面参考图片和图示尺寸。具体步骤统一维护在 [PCM5102 硬件接线说明](../hardware/PCM5102-DAC/README.md)，包含电源前提、焊桥操作和首次电压检查；[整机接线图](wiring.md)覆盖光驱、主控、DAC、功放、喇叭及按键。

默认 GPIO4 → BCK、GPIO5 → LCK／LRCK、GPIO6 → DIN，GND 共地，SCK 接 GND；背面目标为 **1-L、2-L、3-H、4-L**。VIN 在确认模块规格支持后接稳定 5V，A3V3 留空。芯片规格不能替代模块 VIN 额定值，默认 GPIO4/5/6 接法未获得本次成功试听结论。

GPIO 为 3.3V 逻辑；USB GPIO19／20、COM GPIO43／44、Flash／PSRAM 和启动配置脚不用于 DAC 接线。模拟输出接功放或有源音箱输入，不能直接驱动无源喇叭，首次音量调低。

## 已通过的接法与默认配置差异

当前接法已同步到[可拔插洞洞板与逐孔接线](diagrams/discora-wiring.html#perfboard)：保留 GPIO15/16/7，新增 P1 电源插接和 P2 音频线束；实体装配与整板入壳未验收。

2026-11-07，当前 ESP32-S3（COM 尾号 8636）使用下表接法，换掉原 GPIO7→DIN 连接后完成右声道、双声道低音和原始立体声 CD 约 60 秒试听；用户确认左右连续清晰音乐、无明显杂音。DAC 与功放输出采用三线直连，本结论不等于 3.5 mm 插座／线缆已通过本轮验收，也没有证据认定它们损坏。

| 信号 | 本轮实测接法 | 仓库默认 |
| --- | --- | --- |
| BCK | ESP32-S3 GPIO15 → DAC BCK | GPIO4 |
| LCK / LRCK | ESP32-S3 GPIO16 → DAC LCK | GPIO5 |
| DIN | ESP32-S3 GPIO7 → DAC DIN | GPIO6 |
| 数字地与电源 | DAC GND 与当前主控 GND 共地；DAC VIN 接独立 5V；SCK 接 GND，H3 接高 | 电源按模块规格与实物确认 |
| 模拟左 / 右 / 地 | LROUT → 功放 INL，ROUT → INR，AGND → 功放输入 GND | 见硬件说明 |
| 临时测量线 | 已移除，GPIO4 留空 | 无 |

本轮保持 Philips I²S、44.1 kHz、PCM16 双声道、16-bit slot、无 MCLK；并非 64fs 对照配置。临时候选关闭退盘键、换轨键和 OLED；GPIO7 已作 DIN，**不能同时接默认 GPIO7 退盘键**。若仅调整仓库 I²S 引脚，应在新的 sdkconfig 中设置 `CONFIG_DISCORA_I2S_BCLK=15`、`CONFIG_DISCORA_I2S_LRCK=16`、`CONFIG_DISCORA_I2S_DATA=7`，并关闭 `CONFIG_DISCORA_EJECT_BUTTON`；这只对齐引脚，不会生成同一实验固件。

成功 CD 候选来自本地独立源码快照：左右各自缩放为 25% 数字幅度，保留原始声道，并在约 60 秒后自动停止。`bench-left/right/stereo` 命令与截止控制未合入仓库主固件；0.11.0 新增 `DISCORA_CD_PLAYER_GAIN_PERCENT`（默认 100，PSRAM profile 为 25），仓库播放器没有这项自动停止保障。本页的标准测试音仍为峰值 4096、左 441 Hz／右 882 Hz，显式 `stop` 停止。实验中 200 Hz 间歇音等同样属于临时程序。

定位证据及成功候选摘要见[对照记录](records/2026-11-07-cybertrack-audio-crosscheck.md)。早期 32fs／64fs 均无声、供电／焊桥及万用表结果见[历史排查](records/2026-11-05-dac-no-sound.md)。更换 DIN 连接后恢复声音将问题收窄至原数据连接／接点，不能据此判定两块 DAC 损坏，也未定位此前 USB 掉线原因。

## 复现与后续验收顺序

1. 按硬件说明确认实物型号、VIN 额定值、GND、输入引脚、焊桥连通性与电压，保存照片、测量值和接线记录。
2. 只使用音频诊断配置，核对启动日志的模式、GPIO、stopped 状态。此时无自动出声。
3. 发送 `left` / `right`，确认对应模拟输出及音箱通道独立，记录左右是否对调；再测 `stereo` 和 `silence`。
4. 有示波器/逻辑分析仪时保存 LRCK、BCLK 和数据波形：目标 44.1 kHz、1.4112 MHz、Philips I²S、16-bit 双声道。没有仪器则把时钟测量留为未测试，不能由能听到声推断精度通过。
5. 检查 pause / play / stop / 换测试音，记录延迟、遗留数据、异常音和错误日志。当前暂停会丢弃最多约 40 ms 已提交 DMA 的数据，不是采样级无损暂停。
6. 真实 CD-DA 生产者与控制层已接入；短时试听通过后，使用 [CD 播放器 I²S 模式](cd-player.md)，测实际欠载、暂停位置、轨尾排空和整轨/整盘播放。软件消费通过不能替代声音验收。

硬件 DMA 自动清零可避免持续重复旧 DMA 数据，但当前没有独立 DMA 欠载计数，不能用软件队列未欠载推断硬件无静音间隙。[ADR-0006](decisions/0006-i2s-tone-diagnostic.md) 列出实现和限制。

## 适配器离线验证边界

0.6.4 的主机测试直接编译生产 `audio_i2s.c`，以测试专用 IDF API 替身覆盖打开/预装/使能/写入/关闭失败、部分写入、句柄保留与重开、EOF 截止和短尾块静音补齐。播放器另覆盖 EOF 剩余数据少于预填量时的 pause/play。此检查不生成电气信号，不替代到货后的 L/R、时钟、噪声、末尾完整性实测；详见 [记录](records/2026-11-01-m3-player-tail.md)。

## 不接 DAC 的外设测试

0.7.2 增加 I²S 完成块、事件队列溢出、提交 PCM 和补零等独立计数。测试音空载对照发现同步日志会干扰供数窗口；独立低优先级日志任务和优先级调整后，相同序列的溢出由 5 降为 0。DMA 自动补零也会完成，事件队列溢出不是可直接换算的音频欠载计数；这些信息仅用于外设/调度诊断，波形、时钟精度和模拟输出仍待实测。见 [空载记录](records/2026-11-01-m3-i2s-empty.md)。

0.11.0 的 [PSRAM 播放 profile](../firmware/bench/cd-player-psram.defaults) 已包含上述 GPIO15/16/7、25% 幅度和关闭按键／OLED 的配置，另增加 2 MiB 缓冲与欠载自动恢复；它没有 60 秒自动停止或 bench 命令。当前测试与部署见[缓冲记录](records/2026-11-07-buffered-playback.md)。
