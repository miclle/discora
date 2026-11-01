# 新播放器有界控制压力

2026-11-01，0.6.2-player-stress / ESP-IDF v5.4 (`67c1de1eeb`)。沿用[整轨实验](2026-11-01-m3-player-eof.md)的设备、同张 13 轨 CD-DA、OTG 直连与辅助供电；保持接线，使用唯一 COM `1a86:55d3` / `5CF9109063`。无 DAC，没有音频输出。

每轮暂停/恢复、next/prev、非法 track 99、stop、快速 play/stop/play，限定 10 轮；状态检查队列停止、暂停消费不动、恢复播放、非法选择不改代次、欠载计数不增加。快速停止使在途旧回复按代次丢弃，不强制取消 USB。新增状态日志报告 heap free/minimum 和输出任务 stack minimum（ESP-IDF 单位为字节）。

仓库 bench 工具以显式端口、VID/PID/序列号四重核对身份；动作截止和整体截止有界。该工具自身不烧录/复位；本轮通过单独的本地部署脚本刷入实验镜像，完成后 finally 恢复默认固件。软件时钟实验配置执行 set-target esp32s3 / build。

原始证据位于 `.local/bench/2026-11-01-m3-player-stress/`：应用、配置、源码快照、`scenario/serial.log`、`scenario/report.json`、`boot.log`、恢复日志及 `sha256.json`。只写应用 `0x10000`，同此前备份/身份验证流程；RTS 启动不等于冷启动。

## 结果

37.073 秒窗口完成 10 轮、92 条控制命令（不含 status），确认响应 43.1–80.9 ms；含主机串口与轮询延迟，不是硬实时上限。累计有效读取 304 次，实际 stale=12，零欠载、读取错误或设备离线。结束 stopped / queued=0 / delivered=0，停止后的 reads 不再增加。

开始播放后和各轮结束 heap_free 均为 167736 字节、heap_min=167596、output_stack_min=3852。本窗口没有持续内存下降，不能外推长期零泄漏。

第一次运行未进入压力阶段：再次打开 COM 时观察到板卡启动日志，工具在 media=0 时过早退出。证据保留在 `attempt-startup-failed/`，该次也恢复默认固件；工具新增最多 45 秒目录等待后，同一镜像复测通过。工具没有主动发送复位脉冲，但不能保证操作系统打开 COM 不触发板卡复位。

最后恢复 0.4.3 查询模式；25.192 秒内目录有效、没有 READ CD、离线或传输错误，串口释放。原始串口启动边界含非 UTF-8 字节，分析时替换解码；原始 bytes 完整保留。
