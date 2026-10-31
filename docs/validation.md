# 验证手册 — 从只读开始

> 所有命令先识别**正确设备**，不要照抄 `/dev/sr0` 在不确定硬件时执行。实验阶段可以借助 Linux 电脑验证光驱；最终产品不依赖 Linux。

## M0：Linux 侧预验证（不会刻录）

1. 连接 UJ-898 和具有足够电流的 SATA-USB 适配器，插入**真正 Audio CD**。
2. 读取硬件枚举信息：
   ```bash
   lsusb
   lsusb -t
   lsblk -S
   dmesg | tail -n 80
   ```
3. 安装可用的光盘测试工具（Debian/Ubuntu）：
   ```bash
   sudo apt update
   sudo apt install -y cdparanoia sg3-utils cdrskin
   ```
4. 确认设备节点后读取 TOC 和音频：
   ```bash
   cdparanoia -d /dev/sr0 -Q
   cdparanoia -d /dev/sr0 1 /tmp/discora-track01.wav
   ```
   WAV 提取成功说明该 Linux/光驱/桥接组合具备 CD-DA 提取路径，但**不能单凭此推定 ESP32-S3 兼容**。
5. 更换为**空白 CD-R/CD-RW**，仅查询能力，不开始写入：
   ```bash
   sudo cdrskin dev=/dev/sr0 -checkdrive
   sudo cdrskin dev=/dev/sr0 --list_speeds
   sudo cdrskin dev=/dev/sr0 -minfo
   sudo sg_get_config /dev/sr0
   ```
   报告所有可用速度、介质规格、错误日志。支持的最低速度取决于光驱+介质组合，不能从最高 24×/10× 反推。

## M1：ESP32-S3 / USB Host

先按 [组装手册](assembly.md) 确认 Host 数据路径、VBUS 和独立 UART0。2026-10-31 已完成烧录、UART0、[空 Hub 枚举](records/2026-10-31-m1-empty-hub.md)、[光驱三种查询和 61.2 秒连续就绪](records/2026-10-31-m1-optical-probe.md)；首次失败条件见 [首次上板记录](records/2026-10-31-m1-first-boot.md)。下列矩阵仍需逐项保存实测证据，特别是受控重复插拔、真实冷启动和异常恢复。

### 不连接硬件的检查

```bash
python3 firmware/tests/run_host_tests.py
cd firmware
idf.py set-target esp32s3
idf.py build
```

主机侧测试使用合成字节序列，包含描述符截断/长度/接口筛选、CBW、CSW、INQUIRY、固定/描述符 sense、TOC 构造/长度/曲目/lead-out、10,000 组输入边界检查，并启用 ASan/UBSan。它不验证实际 USB 传输、Hub、供电、STALL 恢复或断连。

### 实机步骤（准备好设备后）

当前固件默认执行 INQUIRY、TEST UNIT READY、REQUEST SENSE、READ TOC；受限 READ CD 实验默认关闭，须显式启用。先用无盘状态验证，再插入 Audio CD。

| 场景 | 保存的观察 | 通过条件 / 边界 |
| --- | --- | --- |
| 主控空载启动 | 版本、IDF、启动日志、供电 | UART0 出现等待设备日志，无异常重启 |
| 无盘连接光驱 | VID:PID、Full-Speed、配置、接口、端点/MPS、INQUIRY 原始值/身份 | BOT 查询有效；PDT `0x05`、qualifier 0；不预填 UJ-898 返回值 |
| 无盘 sense | CSW status、sense key/ASC/ASCQ | 实际返回可解释；如 NOT READY / `3A` 表示无介质，并非协议失败 |
| 插入 Audio CD | TUR 与后续 sense、命令耗时 | 正确记录就绪或未就绪；TUR 成功不代表读取音轨 |
| 拔下并重连，至少 10 次 | 断连、device closed、内部 heap、重新枚举结果 | 无崩溃、旧响应串入或持续 heap 下滑；记录每次结果，heap 单值不是无泄漏证明 |
| 冷启动，至少 5 次 | 主控/光驱上电次序、每次完整日志 | 均能复现识别，或清晰记录失败条件，不掩盖供电问题 |
| 传输中拔下 | 取消、回调归还、接口释放、重新连接 | 无缓冲误用或异常重启，恢复后重新读取身份 |
| 超时 / STALL / 无效 CSW（若可复现） | 原始错误、恢复结果、停止查询状态 | 按 ADR-0002 处理；未触发时标“未测试”，不强行干扰硬件制造故障 |
| Hub 与直连对比（按需要） | Hub 型号、拓扑、枚举日志 | 区分 Hub 与桥接器问题；缺少安全直连供电路径时不临时并接 5V |

