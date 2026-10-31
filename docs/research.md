# 参考资料与技术调查

以下是**研究入口**，不是 Discora 的兼容性测试报告。不要直接将外部项目的测试结果迁移成 Discora 的已实现状态。

## 官方资料

- [ESP-IDF USB Host Library](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-reference/peripherals/usb_host.html)：USB Host 生命周期、Client API 与事件。
- [ESP-IDF I²S Driver](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-reference/peripherals/i2s.html)：I²S 主模式、时钟与 DMA。
- [ESP-IDF Programming Guide](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/)：目标芯片与构建工具。
- [USB Mass Storage Class Bulk-Only Transport](https://www.usb.org/document-library/mass-storage-bulk-only-transport-rev-10)：CBW / CSW 协议规范。
- [Multi-Media Commands (MMC)](https://www.t10.org/)：光盘设备相关 SCSI 命令资料入口（以适用的规范版本为准）。

## 可参考的开源项目

- [julpage/ESP32_CD_Player](https://github.com/julpage/ESP32_CD_Player)：ESP32 平台通过 USB 光驱读取 CD-DA 的参考实现；尤其关注 USB/MMC 读盘与 I²S 主从模式。该项目的电路使用 DIT4096 生成音频时钟，改用常见 I²S DAC 时应切换主模式。
- [espressif/esp-idf](https://github.com/espressif/esp-idf)：USB Host、I²S 等官方实现。
- [espressif/esp-idf-ci-action](https://github.com/espressif/esp-idf-ci-action)：本仓库 CI 使用的 ESP-IDF 编译 action。

## 不确定性清单

1. MATSHITA UJ-898 + 当前 SATA/USB 桥接器的 MMC 指令透传支持。
2. 该桥接器能否在 USB Full-Speed 下以 BOT 模式工作。
3. ESP32-S3 USB 实际持续读/写速率以及电源干扰。
4. UJ-898 + 所选空白介质的最低写入速度。
5. 外部项目源码复用时的具体版权/许可证边界。

## 证据要求

新增可靠性结论时，链接设备日志、固件提交 SHA、测试参数和适用的官方规范；**仅链接文章而没有本机测试不能标记为 verified**。
