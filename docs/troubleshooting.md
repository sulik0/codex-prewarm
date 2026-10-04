# Troubleshooting（排错）

先查看任务和日志，再判断问题发生在唤醒、请求还是计时确认这一步。不要仅凭“任务退出码为 0”认定预热成功。

## 先收集这些结果

在项目目录运行：

```sh
python3 healthcheck.py
cat healthcheck.json
```

它只读取任务和历史记录，不发送消息，也不实时查询额度。看 `user_job_loaded`、`root_job_loaded` 和 `remaining_tagged_wake_events`，确认任务存在且后面还有唤醒安排。`latest_scheduled_result` 是最近一条带有计划时间点的记录；部分失败记录没有时间点，需要另查最新状态和日志。`latest_observation` 也可能是后来手动查询写入的结果。

需要实时查额度时，运行：

```sh
python3 "$HOME/Library/Application Support/CodexPrewarm/prewarm.py" --probe
```

这条命令不发送模型请求，但会覆盖最新状态文件。定时结果仍保存在历史日志中。

直接查看用户日志、系统计划和任务：

```sh
prewarm_runtime="$HOME/Library/Application Support/CodexPrewarm"
cat "$prewarm_runtime/status.json"
tail -n 20 "$prewarm_runtime/prewarm.log"
cat "$prewarm_runtime/launchd-error.log"
pmset -g sched
launchctl print "gui/$(id -u)/local.codex-prewarm"
launchctl print system/local.codex-prewarm.wakes
cat "/Library/Application Support/CodexPrewarm/wake-status.json"
```

## 状态表示什么

| 状态 | 说明和下一步 |
| --- | --- |
| `new_window_verified` | 新重置时间已确认，查看 `reset_at`。 |
| `existing_window` | 原有计时还没结束，脚本没有发送。即使使用量已到 100%，也可能返回这个状态。 |
| `delivery_verified_existing_window` | 测试请求完成，但用了已有额度；不表示开始新的计时。 |
| `request_completed_window_unverified` | 请求完成，但新的重置时间未确认。保留记录并检查后续额度，不要立即反复补发。 |
| `outside_schedule` | 本次不在允许执行的时间范围，检查计划时间和时区。 |
| `duplicate_slot_skipped` | 当前时间点已经尝试过发送，没有补发。 |
| `quota_exhausted` | 可用额度已经用完，没有发送。 |
| `probe_active`、`probe_idle`、`probe_expired`、`probe_uncertain` | 手动只读查询的判断结果，不是模型请求结果。 |
| `failed` | 查看 `reason`，按下面的问题表处理。 |
| `already_running` | 已有脚本运行，新进程只打印这个结果，不更新状态文件。 |

具体判断及退出码见[实现细节](implementation.md)。

## 常见问题

### 任务显示 not running

任务运行完就退出，`not running` 本身不是错误。查看是否已加载、最近的退出码、运行次数和日志。只读检查的 `latest_verified_new_window` 来自保留日志；它为空不一定意味着以前从未成功。

### Mac 没有醒来，或者醒来后没执行

检查系统计划里是否有带 `local.codex-prewarm.*` 标记的后续事件，再检查系统任务退出码和 `wake-status.json` 的 `failed_events`。维护任务长时间没运行，有限天数的计划可能用完；修复安装后需要重新补齐。

然后确认用户仍保持登录、网络可用、系统时间与配置一致，并查看电源日志是否记录了真正的 `Wake`。仅短暂后台醒来不一定足以完成用户任务。合盖和电池供电时的测试条件见[部署说明](deployment.md#休眠锁屏和重启)。

### reason 包含 account_changed 或 subscription_login_required

确认 Codex 使用 ChatGPT 账号登录，并且是本项目配置时的账号。换账号后按[配置说明](configuration.md#更换账号或-cli-路径)重新配置并安装。API Key 登录不适用这个订阅预热脚本。

`subscription_auth_unreadable` 表示登录文件无法读取或解析，先检查配置中的 Codex 目录和登录状态。

### reason 包含 model_not_supported

选择当前账号在 CLI 中支持的模型，再重新配置并安装用户任务。桌面应用能调用同名模型，并不能证明 CLI 也支持它。配置方法见[模型设置](configuration.md#选择模型)。

### 后台找不到 Node、Codex 或 Python

后台 PATH 可能和交互终端不同。检查本地及运行目录配置中的 `codex`、`child_path`，让终端先能找到正确 CLI 和 Node，再重新配置。Python 路径写在用户任务里；如果该解释器已经移动或被删除，用可用的 Python 重新运行用户安装器。具体设置见[配置说明](configuration.md)。

### reason 包含 quota_unavailable、quota_query_timeout 或 cli_rpc_ 错误

脚本没有获得可用的额度信息。检查网络、CLI 登录状态及版本，再执行一次只读额度查询。查询失败时脚本不会据此发送模型请求，避免误判。

`five_hour_window_missing`、`target_bucket_missing` 或 `invalid_quota_value` 表示接口结果不符合当前代码的预期。`weekly_quota_unknown` 表示无法确认周额度。检查账号是否还有五小时额度，以及 CLI 接口是否变化，不要把缺失字段当成零使用量。

### 请求超时，或者无法确认是否成功

`model_request_timeout`、`model_request_failed` 表示发送没有得到可确认的完成结果。脚本不会再次启动一次发送；同一计划时间点的尝试已经记在 `state.json` 中。

`idle_state_unconfirmed` 表示发送前不能判断计时状态；`request_completed_window_unverified` 则表示请求已完成，但发送后没有确认新的计时。先查看实时额度和历史记录，不要因为日志没有成功状态就立即重复发送。

`run_deadline_exceeded` 表示整个预热进程超过限制。检查本次发生在哪一步；它也不是可直接补发的依据。

### 管理员安装提示 Operation not permitted

使用项目的 `install-wakes.py`，它会先把文件放到 `/private/tmp` 再请求管理员权限。不要直接让系统后台程序从 Documents 目录读取安装文件。若管理员授权被取消，安装不会完成；查看实际任务和文件，不要只依据曾出现过授权窗口判断成功。

### 改了配置但行为没变

安装后的用户任务读取 Library 中的副本，需要重新安装才会更新。唤醒时间还保存在 `wake.py`，不会随用户配置自动变化。样例配置也不会覆盖已有的本地配置。修改清单见[配置说明](configuration.md)。
