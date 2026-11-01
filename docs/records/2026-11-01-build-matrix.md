# 固件配置构建矩阵

2026-11-01，源码 0.7.3-transfer-wait；ESP-IDF v5.4 (`67c1de1eeb`)、target esp32s3。

GitHub Actions 将原来的单默认配置扩展为五个独立 job：默认查询、独立测试音、CD 软件时钟、CD I²S、故障注入。每个 job 显式组合 sdkconfig.defaults 与对应 profile，执行 set-target / build；使用隔离的 sdkconfig.ci 和 build-ci，fail-fast=false，不让一个配置失败隐藏其余结果。沿用项目现有 ESP-IDF CI action v1 与 v5.4 基线，没有自动烧录或推送。

本地五个隔离配置均完成 set-target esp32s3 / build，额外读取生成 sdkconfig 核对 player/tone/I2S/fault 标志，防止构建成功却选错模式。八组 C ASan/UBSan 检查通过；Python bench 检查继续由现有独立 CI step 执行。本轮未推送，远端 CI 尚未运行，不能将本地结果称为 GitHub 通过。

`.local/bench/2026-11-01-build-matrix/` 保存五套配置/构建日志/应用、模式核对 `checks.json` 和 SHA-256 清单。此矩阵不依赖外接硬件，不代表 I²S 声音、USB 故障恢复、冷启动或刻录验收。
