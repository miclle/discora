# 实验记录索引

本目录保留各次实验的环境、结果、失败窗口和证据限制。旧记录中的“当前版本”“下一步”“未提交”仅对应当时；最新结论见[工程状态](../status.md)，有效待办见[路线图](../roadmap.md)。

原始日志和恢复备份不因阶段结束而自动删除；本地构建中间文件的清理边界见[贡献约定](../../CONTRIBUTING.md#文件与实验产物维护)。

## 2026-11-09

- [USB STALL 与状态超时分层排查](2026-11-09-usb-stall-diagnostic.md)
- [恢复边界离线修复](2026-11-09-usb-offline-recovery.md)
- [断电重连后盘尾回首曲验证通过](2026-11-09-disc-rewind-reconnect.md)

## 2026-11-08

- [第 13 轨单测、电脑对照与单次恢复实验](2026-11-08-track13-followup.md)
- [整盘播放在第 13 轨读取失败](2026-11-08-full-disc-read-failure.md)
- [四键控制实现与软件验证](2026-11-08-four-buttons.md)
- [盘尾回首曲与手动首尾循环选曲](2026-11-08-disc-rewind.md)
- [四键连续排针与装配图修订](2026-11-08-buttons-row.md)
- [四键有声版本启用 OLED](2026-11-08-buttons-oled.md)

## 2026-11-07

- [持续 READ CD 与 I²S 播放对照](2026-11-07-usb-read-clock-comparison.md)
- [USB 仅枚举与查询的分阶段对照](2026-11-07-usb-enum-query-comparison.md)
- [USB 自发掉线诊断](2026-11-07-usb-disconnect-diagnostics.md)
- [两轮整盘播放尝试的 USB 失联](2026-11-07-full-disc-usb-disconnect.md)
- [CyberTrack 面包板音频对照](2026-11-07-cybertrack-audio-crosscheck.md)
- [2 MiB 缓冲、自动恢复与连续播放](2026-11-07-buffered-playback.md)
- [2 MiB 缓冲连续播放日志分析](2026-11-07-buffered-continuous-log-review.md)
- [缓冲与 USB 诊断的审查、分阶段交付](2026-11-07-buffer-usb-review.md)
- [音频诊断审查与交付验证](2026-11-07-audio-delivery.md)

## 2026-11-05

- [OLED 固件部署与初始化超时](2026-11-05-oled-deploy.md)
- [DAC 接入后的无声排查](2026-11-05-dac-no-sound.md)

## 2026-11-04

- [SH1106 OLED 曲目与播放状态软件验证](2026-11-04-oled.md)

## 2026-11-01

- [GPIO8／GPIO9 换轨按键：实现与软件验证](2026-11-01-track-buttons.md)
- [换轨播放器固件部署（保留 GPIO7 退盘）](2026-11-01-track-buttons-deploy.md)
- [整张 CD 的播放器软件时钟验证](2026-11-01-m3-whole-disc.md)
- [播放器固定种子状态组合测试](2026-11-01-m3-state-sequences.md)
- [轨尾恢复与 I²S 适配器离线回归](2026-11-01-m3-player-tail.md)
- [新播放器有界控制压力](2026-11-01-m3-player-stress.md)
- [新播放器受控故障路径](2026-11-01-m3-player-faults.md)
- [新播放器整轨与 EOF 实验](2026-11-01-m3-player-eof.md)
- [I²S 空载实机与日志对照](2026-11-01-m3-i2s-empty.md)
- [13 轨 I²S 空载整盘验证](2026-11-01-m3-i2s-disc.md)
- [I²S EOF 收尾阶段定位](2026-11-01-m3-eof-phases.md)
- [真实 CD 源接入控制核心与软件时钟](2026-11-01-m3-cd-player.md)
- [仓库播放器 bench 工具](2026-11-01-m3-bench-tool.md)
- [固件自主连续播放](2026-11-01-m3-autoplay.md)
- [USB 长等待、取消与迟到回调离线覆盖](2026-11-01-m2-wait-flow.md)
- [OTG 直连缓冲欠载负向验证](2026-11-01-m2-underrun-direct.md)
- [REQUEST SENSE 分阶段诊断与超时对照](2026-11-01-m2-sense-diagnostic.md)
- [有界多轮寻道与恢复分支覆盖](2026-11-01-m2-seek-rounds.md)
- [寻道空闲间隔与单次恢复对照](2026-11-01-m2-seek-recovery.md)
- [共享恢复流程的离线分支验证](2026-11-01-m2-recovery-flow.md)
- [OTG 直连就绪故障与电脑对照](2026-11-01-m2-otg-direct.md)
- [电脑初始化后直连，末轨寻道仍失败](2026-11-01-m2-otg-after-pc.md)
- [GPIO7 轻触按键退盘：实现与离线验证](2026-11-01-button-eject.md)
- [GPIO7 按键退盘固件部署](2026-11-01-button-eject-deploy.md)
- [固件配置构建矩阵](2026-11-01-build-matrix.md)

## 2026-10-31

- [M3 音频控制与 I²S 诊断离线准备](2026-10-31-m3-audio-prep.md)
- [欠载负向测试准备与提前离线](2026-10-31-m2-underrun.md)
- [M2 音乐 CD 曲目目录实测](2026-10-31-m2-toc.md)
- [长时读取、寻道和缓冲实验](2026-10-31-m2-stream.md)
- [M2 READ CD 小片段、电脑对照和短突发](2026-10-31-m2-cdda.md)
- [UJ-898 首次真实 BOT 查询](2026-10-31-m1-optical-probe.md)
- [M1 离线固件验证](2026-10-31-m1-offline.md)
- [M1 首次烧录与 UART0 启动实验](2026-10-31-m1-first-boot.md)
- [USB-OTG 桥接后的空 Hub 枚举](2026-10-31-m1-empty-hub.md)
