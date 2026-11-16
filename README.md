# Mihomo for FreeBSD x86-64（TUN）

为 FreeBSD / amd64（x86-64，`GOAMD64=v1`）构建 mihomo，支持 `system`、`gvisor` 和 `mixed` 三种 TUN 栈。

本仓库跟踪 [MetaCubeX/mihomo 最新正式版本](https://github.com/MetaCubeX/mihomo/releases/latest)，自动构建并在虚拟机中测试。检查通过后，发布至 [Releases](https://github.com/Opnwall/freebsd-mihomo/releases)。

## 下载与使用

从 [Releases](https://github.com/Opnwall/freebsd-mihomo/releases) 下载以下文件：

| 文件 | 说明 |
| --- | --- |
| `clash-meta-freebsd-amd64.xz` | 压缩后的可执行文件 |
| `SHA256SUMS` | SHA-256 校验值 |
| `build-info.txt` | 构建信息 |

为便于现有插件使用，可执行文件沿用 `clash-meta-freebsd-amd64` 名称。

解压、赋予执行权限，并检查版本和配置：

```sh
xz -dk clash-meta-freebsd-amd64.xz
chmod +x clash-meta-freebsd-amd64
./clash-meta-freebsd-amd64 -v
./clash-meta-freebsd-amd64 -t -f config.yaml
```

### TUN 配置

配置示例见 [template.yaml](template.yaml)。运行 TUN 时需满足以下条件：

- 以 root 身份运行，并确保 `if_tun` 可用。
- 根据实际网络配置路由、DNS 和防火墙放行规则。
- 示例默认不启用自动路由，需按部署环境自行配置。

启用 `auto-route: true` 时，补丁沿用独立 FIB 方案：

- `fib-index` 默认为 `2022`。
- `net.fibs` 必须足以容纳所用 FIB 索引。
- 需要设置 `net.add_addr_allfibs=1`。

请根据运行时错误提示配置 `/boot/loader.conf`，并重启系统使其生效。

> 自动化测试覆盖手工路由下的 TUN 转发。真实 pfSense / OPNsense 环境中的自动路由、防火墙规则和转发性能仍需在实际设备上验证。

## 自动构建

| 触发方式 | 行为 |
| --- | --- |
| 每小时定时检查 | 检查上游最新正式 Release；发现尚未发布的版本后构建、测试并发布 |
| 主分支更新 | 构建、测试并发布 |
| Pull Request | 仅执行测试，不发布 |
| Actions 手动运行 | 支持手动触发工作流 |

## 发布前测试

在 FreeBSD 14.3 amd64 虚拟机中通过 `system`、`gvisor`、`mixed` 三种 TUN 栈的启动、实际流量转发和退出清理测试。

### 测试拓扑

FreeBSD VNET jail 中运行独立的 TCP / UDP 回显服务。测试客户端通过 FIB 1 中的主机路由强制将流量送入 `tun9`，代理通过 FIB 0 经 `epair` 连接服务端。测试不依赖公共网站。

### 检查项目

每种 TUN 栈执行相同的检查：

- **数据完整性**：分别测试 IPv4 / IPv6 的 TCP 256 KiB 往返，以及 UDP 64、1200、4096 字节往返，对随机载荷逐字节校验。
- **防止绕过 TUN**：暂停代理后，在相同路由下发起的 TCP / UDP 请求必须失败。
- **路由与抓包**：确认路由指向 `tun9`，并在 TUN 抓包中验证 IPv4 / IPv6、TCP / UDP 的请求和响应。
- **退出清理**：确认代理退出后 TUN 设备已清理。

任何一项失败，均阻止发布和保存迁移补丁。Actions 的 `tun-network-tests` artifact 保留 JSON 校验结果、服务日志、路由记录和 pcap，供排查使用。

这些测试验证手工路由下的功能与数据转发，不代表已验证真实网关中的自动路由或转发吞吐。

## 本地编译

需要 Bash、Go、curl、jq、patch、tar 和 xz。Go 版本见 [`.go-version`](.go-version)。

```sh
scripts/prepare.sh
scripts/build.sh
```

- 本地默认构建版本见 [`build.env`](build.env)；Actions 使用上游最新正式版本。
- 重新准备源码前，请先删除生成目录 `.build/`。
- `sing-tun` 依赖版本以对应上游源码的 `go.mod` 为准，不使用浮动分支。

## 自动迁移

上游更新后，如果补丁无法直接应用，工作流会使用 `patches/bases/` 中记录的原始源码进行三方合并，保留不冲突的上游修改。迁移过程不使用 API，也不猜测接口或逻辑变化。

迁移遵循以下规则：

1. 每次迁移仅尝试一次，不降低测试要求。
2. 候选补丁必须重新编译，并通过三种 TUN 栈的启动、流量转发和清理测试，才会保存到主分支并发布。
3. 出现合并冲突、编译失败或测试失败时停止发布，等待下次定时检查重试。
4. 修改补丁时，必须同步更新对应基线和校验值；基线不匹配时停止迁移。
5. 测试通过前，候选补丁仅保存在本次 Actions artifact 中。

如果补丁与新上游版本不兼容，工作流会失败并保留日志，不发布未经测试的产物。

## 补丁来源

FreeBSD TUN 补丁改编自 [Vincent-Loeng/clash-meta 的 hidden 分支](https://github.com/Vincent-Loeng/clash-meta/tree/hidden)，保留 WireGuard / MIT 版权说明，并适配当前依赖、修正 gVisor TUN 报文头。

本仓库仅构建 FreeBSD / amd64，不添加额外的进程匹配或 redirect 补丁。
