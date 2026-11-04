# 上一曲／下一曲轻触按键

固件 `0.9.1-track-buttons` 新增 GPIO8 上一曲、GPIO9 下一曲。状态为 **implemented**；主机检查和配置构建见[验证记录](records/2026-11-01-track-buttons.md)。当前已部署 `0.10.0-oled` 软件时钟播放器，保留三个按键，初始化及 UART 状态响应通过；本轮 OLED 探测超时、无光驱枚举，实体按键换轨仍未验收。此配置不会出声，见[当前部署记录](records/2026-11-05-oled-deploy.md)。

## 接线

每个按键均使用常开、非自锁轻触开关，分别接对应 GPIO 与 GND：

| 功能 | GPIO | 供应商图纸位置 | 另一触点 |
| --- | --- | --- | --- |
| 上一曲 | GPIO8 | J1-12 | GND |
| 下一曲 | GPIO9 | J1-15 | GND |
| 现有退盘 | GPIO7 | J1-7 | GND |

位置依据[本项目板卡排针摘录](../hardware/ESP32-S3-N16R8/board-data.json)，不是实物逐网验收。元件面朝向观察者、天线向上、USB 向下时，J1 是左排，自顶部数；**GPIO8 并非第 8 针，GPIO9 并非第 9 针，以实物丝印为准**。GND 可使用已确认的公共地。

先断电接线。固件启用内部上拉，按下拉低，不接 5V，也无需另接 3.3V。四脚轻触按键用通断档确认所选触点“松开断路、按下导通”。默认音频 GPIO4/5/6 与这三个按键不冲突；若 CD I²S 改用 GPIO8/9，构建会拒绝，须调整音频引脚或关闭换轨按键。

## 配置与操作

在 `menuconfig → Discora CD player` 开启 `DISCORA_CD_PLAYER` 后，`DISCORA_TRACK_BUTTONS` 默认开启。查询、独立测试音和有界读盘 bench 模式不启用换轨键。已有 sdkconfig 须核对配置并重新构建、烧录；接线不会改变旧固件能力。

可先使用 [cd-player-clock.defaults](../firmware/bench/cd-player-clock.defaults) 验证真实光驱换轨和软件消费，该模式**不会出声**。构建示例（仓库根目录，已加载 ESP-IDF v5.4）：

```bash
mkdir -p .local/bench/track-buttons-manual
idf.py -C firmware -B "$PWD/.local/bench/track-buttons-manual/build" \
  -DSDKCONFIG="$PWD/.local/bench/track-buttons-manual/sdkconfig" \
  -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;bench/cd-player-clock.defaults" set-target esp32s3
idf.py -C firmware -B "$PWD/.local/bench/track-buttons-manual/build" build
```

真实音频须在 DAC 接线验收后改用 [cd-player-i2s.defaults](../firmware/bench/cd-player-i2s.defaults)，详见[音频输出](audio-output.md)。

- 启动和插盘保持 stopped；有效音频目录发布后，先释放按键至少 30 ms，再按下至少 30 ms。输出任务轮询，实际响应还取决于任务调度和 I²S 操作耗时，30 ms 不是最大响应时间保证。
- 每次按下只换一曲，长按不连跳；重新触发前须稳定释放 30 ms。上电按住不会换轨。
- 语义与 UART `prev` / `next` 相同：从相邻受支持音频轨的开头开始播放，跳过数据轨、四声道轨和不足 8 扇区的轨。暂停／停止时按键也会开始目标轨。
- 首轨按上一曲、末轨按下一曲不循环、不重播当前曲、不清空现有音频。上一曲始终选择前一轨，不按当前播放时长切换为“重播本轨”。单音轨光盘的两个换轨键均无相邻目标，使用 UART `play` 开始播放。
- 手动成功换轨取消 `play-disc` 连续模式；旧队列清空、旧代次 USB 回复拒收、旧 I²S 通道关闭后重新预填。已经发出的 USB 命令不强行取消，故实际新曲读取仍可能等待旧命令截止。
- 同时检测到双键按下时，禁止后续换轨，直到两键均稳定释放。已经处理的先前单键动作不会撤销。
- 无可用音频目录或 fault 时不保留动作；目录发布／退盘／失联重置手势，重插盘或故障恢复时按住不会自动换轨。fault 仍须 UART `stop` 后恢复，不用换轨键绕过故障。

## 上板验收

记录板卡、固件版本、ESP-IDF 版本、光驱／桥接 VID:PID、测试介质和日志；未部署前不把下列步骤记为已通过。

1. 软件时钟配置启动应打印 `prev=GPIO8 next=GPIO9 active-low internal pull-up; debounce=30ms`；获得 TOC 后仍为 stopped。
2. 在至少两条音频轨的测试盘上，按下一曲再上一曲，核对 `button=next/prev accepted=1`、实际轨号／源 LBA、后续真实 READ CD 和软件消费推进。
3. 长按 2 秒只换一次；释放再按可以重复。分别测试两键上电按住、双键按住、先释放其中一键，均不应产生额外换轨。
4. 在首／末可用轨验证边界拒绝不改变 generation、队列或当前播放；暂停／停止换轨应从目标轨起点重新预填。
5. 在 READ CD 在途时换轨，核对旧回复拒收；连续播放中换轨应取消连续模式。源故障不自动重试，不以离线注入替代真实故障证据。
6. 退盘、无盘按键、插盘时按住、重连分别验证不会延迟执行旧动作；GPIO7 基本退盘回归单独记录。
7. DAC 验收后再确认真实声音切换、左右声道及无异常复位；软件状态切换不等于声音输出已通过。
