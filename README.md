# Codex 定时预热（macOS）

这个脚本会在工作开始前向 Codex 发一条极短消息，尝试提前开始新一轮五小时额度计时。发送后，脚本会向服务器查询额度信息，确认计时是否真的开始。

默认每天 **08:30、14:00、19:30** 执行。如果 Mac 正在休眠，系统会按计划提前一分钟唤醒它。

## 脚本具体做什么

1. 用户登录后的定时任务先通过 Codex App Server 查询账号的额度。
2. 如果当前五小时额度还没到重置时间，脚本就跳过这次发送。周额度已经用完，或者无法判断本轮计时是否已经开始时，也会跳过。
3. 确认当前没有进行中的五小时计时后，脚本才发送一条消息，要求 Codex 只回复 `OK`。请求在临时空目录里执行，使用只读沙箱和 `--ephemeral`（不保存会话）。
4. 请求完成后，脚本间隔 15 秒查询两次额度。只有两次返回的重置时间保持一致，而且接近发送请求后的五小时，脚本才记录 `new_window_verified`，表示新一轮计时已经确认开始。
5. 系统定时任务每天 00:05 安排未来九天的唤醒时间。每次唤醒都有 `local.codex-prewarm.*` 标记，脚本只管理自己添加的事件，保留 Mac 原有的唤醒安排。

| 发送消息的时间 | 提前唤醒的时间 | 如果这次开始了新一轮计时，预计何时重置 |
| --- | --- | --- |
| 08:30 | 08:29 | 13:30 左右 |
| 14:00 | 13:59 | 19:00 左右 |
| 19:30 | 19:29 | 次日 00:30 左右 |

如果你已经在使用当前五小时额度，脚本不能让它提前重置。实际重置时间以服务器返回的 `reset_at` 为准。这套安排也不会增加周额度。

## 安装前需要准备什么

- 使用 macOS，并保持用户已登录。Codex CLI 需要已经通过 ChatGPT 账号登录。
- 用 Python 3.9 或更新版本运行用户脚本。负责安排系统唤醒的脚本使用 `/usr/bin/python3`，请确认这个解释器可以运行。
- 在终端里能直接运行 `codex`。如果通过 npm 安装 Codex CLI，还需要 Node。
- 安装系统唤醒任务时，macOS 会要求管理员授权。
- 默认模型是 `gpt-5.6-luna`，它已在最初安装这套脚本的账号上测试通过。其他账号请选用自己在 Codex CLI 中能调用的模型。

脚本不需要额外安装 Python 包，也不需要 API Key。预热请求会占用少量订阅额度。虽然只要求回复 `OK`，CLI 仍会附带内置提示，所以实际输入 tokens 不止几个。

## 怎么安装

在项目目录中运行：

```sh
python3 configure.py
python3 install-user.py
python3 install-wakes.py
```

如果要换成自己的账号支持的模型，先运行下面的配置命令，再安装：

```sh
python3 configure.py --model YOUR_SUPPORTED_MODEL
```

`configure.py` 会读取现有 Codex 登录文件中的账号标识，把它计算成 SHA-256 哈希值，用来检查后续运行时是否仍是同一个账号。脚本把这个哈希值和本机路径写入 `config.json`，不会复制登录令牌。Git 会忽略这个配置文件。

如果 Codex 换了账号，脚本会停止发送消息。请重新运行配置和安装命令，让脚本使用新账号。

安装器会把文件放到这些位置：

| 文件 | 位置 |
| --- | --- |
| 用户脚本和运行记录 | `~/Library/Application Support/CodexPrewarm/` |
| LaunchAgent（用户定时任务） | `~/Library/LaunchAgents/local.codex-prewarm.plist` |
| 安排系统唤醒的脚本 | `/Library/Application Support/CodexPrewarm/` |
| LaunchDaemon（系统定时任务） | `/Library/LaunchDaemons/local.codex-prewarm.wakes.plist` |

系统唤醒脚本由 root 拥有，只负责安排唤醒时间，不读取 Codex 登录信息。安装时，安装器会先把系统辅助文件暂存在 `/private/tmp`，再以管理员权限复制到目标位置。这样可以避开 macOS 对后台程序访问 Documents 目录的限制。

## Mac 休眠时怎么运行

`launchd` 能按时间运行任务，但不能自己唤醒 Mac。脚本先用 `pmset` 安排系统唤醒，再由定时任务发送请求。运行期间，`caffeinate -is` 会防止 Mac 因闲置而再次休眠；脚本结束后，这个限制就会解除。

第一次测试时，建议接上电源、保持用户登录和网络可用，并在开盖状态下让 Mac 休眠。锁屏不会退出登录，用户定时任务仍可运行；注销后则不会运行。当前配置不能开机，重启后也需要先登录。

