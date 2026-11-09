# CD-Text 曲名只读探测

- 日期：2026-11-09，Asia/Shanghai。
- 目标：确认当前 13 曲音乐 CD 能否提供 CD-Text 曲名，以决定后续解码与 OLED 滚动显示。
- 结论：当前光驱／桥接器／光盘组合成功执行查询，但返回空 CD-Text 头部，没有文字包。没有可供解码或滚动的曲名；不能据此断言所有光盘均不支持，或完全排除光驱／桥接器的兼容性限制。

## 最小实现

源码版本 `0.12.7-cdtext-probe` 新增默认关闭的 `CONFIG_DISCORA_CDTEXT_PROBE`，仅用于播放器模式。有效 TOC 发布给播放器前，USB client 执行 READ TOC/PMA/ATIP（`0x43`），Format `0x05`、MSF=0、起始轨号=0；先读四字节头部，只有非空、长度合法且不超过现有 18816 字节回复缓冲预算时再读完整数据。头部的保留字节、18 字节包对齐、回复完整性及两次头部一致性均检查。无新 Data-Out 或任意 CDB 接口，不触发音频读取。

不支持可选命令、空或无效元数据回退到曲号显示；介质未就绪／变化时拒绝发布旧目录，传输错误仍按现有 USB fail-closed 路径处理，不能为了可选曲名忽略总线状态。读取发生在音轨发布前；同次 TOC 不循环重试 CD-Text。独立 USB 枚举／查询 A/B 配置仍拒绝这个新命令，不改变其既有实验白名单。

这是原始数据探测能力，**尚未实现曲名解析、字符编码转换或滚动显示**。先验证实际数据来源，不引入假曲名或将主机合成文字当作读盘成功。

