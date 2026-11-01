# 播放器软件时钟 bench

`player_bench.py` 只访问显式指定的 COM，不烧录、不主动发送复位脉冲、不保存 PCM，也不执行机械控制或写盘。部分板卡会在操作系统打开 COM 时复位；工具记录启动日志，并最多等待 45 秒取得目录。它用于已经部署、处于 stopped 的 CD software-clock 固件；I²S 模式会拒绝。另一项目的串口不能凭枚举顺序选择。

需要 Python 3 和 pyserial（可使用 ESP-IDF Python 环境）。先从操作系统设备信息取得端口、USB VID/PID、序列号，四者必须完全匹配且唯一；`inspect` 仅核对身份、不打开串口：

```sh
python firmware/tools/player_bench.py inspect \
  --port "$DISCORA_PORT" --serial "$DISCORA_SERIAL" --vid 1a86 --pid 55d3
python firmware/tools/player_bench.py stress \
  --port "$DISCORA_PORT" --serial "$DISCORA_SERIAL" --vid 1a86 --pid 55d3 \
  --rounds 10 --output .local/bench/player-stress-run1
```

`stress` 每轮执行暂停/恢复、next/prev、非法轨号拒绝、停止及快速 play/stop/play，检查停止稳定、代次、欠载计数。轮数限定 1–20，总截止 600 秒，单条命令响应截止 2 秒，进入 playing 截止 40 秒。轨目必须至少有两条受支持音频轨，并从第一条开始；`track 99` 必须不在本次测试目录中。此场景针对当前 13 轨测试盘，不能直接称为任意光盘通用测试。

`eof` 使用已选择的音轨长度进行整轨验证，要求固件开启 `DISCORA_CD_PLAYER_VERIFY`，从 TOC 计算 `(end_lba - start_lba) * 2352` 后通过 `--expected-bytes` 指定，当前上限为 480 秒。当前首轨例子：

```sh
python firmware/tools/player_bench.py eof \
  --port "$DISCORA_PORT" --serial "$DISCORA_SERIAL" --vid 1a86 --pid 55d3 \
  --expected-bytes 45565296 --output .local/bench/player-eof-run1
```

工具验证 EOF 两端摘要、字节数、最后短块、停止后不追加读取；它不提供独立电脑音频参考。

`faults` 需要显式启用测试注入的固件，分别触发生产暂停和源结果失败，每项每次 MCU 启动仅一次。若命令被拒绝，记录失败并退出，不把未执行的分支记为通过。

输出目录必须不存在，防止覆盖证据。保存 `serial.log` 和 `report.json`，后者包括成功/失败、已完成动作、命令响应时间、状态、工具/串口日志 SHA-256 和观察到的固件版本（未捕获启动时版本列表可为空）；失败也关闭串口，并尽力向已识别的软件播放器发送 stop。实际设备失联可能使停止命令无法到达。脚本不负责自动恢复固件，部署与恢复须另行明确执行。

响应时间是主机发送至读到固件 acknowledgement 的时间（含串口排队和 Python 轮询），不是硬实时上限或 USB 取消时间。heap、stack 和 stale 如有报告，仅代表该有限窗口。

离线检查：`python3 firmware/tests/player_bench_test.py`。没有 pyserial 也可运行，不打开任何设备。

实验记录：[整轨](../../docs/records/2026-11-01-m3-player-eof.md)、[10 轮控制](../../docs/records/2026-11-01-m3-player-stress.md)、[受控故障](../../docs/records/2026-11-01-m3-player-faults.md)。整轨最初使用本地部署脚本内的相同验收规则；仓库工具的 EOF 场景随后通过离线 fixture，未单独重跑实盘整轨。压力与故障场景已由仓库工具在实板上执行，工具改动以本地源码快照区分。

## 整盘场景

`disc` 只使用本次串口采集中完整的 `TOC validated` 和逐轨记录，拒绝不完整目录、数据轨或不连续边界，不复用旧目录文件。当前限制为每轨 8 扇区至 480 秒、总音频不超过 75 分钟、整体截止 90 分钟。

```sh
python firmware/tools/player_bench.py disc \
  --port "$DISCORA_PORT" --serial "$DISCORA_SERIAL" --vid 1a86 --pid 55d3 \
  --output .local/bench/player-disc-run1
```

需要开启摘要的 software-clock 固件。每轨显式选择后，按 1× 软件时钟读至 EOF，检查两端摘要/长度/尾块、轨号、停止后的读取计数；通过后才进入下一轨。每轨完成原子更新 JSON 检查点，整盘通过才置 passed=true；任何实际错误中止本轮，不自动重试。该脚本的逐轨调度不改变固件的“单轨 EOF 停止”语义，不是无缝播放；摘要一致只证明软件队列一致，不是独立电脑内容校验。
