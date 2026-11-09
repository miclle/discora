# OLED 中文布局与单轨进度软件验证

- 日期：2026-11-09。
- 源码版本：`0.12.6-oled-progress`。
- 状态：implemented；主机测试、渲染检查和 ESP32-S3 构建通过，后续已授权烧录 9063，启动及 OLED 初始化通过，中文与进度条已有用户实屏确认，长时音频并行待完整验收。

## 修改

移除固定 `DISCORA`、`I2S OUTPUT`；显示中文“曲目 XX”和播放状态、已播／总时长、底部单轨进度条。软件时钟配置在状态旁保留“无声”。中文采用 Noto Sans CJK SC 2.004 派生的固定界面字形，保留 OFL 1.1 许可、输入摘要及生成脚本，见[字体说明](../../firmware/fonts/README.md)。

本轨长度来自 TOC 起止 LBA；进度来自 `audio.dequeued_bytes`，按 2352 字节／扇区、75 扇区／秒计算，限制在本轨内。该位置表示交给输出适配器的音频量，不把 USB 预读计为已播，不表示 DAC 实际发声位置。暂停／缓冲不推进，换曲／手动停止归零，单轨 EOF 保留满条；连续盘尾仍按现有核心回首轨停止。无目录清除旧时间和进度。

显示任务继续在释放播放器锁后渲染和通信；像素未变不发送。前一帧缓存占用 1024 字节静态 RAM，避免在既有 4 KiB 任务栈内再放一帧；当前帧仍在原栈内。I²C 驱动、地址、引脚和有界失败退出逻辑不变。

曲名／CD-Text 读取、解码和滚动未实现；当前盘是否提供曲名未验证。固定界面中文不等同于任意中文曲名支持。

## 验证

1. `python3 firmware/tests/run_host_tests.py`：全部通过，使用 ASan／UBSan；包括现有 100 个种子／500000 次播放器动作检查。
2. OLED 新增检查：预读不推进、暂停保持、欠载自动重缓冲保留位置、非零轨起点、非连续轨号、换轨／停止／介质失效复位、单轨 EOF 满条、过大位置钳制、零时长、无目录清除及空／半／满条像素边界。原有 SH1106 分页／列偏移和每笔 I²C 失败覆盖保留。
3. 使用实际 `oled_render` 输出七种状态的 PGM 预览，左列 I²S、右列软件时钟；检查中文、时间、进度框和“无声”标记无重叠、无裁切。预览使用合成状态，不是设备截图。
4. ESP-IDF **v5.4**，ESP32-S3，独立 sdkconfig／build 执行 `idf.py set-target esp32s3` 和 `idf.py build` 成功。组合为 I²S＋PSRAM＋USB diagnostics＋单次寻道恢复＋四键＋OLED，GPIO15／16／7、GPIO1／2／42／41、GPIO10／11、0x3c、25% 数字幅度，与最近部署配置一致。
5. 最终应用 `discora.bin`：`0x62d10` 字节，1 MiB 应用分区余量 61%；SHA-256 为 `d16f1de46f543e5ff93dc755fcf34a7fd68ce31bbda7b3509fef7a4fafcb6215`。

本地证据位于忽略目录 `.local/bench/2026-11-09-oled-ui/`：`host-tests.log`、`set-target.log`、`build.log`、`preview.pgm`、`preview.png`、`sdkconfig` 及 `build/discora.bin`。开始激活工具链时，系统 Python 3.14 未匹配已有 IDF v5.4 环境；改用已安装的 `idf5.4_py3.9_env` 后成功，未重装或修改其它工具链。

上述离线阶段未访问串口、重启／烧录主控或发送光驱命令，没有新的设备型号、桥接器、光盘或声音实验结果。离线阶段结束时最近部署仍为 0.12.5；后续部署见下节，新画面按[实屏验收步骤](../oled-display.md#实屏验收)另验。


## 用户授权烧录 9063（22:52，Asia/Shanghai）

用户要求烧录后，以 VID:PID `1a86:55d3`、USB 序列号 `5CF9109063` 唯一匹配串口，确认无占用，再由 esptool 核对芯片 MAC `7c:4f:ad:1d:0e:18`。Secure Boot／Flash Encryption 均关闭。候选应用摘要与上述构建记录一致。

- 先备份 `[0, 0x110000)`，原应用与已部署 0.12.5 镜像逐字节一致，分区表与候选构建一致；备份 SHA-256：`8fbd8588459e3977168ad013f22d1fe837a712d90574b69b42edc1ebd50efc0a`。
- 仅向 `0x10000` 写入 404752 字节的 0.12.6 应用；写入报告 `Hash of data verified`，独立 `verify_flash` 确认新应用与原前 65536 字节均匹配。未修改 bootloader、分区表、NVS 或 eFuse。
- 重启采集 25.065 秒，22:52:50 结束；版本、ESP-IDF v5.4 及完整 ELF SHA-256 `b8a8ab9c524beafdd0140fa181827902b6bda6069a57f9ed99ac3aa44b0e6150` 均一致。
- 日志确认四键 GPIO1／2／42／41 与 SH1106（GPIO10／11，0x3c）初始化成功；识别 UJ-898／HC10、13fd:0840 Full-Speed 桥接器，TOC 为 13 条音轨、lead-out LBA 252645。该窗口无显示禁用、transport error 或 panic。
- 脚本仅发送一次 `status`，未发送播放／换轨／退碟；快照为 `stopped`、曲目 1、`reads=0`、`delivered=0`、`underruns=0`、I²S `tx=closed`。未开始音频读取；由用户自行测试显示。
- 采集后关闭串口，lsof 确认释放。初始化成功不代替中文清晰度、进度动态更新和音频并行实屏验收。

备份、写入／校验、启动日志和脚本位于 `.local/bench/2026-11-09-oled-ui/deploy/`。本次未提交或推送。


## 中文与进度条用户验收

2026-11-09，用户明确反馈“OLED 中文显示和进度条都正常”。据此将 9063 上 0.12.6 的中文显示及进度条记为 bench-tested（用户实屏确认）；不据此扩展为所有异常状态、计时精度或长时间音频并行验收。
