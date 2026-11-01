# 新播放器受控故障路径

2026-11-01，0.6.3-player-faults，ESP-IDF v5.4 (`67c1de1eeb`)；沿用[整轨实验](2026-11-01-m3-player-eof.md)设备、13 轨 CD-DA、OTG 直连、辅助供电，唯一 COM `1a86:55d3` / `5CF9109063`。没有改接线，没有 DAC。

## 注入边界

`DISCORA_CD_PLAYER_FAULT_TEST` 默认关闭且只允许软件时钟模式。显式 `test delay` 在 playing 时阻止新 READ 请求派发 1200 ms，不阻塞 USB 事件服务，允许已在途命令返回；继续由真实消费任务耗尽实际 PCM 队列。`test fail` 在下一次可派发请求处向共享播放器核心传入失败，该次不发送 USB，日志明确标为 synthetic，不伪造 SCSI/REQUEST SENSE。

两项各限每次 MCU 启动一次，stop/换轨不退回预算；失败注入绑定当前 generation，停止/换轨使尚未触发的旧注入失效。预期欠载后不自动恢复，须 play；fault 后 play 被拒绝，须 stop 再 play。此阶段验证软件状态/退出，不验证真实光驱故障恢复。

实验 profile 单独保留在 `firmware/bench/cd-player-faults.defaults`。软件时钟普通 profile 未启用注入，查询/测试音/I²S 模式均不开放这些命令。

本地证据 `.local/bench/2026-11-01-m3-player-faults/` 保存配置、应用/源码快照、`scenario/serial.log`、`scenario/report.json`、部署/恢复日志和摘要；沿用身份、备份与应用 `0x10000` 校验流程。脚本不无限重试，发生真实 USB 错误则退出并恢复查询固件。

## 实测结果

9.560 秒脚本窗口完成两项注入。生产暂停后在约 850 ms 出现一次真实软件队列欠载：queued=588、delivered=206388、reads=11；随后约 1.7 秒内这些计数保持不动，没有自动重试或伪 PCM。显式 play 后同代次恢复到 playing。

源失败注入进入 fault，清空队列/交付计数并改变代次；约 1.1 秒观察期 reads=21 不变，play 明确拒绝。stop 后 play 恢复，随后在 playing 状态再次发送两种注入命令均被拒绝，验证预算没有因 stop 退款。累计 underruns=1，无实际 USB 断连、传输错误或光驱命令失败。

五组共享核心主机测试通过，故障配置执行 set-target esp32s3 与 build。注入路径为真实设备上的软件实验，真实光驱错误下的 SCSI 有界恢复仍未触发，不能记为通过。

最后恢复 0.4.3 查询模式；25.048 秒采集取得有效目录，无 READ CD、离线或传输错误；串口释放。
