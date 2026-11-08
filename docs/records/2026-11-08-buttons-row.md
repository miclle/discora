# 2026-11-08：四键连续排针与装配图修订

## 交付状态

按用户要求，将四个按键信号集中到同一排连续针脚，同时更新整机接线图与洞洞板装配说明。版本为 **0.12.1-buttons-row，implemented**：主机检查及四种 ESP32-S3 配置构建通过。用户已明确硬件接线与实测留待后续，软件交付阶段未连接设备、烧录或执行机械退碟；随后按用户新授权完成部署，见文末。未提交、推送。此前四键行为及初版产物保留在[0.12.0 记录](2026-11-08-four-buttons.md)。

## 引脚与线束

元件面朝向观察者、天线向上、USB 向下时，J2 是主控右排，从上向下计数。供应商排针摘录与项目洞洞板候选数据对应如下；这是资料与静态映射核对，不代表实物逐网验收。

| 功能 | GPIO / 主控排针 | 洞洞板（X，Y） | P3 芯号 |
| --- | --- | --- | --- |
| 公共地 | GND / J2-1 | （J，A） | 1 |
| 播放／暂停 | GPIO1 / J2-4 | （M，A） | 2 |
| 上一曲 | GPIO2 / J2-5 | （N，A） | 3 |
| 下一曲 | GPIO42 / J2-6 | （O，A） | 4 |
| 退碟 | GPIO41 / J2-7 | （P，A） | 5 |

P3 为板外可拔五芯线束，四个常开按钮共地。从已有排母底部焊脚引出，不新增板面插座、不移动原候选孔位。接头针号由项目定义，两侧必须逐线确认。GPIO7 仍只接 DAC DIN，音频 GPIO15／16／7、OLED GPIO10／11、COM GPIO43／44 和 USB Host GPIO19／20 均保持。

GPIO41／42 具有外部 JTAG 复用功能，使用 `gpio_config()` 配置为普通输入及内部上拉，不与外部 JTAG 同时使用；依据 [ESP-IDF GPIO 文档](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-reference/peripherals/gpio.html)及本地 v5.4 驱动实现。没有修改 eFuse 或 USB-OTG 焊桥。

## 软件变更与验证

增加上一曲／下一曲 GPIO 配置项，保留旧默认 GPIO8／9；四键 overlay 明确覆盖为 1／2／42／41。退碟旧查询默认 GPIO7、播放键默认关闭均保留。本次不改变 0.12.0 的暂停恢复、连续播放、换轨或退碟控制语义。

- 完整 `python3 firmware/tests/run_host_tests.py` 通过（ASan／UBSan），包括 100 个固定种子、500000 步独立 FIFO 模型，以及 USB、缓冲、恢复、按键和 I²S fake driver 检查。
- 77 组编译期引脚检查通过：连续排针及旧默认、各角色保留／不可用 GPIO、I²S／OLED 冲突、每一对按键重号。GPIO 掩码使用 64 位，覆盖 GPIO41／42。
- ESP-IDF v5.4，各配置独立 sdkconfig 与 build 目录，均完成 `idf.py set-target esp32s3` 和 `idf.py build`：

| 配置 | defaults 叠加顺序 | 结果 |
| --- | --- | --- |
| 四键有声候选 | sdkconfig → cd-player-i2s → cd-player-psram → usb-diagnostics → cd-player-seek-recovery → cd-player-buttons | PASS |
| 默认查询 | sdkconfig | PASS |
| 原 CD I²S | sdkconfig → cd-player-i2s | PASS |
| 四键软件时钟 | sdkconfig → cd-player-clock → cd-player-buttons | PASS |

候选应用大小 **383056 字节**。应用 SHA-256：`6db61daa9fc45c056b973797e3a767ec90c6251b81597bf9946ec8b6cb773ccd`；ELF SHA-256：`ffa75dcb8c6b2375c86368bb8180ec338e344857eda3f83bab8c3c256636017c`。

