# 2026-10-31：M3 音频控制与 I²S 诊断离线准备

结论：**源码 implemented，主机侧测试及三种配置构建通过；没有音频硬件实测。** DAC 在采购中，不能把生成的诊断数据、构建成功或离线状态机测试当作实际 DAC 或 CD 播放成功。

## 范围与设备状态

- 源码版本 `0.5.0-audio-prep`，以 `5803866` 为工作区基线开发，本轮按阶段本地提交，未推送；下方快照标识实际构建源码。
- 本轮没有打开串口、烧录、复位设备或执行光驱命令。开发板最后已知为默认关闭实验的 `0.4.3-underrun-bench`；此前 600 秒顺序通过仍对应 0.4.2，不改写历史窗口。
- 用户预计 OTG 转接头于 2026-11-01 到货，PCM5102 模块约三天后到货；实际型号、VIN 和跳线未确认。
- 默认仍运行 USB probe。独立音频模式只运行 UART 控制的生成测试音，不启动光驱服务；上电 stopped，收到明确命令后才开 I²S。

## 交付与假设

- `audio_core` 管理 stopped / prefill / playing / paused / underrun / fault，使用帧对齐环形队列。stop / 新源 / fault 清空并改变 generation，拒收旧代次数据；状态和 dequeued bytes 不代表模拟输出已播放。
- `test_tone` 独立生成 PCM16LE L/R 交织样本：左 441 Hz、右 882 Hz、双声道或零样本，名义最大幅度 4096，约 −18 dBFS；没有商业音频或虚构光驱响应。
- `audio_i2s` 是原生 ESP-IDF standard TX 适配，目标 44.1 kHz / 16-bit stereo / Philips I²S / 无 MCLK 输出；候选 GPIO4/5/6。当前 GPIO 和时钟目标只是实现配置，尚未测量。
- `audio_diag` 为单所有者任务，COM 命令 `left/right/stereo/silence/play/pause/stop/status/help`。状态查询区分软件 state 与 TX running/closed；fault 需 stop 后重试，过长/异常命令丢弃。
- 诊断软件环形队列 14112 字节，DMA 7056 字节，完整预装后 enable，检查写返回值和精确长度。暂停/停止关闭并删除通道，恢复重建；删除失败保留 handle 并锁定 fault。

暂停保留尚未提交的软件队列，但已排队 DMA 最多约 40 ms 数据会被丢弃，不能称为采样级无损暂停。USB/CD 源、精确播放位置、EOF drain、硬件 DMA 欠载统计和淡入淡出未实现；这不是完整 CD 播放器。设计见 [ADR-0006](../decisions/0006-i2s-tone-diagnostic.md)，[到货接线/验收](../audio-output.md)。

## 主机侧测试

`python3 firmware/tests/run_host_tests.py` 通过，C11、`-Wall -Wextra -Werror -pedantic`、ASan/UBSan：

1. 原 BOT/SCSI/TOC/READ CD fixtures 和 10000 组异常输入通过。
2. 原 PCM 队列 20000 次操作、回绕/顺序/满空边界及跨轨游标通过。
3. 新增预填门槛、暂停时禁止出队但保留数据、恢复、停止清队列、旧 generation 拒收、欠载不自动恢复、fault 清除、超量/不对齐读取拒绝。
4. 新增左/右互不串入、静音、固定周期、幅度上界/零均值、正负样本端序和分块渲染连续性检查。

这些输入为合成 fixtures，使用的是实际纯 C 核心，但不验证 I²S API 的硬件执行、DMA 时序、串口交互延迟、模拟电平或听感。原生适配只完成源码检查和构建。

## 构建

macOS arm64，ESP-IDF tag v5.4 (`67c1de1eeb`)，Xtensa GCC 14.2.0，Python 3.9.6。每个配置分别执行 `idf.py set-target esp32s3 && idf.py build`（独立 build / sdkconfig）；最终源码变更后增量构建通过。

| 配置 | 模式 / 配置检查 | 应用字节数 |
| --- | --- | --- |
| default | 音频开关关闭，默认 USB 查询 | 279504 |
| i2s-tone | 音频开关开启，CD-DA bench 不可选，GPIO4/5/6 | 234640 |
| otg-direct | 音频关闭，寻道/完整首轨开启，软件缓冲 60 秒 | 298288 |

