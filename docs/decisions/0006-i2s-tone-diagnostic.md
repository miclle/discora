# ADR-0006：独立测试音诊断与可离线验证的音频状态机

- 日期：2026-10-31
- 状态：Accepted；源码 implemented；短时 DAC 试听 bench-tested，完整验收未完成（更新于 2026-11-07）

## 背景

USB OTG 转接头和 PCM5102 模块尚未到货。M2 已有 600 秒顺序数据和缓冲证据，但回跳/远距离寻道失败；先准备与寻道无关的音频输出层，不能把编译或合成测试音当作 CD 播放成功。

## 决策

1. 增加默认关闭的 `CONFIG_DISCORA_AUDIO_DIAGNOSTIC`。启用后只运行独立 UART0 控制的测试音服务，不启动 USB 光驱任务；CD-DA bench 开关在此模式不可选。默认配置继续使用 USB probe，诊断模式上电为 stopped，显式命令才开 I²S。
2. `audio_core.c` 是无设备调用的单所有者状态机，复用已测试的帧对齐环形队列。状态为 stopped / prefill / playing / paused / underrun / fault；只在达到预填门槛后允许取数。欠载保留剩余软件数据，需显式 play 恢复；fault 需 stop 清除。
3. stop / fault / 新测试源清空队列并改变 generation，旧代次输入被拒收；pause 保留尚未交给输出层的软件队列。计数名为 dequeued bytes，不把交给 DMA 的数据当作已听到的音频。
4. `test_tone.c` 独立生成有明确标签的 PCM16LE 左右交织数据：441 Hz 左声道、882 Hz 右声道、双声道或数字静音，名义峰值 4096（约 −18 dBFS）。固定周期查表，不复制商业音频；它不是光驱反馈，也不是 CD-DA 读取模拟。
5. `audio_i2s.c` 使用 ESP-IDF v5.4 原生 standard-mode TX API：master、Philips I²S、44.1 kHz、16-bit stereo、16-bit slot、MCLK 不输出。目标 LRCK 44.1 kHz、BCLK 1.4112 MHz，实际频率和左右映射须实测。
6. 初选 GPIO4 / 5 / 6 作为 BCLK / LRCK / DATA，基于现有板卡引出资料，未做连通性或实机验收。首版只接受 GPIO1/2/4..18 且三者不同，避开 USB、串口、内存、启动配置和 RGB 引脚。模块 VIN/跳线按到货实物确认。
7. 诊断环形队列为 8 × 441 帧（14112 字节）；先填满后，给 4 × 441 帧 DMA（7056 字节）预装真实诊断数据，再 enable。每次完整写入检查返回值和字节数，目标写超时 25 ms；错误关闭输出并锁定 fault。
8. 单一任务处理 COM 命令、生成 PCM、调用输出层。暂停、停止和换测试音都会 disable / delete 通道，恢复时重建并预装，避免旧 DMA 数据串到新源。删除失败时保留 handle 并报告 fault，不覆盖仍拥有的资源。
9. 暂停不是采样级无损暂停：最多约 40 ms 已提交 DMA 的数据会被丢弃，软件队列保留。CD 音轨源尚未接入、精确播放位置 / EOF drain / 硬件 DMA 欠载统计 / 淡入淡出均未实现，不能据此宣布完整播放器通过。

## 验证与依据

- 主机侧 ASan/UBSan 检查预填充、暂停/恢复、停止后拒收旧代次、欠载显式恢复、fault 清除、声道独立、周期/幅度/端序及分块连续性。
- 默认 USB 和测试音诊断配置分别构建。DAC 尚未到货，本轮不烧录、不打开串口，不运行光驱或音频硬件实验。
- [接线和验收草案](../audio-output.md)；[离线记录](../records/2026-10-31-m3-audio-prep.md)。
- API 依据：[ESP-IDF v5.4 I²S](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-reference/peripherals/i2s.html)。
- 芯片接口依据：[TI PCM5102](https://www.ti.com/lit/ds/symlink/pcm5102.pdf)、[TI PCM5102A](https://www.ti.com/lit/ds/symlink/pcm5102a.pdf)。芯片级参数不替代具体模块供电/跳线说明。

## 2026-11-06 诊断补充

为排查已接 DAC 但无声的现象，新增默认关闭、仅独立诊断可用的 `CONFIG_DISCORA_DIAG_I2S_64FS`：数据宽度仍为 16 位，slot 与 WS 宽度均为 32，名义 BCLK 2.8224 MHz；保持测试音和 DMA 大小不变。默认 16-bit slot 和 CD 播放配置不变。两种时钟组合均在 TI 表 11 支持范围内，此项仅为可回退的对照实验，不据此推定原配置错误或模块损坏。验证状态见[排查记录](../records/2026-11-05-dac-no-sound.md)。

## 2026-11-06 MCU 时钟计数补充

在用户无逻辑分析仪／示波器、换 DAC 仍无声的情况下，新增默认关闭的独立诊断选项 `CONFIG_DISCORA_DIAG_CLOCK_PROBE`。通过原 GPIO 输入路径、两个 PCNT 单元和一秒门控计数，提供比名义配置值更直接的 MCU 端时钟活动证据；不增加接线，不修改 PCM 格式，不将计数正常解释为 DAC 端波形或声音正常。计数资源仅诊断启用时分配、在诊断生命周期内复用，错误后拒绝重试直到重启。接口、限制与配置见[音频诊断说明](../audio-output.md)。

## 2026-11-07 实测边界更新

PCM5102A 与 TPA3118D2 已完成独立左右测试音及约 60 秒原始立体声 CD 试听。成功实验使用 GPIO15/16/7、16-bit slot；主线默认 GPIO4/5/6 不变，64fs 选项仍只作诊断对照。原 DIN 连接更换后恢复声音，不能推断 DAC 损坏或原 32fs 格式不兼容。实际接法、临时候选与主线的区别见[音频说明](../audio-output.md#已通过的接法与默认配置差异)，日志与听感见[实测记录](../records/2026-11-07-cybertrack-audio-crosscheck.md)。此前 USB 掉线根因、长时间播放及波形指标仍未验收。
