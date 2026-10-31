# PCM5102 音频输出准备与到货验收

状态：源码和离线检查已实现，实际模块、电气连接、声音、I²S 时钟均未验收。USB 转接头和 DAC 分别按到货情况验证；本页的测试音不是音乐 CD 播放。

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

## 候选接线

按 ESP32 板卡丝印找 GPIO，不凭排针位置猜测。下表仅为当前软件默认值，模块到货后再核对实物标签和电源设计。

| ESP32-S3 | PCM5102 模块常见标记 | 作用 |
| --- | --- | --- |
| GPIO4 | BCK / BCLK | 位时钟，主控输出 |
| GPIO5 | LCK / LRCK / WS | 左右字时钟，主控输出 |
| GPIO6 | DIN / DATA | 主控发送音频数据；不是 DAC 的模拟输出 |
| GND | GND | 公共信号地 |
| 供电待确认 | VIN / VCC | 按模块规定供电；不能由 PCM5102 芯片规格推断模块 VIN 可接 5V |

GPIO 为 3.3V 逻辑。不得把模块的 5V 接到 GPIO。USB GPIO19/20、COM GPIO43/44、Flash/PSRAM 与启动配置引脚不用于此接线。

芯片支持三线接口，当前不输出 MCLK；三线 PLL 启动时 SCK 的低电平条件、FMT 的 I²S 选择、XSMT 的解除静音条件，应按实际模块原理图/焊桥确认。模块已有相应配置时不盲目更改；到货照片和规格核对完成前，VIN、SCK、FMT、XSMT 的具体接法仍待定。[TI PCM5102 数据手册](https://www.ti.com/lit/ds/symlink/pcm5102.pdf)、[PCM5102A 数据手册](https://www.ti.com/lit/ds/symlink/pcm5102a.pdf)。

DAC 为线路输出，接有源音箱或立体声耳放/功放的输入；不能直接驱动无源喇叭。首次测试把音箱音量调低。

## 验收顺序

1. 模块到货后确认型号、VIN、GND、输入引脚、格式和静音跳线，保存照片与接线记录。
2. 只使用音频诊断配置，核对启动日志的模式、GPIO、stopped 状态。此时无自动出声。
3. 发送 `left` / `right`，确认对应模拟输出及音箱通道独立，记录左右是否对调；再测 `stereo` 和 `silence`。
4. 有示波器/逻辑分析仪时保存 LRCK、BCLK 和数据波形：目标 44.1 kHz、1.4112 MHz、Philips I²S、16-bit 双声道。没有仪器则把时钟测量留为未测试，不能由能听到声推断精度通过。
5. 检查 pause / play / stop / 换测试音，记录延迟、遗留数据、异常音和错误日志。当前暂停会丢弃最多约 40 ms 已提交 DMA 的数据，不是采样级无损暂停。
6. 诊断稳定、USB 直连寻道对照完成后，再接入真实 CD-DA 生产者和真实 I²S 消费者；重新测欠载、暂停位置和整轨/整盘播放。

硬件 DMA 自动清零可避免持续重复旧 DMA 数据，但当前没有独立 DMA 欠载计数，不能用软件队列未欠载推断硬件无静音间隙。[ADR-0006](decisions/0006-i2s-tone-diagnostic.md) 列出实现和限制。