最初安装这套脚本的 Mac 已有一次实际运行记录：它在电池供电时，从电源日志所称的 Deep Idle 休眠状态按计划醒来，定时任务成功查询额度，随后 Mac 再次休眠。不过，当时五小时额度尚未到重置时间，脚本跳过了发送，因此还不能据此确认“休眠后发送消息并开始新一轮计时”也已经成功。

合盖、仅用电池或系统只短暂醒来时，任务不一定每次都能完成。请查看自己的运行记录，确认执行结果。

如果 Mac 比计划晚醒超过 30 分钟，脚本会跳过该时段，避免补发消息把计时起点拖后。每个时段最多尝试发送一次消息；请求超时或无法确认是否发送成功时，脚本不会自动补发。查询额度失败后，脚本会最多尝试三次。整次运行最多约八分钟。

## 怎么确认是否成功

运行下面的命令，可以检查定时任务、历史结果，以及系统记录的休眠和唤醒时间。它只读取记录，不发送模型请求：

```sh
python3 healthcheck.py
```

检查结果会写入本地 `healthcheck.json`，Git 会忽略这个文件。只有 `latest_verified_new_window` 中有记录，才说明脚本曾经确认新一轮计时开始。检查脚本还会整理最近几次定时执行前后的休眠和唤醒记录，运行完就退出。

如果只想查当前额度，运行：

```sh
python3 "$HOME/Library/Application Support/CodexPrewarm/prewarm.py" --probe
```

查看最近一次结果、历史日志和系统唤醒安排：

```sh
cat "$HOME/Library/Application Support/CodexPrewarm/status.json"
tail -n 20 "$HOME/Library/Application Support/CodexPrewarm/prewarm.log"
pmset -g sched
launchctl print "gui/$(id -u)/local.codex-prewarm"
launchctl print system/local.codex-prewarm.wakes
cat "/Library/Application Support/CodexPrewarm/wake-status.json"
```

`--probe` 会把本次查询结果写入最新状态文件。此前定时任务的结果仍保存在 `prewarm.log` 及它的备份文件中。

| 状态 | 说明 |
| --- | --- |
| `new_window_verified` | 两次查询都确认了同一个新的重置时间 |
| `existing_window` | 本轮计时还没结束，脚本没有发送消息 |
| `delivery_verified_existing_window` | 测试消息已完成，但用的是原有五小时额度 |
| `request_completed_window_unverified` | 请求已完成，但脚本还不能确认新一轮计时开始 |
| `outside_schedule` | 比计划晚醒超过 30 分钟，脚本没有发送消息 |
| `quota_exhausted` | 可用额度已用完，脚本没有发送消息 |
| `failed` | 执行失败，原因见 `reason`；脚本不会自动重复补发 |

请分别确认 Mac 是否醒来、请求是否完成，以及新一轮计时是否开始。即使 CLI 正常退出，或者使用量显示为 0%，也不能只凭这一点认定预热成功。

## 怎么更新或卸载

改动代码后，先运行相关测试，再重新安装用户任务。如果还改了系统唤醒脚本，再重新安装系统任务：

```sh
python3 -m unittest discover -s tests -v
python3 install-user.py
# 改了系统唤醒脚本时，再运行这一项；它需要管理员授权
python3 install-wakes.py
```

默认三个时间点同时写在 `config.example.json`、本地 `config.json` 和 `wake.py` 中。要调整时间，请先卸载旧计划，再同步修改这三个文件并重新安装。只修改本地配置，不会改变系统已经安排的唤醒时间。

Mac 按系统当地时间执行这些计划，请让系统时区与配置时区保持一致。旅行或切换时区后，需要重新检查执行时间。

卸载命令如下：

```sh
python3 uninstall.py
```

卸载时需要管理员授权。脚本会移除定时任务和自己添加的唤醒事件，保留源代码及日志，也会保留其他程序安排的电源事件。

## 怎么提交更新

每次更新并完成相关检查后，提交代码并推送到 GitHub。请不要提交账号配置、本机路径和私有运行记录。具体约定见 `AGENTS.md`。

## 文档依据和测试情况

官方 [Codex 非交互模式文档](https://learn.chatgpt.com/docs/non-interactive-mode) 介绍了 `codex exec`；官方 [App Server 文档](https://learn.chatgpt.com/docs/app-server) 说明了如何查询账号和额度；Apple 提供了 [pmset 定时唤醒说明](https://support.apple.com/guide/mac-help/schedule-your-mac-to-turn-on-or-off-mchl40376151/mac)。

脚本根据服务器返回的额度信息判断计时是否开始。服务方没有因此承诺每次预热都一定能按预期开始计时。

测试检查了这些情况：旧计时尚未结束；还没开始使用时，接口显示的重置时间随当前时间向后移动；新一轮计时开始后，重置时间保持不变；Mac 晚醒时是否应该补跑；配置脚本是否会复制登录令牌。休眠后首次开始新一轮计时，以及其他休眠条件下的表现，仍需要查看实际运行记录才能确认。
