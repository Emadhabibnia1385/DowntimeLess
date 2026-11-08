<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/brand/logo-dark.webp">
    <img src="./assets/brand/logo-light.webp" width="420" alt="DowntimeLess">
  </picture>
</p>

<p align="center">
  <img src="./assets/hero.svg" width="100%" alt="DowntimeLess：主控服务器通过轻量 agent 监控中转和出口服务器">
</p>

<p align="center">
  在一个面板里监控和管理 VPN 服务器集群：<br>
  服务器、中转、隧道、流量额度、DNS 故障切换和各类面板，并提供 AI 智能体可直接读取的 API。
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0-A3E635?style=flat-square&labelColor=0B1210" alt="Version 0.1.0">
  <img src="https://img.shields.io/badge/python-3.10%2B-A3E635?style=flat-square&labelColor=0B1210" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/UI-Persian%20%C2%B7%20RTL-A3E635?style=flat-square&labelColor=0B1210" alt="Persian RTL UI">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-A3E635?style=flat-square&labelColor=0B1210" alt="MIT license"></a>
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.fa.md">فارسی</a> · <a href="README.ru.md">Русский</a> · <b>简体中文</b>
</p>

VPN 集群的故障往往是一个绿点看不出来的：中转能 ping 通却不转发数据，隧道显示 “active” 却空闲，流量额度用完后整个机房看起来像宕机。**DowntimeLess** 在每台服务器上放一个很小的 agent，由主控服务器统一监控，通过 Telegram 告诉你哪里出了问题以及下一步该试什么，同时把同样的数据以 JSON API 提供给 AI 智能体，让问题更快被定位和解决。

它融合了三个项目的思路：[Uptime Kuma](https://github.com/louislam/uptime-kuma) 的监控模型，[cloudflare-telegram-bot](https://github.com/ExPLoSiVe1988/cloudflare-telegram-bot) 的 DNS 故障切换与加权负载均衡，以及 [VPNOpsNyx](https://github.com/nyxon-tech/vpnopsnyx) 经过实战检验的运维规则。

## 安装

在主控服务器上（Ubuntu 或 Debian，root 权限）：

```sh
bash <(curl -fsSL https://raw.githubusercontent.com/Emadhabibnia1385/DowntimeLess/main/install.sh)
```

安装程序会询问面板子域名、Telegram 机器人令牌和 TLS 模式，把服务安装到 nginx 之后，并显示一次性链接。在 Telegram 中打开一次，你就成为所有者。之后运行 `sudo downtimeless` 打开菜单。

| 菜单 | 作用 |
| --- | --- |
| Install | 首次设置：软件包、venv、systemd 服务、nginx 站点、检查机器人 |
| Update | 拉取最新版本、重启、检查健康状态，失败则回滚 |
| Edit settings | 机器人令牌、公开 URL、端口，或在编辑器中打开 `.env` |
| Status · Logs · Restart | 服务状态、实时日志、带健康检查的重启 |
| Owner link | 显示面板地址和待使用的所有者链接 |
| Backup · Uninstall | SQLite 备份；卸载时默认保留数据 |

然后在面板中添加服务器，每台服务器都会显示一条要在该机器上执行的命令：

```sh
curl -fsSL https://panel.example.com/agent/install.sh | sudo bash -s -- --master https://panel.example.com --token <one-time-token>
```

## 功能

- **集群总览。** 每台服务器的 CPU、内存、磁盘、steal、TCP 重传、conntrack、运行时间、公网 IP、国家、城市和机房。
- **链路矩阵。** 每台服务器互相 ping，中转到出口的链路中断会以丢包率和延迟显示。
- **流量。** 按小时、天、周、月统计每台服务器的下载和上传，来自重启后仍然有效的网卡计数器。
- **报告问题，而不只是数字。** `/issues` 列出问题、证据和建议的下一步。
- **Telegram。** 登录确认、离线与恢复告警，以及开发者日志频道。
- **安全操作。** 任意 agent 都可以做 ping、TCP 检查和测速。升级和重启只在服务器权限级别允许且有已登录的人时才可用。
- **API 优先。** 面板里的一切都是有文档的 JSON 接口。

后续计划依次为：已购流量账本与 “还剩 N 天” 告警，从多个探测点做 HTTP/TCP/关键词/DNS/证书监控，Cloudflare 令牌与 DNS 故障切换和加权负载均衡，PasarGuard / 3x-ui / Marzban / Marzneshin / Hiddify 连接器，以及 AI 运维。详见 [docs/ROADMAP.md](docs/ROADMAP.md)。

## 工作原理

```
 浏览器 / Telegram Mini App ──HTTPS──▶ nginx ──▶ master（FastAPI + SQLite，同时提供网页面板）
                                                  ▲
                                   HTTPS，仅出站   │ 每 30 秒：指标 + ping 结果 ⇄ 任务
                                                 每台服务器上的 agent（单个 Python 文件，仅标准库）
```

- agent 只主动向外连接，SSH 密钥和 root 密码不会离开服务器。
- 任务是封闭列表。任何会改动服务器的操作，都要先提高该服务器的权限级别。
- 登录通过 Telegram 确认（显示 IP 和浏览器，询问 “是你本人吗？”），之后可选设置密码。密钥类数据只保存哈希。

## 面向 AI 智能体

在面板（所有者，API 密钥）创建一个密钥交给智能体：

```sh
curl -H "Authorization: Bearer dl_..." https://panel.example.com/api/v1/snapshot   # 整个集群 + 问题 + 链路矩阵
curl -H "Authorization: Bearer dl_..." https://panel.example.com/api/v1/issues     # 哪里出了问题，附证据
```

`read` 密钥只能读取。`operate` 密钥还可以排队只读检查。任何密钥都不能重启、升级或管理用户和密钥。接口定义在 `/api/openapi.json`，给智能体看的说明在 `/llms.txt`。

## 仓库结构

| 路径 | 内容 |
| --- | --- |
| `master/` | FastAPI 后端、SQLite、Telegram 机器人、测试 |
| `agent/` | 安装在每台服务器上的采集器 |
| `web/` | 波斯语 RTL 网页面板（构建产物会提交） |
| `install.sh` | 主控安装与管理脚本 |
| `docs/` | [架构](docs/ARCHITECTURE.md)、[路线图](docs/ROADMAP.md)、[OpenAPI](docs/openapi.json) |

## 开发者

作者 Emad Habibnia · Telegram [@emadhabibnia](https://t.me/emadhabibnia) · GitHub [emadhabibnia1385](https://github.com/emadhabibnia1385)。

## 许可证

[MIT](LICENSE)
