# Roadmap and feature map

What DowntimeLess takes from the three systems it merges, and where each idea lands.

| Idea | Source | DowntimeLess design |
| --- | --- | --- |
| Monitor types: ping, TCP, HTTP(s), keyword, DNS, certificate expiry, push | Uptime Kuma | One `monitor` model. Every agent is also a **probe location**, so each check runs from several servers, not only from the master. |
| Push monitors / heartbeat | Uptime Kuma | The agent report is the heartbeat; a server with no report for 3 intervals is `offline`. |
| 20-second intervals, retries before alert, resend while down | Uptime Kuma | Per-monitor `interval_s`, `retries`, `resend_every`. |
| Status page, optional custom domain | Uptime Kuma | Public read-only page per group of servers, no secrets (phase 3). |
| Maintenance windows | Uptime Kuma | Silence alerts and block failover during a window. |
| Monitoring groups with an error threshold | cloudflare-telegram-bot | **Probe group**: "down only if at least N of M probes fail". This is the same rule the ops skill demands (two in-country probes must agree). |
| Failover: switch DNS to a healthy backup IP | cloudflare-telegram-bot | DNS **rule** per Cloudflare name: pool of IPs (relays), probe group, thresholds. Guards: never remove the last record, two probes agree, data-path test before re-adding, every change logged and sent to Telegram. Starts as "propose and ask in Telegram", auto mode is opt-in per rule. |
| Weighted load balancing (weighted random / round robin) | cloudflare-telegram-bot | Pool entries carry a weight; the rule keeps the heaviest healthy subset in DNS and rotates it. Respects per-relay quota and real-user MB/conn from the agent. |
| Per-rule alert recipients | cloudflare-telegram-bot | Each monitor/rule has its own Telegram chat or group list. |
| Alias for domains and records | cloudflare-telegram-bot | `alias` field on servers, monitors, DNS names. |
| Bulk change, move/copy record, backup/restore as JSON | cloudflare-telegram-bot | DNS tools page; backup/restore of the whole DowntimeLess config too. |
| Multiple DNS providers (Cloudflare, ArvanCloud) | cloudflare-telegram-bot | `dns_provider` interface; Cloudflare first, ArvanCloud second. |
| Hetzner Cloud: power, reboot, traffic and cost | cloudflare-telegram-bot | `cloud_provider` interface (Hetzner first): purchased traffic, remaining GB, alert days ahead. |
| Relay-to-exit data path measured in delivered bytes, real users per relay | vpnopsnyx | Agent jobs: `speedtest_*`, listener checks, `ss` counters like `realuse.sh`. |
| Safe upgrade/reboot, panel update with rollback | vpnopsnyx | Whitelisted jobs behind a per-server permission level and human approval. |

## Phases

1. **v0.1 (this release line)**: installer menu, Telegram login + password, servers, agent metrics, ping matrix between servers, dashboard, alerts to Telegram.
2. **Traffic**: purchased-traffic ledger ("I bought 2 TB"), remaining GB, alerts N days ahead; daily/weekly/monthly charts per relay and exit.
3. **Monitors + status page**: HTTP/TCP/keyword/DNS/cert monitors from probe groups, maintenance windows, public status page.
4. **Cloudflare**: tokens, DNS name inventory, tunnel map (which exit serves which relay, which relay is cut), failover and weighted LB rules.
5. **Panels**: PasarGuard first, then 3x-ui, Marzban, Marzneshin, Hiddify. Read nodes, inbounds, hosts/domains/ports from a subscription link, panel and node update.
6. **Speed and upgrade jobs**, ArvanCloud and Hetzner providers, AI operator (Claude) with the vpnopsnyx skill as its knowledge.
