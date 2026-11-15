# mihomo for FreeBSD x86-64 (TUN)

仅构建 FreeBSD / amd64（x86-64，GOAMD64=v1）的 mihomo，包含 TUN 的 system、gvisor 和 mixed 栈。

每小时检查 [MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo/releases/latest) 的最新正式 Release；发现新版本后自动编译，在 FreeBSD 14.3 amd64 虚拟机测试三种 TUN 栈，成功后发布到 [Releases](https://github.com/Opnwall/freebsd-mihomo/releases)。已发布版本跳过；失败不发布，下次检查重试。GitHub 定时任务可能延迟，支持 Actions 手动运行。

主分支更新也会编译和发布，PR 仅测试。只生成 `clash-meta-freebsd-amd64.xz`、`SHA256SUMS`、`build-info.txt`，保留原二进制文件名便于现有插件使用。

```sh
xz -dk clash-meta-freebsd-amd64.xz
chmod +x clash-meta-freebsd-amd64
./clash-meta-freebsd-amd64 -v
./clash-meta-freebsd-amd64 -t -f config.yaml
```

TUN 示例见 [template.yaml](template.yaml)。以 root 运行并确保 if_tun 可用，按实际网络配置路由、DNS 和防火墙放行规则。默认示例不启用自动路由。启动测试不代表真实网关上的自动路由和转发吞吐已经验证。

`auto-route: true` 沿用原补丁的独立 FIB 方案，`fib-index` 默认 2022，需要足够的 `net.fibs` 和 `net.add_addr_allfibs=1`；按错误提示配置 `/boot/loader.conf` 并重启。补丁不兼容新上游版本时，工作流会失败并保留日志，不发布未经测试的产物。

本地交叉编译需 Bash、Go（版本见 `.go-version`）、curl、jq、patch、tar、xz：

```sh
scripts/prepare.sh
scripts/build.sh
```

重新准备源码前删除生成目录 `.build/`。Actions 使用最新上游正式版；本地默认版本见 `build.env`。准确的 sing-tun 依赖来自上游 go.mod，不使用浮动分支。

FreeBSD TUN 补丁改编自 [Vincent-Loeng/clash-meta 的 hidden 分支](https://github.com/Vincent-Loeng/clash-meta/tree/hidden)，保留 WireGuard/MIT 版权说明，适配当前依赖并修正 gVisor TUN 报文头。本仓库不再构建其他架构，也不添加额外的进程匹配或 redirect 补丁。

## 补丁自动迁移

补丁无法直接应用时，使用 `patches/bases/` 中记录的原始源码做三方合并，保留不冲突的上游修改；不使用 API，也不猜测接口或逻辑变化。迁移候选必须重新编译，并通过 FreeBSD 中 system、gvisor、mixed 三种 TUN 栈的启动和清理测试，才会保存到主分支并发布。发生冲突、编译失败或测试失败时停止发布，下次定时检查重试。实际网络转发测试覆盖 IPv4/IPv6 的 TCP 和 UDP；自动路由仍需实际设备验证。

每次迁移仅尝试一次，不降低测试要求。修改补丁时需同步更新对应基线和校验值；基线不匹配会停止迁移。测试通过前候选补丁仅保存在本次 Actions artifact 中。

## 实际 TUN 流量测试

发布前，对 system、gvisor、mixed 每种栈执行相同的真实网络测试：FreeBSD VNET jail 中运行独立 TCP/UDP 回显服务，测试客户端的 FIB 1 主机路由强制走 tun9，代理的 FIB 0 出站经 epair 到服务端。测试不依赖公共网站。

- IPv4 和 IPv6：TCP 256 KiB 往返、UDP 64/1200/4096 字节往返，随机载荷逐字节校验。
- 暂停代理时，同样的路由下 TCP/UDP 请求必须失败，防止绕过 TUN。
- 抓包验证 TUN 上两种协议、两种地址族的请求和响应；检查路由确实指向 tun9。
- 退出后确认 TUN 设备清理。任何一项失败均阻止保存迁移补丁和发布。

Actions 的 `tun-network-tests` artifact 保存 JSON 校验结果、服务日志、路由记录与 pcap。该测试验证手工路由下的转发，不等同于真实 pfSense/OPNsense 环境的自动路由、防火墙规则或性能测试。