脚本、四配置构建日志与产物、主机检查日志、静态映射结果及源码摘要保存于忽略目录 `.local/bench/2026-11-08-buttons-row/`。产物未加入 Git；这些检查均不能代替有声按键实测。

## 图文交付与边界

- [整机接线与装配图](../diagrams/discora-wiring.html)：总览更新为四键，候选孔位图高亮 M／N／O／P 列的 A 行，新增 P3 线束放大图与接线顺序；独立 SVG 总览与 HTML 内嵌总览一致。
- [整机接线说明](../wiring.md)、[洞洞板装配说明](../perfboard-layout.md)、[四键控制](../playback-controls.md)及板卡、固件配置说明同步新引脚。
- 1260 个候选孔位、52 个排母针位和 5 条线束映射核对通过；HTML 自检通过，浏览器目视检查总览、候选孔位与线束图可读。
- 保留历史台架图及其原观察方向；新候选使用元件面 X 从左向右、Y 从上向下的丝印坐标。新旧坐标不混用。
- 本次未重新计算当前外壳 CAD 装配。此前包络试算仅作为历史记录；P3 壳体、背面走线、弯曲与固定空间以及当前外壳净距仍待试装。DCE001 半孔针序、最终裁剪／安装孔和供电实测仍未验收。

后续按[四键验收清单](../playback-controls.md#实机验收)完成断电通断检查、确认主控与固件、部署及独立有声／机械验收。

## 后续授权部署（22:39，Asia/Shanghai）

用户随后明确要求烧录。实时枚举主控 `1a86:55d3`、序列号 `5CF9109063`，芯片 MAC `7c:4f:ad:1d:0e:18`；串口独占检查通过，Secure Boot 与 Flash Encryption 均关闭。固件源码摘要与先前已通过构建的交付物一致，无需重建。

读取并备份 `[0, 0x110000)` 共 1114112 字节，SHA-256 `b72c8d5ea63504333383960b01bbae00110a25b0116daf960ba2006dde50d656`；板上原应用逐字节匹配 0.11.3 单次寻道恢复候选 `5b0579c2…`，分区表匹配当前构建。仅写入 `0x10000` factory app，写入摘要通过；独立 `verify_flash` 再次确认新应用匹配，并确认前 65536 字节原样保留。未写 bootloader、分区表、NVS 或 eFuse，未回退。

随后重启 MCU，采集 25.078 秒启动／状态日志，22:39:18 结束。版本 `0.12.1-buttons-row`、IDF v5.4、完整 ELF `ffa75dcb8c6b2375c86368bb8180ec338e344857eda3f83bab8c3c256636017c` 均匹配。GPIO1／2／42／41 均记录为输入、内部上拉；2 MiB PSRAM 队列、529200 字节预填初始化正常。只发送 `status`，最终 `state=stopped media=0 reads=0 continuous=0`，I²S `tx=closed handle=0 pcm_submitted=0 opens=0`。没有 panic、READ CD、退碟完成或 transport error。串口已关闭，lsof 确认释放。

本窗口未枚举到光驱，没有 TOC，不能据此判断是否接线或供电，也未进行有声播放、实体四键和机械退碟验收。保留既有 bootloader 的 2 MiB 映射，物理 Flash 检出 16 MiB，仍有原容量提示；本次应用位于原 factory 分区范围内，不扩大部署范围更换 bootloader。

证据位于 `.local/bench/2026-11-08-buttons-row/deploy/`：备份、部署脚本、各步骤日志、`deploy.json`、`boot.log` 与 `boot-checks.json`。初次启动检查器错误假设 sink 为小写、完整 ELF 摘要连续输出，导致两项匹配失败；根据原日志的 `I2S-unverified` 与两行十六进制格式修正解析后通过，未重新采集或改写设备反馈，初次结果另存。
