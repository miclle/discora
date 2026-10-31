# 2026-10-31：M1 首次烧录与 UART0 启动实验

结论：**烧录、校验、UART0 启动已 bench-tested；USB Hub / 光驱尚未枚举。** 不能据此认定 M1 或 CD 播放通过。

## 已确认的连接和设备边界

- 用户报告：电脑 USB 接开发板 COM；开发板 USB 接 Type-C Hub；UJ-898 经 SATA / Slimline SATA-USB 桥接器接 Hub，桥接器/光驱单独供电，放入光盘后已自动吸入。光盘类型和各设备具体型号尚未提供。
- 电脑上有两个 USB 串口。仅操作本次新出现的 `USB Single Serial`（COM 桥接器 VID:PID `1A86:55D3`）。此前的 `USB JTAG/serial debug unit` 属于其它项目，没有打开、复位或烧录。
- **上述 `1A86:55D3` 是开发板 COM 桥接器，不是光驱 SATA-USB 桥接器或 Hub 的 VID:PID。** 后两者仍未取得。
- esptool 从目标 COM 读取：ESP32-S3，revision v0.2，40 MHz 晶振；报告内置 8 MB PSRAM（AP_3v3），检测到 16 MB quad Flash。开发板具体型号仍未知，PSRAM 尚未做独立测试。

## 烧录与备份

使用 [离线验证记录](2026-10-31-m1-offline.md) 对应的构建，烧录前重新核对应用 bin / ELF 校验值。

| 项目 | 结果 |
| --- | --- |
| esptool | 4.12.0，通过明确指定的目标 COM，460800 baud |
| 备份 | 烧录前读取 `0x00000000` 起、长度 `0x54000`（344,064 字节），覆盖本次所有被写入的 Flash 扇区；不是整颗 16 MB Flash 备份 |
| 备份 SHA-256 | `9a8bf47520e4815dcdc95ed32a594e8fc8828b086f1e17576f43c2ad0704422b` |
| 烧录范围 | bootloader `0x0`、partition table `0x8000`、app `0x10000`；未执行整片擦除 |
| 写入校验 | 三个文件均返回 `Hash of data verified` |
| 应用 bin SHA-256 | `f9a7f0efa33ade4ec661927009ecf0d50a1973b82e49f87ac7070c6788648a38` |
| 应用 ELF SHA-256 | `2a1a3d89bba7655f05edd8c508119a9fbad5a57394fd5a78b3096d44f2bfcb90` |
| 操作 | 烧录后通过目标 COM 的 RTS 复位，记录 UART0 115200 日志；不是断电冷启动验收 |

当时备份和原始工具/串口日志存放在本地被忽略的 `firmware/build/bench-2026-10-31-9k2eyvtm/`，不提交可能含原固件数据、设备序列号或个人路径的原始文件。这些文件后来被 fullclean 删除，详见文末更正。

## 实际观察

45 秒串口采集窗口中观察到一次 Discora 启动，无 panic、abort、brownout 或再次启动记录。UART0 正常输出；应用 ELF SHA 与离线构建一致。

以下是该次真实 UART 日志的摘录，未填入尚未出现的设备信息：

```text
I (275) usb_probe: Discora M1 read-only probe version=61b8229-dirty IDF=v5.4
I (295) usb_probe: Only INQUIRY / TEST UNIT READY / REQUEST SENSE; no media writes or eject
W (305) usb_probe: Native USB PHY is now Host; use independent UART0 for logs. External 5V VBUS required.
I (345) usb_probe: Waiting for USB optical drive; readiness polling interval=5000 ms
```

- USB device descriptor 日志：0 条；没有拿到 Hub 或光驱 VID:PID。
- INQUIRY 命令：0 条；TUR / sense 尚未开始。
- 没有记录到 USB 传输错误；当前观察不足以定位为驱动、Hub、电源或线材故障。
- Bootloader 提示检测到 16 MB Flash，而镜像头配置为 2 MB，因此按 2 MB 使用。这是当前保守构建配置与物理容量不同；没有证据表明它导致 USB 未枚举。本次 app 仅 277,008 字节，不需要为排查 USB 立即扩大分区。
- 原始 UART 日志 SHA-256：`4f65c6b5f2b62b7844953fbcac771f306d5cb2714914877411233aaca4e3843d`。

## 待核对与下一步

1. 总线供电 Hub 的上行 VBUS 是否实际有 5V，开发板 USB 到 Hub 上行口的角色和线材是否合适。
2. 开发板、Hub、SATA-USB 桥接器具体型号；开发板 Type-C 的 CC / VBUS 连接是否适合 Host。
3. 在确认数据角色与供电路径后再次捕获枚举；必要时用万用表测 VBUS，或在有明确安全供电路径的条件下对比直连。
4. 枚举成功后再读取真实 INQUIRY、介质 sense；不因吸盘成功推断 USB 或 CD-DA 成功。

尚未进行无盘/有盘对比、重复插拔、冷启动、故障恢复、READ TOC、READ CD、I²S 或刻录测试。

## 后续用户补充与照片观察

