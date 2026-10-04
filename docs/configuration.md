# 配置说明

先在项目目录运行配置脚本，再安装任务。首次配置读取 `config.example.json`；如果本地已有 `config.json`，脚本会保留其中的时间、时区、补跑宽限和模型设置。只改样例文件不会覆盖这些现有设置。

## 配置字段

| 字段 | 默认值或生成方式 | 脚本如何使用 |
| --- | --- | --- |
| `times` | `08:30`、`14:00`、`19:30` | 用户安装器生成定时任务；预热脚本判断当前属于哪个时间点。 |
| `timezone` | `Asia/Shanghai` | 预热脚本计算日期和时间；用户任务也设置 `TZ` 环境变量。 |
| `catchup_minutes` | `30` | 用户脚本最多允许比计划晚多少分钟执行。 |
| `model` | `gpt-5.6-luna` | 传给 `codex exec --model`。 |
| `codex` | `configure.py` 在 PATH 中找到的 CLI 路径 | 用户脚本启动 Codex CLI。 |
| `codex_home` | 配置时的 `CODEX_HOME`，未设置时使用 `~/.codex` | 用户脚本读取这里的登录文件，并将该目录传给 CLI。 |
| `child_path` | 配置时发现的 Node 目录，加上常用系统和 Homebrew 路径 | CLI 子进程使用的 PATH。 |
| `account_fingerprint` | 登录账号标识的 SHA-256 哈希值 | 发送前检查账号是否还是配置时的账号。 |

配置文件写入项目目录，权限为 `0600`，不会提交到 GitHub。安装后的任务读取 Library 中的配置副本，修改项目配置后需要重新运行用户安装器。安装和更新的步骤见[部署说明](deployment.md)。

## 选择模型

默认模型在最初安装这套脚本的账号上测试通过，其他账号应选择自己的 Codex CLI 支持的模型：

```sh
python3 configure.py --model YOUR_SUPPORTED_MODEL
```

模型请求固定使用低推理强度。`codex exec` 带有 `--ignore-user-config`，所以预热不会跟随你在全局 Codex 配置里改动的模型或其他用户设置。换模型应修改本项目配置并重新安装。

CLI 和桌面应用能调用的模型可能不同。不能仅因桌面应用中可用，就认定同名模型在 CLI 中也可用；具体错误的检查方法见[排错说明](troubleshooting.md)。

## 更换账号或 CLI 路径

配置脚本读取现有 `auth.json`，但不复制登录令牌。如果 CLI 换了账号，预热脚本会停止发送，避免使用你尚未为本项目确认的账号。重新登录后，再运行配置脚本和用户安装器。

CLI 或 Node 路径变化时，也先让终端能找到正确程序，再重新配置。配置脚本除了当前能找到的 Node 目录，还加入 `/opt/homebrew/opt/node@20/bin` 等常用路径；它不会自动找到所有 Homebrew 版本的 Node。

## 调整时间

发送计划和唤醒计划目前分别保存在不同位置。调整前先按[部署说明](deployment.md)卸载旧计划，再同步修改这些文件：

| 位置 | 需要调整的内容 |
| --- | --- |
| 本地 `config.json` 的 `times` | 用户任务的发送时间。 |
| `config.example.json` 的 `times` | 新安装时采用的时间。 |
| `wake.py` 的 `TIMES` | 系统唤醒对应的发送时间，脚本会自动减去一分钟。 |
| `wake.py` 写入报告的 `times` 列表 | 让报告显示修改后的时间。 |

修改后重新安装用户和系统任务。`install-user.py` 会从本地配置生成计划，不需要另改安装器。`wake.py` 不读取用户配置，所以单改 `config.json` 不会改变唤醒时间。

## 时区和补跑宽限

launchd 的日历计划和 `wake.py` 跟随 Mac 的系统当地时间。任务中的 `TZ` 不会替你修改系统时区。请让 Mac 的系统时区与配置一致；旅行或切换时区后重新检查计划。

检查脚本目前在 `healthcheck.py` 中固定使用 `Asia/Shanghai`。如果改用其他时区，还要同步修改它的 `ZONE`，否则它可能把日志中的时间解释错。

`catchup_minutes` 控制预热脚本允许补跑的范围。检查脚本关联任务和唤醒记录时，仍固定使用 30 分钟范围；预热脚本的部分原因文字也固定写着 30 分钟。调整这个字段时，需要同步核对这些代码和报告文字。相关判断见[实现细节](implementation.md)。
