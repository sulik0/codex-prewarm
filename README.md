# Codex Prewarm for macOS

用官方 Codex CLI、launchd 和系统定时唤醒，在工作前尝试开启订阅的 5 小时窗口，并用服务器额度读数核验结果。默认每日 **08:30、14:00、19:30** 执行，提前一分钟安排唤醒。

## 工作方式

1. 用户 LaunchAgent 查询官方 app-server 的账户额度。
2. 已有有效的 5 小时窗口直接跳过；周额度耗尽或空闲状态无法确认也跳过。
3. 空闲或旧窗口已结束时，发送一次极短请求，只要求回复 `OK`，使用临时空目录、只读沙箱和 ephemeral 会话。
4. 请求后间隔 15 秒读取两次服务器额度，重置时间必须稳定且接近请求后的 5 小时，才记录 `new_window_verified`。
5. 系统 LaunchDaemon 每天 00:05 补齐未来 9 个日历日的独立 `pmset wake` 事件，保留其他电源事件及重复计划。

| 请求时间 | 系统唤醒 | 如果此次开启新窗口，预计到期 |
| --- | --- | --- |
| 08:30 | 08:29 | 13:30 左右 |
| 14:00 | 13:59 | 19:00 左右 |
| 19:30 | 19:29 | 次日 00:30 左右 |

这是请求时间表，不能强制提前刷新已有窗口。实际到期时间以服务器返回的 `reset_at` 为准；周额度不会因此增加。

## 环境要求

- macOS，用户已登录，Codex CLI 已通过 ChatGPT 账户登录。
- 用户脚本使用 Python 3.9+；当前系统辅助程序使用 `/usr/bin/python3`，需要该解释器可用。
- `codex` 在 PATH 中；npm 安装的 CLI 还需要 Node。
- 安装系统唤醒辅助程序需要 macOS 管理员授权。
- 当前默认模型 `gpt-5.6-luna` 是原部署账户在 CLI 中实测可用的轻量模型；其他账户应选择自己的 CLI 支持的模型，不保证该名称对所有账户适用。

没有 Python 第三方依赖，不需要 API Key。预热本身会占少量订阅额度。短提示仍包含 CLI 内置上下文，不等于只有几个输入 tokens。

## 安装

```sh
python3 configure.py
python3 install-user.py
python3 install-wakes.py
```

指定本账户在 CLI 中支持的模型：

```sh
python3 configure.py --model YOUR_SUPPORTED_MODEL
```

`configure.py` 从已有登录读取账户标识，只保存 SHA-256 指纹及机器路径到本地 `config.json`，不复制 tokens。这个文件已被 Git 忽略。账户更换后运行脚本会停止发送，需要明确重新运行配置并安装。

用户运行文件位于 `~/Library/Application Support/CodexPrewarm/`，任务位于 `~/Library/LaunchAgents/local.codex-prewarm.plist`。系统辅助文件位于 `/Library/Application Support/CodexPrewarm/`，任务位于 `/Library/LaunchDaemons/local.codex-prewarm.wakes.plist`。系统辅助程序由 root 所有，仅安排唤醒，不读取 Codex 凭证。

管理员安装器临时将辅助文件放在 `/private/tmp`，避免 macOS 后台访问 Documents 的隐私限制。

## 休眠执行条件

`launchd` 本身不能唤醒电脑。本方案通过 `pmset` 提前唤醒，然后执行请求；运行期间使用 `caffeinate -is`，结束后释放，不维持全天清醒。

建议先用连接电源、用户保持登录、网络可用、开盖休眠的条件验证。锁屏保留登录会话；注销后用户任务不运行。关机不属于当前配置的唤醒范围；重启后需先登录。

原部署机器已有一次电池供电时从 Deep Idle 按计划唤醒、定时查询额度成功、随后再次休眠的记录。该次因已有窗口而跳过发送，不能视为休眠状态下开启新窗口的验证。合盖、仅电池供电、深度休眠或短暂后台唤醒不能保证每次都成功，须检查自己的日志。

晚于计划超过 30 分钟醒来会跳过该时段。每个时段最多尝试一次模型请求，发送超时或结果不明时不自动补发；额度查询会有限重试，整次运行上限约 8 分钟。

## 核验与诊断

只读检查任务状态、历史窗口结果及真实休眠唤醒证据，不发送模型请求：

```sh
python3 healthcheck.py
```

报告写入本地 `healthcheck.json`，已被 Git 忽略。`latest_verified_new_window` 非空才表示日志中存在服务器核验成功的新窗口。该检查不增加常驻进程或额外定时任务。

只查当前账户额度，不发送模型请求：

```sh
python3 "$HOME/Library/Application Support/CodexPrewarm/prewarm.py" --probe
```

最新状态和历史结果：

```sh
cat "$HOME/Library/Application Support/CodexPrewarm/status.json"
tail -n 20 "$HOME/Library/Application Support/CodexPrewarm/prewarm.log"
pmset -g sched
launchctl print "gui/$(id -u)/local.codex-prewarm"
launchctl print system/local.codex-prewarm.wakes
cat "/Library/Application Support/CodexPrewarm/wake-status.json"
```

`--probe` 会更新最新状态文件，定时执行的历史记录仍在轮转日志中。

| 状态 | 含义 |
| --- | --- |
| `new_window_verified` | 新窗口通过两次服务器读数核验 |
| `existing_window` | 已有有效窗口，未发送 |
| `delivery_verified_existing_window` | 安装测试请求成功，但用了已有窗口 |
| `request_completed_window_unverified` | 请求完成，但新窗口未核验成功 |
| `outside_schedule` | 错过时间超过 30 分钟，未发送 |
| `quota_exhausted` | 适用额度已耗尽，未发送 |
| `failed` | 查看 `reason`，不会自动重复补发 |

本项目把“唤醒成功”“请求完成”“新窗口核验成功”分别记录，不能用进程退出成功或额度显示 0% 替代窗口核验。

## 更新和卸载

修改代码后运行测试，再重新安装用户任务；修改系统辅助程序时重新安装唤醒任务：

```sh
python3 -m unittest discover -s tests -v
python3 install-user.py
# 仅系统辅助程序变更时需要这一项及管理员授权
python3 install-wakes.py
```

默认三个时间点同时写在 `config.example.json`、本地 `config.json` 和 `wake.py` 中。若要改时间，应先卸载旧计划，再同步修改上述配置和辅助程序并重装；单改本地配置不会改变系统唤醒事件。计划时间跟随 Mac 的系统当地时间，请保持与配置时区一致，旅行或切换时区后重新核对。

卸载计划及本项目标记的唤醒事件，保留源代码和诊断日志：

```sh
python3 uninstall.py
```

需要管理员授权，不会清除其他电源事件。

## Git 提交约定

本项目每次更新并验证后提交、推送到 GitHub。账户配置、机器路径和私有运行证据不纳入版本控制，具体协作约定见 `AGENTS.md`。

## 依据和验证范围

官方 [Codex 非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode) 提供 `codex exec`；官方 [App Server 文档](https://learn.chatgpt.com/docs/app-server) 提供账户和额度查询；Apple 提供 [pmset 定时唤醒说明](https://support.apple.com/guide/mac-help/schedule-your-mac-to-turn-on-or-off-mchl40376151/mac)。

新窗口判断是本项目根据实际服务器读数采用的核验规则，不是服务方对额度起点的承诺。测试覆盖活动窗口、移动的空闲投影、固定的新重置时间、计划补跑边界和不复制账户凭证等判断。实际冷启动新窗口和不同休眠条件仍须以运行记录确认。
