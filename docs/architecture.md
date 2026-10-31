# 架构初稿（待实验验证）

## 总体数据路径

```text
CD-DA disc
   ↓
MATSHITA UJ-898 (SATA/ATAPI optical drive)
   ↓
SATA ↔ USB bridge [必须验证 USB MSC BOT / MMC passthrough]
   ↓  USB Full-Speed (12 Mb/s theoretical line rate)
ESP32-S3 USB Host → BOT transport → SCSI/MMC command layer
   ↓
READ TOC → track metadata
READ CD  → 2352-byte audio sectors → ring buffer → I²S stereo
                                               ↓
                                         PCM5102A or similar DAC
                                               ↓
                                      L/R line out → amp / active speakers
```

主控和光驱需要安全的公共信号地；光驱 5V 电源不是来自 GPIO。SATA 光驱的低层电气接口由已存在的 USB 桥接器负责，ESP32-S3 不直接连接 SATA。

## 为什么不是普通 U 盘

- 数据盘可能暴露文件系统；**Audio CD 不等同于文件系统**。
- 需要 SCSI/MMC 指令：INQUIRY (0x12)、TEST UNIT READY (0x00)、REQUEST SENSE (0x03)、READ TOC/PMA/ATIP (0x43)、READ CD (0xBE)、START STOP UNIT (0x1B) 等。
- MSC Bulk-Only Transport 封装 CBW → data → CSW；必须正确处理端点、方向、residue、sense、stall、超时与重试。
- 不假设桥接器支持每一条 MMC 指令；首先用实际 USB 描述符与设备响应验证。
- 优先单一驱动访问任务，队列化命令，避免多个任务同时读写设备。

## CD-DA 音频

- 44,100 sample/s × 16 bit × 2 = **1,411,200 bit/s**（约 176.4 KB/s）。
- 一扇区音频为 **2352 字节**，每秒 75 扇区；留足环形缓冲以应对光驱抖动和 USB 调度。
- I²S 用主模式输出 BCLK/LRCK/DATA 给立体声 DAC；PCM 左右交织，必须明确左右采样与字节顺序。
- 对 USB DMA 使用符合内存能力要求的缓冲；在搬运、I²S DMA 与任务之间管理缓存所有权。
- 模块间以原始 PCM 帧、音轨元数据和显式错误码传递数据。

## 刻录通路（研究阶段）

```text
SD / flash ISO or PCM → source reader → buffer → USB BOT
   → MMC write/setup → WRITE(10) or suitable write mode
   → SYNCHRONIZE CACHE → CLOSE TRACK/SESSION → verify
```

刻录需要对介质能力、写入模式、缓存 underrun 和状态变化建模。数据 CD 1× 用户吞吐约 150 KB/s；音乐 CD 1× 原始音频吞吐约 176.4 KB/s。USB Full-Speed 理论 1.5 MB/s 并不是持续有效吞吐，不能推定 8× 刻录可用。**若最低允许写速超过实际吞吐，必须及时停止该方案而非冒险烧盘。**

## 待决策事项

1. 实际 USB 桥接器 VID:PID、接口协议和 MMC 透传能力。
2. 选用现有 USB Host MSC 扩展，还是独立实现可控 BOT 层。
3. 缓冲空间与 SD 卡传输是否与 USB 带宽/任务调度冲突。
4. PCM5102A 不需要外部 MCLK 的具体模块接法与时钟精度验证。
5. 是否需要 PSRAM；初期先不用其承担 USB DMA。
