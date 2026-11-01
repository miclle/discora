# GPIO7 按键退盘固件部署

2026-11-01，用户授权将新固件烧入 ESP32-S3，准备测试按键退盘。本次部署的是默认查询配置 `0.9.0-button-eject`，ESP-IDF v5.4；`CONFIG_DISCORA_EJECT_BUTTON=y`，CDDA probe / CD player / 测试音关闭。

## 设备与备份

只操作当前唯一符合 COM `1a86:55d3`、序列号 `5CF9109063` 的串口；未操作另一个原生 USB JTAG 串口。esptool 确认 ESP32-S3 rev v0.2、8 MB embedded PSRAM，Secure Boot / Flash Encryption 均关闭，未修改 eFuse。原应用实际读回为 `discora / 0.4.3-underrun-bench / ESP-IDF v5.4`，镜像校验有效。

烧录前读回 Flash `[0x0, 0x110000)` 共 1114112 字节，保存原始镜像、独立 1 MiB 应用区与分区表；全部放在受 Git 忽略的 `.local/bench/2026-11-01-button-eject-deploy/`。原分区与候选构建分区逐字节一致：nvs 0x9000 / 24 KiB，phy_init 0xf000 / 4 KiB，factory 0x10000 / 1 MiB。

- 备份 `before-first-0x110000.bin` SHA-256：`b3cf73f57c8850aea32923ce9ad9ab1ccc0fb8950b7ba04715977712dfd4be60`。
- 新应用 `flashed-discora.bin`：285328 字节，SHA-256 `fb73d5c407d39c509a0f80fa2601eef614d7b04632128debe815c42135281f21`。
- 应用 ELF SHA-256：`396f0758fbdedcd57aa79bb811fac9aef920c12121fa4d9bed71845d10bce97f`，与实际启动日志一致。

只写入 `0x10000` 应用；擦除范围 `0x10000–0x55fff`。写入时摘要校验通过，随后单独 `verify_flash` 再次通过。未重写 bootloader、分区表、NVS 或其它应用；未提交、未推送。

## 启动验证

复位后采集 30.045 秒 UART0 / 115200 日志：

- 运行版本 `0.9.0-button-eject`、IDF v5.4，与候选 ELF 摘要一致。
- GPIO7 InputEn=1、OutputEn=0、Pullup=1；按键日志为 active-low、30 ms debounce、release before press。
- `13fd:0840` 桥接、Full-Speed BOT；INQUIRY 识别 `MATSHITA / DVD-R UJ-898 / HC10`。
- 当前 CD 目录有效：13 条音频轨、lead-out LBA 252645。
- 6 次 TUR 就绪成功，零 device closed、transport error、READ CD、退盘完成或 panic；启动窗口内无额外启动记录。
- 板上检测到 16 MiB Flash，镜像头继续沿用原配置 2 MiB，启动日志保留此提示；本次应用位于已核对的 1 MiB factory 分区内，未调整 Flash 布局。

原始安全信息、备份、写入/独立校验日志、启动日志、`boot-checks.json` 与 `sha256.json` 均保存在上述本地证据目录。采集结束串口已关闭。设备保持新固件，不恢复 0.4.3。

## 验证边界与下一步

烧录、GPIO 输入配置及正常查询启动已 bench-tested；尚未观察实际按键接通、ALLOW / START STOP UNIT 返回或机械退盘，因此退盘功能仍为 implemented，未标 verified。用户可按[接线说明](../eject-button.md)将常开非自锁按键连接 GPIO7 与 GND，再进行短按、长按、上电按住及重插盘测试。本镜像用于空闲退盘，未启用播放器，不构成播放中退盘验收。

## 用户实测反馈：按键触发与实际退盘成功

2026-11-01，部署后用户明确反馈：“按键测试成功，退盘也成功了”。本次按键触发及实际光盘退出记为 **bench-tested（用户实测反馈）**，上下文为刚部署的默认查询配置 `0.9.0-button-eject`、GPIO7、ESP32-S3 与 UJ-898 / HC10、`13fd:0840` 桥接链路。

反馈时没有新增串口采集，未取得本次按下对应的 ALLOW / START STOP UNIT CSW、sense、动作时延或重复次数；此前 30.045 秒启动日志不包含此次按键动作。用户实物观察与部署日志分别保留，不把反馈写成工具捕获的命令返回。

本次证明该组合的一次报告中的基本按键退盘链路成功，不标记完整 verified。长按只触发一次、上电按住不误触发、重插盘、无盘/数据盘、断连/重连、连续重复及播放中退盘仍待分别验收；电气波形、供电裕量和板卡逐网一致性未测。本次仅同步记录，未重新打开串口、烧录或发起退盘。
