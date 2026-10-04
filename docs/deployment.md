# 部署与维护

第一次安装的完整命令见 [README 的 Quick Start](../README.md#quick-start)。本页解释安装条件、文件位置和后续维护。

## 安装条件

用户脚本需要 Python 3.9 或更新版本，系统唤醒脚本需要可运行的 `/usr/bin/python3`。Codex CLI 应已经通过 ChatGPT 账号登录，在终端中可以直接执行 `codex`。通过 npm 安装的 CLI 还需要 Node。如何选择模型和发现程序路径见[配置说明](configuration.md)。

安装过程分成三步：配置脚本生成本地配置；用户安装器加载登录后的定时任务；系统安装器请求管理员授权并加载唤醒维护任务。系统任务安装后会立即安排后续唤醒，之后每天继续补齐。

用户安装器使用运行它的 Python 路径创建任务。请用准备长期保留的 Python 安装，不要用即将删除的临时虚拟环境。

## 文件会安装到哪里

| 位置 | 内容 |
| --- | --- |
| 项目目录的 `config.json` | 本机配置，安装时复制到运行目录。 |
| `~/Library/Application Support/CodexPrewarm/` | 用户脚本、配置、文件锁、最新结果、发送尝试记录和日志。 |
| `~/Library/LaunchAgents/local.codex-prewarm.plist` | 用户定时任务，标签为 `local.codex-prewarm`。 |
| `/Library/Application Support/CodexPrewarm/` | 系统唤醒脚本、最近一次安排结果和系统任务日志。 |
| `/Library/LaunchDaemons/local.codex-prewarm.wakes.plist` | 系统定时任务，标签为 `local.codex-prewarm.wakes`。 |
| 项目目录的 `healthcheck.json` | 按需运行检查脚本后生成的报告。 |

用户运行目录权限为 `0700`，复制的代码和配置为 `0600`。系统辅助文件由 root 拥有。管理员安装器把文件暂存在 `/private/tmp`，再复制到系统位置，避免后台读取 Documents 目录受到 macOS 隐私限制。

`prewarm.log` 达到 128 KiB 后会换到备份文件，最多保留两份备份。任务的标准输出和错误输出另写入 `launchd.log`、`launchd-error.log`；这些文件没有配置自动轮转。系统任务使用 `wake.log`、`wake-error.log`，也没有配置轮转。

## 休眠、锁屏和重启

launchd 按计划运行任务，pmset 先唤醒 Mac。用户任务运行期间使用 `caffeinate -is`，结束后解除防止闲置休眠的限制。`-s` 的系统休眠限制仅在接电时生效；这不保证能阻止合盖或其他原因引起的休眠。

第一次实际测试建议接电、保持用户登录和网络可用，并在开盖状态下让 Mac 休眠。锁屏仍保留用户任务；注销后用户任务不运行。当前只安排 `wake`，不会启动已经关机的 Mac，重启后需要先登录。

合盖、仅用电池或系统只短暂醒来时，任务可能无法完成。项目目前实际确认到哪一步见[测试说明](testing.md)，检查自己的执行结果见[排错说明](troubleshooting.md)。

如果维护系统唤醒计划的任务长时间没有运行，已安排的有限天数会逐渐用完。不要把一次安装成功当作永久存在的唤醒计划；应查看 `wake-status.json` 和剩余事件。

## 更新

更新项目后，先检查改动。如果改了代码，按[测试说明](testing.md)运行相关测试；只改文档时检查内容、链接和 diff 即可。

改了 `prewarm.py` 或本地配置后，重新安装用户任务：

```sh
python3 install-user.py
```

CLI 路径或账号发生变化时，先按[配置说明](configuration.md)重新生成配置。

只有系统唤醒脚本或其任务配置也发生变化时，才需要重新安装系统任务：

```sh
python3 install-wakes.py
```

这一步需要管理员授权。检查脚本在项目目录直接运行，不需要复制到 Library。调整时间的同步修改清单见[配置说明](configuration.md#调整时间)。

## 卸载

```sh
python3 uninstall.py
```

卸载先要求管理员授权，停止系统任务，并撤销 `wake.py` 根据当前时间表在九天范围内找到的本项目事件；随后停止用户任务并删除两份任务 plist。它不会按名称删除所有历史事件，也不会清除其他程序的电源计划。

代码、配置和日志会保留。如果计划时间需要修改，请先用旧版 `wake.py` 卸载，再改时间和重装，否则旧时间对应的事件可能仍然存在。如果取消管理员授权，卸载不会继续移除用户任务。

## 提交更新

相关检查完成后，创建 Git commit 并推送到项目远端分支。提交前检查文件列表，确认不包含本机配置和运行记录。维护约定见 [`AGENTS.md`](../AGENTS.md)。
