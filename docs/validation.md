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

- 在独立 5V VBUS 支持下枚举驱动器。
- 记录设备描述符：VID:PID、USB speed、interface class/subclass/protocol。
- 仅测试只读命令：INQUIRY、TEST UNIT READY、REQUEST SENSE、READ TOC。
- 设备无法就绪时保留 sense key/ASC/ASCQ，不要循环无界重试。
- 测试断开、重新连接、多次进出盘与电源冷启动。

## M2：CD-DA

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
