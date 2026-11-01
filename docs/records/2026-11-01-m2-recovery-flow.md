# 2026-11-01：共享恢复流程的离线分支验证

源码 0.5.5-recovery-flow 将原有恢复顺序提取到平台无关的 `cdda_recovery.c`，真实 USB 适配与离线测试调用同一函数。回调依次负责健康检查、处理 USB 事件的 1000 ms 等待、TUR 和同一 READ CD 重放；TUR 后额外复查健康状态。原来的失败 CSW / 有效 sense 准入、每次启动一次预算、超时/所有权约束和日志保留。

真实 USB 适配继续持有相同音轨、LBA、扇区数；传输故障不会作为可恢复 sense。预算在等待前消耗，不因等待中失联、TUR 失败、重放失败或重连退款。READ CD 重放只有成功 CSW 及完整长度才返回成功。

主机 ASan/UBSan 四组检查通过。新增脚本化回调覆盖：缺失/其它 sense、初始不健康、等待报告失联、等待后失联、TUR 失败、TUR 后失联、重读失败、重读成功，以及所有已消耗预算后的再次调用拒绝；断言等待前已预留预算、调用顺序 W→T→R、重读最多一次。测试没有连接光驱，不产生伪装成真实设备的日志。

ESP-IDF v5.4 下，默认关闭和启用恢复的多轮配置分别独立 set-target / build 通过。本阶段没有烧录，最终硬件状态仍为欠载实验后恢复的默认 0.4.3。实际光驱错误恢复仍未实测触发，不能由离线 PASS 改为 bench-tested。

本地证据位于忽略目录 `.local/bench/2026-11-01-m2-recovery-flow/`。

| 证据 | SHA-256 |
| --- | --- |
| `host-tests.log` | `1be9d288b314cbb02fccfd9c155d91873c026bb18f419c2c969e800f390cca70` |
| `lab-build/discora.bin` | `66f033cb0aaf3a61f40990972a0f6664e26cc69e4680ce796988e729252bb449` |
| `default-build/discora.bin` | `2c8195491a5eaeeaed4e8ceac1ce2b053ac25c21bedd6bd383e9b324eeb02b66` |
