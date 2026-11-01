# 2026-11-01：OTG 直连缓冲欠载负向验证

源码 0.5.4，ESP-IDF v5.4 (`67c1de1eeb`)，使用 [underrun-control.defaults](../../firmware/bench/underrun-control.defaults) 独立 set-target / build 通过。保持既有 COM、OTG 直连、充电宝辅助供电和同一 13 轨音乐 CD 不动。Discora COM `1a86:55d3` / `5CF9109063`；桥接 `13fd:0840`、Full-Speed BOT `08/02/50`、UJ-898 / HC10、LUN 0。没有 DAC 或 I²S 输出。

短探测通过后，从 LBA 414 顺序衔接；预填耗时 115025 μs。启动软件时钟消费约 2 秒后，真实暂停生产者 1200 ms，消费继续按时钟读取真实 CD PCM；没有直接修改欠载统计或伪造设备反馈。

```text
negative control: pause producer 1200 ms; expect real clock-sink underrun
buffer failed seconds=60 produced=489216 consumed=488184 underruns=1 missing_bytes=732 low_active=1032 high=148620 longest_read_us=17388 sink_max_late_us=0 transitions=0 joined=1
negative-control PASS underruns=1 missing_bytes=732 joined=1 ring_released=1; not a normal streaming PASS
read outcome failures=0 recovery_reserved=0 recovered=0
```

消费约 2.78 秒后出现一次真实欠载，任务完成、缓冲释放；60 秒是配置目标，不是完成播放时长。正常流结果正确为 failed，负向控制为 PASS；生产/消费摘要不一致是此中止窗口的预期结果。实验采集 17.838 秒，一次枚举、零设备关闭、零传输错误。此前 2026-10-31 在注入前离线的失败记录保留；本轮首次补齐该实机分支。

烧录前实时核对 0.4.3 应用，复用 sense-control 的 0x0–0x110000 备份并核对分区及原应用，仅烧录 0x10000，写入校验通过。实验后恢复默认关闭读取的 0.4.3；恢复文件不是全 16 MB 备份。最终 25.202 秒采集取得目录、5 次 TUR 成功，READ CD 数 0、无离线，串口已释放。

此结果覆盖软件时钟缓冲的预期欠载和退出，不覆盖真实 I²S DMA 欠载、未退出任务隔离或音频恢复。原始日志/配置/应用/备份保存在忽略目录 `.local/bench/2026-11-01-m2-underrun-direct/`，未保存 PCM。

| 证据 | SHA-256 |
| --- | --- |
| `direct.log` | `903850fdcd1905a17bfb869276ba8a2037fec9bcdb62c3d72adf7879c9963d47` |
| `final-default.log` | `f97b9d55770639c88614cdf9e4ba4a5a4a937cb641305f4b60a8cf521ee4a4d2` |
| `direct-build/discora.bin` | `26af9f351472389768bea876e203c4b927a67f75afe796a85e1b3e0afa67fc5e` |
