# Codex 定时预热（macOS）

在工作开始前向 Codex 发一条极短消息，尝试提前开始新一轮五小时额度计时。脚本随后查询服务器，确认计时是否真的开始。

## 核心能力

- 每天 08:30、14:00、19:30 自动执行，并提前一分钟安排系统唤醒。
- 已有五小时计时仍在进行、额度不足或无法确认状态时，跳过发送。
- 请求完成后再次查询服务器，分别记录请求结果和计时是否开始。
- 提供日志和只读检查命令，便于确认休眠时有没有执行。

它不能提前重置正在使用的额度，也不会增加周额度。

## Quick Start

需要 macOS、Python 3.9+、可用的 `/usr/bin/python3`，以及已通过 ChatGPT 账号登录的 Codex CLI。通过 npm 安装 CLI 时还需要 Node。系统唤醒任务的安装会要求管理员授权；默认模型是否能用取决于你的 CLI 账号，详见[配置说明](docs/configuration.md)。

```sh
git clone https://github.com/sulik0/codex-prewarm.git
cd codex-prewarm
python3 configure.py
python3 install-user.py
python3 install-wakes.py
python3 healthcheck.py
```

这是私有仓库，克隆时需要 GitHub 访问权限。检查结果写入本地 `healthcheck.json`；只有 `latest_verified_new_window` 有记录，才说明脚本曾经确认新一轮计时开始。第一次休眠测试建议接电、保持登录和网络可用，并在开盖状态下进行。

## 文档

- [项目架构](ARCHITECTURE.md)：各脚本如何配合，以及为什么采用这些技术。
- [配置](docs/configuration.md)：模型、时间、时区和账号设置。
- [部署与维护](docs/deployment.md)：安装位置、休眠条件、更新和卸载。
- [实现细节](docs/implementation.md)：额度判断、超时、重复执行和结果记录。
- [测试](docs/testing.md)：自动测试、实际运行检查和目前确认到哪一步。
- [Troubleshooting（排错）](docs/troubleshooting.md)：检查命令、状态解释和常见问题。
