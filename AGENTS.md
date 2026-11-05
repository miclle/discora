# AGENTS.md — Discora

本文件是此仓库的 AI Agent / Codex / 人类贡献者协作约定，优先遵守仓库已有代码和实验记录。

## 核心上下文

- Discora 是**独立的 ESP32-S3 光驱项目**，不依赖其它 CD 机项目。
- 目标是低成本 MCU 独立控制 USB 光驱，优先 CD-DA 立体声播放，随后研究 CD-R/CD-RW 刻录。
- 首测硬件：MATSHITA DVD-R UJ-898 + SATA-USB 桥接器；该组合在 ESP32-S3 下**尚未验证**。
- 项目必须清楚区分 `planned`、`implemented`、`bench-tested`、`verified`，禁止仅凭编译成功宣称功能可用。

## 执行方式

1. 开始修改前阅读 `README.md`、`docs/requirements.md`、`docs/architecture.md`、`docs/status.md` 和相关决策记录。
2. 先围绕一项可测假设实现最小变更，再记录日志、设备型号、USB 桥接芯片/VID:PID、光盘介质、ESP-IDF 版本与结果。
3. 优先使用 ESP-IDF 原生 API；新增第三方组件前检查许可证、版本与 ESP32-S3 兼容性。
4. 保持 `firmware/` 可独立编译。改动固件时运行 `idf.py set-target esp32s3 && idf.py build`；若缺少工具链或硬件，明确注明未执行。
5. 变更硬件接口、供电假设、协议策略时更新对应文档；作出重要取舍写入 `docs/decisions/`。
6. 不为追求“演示完成”而模拟设备反馈或伪造 CD-DA/刻录成功日志。

## 工程边界

- **M0–M3**：供电与兼容性探测 → USB/SCSI → CD-DA → I²S Stereo。
- **M4**：仅在测速和桥接兼容性得到实测支持后开展刻录。
- USB Full-Speed 理论带宽不等于可持续有效吞吐量；必须实测。
- PSRAM 不应默认作为 USB DMA 可用缓冲；关注 DMA 内存能力和缓存跨任务所有权。
- 对刻录/擦除等会永久改变介质的命令，使用明确的用户操作与可复现的测试介质，默认拒绝在未确认设备时运行。

## 文档和质量

- **外壳设计强制约定**：除按钮及既有操控布局外，整机外壳必须尽量保持左右对称设计，以机身中心面为对称基准；外轮廓、提手、侧面造型、格栅和声学结构优先采用镜像设计。调整内部布局时仍须遵守此约束，不可避免的不对称须在设计说明中记录具体原因；CAD 修改后检查相应的左右对称性。

- 中文为主，保留技术标准名、命令和 API 英文原文。
- 文档中用具体参数、数据与验收标准代替夸张的“已支持”。
- 接口边界优先：USB transport、MMC commands、CD-DA reader、audio pipeline、UI/control、writer。
- 禁止提交构建输出、设备密钥、个人路径、未经授权的第三方源码或受版权保护的 CD 音频转储。
- 不随意更改既有 LICENSE；第三方代码须保留适用的许可声明。
