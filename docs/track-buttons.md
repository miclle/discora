# 上一曲／下一曲轻触按键

`0.12.3-disc-rewind` 使用 GPIO2 上一曲、GPIO42 下一曲，换轨后开启连续播放，暂停中换轨保持暂停。新增播放／暂停及迁移退碟接线见[四键控制](playback-controls.md)，当前构建／部署／验收见[本轮记录](records/2026-11-08-buttons-row.md)。历史实现与软件时钟部署分别见[0.9.1 记录](records/2026-11-01-track-buttons.md)、[0.10.0 记录](records/2026-11-05-oled-deploy.md)，不代表本版本实体按键验收。

## 接线

每个按键均使用常开、非自锁轻触开关，分别接对应 GPIO 与 GND：

| 功能 | GPIO | 供应商图纸位置 | 另一触点 |
| --- | --- | --- | --- |
| 上一曲 | GPIO2 | J2-5 | GND |
| 下一曲 | GPIO42 | J2-6 | GND |
| 退碟 | GPIO41 | J2-7 | GND |
| 播放／暂停 | GPIO1 | J2-4 | GND |

J2 是元件面天线向上时的右排，从顶部数。四个信号占连续 J2-4～7；GPIO 号不是排针序号，以实物丝印为准。使用内部上拉，常开触点接地，先断电接线，不接 5V。GPIO41／42 不与外部 JTAG 同时使用，其他外设引脚保持原分配；详细线束和图纸依据见[四键接线](playback-controls.md)。


## 配置与操作

在 `menuconfig → Discora CD player` 开启 `DISCORA_CD_PLAYER` 后，`DISCORA_TRACK_BUTTONS` 默认开启；默认引脚仍为 GPIO8／9。四键 overlay 显式设 `DISCORA_PREV_GPIO=2`、`DISCORA_NEXT_GPIO=42`，必须加载该 overlay 才与上表一致。查询、独立测试音和有界读盘 bench 模式不启用换轨键。已有 sdkconfig 须核对配置并重新构建、烧录；接线不会改变旧固件能力。

可先使用 [cd-player-clock.defaults](../firmware/bench/cd-player-clock.defaults) 验证真实光驱换轨和软件消费，该模式**不会出声**。构建示例（仓库根目录，已加载 ESP-IDF v5.4）：

```bash
mkdir -p .local/bench/track-buttons-manual
idf.py -C firmware -B "$PWD/.local/bench/track-buttons-manual/build" \
  -DSDKCONFIG="$PWD/.local/bench/track-buttons-manual/sdkconfig" \
  -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;bench/cd-player-clock.defaults;bench/cd-player-buttons.defaults" set-target esp32s3
idf.py -C firmware -B "$PWD/.local/bench/track-buttons-manual/build" build
```

真实音频按[四键有声构建](playback-controls.md#接线与配置)依次叠加 I²S、PSRAM 和四键配置。

- 启动和插盘保持 stopped；有效音频目录发布后，先释放按键至少 30 ms，再按下至少 30 ms。输出任务轮询，实际响应还取决于任务调度和 I²S 操作耗时，30 ms 不是最大响应时间保证。
- 每次按下只换一曲，长按不连跳；重新触发前须稳定释放 30 ms。上电按住不会换轨。
- 语义与 UART `prev` / `next` 相同：从相邻受支持音频轨的开头开始播放，跳过数据轨、四声道轨和不足 8 扇区的轨。暂停时选择目标轨但保持暂停；停止时开始目标轨，二者均开启连续模式。
- 首条可播放音轨按上一曲转到末条，末条按下一曲转到首条；暂停时保持暂停，其余可用状态从目标曲起点播放。上一曲始终选择前一轨，不按当前播放时长切换为“重播本轨”。单音轨光盘的两个换轨键均无相邻目标，使用播放／暂停键或 UART `toggle` 开始播放。
- 手动成功换轨开启连续模式（0.12.0）；旧队列清空、旧代次 USB 回复拒收、旧 I²S 通道关闭后重新预填。已经发出的 USB 命令不强行取消，故实际新曲读取仍可能等待旧命令截止。
- 同时检测到两个以上播放／换轨键按下时，禁止后续动作，直到三个键均稳定释放。已经处理的先前单键动作不会撤销。
- 无可用音频目录或 fault 时不保留动作；目录发布／退盘／失联重置手势，重插盘或故障恢复时按住不会自动换轨。fault 仍须 UART `stop` 后恢复，不用换轨键绕过故障。

## 上板验收

记录板卡、固件版本、ESP-IDF 版本、光驱／桥接 VID:PID、测试介质和日志；未部署前不把下列步骤记为已通过。

1. 软件时钟配置启动应打印 `prev=GPIO2 next=GPIO42 active-low internal pull-up; debounce=30ms`；获得 TOC 后仍为 stopped。
2. 在至少两条音频轨的测试盘上，按下一曲再上一曲，核对 `button=next/prev accepted=1`、实际轨号／源 LBA、后续真实 READ CD 和软件消费推进。
3. 长按 2 秒只换一次；释放再按可以重复。分别测试两键上电按住、双键按住、先释放其中一键，均不应产生额外换轨。
4. 在首／末可用轨验证边界拒绝不改变 generation、队列或当前播放；暂停换轨保持暂停且不派发新读取；停止换轨从目标轨起点重新预填，continuous=1。
5. 在 READ CD 在途时换轨，核对旧回复拒收；连续播放中换轨应保留连续模式。源故障不自动重试，不以离线注入替代真实故障证据。
6. 退盘、无盘按键、插盘时按住、重连分别验证不会延迟执行旧动作；四键 profile 的 GPIO41 退盘回归单独记录。
7. DAC 验收后再确认真实声音切换、左右声道及无异常复位；软件状态切换不等于声音输出已通过。