- 用户确认 Hub **没有独立供电口**。
- 照片可见 UGREEN、标注 `10Gbps` 的 Hub；开发板接有两条 Type-C 线。模块丝印可见 `S3-N16R8`，但这不能替代开发板完整型号或原理图。
- 照片可见光驱连接线分叉，一路 USB-A 接 Hub，另一路 USB-A 接充电宝；这与用户报告的辅助供电一致。
- 照片不能确认开发板 USB 口是否向 Hub 提供 5V、Type-C CC 配置、分叉线的 VBUS 是否隔离/回送，也不能证明该 Hub 在 Full-Speed 下兼容。
- 当前优先取得开发板背面标识/焊盘信息及实际 VBUS 测量；未确认电路前不指定短接 `OTG` / `IN-OUT` 等焊盘，不把“Hub 无独立供电口”直接写成已证实的故障原因。

## USB-OTG 焊盘检查（用户测量）

用户提供背面照片，可见 `USB-OTG` 两半焊盘，外观上没有焊锡桥。按指导断开开发板 COM/USB 后测电阻，再只接 COM、USB 口保持空置测对 GND 电压。以下数值为用户报告，未由自动仪器采集：

| 项目 | 结果 |
| --- | --- |
| 焊盘 A（用户称 USB 字样下方）对 GND 电压 | 4.83 V |
| 焊盘 B（用户称 OTG 字样下方）对 GND 电压 | 1.98 V |
| A–B、A–GND、B–GND 电阻 | 表显示 `1 .`；表笔互接显示 `00.0`。表示所选电阻量程超量程，不是 0 Ω；实际量程尚未记录，不能当作无限电阻 |

找到 [AI-S3 同类板原理图](https://github.com/Xylopyrographer/BitsNThings/blob/main/AI-S3%20ESP32-S3%20Dev%20Board/AI-S3%20ESP32-S3%20Dev%20Board%20Schematic.pdf) 及同仓库板卡照片，外形/接口/焊盘布局相似；参考图中 `USB-OTG` 跳线旁路 USB2 VBUS 与板上 5V 之间的二极管 D2，USB2 CC1/CC2 为下拉。该资料不是本机已确认同版原理图。

当前推断：A 侧已有接近 5V 的电压，B 侧未显示正常 5V；B 的 1.98 V 可能由高阻/漏电产生，不能证明可供电。下一步在完全断电状态用二极管档测 A/B 两个方向，以核对是否符合隔离二极管路径；尚未要求焊接或实际桥接，尚未证明焊盘就是未枚举的根因。

## 用户提供的本地供应商资料核对

用户随后提供 `hardware/ESP32-S3-N16R8/` 目录。直接渲染并核对 [独立原理图](../../hardware/ESP32-S3-N16R8/ESP32-S3-SCH.pdf) 与 [V1.4 原理图](../../hardware/ESP32-S3-N16R8/ESP32-S3-SCH-V1.4.pdf) 的 USB/电源部分，两份均显示：

- USB1 是 COM/CH343P 通道；其 VBUS 通过 D1 向板上 5V 网供电。
- USB2 是原生 USB，D− 接 GPIO19，D+ 接 GPIO20；VBUS 通过 D2 向板上 5V 网供电。
- `USB-OTG` 标注的 0 Ω 支路**与 D2 并联**，连接 USB2 VBUS 与板上 5V。D2 单独存在时不提供板上 5V 向 USB2 VBUS 的反向供电路径；桥接该支路会旁路此隔离。
- `USB-JTAG` 是另一条经 R11 10 kΩ 到 VDD33 的 GPIO3 配置支路，不能与 USB-OTG 供电支路混淆。
- USB2 CC1/CC2 分别经 R9/R10 5.1 kΩ 接地，图中不是完整的 Type-C Source/DRP 控制电路。供电桥接后仍须通过实际 Hub 枚举验证连接可用。
- 排针 `5Vin` 的 `IN-OUT` 支路与 D3 并联，和 USB-OTG 支路是不同位置，不应一起短接。

目录 README 中“GPIO3 选项”把 USB-OTG 描述为接地支路，与上述两份 PDF 不符；本次核对以 PDF 实际连线为准，没有修改用户提供的原始目录。供应商图纸仍不等于实物逐网验证，但比此前网上同类板资料更直接。

据此，USB-OTG 供电跳线未桥接是当前优先验证的原因。若实施桥接，应先完全断开 COM、USB 与外部供电，桥接后先只接 COM 检查两半对 GND 均接近 5V，再连接没有外设的 Hub 验证枚举。光驱分叉线的充电宝支路暂不接回，以免未知的 VBUS 回送影响单一电源测试；光驱测试需在其电源路径确认后进行。桥接尚未执行或测量，不记录为已修复。

## 原始证据可用性更正（2026-10-31）

推进 M2 时，执行 `idf.py set-target esp32s3` 触发 fullclean，误删了放在 `firmware/build/` 内的 M1 原始串口/构建日志、统计文件及首次烧录前的备份。本文原有摘录、统计及校验值仍保留，但**不能再据原始文件复核这些历史窗口**；首次烧录前的原固件已无可用备份，不能声称仍可恢复。后续从设备重新读取的 M1 Flash 备份只用于回退到 Discora M1，不是首次烧录前固件的恢复。M1 应用从 Flash 提取后与本文历史 bin SHA-256 一致；原 M1 ELF 未恢复。

新的原始采集、烧录前备份、构建产物快照均放在被 Git 忽略的 `.local/bench/`，不再存放于会被构建清理的目录。详见 [M2 TOC 记录](2026-10-31-m2-toc.md)。
