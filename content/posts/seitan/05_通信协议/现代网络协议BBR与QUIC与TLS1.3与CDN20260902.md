+++
title = 'BBR拥塞控制与QUIC与TLS1.3与CDN'
date = 2026-09-02T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['网络', 'TCP', 'BBR', 'QUIC', 'TLS', 'CDN', 'WiFi6E']
+++

# BBR 拥塞控制、QUIC、TLS 1.3 与 CDN

传统 TCP 生态在演进中出现了一批新机制：拥塞控制从丢包驱动转向建模驱动（BBR）、传输层被 QUIC 重造、TLS 1.3 重写握手、CDN 成为内容分发的标准架构。本文整理它们的核心原理与设计动机，以及 WiFi 6E 的 AFC 频谱协调机制。

## WiFi 6E 的 AFC（Automatic Frequency Coordination）

6GHz 频段里已有 incumbent 业务（固定卫星、微波回传等）。**标准功率**的 WiFi 6E 设备发射前必须向 AFC 系统查询：AFC 根据设备位置与 incumbent 数据库，**动态分配可用信道与最大发射功率**，从频率层面避免干扰。AFC 解决的是频谱的动态分配问题，干扰避免是其结果。

## BBR：从丢包驱动到建模驱动

传统 CUBIC/Reno 靠**丢包**当拥塞信号，会不断加窗直到把瓶颈缓冲区填满，产生 bufferbloat（队列延迟大）。BBR（Bottleneck Bandwidth and RTT，Google 2016）换个思路：

- 主动估计两个量：**瓶颈带宽 BtlBw** 与 **最小 RTT（RTprop）**；
- 以 `pacing rate ≈ BtlBw` 匀速发包，把排队控制在最小，**而不是优先填满缓冲区**；
- 高丢包线路上表现优于 CUBIC，延迟也更稳定。

BBR 在 Google 内部（YouTube/搜索等）大规模使用。与之相对，"填满缓冲区以提高吞吐"恰是传统基于丢包算法的问题根源。

TCP 可靠传输的根基仍是**序列号与确认号**（配合超时重传/快速重传）；三次握手建立连接、滑动窗口做流量控制、校验和只检错。参见 [TCP三次握手与可靠性](../05_通信协议/0001.TCP三次握手与可靠性20260228-写的太烂，重写.md)。

## QUIC 与回退现实

QUIC 基于 **UDP 443**，内建 TLS 1.3，优势是 0-RTT 建连、连接迁移、消除传输层队头阻塞。

部署中最大的现实问题：**企业防火墙/运营商设备可能直接阻断 UDP 443**。客户端探测到 UDP 不通后回退到 TCP + TLS（TCP fallback）——这是 QUIC 落地最常见的降级场景。QUIC 强制 TLS 1.3，客户端不支持 TLS 1.3 时根本不会尝试 QUIC，不算回退。

## TLS 1.3 握手的加密改进

TLS 1.3 相比 1.2 的重要改进：握手从 2-RTT 缩到 1-RTT，且**服务器证书在握手期间就被加密**（ServerHello 之后随即切换到加密通道发送 Certificate）。

握手消息里仍然明文的部分（ClientHello/ServerHello 本身）包括：

- 客户端随机数；
- 服务器公钥/密钥交换参数（公钥本来就是公开的）；
- **SNI（Server Name Indication）**：告诉服务器要访问的域名——**始终明文**，这是 TLS 1.3 未解决的隐私点，需要 ECH（Encrypted Client Hello）扩展才能加密。

TLS 加密原理整体参见 [TLS与HTTPS加密原理](../05_通信协议/0009.TLS与HTTPS加密原理20260423.md)。

## CDN 工作原理

- **调度**：DNS CNAME 解析把用户导向最近的边缘节点，也常用 Anycast 就近接入；
- **缓存**：边缘节点按 **TTL + 回源策略**缓存内容，有失效与刷新机制（并非永久有效）；
- **动态内容加速**：动态内容无法直接缓存，需要路由优化、协议优化、边缘计算等特殊配置。

## 小结

| 技术 | 解决的问题 |
| --- | --- |
| AFC | 6GHz 频谱共享时的动态频率分配 |
| BBR | 丢包驱动拥塞控制的 bufferbloat 与高丢包退化 |
| QUIC | TCP+TLS 的队头阻塞、建连延迟、部署升级难 |
| TLS 1.3 | 握手延迟与 1.2 的加密盲区（证书明文） |
| CDN | 内容分发的延迟与源站压力 |
