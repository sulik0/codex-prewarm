# 测试说明

代码判断正确、CLI 请求完成，以及休眠后能否开始新一轮计时，需要分别检查。

## 自动测试和 CI

在项目目录运行：

```sh
python3 -m unittest discover -s tests -v
sh -n install-system.sh
sh -n uninstall-system.sh
```

当前有十项 unittest：

| 文件 | 检查什么 |
| --- | --- |
| `tests/test_decisions.py` | 已开始或已结束的计时、随时间移动的预计重置时间、使用量为零时仍可能已有计时、新的固定重置时间、过远的重置时间，以及三个计划时间点和晚醒边界。 |
| `tests/test_configure.py` | 配置只保存账号哈希值，不复制登录令牌；拒绝 API Key 登录和缺少账号标识的情况。 |

这些测试不发送模型请求，也不操作 launchd 或系统唤醒计划。GitHub Actions 在 Ubuntu、Python 3.13 上运行同一组测试和 shell 语法检查；它不会验证 macOS 实际部署。

macOS 上还可以检查系统任务 plist：

```sh
plutil -lint local.codex-prewarm.wakes.plist
```

## 检查实际运行

安装后先按[排错说明](troubleshooting.md)运行只读检查，确认两个任务已加载、未来仍有本项目的唤醒事件，并查看最近一次定时结果。

如需测试实际发送，在确认当前账号和额度后运行：

```sh
python3 "$HOME/Library/Application Support/CodexPrewarm/prewarm.py" --test-send
```

这个命令会消耗少量订阅额度。已有计时未结束时，成功结果是 `delivery_verified_existing_window`；它能说明 CLI 完成了请求，但不能说明开始了新的计时。

正常定时任务才检查计划时间，并记录是否已在该时间点尝试过发送。不要把连续手动测试当成自动重试策略。各启动方式见[实现细节](implementation.md#运行模式和防止重复发送)。

## 检查休眠后首次开始计时

1. 确认原有五小时计时会在计划执行前结束；如果计划前又使用 Codex 开始了新一轮计时，任务会正常跳过。
2. 按[部署说明](deployment.md#休眠锁屏和重启)准备电源、登录和网络条件，再让 Mac 休眠。
3. 计划时间过后运行只读检查，分别查看系统醒来的记录、定时任务结果和 `latest_verified_new_window`。
4. 只有日志出现 `new_window_verified`，才能认为脚本确认了新的计时。用电源日志判断休眠与唤醒，用发送结果判断请求是否完成，不把其中一项当成全部成功。

模型请求包含 CLI 内置提示，即使输出很短，输入 tokens 仍可能较多。测试时记录实际使用量，不根据提示长度推断费用或额度。

## 目前实际确认到哪一步

截至首次部署后的本机检查，已确认 CLI 在 launchd 后台完成短请求，并能再次查询额度；已有计时仍在进行时，正式定时任务会跳过发送。还观察到一次电池供电时按计划从 Deep Idle 休眠状态醒来、后台查询完成、随后再次休眠的记录。

那次休眠执行没有发送消息，因为旧计时还没结束。因此休眠后发送消息并首次开始新一轮计时，仍没有完整的实测记录。本机详细时间、使用量和报告保存在 Git 忽略的本地文件中，不作为项目通用配置提交。
