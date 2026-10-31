# 当前工程状态

更新时间：2026-10-31（READ CD 小段音频和电脑参考）

证据分层：`planned` 为计划；`implemented` 为源码已实现；`bench-tested` 为在指定硬件上实验过；`verified` 为满足相应验收条件。已完成烧录、UART0、Hub/光驱枚举、三种基础查询的真实返回、61.2 秒连续 13 次 TUR 就绪，以及单张 CD 的 13 轨目录、READ CD 小片段/短突发与电脑参考对照；长时稳定、冷启动与受控重复插拔仍待验收，M0/M1 未整体通过。

| 事项 | 状态 | 证据 / 备注 |
| --- | --- | --- |
| 仓库创建及 Apache-2.0 License | 已存在 | 用户创建仓库时已有 LICENSE |
| ESP-IDF 固件构建 | 本地构建通过 | v5.4、目标 esp32s3；当前为 0.3.1-cdda-probe；默认关闭 279,472 字节 / 实验开启 291,136 字节，两配置均构建通过 |
| 烧录 / UART0 启动 | bench-tested | 写入校验通过；45 秒启动采集窗口无异常重启记录，详见首次实测记录 |
| 初始化 GitHub Actions | 构建成功 | [运行 41173591262](https://github.com/miclle/discora/actions/runs/41173591262)，对应初始化提交 `61b8229`，不是本轮改动的 CI |
| 本轮 CI 配置 | implemented | 新增主机侧 ASan/UBSan 协议测试；本轮已分阶段本地提交，未推送，未触发新 CI |
| USB Host / BOT 最小探测 | implemented；常规查询 bench-tested | 原生 USB Host、接口筛选、基础查询及 READ TOC 已实测；超时/STALL 故障恢复仍待触发验证 |
| 空 Hub 枚举 | bench-tested | USB-OTG 桥接后枚举 `05e3:0610`，Full-Speed，class `0x09`；下游未接设备 |
| UJ-898 在 ESP32-S3 USB Host 枚举 | bench-tested | 桥接器 `13fd:0840`，Full-Speed，class/subclass/protocol `08/02/50`；前期有离线重枚举，原因未定位 |
| INQUIRY / TEST UNIT READY / REQUEST SENSE | bench-tested | INQUIRY 为 MATSHITA UJ-898 / HC10；sense 有效，后续 61.2 秒连续 13 次 TUR 成功；TOC / READ CD 另见后续项 |
| READ TOC | bench-tested | 单张音乐 CD 取得 13 条音频轨、116 字节目录，lead-out LBA 252645；逐轨 LBA 和 lead-out 已与 macOS 参考目录一致 |
| CD-DA 2352 字节扇区读取 | implemented；小片段 bench-tested | 单/8 扇区与电脑 SHA-256 一致；256 扇区短突发 739,858 bytes/s。默认关闭，长时/寻道待测 |
| I²S 左右双声道输出 | 未实现 | 待 M3 |
| CD-R / CD-RW 实际刻录 | 未验证 | 存在 USB 带宽和最低写速风险；待 M4 |

请优先追加**带日期的测试记录**，不要覆盖此前失败证据。运行 CI 的绿灯仅表示在指定 ESP-IDF 环境中成功构建，不代表 USB、音频、刻录功能通过。

## 2026-10-31 软件验证记录

- `python3 firmware/tests/run_host_tests.py`：通过。直接编译固件协议代码，运行合成 fixtures 和 10,000 组边界输入，启用 ASan/UBSan。
- `idf.py set-target esp32s3 && idf.py build`：通过，ESP-IDF tag `v5.4`，Xtensa GCC 14.2.0；最终应用大小 277,008 字节，1 MiB app 分区剩余约 74%。
- [验证快照](records/2026-10-31-m1-offline.md) 保存源码与产物校验值、环境和明确未测试项；M1 原始产物后来被 fullclean 清除，详见下方证据可用性更正。
- [ADR-0002](decisions/0002-read-only-native-bot-probe.md) 记录原生 BOT、LUN/接口边界、错误恢复与 EP0 超时限制。

## 2026-10-31 首次上板记录

用户完成连接后，仅操作新出现的目标 COM，确认 ESP32-S3、16 MB Flash、芯片报告 8 MB PSRAM；其它项目串口未操作。备份被覆盖的扇区后烧录并校验成功，UART0 输出匹配本次 ELF 的启动信息。45 秒内未出现 Hub/光驱描述符和 INQUIRY 命令，不能标记 USB 通信成功。详情与日志摘录见 [首次上板记录](records/2026-10-31-m1-first-boot.md)。

## 2026-10-31 空 Hub 枚举

用户报告桥接后两半焊盘对 GND 均为 4.83 V。只接空 Hub 后，实际取得 `05e3:0610`、Full-Speed、Hub class `0x09` 的描述符；180 秒采集窗口无异常重启记录。BOT client 跳过 Hub 接口是预期行为。详情见 [空 Hub 记录](records/2026-10-31-m1-empty-hub.md)。

## 2026-10-31 光驱查询与首次就绪

真实取得桥接器 `13fd:0840` 及 UJ-898 / HC10 身份。第一轮 26 次重新枚举包含用户手动操作，不能用于判定自动掉线；静置轮前期仍有 6 次枚举，随后在启动后 87.925 秒 TUR 首次成功。没有记录到 ESP32 brownout、panic 或 BOT transport error。详见 [光驱实测记录](records/2026-10-31-m1-optical-probe.md)。

后续第三轮只枚举一次光驱，启动后 1.425–62.625 秒连续 13 次 TUR 成功，没有光驱离线、额外 ESP32 启动或 BOT transport error。该短窗口结果与此前失败/准备过程一并保留，详见同一实测记录。

下一项动作：扩大持续读取时长和寻道覆盖，设计 USB → PCM 环形缓冲，再验证 I²S 双声道；同时保留 M1 受控无盘/有盘、插拔及冷启动验收。按用户要求暂缓双 USB-A 内部测量，供电隔离仍未验证；异常时停止本轮实验。此前不把 M0/M1 标为 VERIFIED。

## 原始证据可用性更正

M2 的 `set-target` / fullclean 误删了放在 `firmware/build/` 内的 M1 原始日志、统计文件、原 ELF 和首次烧录前备份。历史记录保留摘录、统计与 SHA-256，但不能再用原始日志复核；首次烧录前固件不能恢复。已经从设备重新备份当前 Discora M1 的 Flash，并提取出与历史 SHA-256 一致的 M1 应用，可回退到 M1，不能替代丢失的首次烧录前备份。所有后续备份、日志和构建快照改存被忽略的 `.local/bench/`。详细记录见 [M2 TOC 实测](records/2026-10-31-m2-toc.md)。

## 2026-10-31：音乐 CD 曲目目录

`0.2.0-toc-probe` 已烧录，写入校验通过，READ TOC 的 4 字节头与 116 字节完整响应均为 CSW=0、residue=0，解析为 13 条音频轨、0 条数据轨，目录时长 56:08:45（分:秒:帧，75 帧/秒）。本轮只读取元数据，不包含 PCM、I²S 或刻录；M2 尚未整体完成。详见 [实测记录](records/2026-10-31-m2-toc.md) 与 [ADR-0003](decisions/0003-formatted-toc-probe.md)。

## 2026-10-31：READ CD 参考对照

首版实验的三次 READ CD 均未取得有效音频，包含自动离线和两次 3 秒截止；这些失败保留。修正后 `0.3.1-cdda-probe`（显式启用实验）首次单扇区读取耗时 3.633 秒并成功，35 条 READ CD 的 CSW 均为 0，累计读取 273 扇区（含重复区间）。单/8 扇区与 macOS 同盘、同位置参考 SHA-256 一致；256 扇区连续短突发为 739,858 bytes/s。当前仅小片段/短突发 bench-tested，不能把它等同于长时播放或完整 M2 VERIFIED。

实验开关默认关闭，每次启动最多一次，重连不会重新触发；音频数据阶段单独采用 30 秒截止。首次 USB 错误根因仍未定位，不因为后续成功而认定电源或桥接器完全合格。详情、版本/配置/最终部署和校验值见 [READ CD 实测](records/2026-10-31-m2-cdda.md) 与 [ADR-0004](decisions/0004-bounded-cdda-probe.md)。

最终开发板为 `0.3.1-cdda-probe` 默认关闭实验配置：30 秒独立采集取得有效 TOC，日志明确 `CDDA probe enabled=0`，READ CD 发送数为 0。开启实验的镜像及成功窗口独立保留。
