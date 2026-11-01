# 2026-11-01：电脑初始化后直连，末轨寻道仍失败

结论：同一个新 OTG 在电脑上取得目录和三段匹配参考的数据后，保持辅助供电接回 ESP32-S3，基础查询和短顺序读取成功。**绕过外部 Hub 后仍在轨 13 / LBA 223917 返回 READ CD 命令失败，随后 REQUEST SENSE 超时；完整首轨和 60 秒缓冲未运行。** 本轮采集没有 USB 设备离线，不把命令失败等同于物理断连。结束已恢复默认关闭实验的 0.4.3，目录有效。

## 条件与前置对照

- ESP32-S3 rev v0.2，16 MB Flash / 8 MB PSRAM；COM 仅匹配 `1a86:55d3`、序列号 `5CF9109063`，未操作其它项目串口。
- MCU native USB → 新 USB-C 公 / USB-A 母 OTG → SATA-USB 桥接器 `13fd:0840` → MATSHITA DVD-R UJ-898 / HC10；无外部 Hub。MCU 下 Full-Speed，BOT `08/02/50`、IN `0x81` / OUT `0x02`、MPS 64、LUN 0。
- 同一 13 轨音乐 CD，lead-out LBA 252645。光驱辅助供电仍接充电宝；实际供电规格、带载电压/电流和精确 OTG 型号未确认。
- 电脑端通过同一 OTG，High-Speed 480 Mb/s，40.281 秒的 39 次 IORegistry 采样中桥接器均存在、实例不变。目录 13 个起点与 lead-out 匹配；三个 8 扇区窗口的 SHA-256 与此前参考一致，包含 MCU 失败位置 LBA 0 / 223917。详见 [前置记录](2026-11-01-m2-otg-direct.md)。
- 用户确认只把 OTG 的 Type-C 端从电脑移回 MCU，两个 USB-A 插头及辅助供电保持不动。0.4.3 默认查询取得有效目录，4 次 TUR 成功，READ CD 数 0；原始采集包含移动前的等待，不把全部 78.193 秒当作 MCU 已连接稳定时长。

电脑初始化及持续辅助供电是本轮条件，不是已确认的修复。没有进行严格独立冷启动，不能由这轮成功查询消除首次直连反复离线的证据，或将该组合标为 VERIFIED。

## 软件与部署

复用已构建的 `0.5.0-audio-prep` / `otg-direct` 镜像，ESP-IDF v5.4 (`67c1de1eeb`)、Xtensa GCC 14.2.0。重新核对保存的 manifest 和当前固件源码基线，没有修改固件或重新构建。配置启用短探测、12 位置寻道、完整首轨、60 秒软件时钟缓冲；独立 I²S 和欠载注入关闭。

烧录前另备份 Flash `0x0–0x110000`，确认应用与 0.4.3 默认镜像相同，分区表一致。仅更新应用 `0x10000`，写入校验成功；bootloader、分区表和 NVS 未写入。结束写回原 0.4.3 应用并校验。1.1 MB 区间备份不等于完整 16 MB Flash 备份。两轮启动为 RTS 复位，不是完整断电冷启动。

## 实验结果

1. 单次枚举取得目录和光驱身份；短探测的 35 条 READ CD 完成，单 / 8 扇区摘要与此前相同。256 扇区顺序突发为 734188 bytes/s，最长一次 29023 μs。
2. 寻道第 1 项，轨 1 / LBA 150，8 扇区读两次摘要一致，首次读取耗时 3672295 μs。
3. 第 2 项，轨 13 / LBA 223917，Data-In STALL 后取得有效 CSW：status 1、received 0、residue 18816、耗时 9675 ms。不是 30 秒音频数据截止触发，也不是成功的数据读取。
4. 后续 REQUEST SENSE 的 Bulk IN 在 3020 ms 超时，没有有效 sense。执行一次 BOT reset recovery，报告 `ESP_OK`，停止命令探测；没有自动重放 READ CD。
5. 扩展阶段在此失败，12 项寻道只完成 1 项；完整首轨和缓冲均未执行，不登记为通过。

```text
I (8091) cdda_bench: seek step=1/12 track=1 lba=150 sectors=8 elapsed_us=3672295 repeat=match
W (17771) usb_probe: USB status=4 ep=0x81 actual=0
I (17771) usb_probe: command=READ CD CSW=1 received=0 residue=18816 elapsed_ms=9675
I (17781) usb_probe: command=REQUEST SENSE tag=43 requested=18 LUN=0
W (20801) usb_probe: transfer deadline exceeded ep=0x81; cancel and drain before reuse
E (20801) usb_probe: command=REQUEST SENSE transport error=ESP_ERR_TIMEOUT elapsed_ms=3020
W (20811) usb_probe: BOT recovery=ESP_OK; command probing stopped until reconnect
I (20831) cdda_bench: extended bench failed negative_control=0 seeks=enabled full_track=enabled (software sink only; not I2S playback)
```

主机实验采集 31.023 秒，单次 MCU 启动、一次桥接器枚举、零 device closed。成功长阶段日志被抑制：原始日志只有 35 条显式 READ CD 起始行，但由短探测 35 条、寻道第 1 项两条成功和第 2 项一条失败可知共执行 38 条 READ CD，不能仅按可见起始行统计总数。没有存储或打印音乐 PCM。

## 恢复和结论边界

0.4.3 默认关闭实验的 25.203 秒采集：一次 MCU 启动、一次光驱枚举、有效 13 轨目录、5 次 TUR 成功、READ CD 数 0，零 device closed / transport error。当前保留此配置，物理直连不需要再次改动。

相同末轨位置在没有外部 Hub 的路径中仍返回命令失败，移除 Hub 没有解决该故障，不能将 Hub 认定为唯一原因。本轮区分了有效的失败 CSW 和后续错误详情获取超时，但没有 sense 内容，尚不能区分介质/机械、桥接兼容性、Full-Speed 传输策略或带载供电问题。电脑同位置可读不等于已排除这些条件差异。

下一项可测假设是 READ CD 失败后的 REQUEST SENSE 等待策略是否过短；应将其作为单独诊断、记录真实错误详情，不改写本轮失败，也不通过自动重试掩盖失败。目前尚未修改该策略或执行下一轮。此前 0.4.2 的 600 秒顺序缓冲和电脑整窗摘要一致继续是独立历史结果，I²S 仍未验收。

## 证据与校验

本地忽略目录 `.local/bench/2026-11-01-m2-otg-after-pc/` 保存备份、源码、配置、镜像和原始日志。电脑及接回后的默认查询证据在 `.local/bench/2026-11-01-m2-otg-direct/`。没有提交或推送，保留已有 README / CAD 修改。

| 本轮文件 | 字节数 | SHA-256 |
| --- | --- | --- |
| `direct.log` | 16761 | `470de92a6e4ee91f447dc2bd6e050bec046a53cf44a008926bb36e6da1761bb3` |
| `final-default.log` | 8016 | `3541d3e6e33d640cda3e042ba127a80742631a199c9d4886f5b964e81b2bae37` |
| `before-flash.bin` | 1114112 | `4eeea6eb003498d4a5953c0eca5ee30c0a87e8fe921bb76e08df10b7e67c8fdc` |
| `direct-build/discora.bin` | 298288 | `0d14a381bb58050e997d31a96eb56cf08ebfd076030bdeb67a69dd61630fae47` |
| `restore-build/discora.bin` | 279504 | `b1878225b49fdf2c07816343b0159f714d5fee29902b9b39337e9b6b340a5c7e` |