协议参考：[libburn 原项目 CD-Text 格式文档（Debian 存档）](https://sources.debian.org/src/libburn/1.3.2-1.1/doc/cdtext.txt)、[libburn 作者对 READ TOC Format 5 的说明](https://lists.gnu.org/archive/html/libcdio-devel/2012-11/msg00012.html)。未复制第三方实现源码。

## 软件验证与构建

- 完整 `python3 firmware/tests/run_host_tests.py` 通过，ASan／UBSan 与已有 100 种子／500000 步播放器检查通过。
- 新增 Format 5 CDB／CBW、SCSI／ATAPI 长度、分配长度大小端、空头部、正常包长、短头部、非对齐／超限／保留字节非零／空指针拒绝检查；A/B 白名单保持拒绝 CD-Text。
- ESP-IDF **v5.4**，ESP32-S3；在当前四键有声／OLED／PSRAM／USB diagnostics／一次寻道恢复组合后叠加 `bench/cdtext-probe.defaults`，独立 sdkconfig／build 执行 `set-target esp32s3` 和 `build` 成功。
- 实验 app：`0x63110`（405776）字节；SHA-256 `8dd2e3724a81124895307c2d4cfe9eabcd479da3906a1cbc299782f5de04fae2`。
- 实验 ELF SHA-256：`d8fd0531cdedf3aaff16b88bef3bc70bf741ffc5b5d2407d43fd5ff06cd5eabb`。

## 9063 实测

唯一匹配 USB-UART `1a86:55d3`、序列号 `5CF9109063`，并核对 ESP32-S3 MAC `7c:4f:ad:1d:0e:18`；Secure Boot／Flash Encryption 关闭。先备份 `[0, 0x110000)`，原应用与用户已确认中文及进度正常的 0.12.6 镜像一致，分区表匹配。备份 SHA-256：`481f5fbd87f9f4b44a8a7f234be03926ed3bdf9035003a3bc90f05b722b5d3bc`。

仅写应用 `0x10000`，写入和独立 verify_flash 均通过，同时校验原前 65536 字节未变。启动日志确认版本与 ELF、四键和 SH1106 初始化正确。设备为 MATSHITA DVD-R UJ-898／HC10，桥接器 `13fd:0840` Full-Speed，当前盘 13 条音频轨、lead-out LBA 252645。

23:00:22 结束的 25.075 秒采集中，原始响应为：

```text
command=READ TOC (CD-Text) tag=5 requested=4 LUN=0
command=READ TOC (CD-Text) CSW=0 received=4 residue=0 elapsed_ms=7
00 02 00 00
CD-Text response empty: zero packs; keep track numbers
media published=1; playback remains stopped
```

长度字段 `0x0002` 加自身两字节共四字节，仅有头部；不需要发起完整数据读取。查询通过而内容为空，未出现非法命令 sense、USB transport error 或 panic。随后 TOC 正常发布，status 为首轨 stopped、reads=0、delivered=0、I²S 关闭。脚本仅发送一次 status，未播放、换轨、退盘或刻录。

原始证据和脚本保存在忽略目录 `.local/bench/2026-11-09-cdtext/`；`deploy/` 保存备份、写入校验和 `boot.log`。此记录不将空结果误记为曲名功能验收。下一项有意义的验证是使用明确含有 CD-Text 的光盘；取得真实包后再实现并验收编码解析与滚动显示。


## 恢复用户已确认版本

探测结束后，将备份的原 1 MiB factory 应用分区写回 `0x10000`，写入校验通过；独立校验 `[0, 0x110000)` 与本次备份完整一致，前缀未改。23:01:45 结束的 25.080 秒重启采集确认已恢复 **0.12.6-oled-progress**，ELF `b8a8ab9c…`，四键、SH1106 和 13 轨 TOC 正常，首轨 stopped、reads=0，无 panic／transport error。串口已关闭，lsof 确认释放。

恢复证据见 `deploy/restore-write.log`、`restore-verify.log` 和 `restore-boot/`。9063 继续运行用户已确认中文与进度条正常的 0.12.6；源码保留 0.12.7 的可选探测能力，默认不开启。未提交或推送。


## 提交前审查修复

审查确认一处介质状态处理问题：TOC 读取成功后，CD-Text 的头部或完整数据查询可能返回 NOT READY（例如 `02/3a/00` 无盘）或 UNIT ATTENTION（例如 `06/28/00` 换盘）。原路径在读取 sense 后继续发布之前的 TOC，可能短暂显示和选择已失效曲目。

现将可选元数据缺失与播放源失效分开：上述两类 sense、REQUEST SENSE 失败、传输失败或已断连均拒绝发布 TOC，留待后续有界目录查询；头部成功后若已断连，也不再发送完整数据请求。正常空回复、无效元数据和不支持可选命令仍保留有效曲号。默认 CD-Text 探测仍关闭，OLED 保留曲号显示。

新增离线测试从 `usb_probe.c` 提取原样的生产函数，替换通信、日志及发布入口；在头部／数据两个阶段分别覆盖无盘、未就绪、换盘、复位、sense 失败、断连和传输失败，以及空／完整／超限／截断／变化回复。把失败处理恢复为旧的“不区分 sense”行为时，测试在旧 TOC 被发布处失败；修复版通过。该证据为合成传输回归，不冒充真实拔盘实验。

完整 ASan／UBSan 主机测试和 17 项 bench 工具检查通过；中文字形重新生成后与暂存产物一致。ESP-IDF v5.4 的正常四键 OLED 和 CD-Text 探测配置均使用独立目录完成 `set-target esp32s3`／`build`：

| 审查后配置 | app 字节数 | ELF SHA-256 |
| --- | --- | --- |
| 正常四键有声／OLED，CD-Text 关闭 | 404880 | `3166c841c7677d026d73b3de51e39a9717a8033e55f662deb2667404057f58c9` |
| 同配置叠加 CD-Text 探测 | 405968 | `bff88f1c8a8c2d7f692ab3f740d2a4559b28206c23d1a6155433446f4f8c9fd1` |

CI 新增 `cdtext-probe` 构建项，默认运行的主机测试包含上述回归。复查未发现其它可确认的 OLED／CD-Text 缺陷。审查证据位于 `.local/bench/2026-11-09-oled-review/`；审查后的源码未再次烧录，9063 仍为前述已恢复的 0.12.6。
