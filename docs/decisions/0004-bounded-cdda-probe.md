# ADR-0004：默认关闭、每次启动一次的 READ CD 实验

- 日期：2026-10-31
- 状态：Accepted；本组合小片段及短突发 bench-tested，长时读取待验收
- 扩展 [ADR-0003](0003-formatted-toc-probe.md)，保留 M1/M2 历史决策和失败记录。

## 背景

目录已能读取，但 READ CD 会触发不同的数据量、寻道和电机负载，不能沿用 TOC 成功推断音频可用。首个 `0.3.0-cdda-probe` 实验在单扇区读取阶段失败，光驱自动离线重枚举；重连后重新尝试又两次触及 3 秒截止时间。用户确认未移动接头或开关供电。电脑端 High-Speed 路径能够读取同盘的音频片段，尚不能据此排除 Full-Speed、Hub、电源或 MCU 驱动问题。

## 决策

1. 新增独立的 `probe_make_read_cd_cbw`，必须传入已校验音轨、起始 LBA 和扇区数；普通查询构造入口拒绝 READ CD。只接受音频轨、1–8 扇区、非负 LBA 和完全处于同一轨道内的区间；禁止跨轨或读 lead-out。
2. 固定 READ CD (`0xBE`)、12 字节 CDB、Expected Sector Type=CD-DA、DAP=0、RelAdr=0；User Data=`0x10`，不请求 C2 或 sub-channel。每扇区精确请求 2352 字节，无任意 CDB 或 Data-Out 接口。
3. 只选择 CONTROL 中数据/四声道位均未置位、长度足够的第一条音频轨。较长音轨从 INDEX 01 后 150 扇区开始，短轨从起点开始。该选择不是对 PCM 声道、字节序或音频质量的验收。
4. 先读 1 扇区，再从相同 LBA 读 8 扇区、重复读 8 扇区。比较单扇区与批量前缀、两次批量的 SHA-256。只有完全匹配才进行最多 32 批、每批 8 扇区的连续短突发，总读取最多 273 扇区。短突发吞吐包含日志/命令开销，不能替代长时播放或寻道验收。
5. `CONFIG_DISCORA_CDDA_PROBE` 默认关闭，位于 `menuconfig → Discora bench probes`。手动启用后每次 MCU 启动最多执行一次，TUR 失败、换盘、光驱断连/重连都不重置次数。修正首轮固件在自动重枚举后会重新触发实验的问题，避免故障循环。没有自动重放失败 READ CD。
6. 保持 CBW、CSW、普通查询和控制传输的 3 秒截止时间；READ CD Data-In 单独使用 30 秒，Bulk 取消后仍最多等 2 秒。电脑首次 8 扇区取样耗时约 3.86 秒，3 秒不能作为光驱读取的通用截止时间；但首轮约 2 秒出现的 USB 错误发生在截止前，不由此解释。
7. 一个常驻 client 串行持有 18,816 字节响应缓冲，放在静态内部 DRAM，USB transfer 另由原生 Host 分配；不将大响应放入 8192 字节 task stack，也不默认使用 PSRAM DMA。MBed TLS SHA-256 来自 ESP-IDF 自带组件，不引入外部源码。
8. 音频 bytes 不打印、不存入 Flash，也不提交商业光盘转储。只保存命令元数据、长度、sense、耗时和校验摘要；无论命令失败还是有效长度不足，都停止本轮音频探测。

## 验证和开放项

- 合成测试覆盖 READ CD 精确 CDB/CBW、端序、SCSI/ATAPI 长度、最大扇区数、无效音轨、跨轨和整数边界。
- 默认关闭和显式启用两种配置均需独立构建。构建通过不代表实机读取通过。
- 电脑参考经 macOS Audio CD 文件系统读取，已核对 2ch / 16-bit / 44.1 kHz 和 8 扇区长度；该 High-Speed 路径不是 ESP32-S3 Full-Speed 的验收。
- 原始失败、修正版本和最终上板状态见 [M2 READ CD 记录](../records/2026-10-31-m2-cdda.md)。持续吞吐、读取偏移/字节序、参考音频一致性、换轨和 I²S 仍需相应证据。
- 规范依据：T10 MMC-4 rev 5a §6.24，Table 349–353（[标准文档镜像](https://www.13thmonkey.org/documentation/SCSI/mmc4r05a.pdf)）。

## 2026-11-01：只读恢复实验的有限例外

0.5.2 新增默认关闭的单次 READ CD 恢复，仅接受有效 `03/02/00` 且设备仍连接、再次 TUR 就绪；传输错误不重放，重连不重置预算。此前无自动重放规则仍适用于默认配置，完整条件见 [ADR-0007](0007-bounded-seek-recovery.md)。
