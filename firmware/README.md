# Discora firmware

这是**可供编译的最小工程骨架**，尚未实现 USB Host、CD 播放或刻录。ESP-IDF 版本基线选择 v5.4（不是“最新版本”的声明）。

```bash
# 先安装并加载 ESP-IDF v5.4 环境
cd firmware
idf.py set-target esp32s3
idf.py build
idf.py -p <SERIAL_PORT> flash monitor
```

`<SERIAL_PORT>` 是占位符；例如 macOS 可能为 `/dev/cu.usbmodem*`，Linux 可能为 `/dev/ttyUSB0` 或 `/dev/ttyACM0`。

预期串口日志包含 `Discora boot-only firmware skeleton`，并明确注明光驱、音频和刻录功能未实现。

后续建议模块边界：

- `usb_transport`：USB Host 枚举、MSC BOT 与传输错误处理。
- `mmc`：SCSI/MMC CDB 封装与设备能力检测。
- `cdda`：TOC、音轨扇区读取、缓冲。
- `audio`：立体声 I²S DAC 流。
- `writer`：介质能力、写入、缓存同步与封盘（在 M4 后引入）。

暂不添加空壳组件或虚构函数；通过相应里程碑后再拆分。