固件每 5 秒正常查询一次介质就绪状态；INQUIRY 对特定临时 sense 最多尝试三次。传输异常后只做一次 BOT Reset Recovery，不自动重放命令。普通查询、CBW、CSW 和控制传输为 3 秒应用层截止时间，READ CD 数据阶段为 30 秒；Bulk 取消后再等待最多 2 秒；若缓冲未归还或 EP0 控制请求超时，停止探测并拔下设备。等待栈归还所有权不等于继续重试设备命令。

### 日志字段（字段说明，不是成功日志）

- `USB address / VID:PID / speed / config`：USB 枚举结果。
- `interface / alt / class / subclass / protocol`：包括不支持接口在内的描述符。
- `BOT interface / IN / OUT / MPS / LUN`：实际选择的传输接口，当前固定 LUN 0。
- `command / tag / requested / CSW / received / residue / elapsed_ms`：一次命令的传输与状态。
- `INQUIRY vendor / product / revision / PDT / qualifier`：真实设备身份，日志不输出 USB 序列号。
- `sense key / ASC / ASCQ`：真实设备错误或介质状态；无合法 sense 不猜测“无盘”。

完整实验日志、备份和构建产物快照保留在被 Git 忽略的 `.local/bench/<实验名称>/`，不得放在 `firmware/build/` 等会被 fullclean 删除的目录；提交前脱敏设备序列号、个人路径等。按下方模板记录板卡、Hub、桥接器、光盘介质、固件源码版本/校验值与结果。

## M2：CD-DA

- 已实现 READ TOC 格式 0、MSF=0：检查 4 字节头和完整响应的一致性、声明长度、顺序曲目号、ADR、严格递增 LBA 和最终 `0xAA` lead-out；不完整或畸形响应不发布目录。
- 目录给出的末地址为排他边界；时长由相邻 INDEX 01 起点相减，单位 `MM:SS:FF`（75 帧/秒），可能包含轨间间隙；不是逐采样音频或听感时长的验证。多会话盘、负 LBA、CD-TEXT 未在本轮支持/验收范围。
- 单张音乐 CD 的 13 条音频轨已 [bench-tested](records/2026-10-31-m2-toc.md)，后续与 macOS 参考目录逐轨 LBA 和 lead-out 对照一致；换盘/无盘/不同介质仍待验收。

- [READ CD 实测记录](records/2026-10-31-m2-cdda.md)：单/8 扇区与电脑参考摘要一致，重复批量相同，256 扇区短突发约 740 KB/s；保留首次失败和两次超时，不宣布整张盘或长时吞吐通过。
- 通过 `menuconfig → Discora bench probes → Run one bounded READ CD probe per MCU boot` 显式启用实验；默认关闭。一次启动最多执行一次，重连或 TUR 状态变化不重新触发；失败后先检查日志，不反复复位试错。
- 在已知音轨上发送 READ CD；记录每个命令的起始 LBA、扇区数、完成时间及错误码。
- 对 2352 字节扇区数据进行长度和内容校验；测试跨音轨和光驱寻道。
- 统计连续读取速率、最长暂停时间、误码/重试次数。
- 与 Linux 提取的波形/哈希进行参考对比，注明驱动 offset 可能影响字节一致性。

## M3：音频播放

- 首先用固件生成的已知 L/R 测试 PCM 验证 I²S 时钟、通道独立性，再接入 CD-DA。
- 测量实际 44.1 kHz、16-bit、两声道输出。
- 播放一整张测试盘，监控环形缓冲欠载、5V 电压与重启。
- 确认音轨切换不会遗留上一轨 PCM 数据或造成明显爆音。

## M4：刻录安全门槛

- **只有在明确确认桥接器写入命令透传、实测稳定有效写速、介质最低允许速度、可处理 underrun 后才进行写入。**
- 先使用可牺牲的空白 CD-RW 或明确标记的 CD-R；记录操作前的设备信息。
- 从小型 ISO 镜像单轨写入，再执行同步、封盘/会话关闭和读取校验。
- 禁止在未知、珍贵或含重要数据的介质上进行擦除/写入实验。
- 出现速度不足或反复失速，**暂停刻录阶段**，不要因为设备支持 BurnProof 就假设固件可以忽略吞吐问题。

## 实验记录模板

```text
日期：
测试者：
ESP32-S3 开发板 / IDF：
USB 桥接器 VID:PID / 接口协议 / 速度：
光驱型号 / 固件：
光盘类型 / 标称速度：
供电与电压/电流：
具体命令 / 日志路径：
结果：通过 / 失败 / 未测试
观察与下一步：
```

**隐私与版权**：不要把商业光盘提取的音频、私人路径与设备序列号直接提交到公共仓库；提交脱敏日志和统计结果即可。
