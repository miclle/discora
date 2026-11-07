# 2026-11-07：音频诊断审查与交付验证

## 范围与审查结果

基线为 `a8c6dc3`。审查包含原有未提交的固件、主机测试、bench 配置与两份无声／交叉对照记录，以及本轮关联文档修订；固件阶段提交为 `d2cffb1`。本轮不连接串口、不烧录、不播放，不把源码构建结果作为新的听音证据。

- 固件增加默认关闭的 64fs slot 对照与 MCU PCNT 时钟探针；复核 PCM16 DMA 大小、配置隔离、GPIO 输入路由、取消／重开及失败后禁止重试路径，未发现可确认的阻塞性代码缺陷。
- 原 CI 矩阵没有编译新启用路径，补充 `tone-64fs-probe`，保留原五配置。
- README、状态、架构和音频／接线说明中“未接 DAC”及旧板上部署描述已过时，更新为约 60 秒原始立体声短时实测通过；明确 GPIO15/16/7 实验接法与默认 GPIO4/5/6、临时增益／自动停止与主固件的区别。
- 历史失败按原顺序保留，记录顶部增加最终结论和适用范围。DIN 连接故障范围不等同于已找到某个损坏元件；USB 掉线、整盘及启动稳定性仍未验收。

## 本地验证

| 检查 | 结果 |
| --- | --- |
| `python3 firmware/tests/run_host_tests.py` | 通过；ASan/UBSan，含 64fs／非诊断配置隔离、PCNT 门控／取消／输入重启用／资源复用及初始化、启动、读取失败路径 |
| `python3 firmware/tests/player_bench_test.py` | 15 项通过；离线工具检查，无设备访问 |
| 默认探测配置 | ESP-IDF v5.4：`set-target esp32s3` 和 `build` 通过 |
| 64fs + PCNT 独立诊断 | ESP-IDF v5.4：`set-target esp32s3` 和 `build` 通过；生成配置确认两项开关均启用 |
| CD I²S 配置 | ESP-IDF v5.4：`set-target esp32s3` 和 `build` 通过；诊断关闭，默认 GPIO4/5/6 保持不变 |
| 文档／提交检查 | 变更 Markdown 本地文件链接存在；未新增个人绝对路径、私钥或凭据字段；`git diff --check` 通过 |

三套构建均使用新的独立 sdkconfig 与构建目录，位于忽略目录 `.local/bench/delivery-20261107/`。从 `firmware/` 执行以下命令模式，`<config>` 与 `<build>` 分别指定隔离位置：

```sh
idf.py -B <build> -DSDKCONFIG=<config> -DSDKCONFIG_DEFAULTS="<defaults>" set-target esp32s3
idf.py -B <build> -DSDKCONFIG=<config> build
```

三项 `<defaults>` 依次为：

1. `sdkconfig.defaults`
2. `sdkconfig.defaults;bench/i2s-tone.defaults;bench/i2s-tone-64fs.defaults;bench/i2s-clock-probe.defaults`
3. `sdkconfig.defaults;bench/cd-player-i2s.defaults`

| 本次本地应用 | 大小（字节） | SHA-256 |
| --- | ---: | --- |
| default | 285328 | `40e8dba355ab09976d292a1ca01779b756cee2d6f48b2d2ab4838744dcad8682` |
| tone-64fs-probe | 264288 | `dc0211ace3d943dc192c6eae9aebaab560a0362329b0538feb9f057a0b2c8227` |
| cd-i2s | 386080 | `870b8238a38581f956a0be9a54e22da6d803295f7fc2156d1ce5483ad2ab4145` |

以上为构建产物，不是当前板上成功试听的候选。候选身份与听感记录见[音频对照记录](2026-11-07-cybertrack-audio-crosscheck.md)。备份、原始日志、临时源码和二进制保留本地，不进入 Git；远端 CI 须以推送提交对应运行结果为准，本表仅记录本地验证。