只构建，没有烧录任何一种配置，也没有从新固件取得真实启动/设备返回。默认构建及既有直连 profile 用于核对模式互斥后仍能编译，不是 USB 功能的重新上板回归。

## 校验快照

产物、源码、sdkconfig 和工具日志保存在忽略的 `.local/bench/2026-10-31-m3-audio-prep/`，未放入 `firmware/build/`。没有音乐 PCM 转储，不提交构建输出。时间、环境及绝对路径可能影响产物，不承诺跨机器逐字节可复现。

| 本地相对文件 | SHA-256 |
| --- | --- |
| `host-tests.log` | `a741b13560f2ac89f28ab318d810e7ef0f09e0ce7c908900f2e0dde688d38203` |
| `default-build/discora.bin` | `d2fdc47ce2c20113550621309ffa751515665ca3843731c6ae2f9a33759439bb` |
| `default-build/discora.elf` | `725a5fc45f82ee35c6994b5b0fb6ebb1e1e96b02f51c39a7a5c7e81b2325f2df` |
| `tone-build/discora.bin` | `e01530dc87866cc528ebbd9836919b834548a5200e3d596ec36bf1b65ff876bb` |
| `tone-build/discora.elf` | `78ad7a847f9e752c19518a6dfbd6925c75d4970f5be6dfb898c4de25a623a3ce` |
| `direct-build/discora.bin` | `0d14a381bb58050e997d31a96eb56cf08ebfd076030bdeb67a69dd61630fae47` |

| 源码 | SHA-256 |
| --- | --- |
| `firmware/main/main.c` | `27c56c5d30a862949cbe24942e3e91a39d12cb3c7749b8a2fc2e3331a131d66a` |
| `firmware/main/audio_core.c` | `c4b8e619795cdcb0ce87a54b93bc6303ffc8c2424d955ed02d534397e14998ef` |
| `firmware/main/audio_core.h` | `d6a50333f92f93169543cb4fdb0e4f3b4897b8a17d56630d23c9572f4e6980cf` |
| `firmware/main/test_tone.c` | `c9054230c28bfd522a9e1f43f2bcd1a8123bfdd9dec0a5818612bfe8e478bbb8` |
| `firmware/main/test_tone.h` | `7dceef5b8dcab60c1b643f3012af69032e6334b1f90104ff8ddedb845742ed29` |
| `firmware/main/audio_i2s.c` | `04fc32757b14f0855b13e58a6839d687775190d2121052a711587d639bdfcafb` |
| `firmware/main/audio_i2s.h` | `8d43ae2e6f4e9d553561701049418bacfe41384d842710f72c7514296e012508` |
| `firmware/main/audio_diag.c` | `190f728c80194365a9a7dd7946838c01341816e93f8f08db8d6ae8802036c9f9` |
| `firmware/main/audio_diag.h` | `72d838e48a518255aea924203905d2f7eec5a0aed3d5e2455c7e7fad190731ab` |
| `firmware/main/CMakeLists.txt` | `18c8e4724902e2130ad494d51ab6d11527d6c0c0941d1c67c90913b8a5770992` |
| `firmware/main/Kconfig.projbuild` | `e463235dbd6a29fe226f4de68b0f508bbb0642a314afcd9a358c6e800c1ce37c` |
| `firmware/CMakeLists.txt` | `13b89af60966311eccada062bde414f189a01cedf3dc41ac0bbbf51f5227e061` |
| `firmware/bench/i2s-tone.defaults` | `8017cb29ead2e395d76dbee59a94702e59c637870e8644d24ff6db471b8649b1` |
| `firmware/bench/otg-direct.defaults` | `03cb42ea5635a4653ec7aab50d4c89be2c9c70101091cedee2197280836d0d61` |
| `firmware/tests/audio_core_test.c` | `e5573ec63e56660624be371bdeb18c199fde301f9d9f4d0b25d04a4b20a7764e` |
| `firmware/tests/run_host_tests.py` | `2af03c52feded734d813a06a8acfa59abc5bccbb93232ae505f4751e66045ec4` |

## 下一步

先做 USB OTG 直连对照，保留已失败的寻道证据。DAC 到货后核对模块 VIN/跳线，以独立诊断模式确认实际时钟、L/R、暂停/停止和异常音，再把 USB/CD-DA 生产者接入真实 I²S 消费通路，重新验证欠载与整轨/整盘播放。模块电源接法不能由芯片规格或普通商品名称推断。
