+++
title = 'cgroups资源管控与OOMKiller机制'
date = 2026-09-02T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['Linux', 'cgroups', 'OOM', '内存管理', '容器']
+++

# cgroups 资源管控与 OOM Killer 机制

当多个服务共享一台设备，如何保证谁也不吃光资源？Linux 的答案是 cgroups：把进程组织成树，按组限制 CPU、内存、IO；限制逼近极限时由 OOM Killer 兜底。本文整理 cgroups v2 的控制接口，以及 cgroup 级与系统级两个层面的 OOM 机制。

## cgroups v2 的资源控制

cgroups v2 采用统一层级，把进程组织进一棵控制树，在各节点挂资源限制：

| 资源 | v2 接口 | 说明 |
| --- | --- | --- |
| CPU | `cpu.max`（quota/period） | 进程/组级 CPU 配额 |
| 内存 | `memory.max` / `memory.swap.max` | 内存与**内存+Swap 总量**可分别限制 |
| 内存压力 | `memory.high` | 超过即节流回收，软限制 |
| IO | `io.max` | 按设备的 IOPS/带宽 |
| 设备 | eBPF program attach 到 cgroup | 跨层级的设备访问控制 |

一个常见误解是"cgroups v2 不支持实时线程（RT）调度"——实时线程的调度由内核 RT 调度器（SCHED_FIFO/RR）负责，cgroup 只是资源配额的控制界面；v2 移除的只是旧版 cgroup 级 RT bandwidth 接口，与"不支持 RT 调度"是两回事。

## 两个层面的 OOM

**cgroup 级 OOM**：组内内存超 `memory.max` 时，内核先尽力回收，回收不动就在**该 cgroup 内**触发 OOM，杀组内 badness 最高的进程（不影响组外）。

**系统级 OOM Killer**：全局内存+Swap 耗尽时触发，选杀算法：

```
badness ≈ (rss + swap + 页表) × (1000 + oom_score_adj) / 1000
```

要点：

- 按 **oom_score** 打分选杀，不是简单"谁占得多杀谁"——占用多但 `oom_score_adj = -1000` 的进程完全不会被杀，反之 adj 高的轻进程可能先被杀；
- `oom_score_adj` 范围 -1000~1000：**-1000 永不杀**（如 sshd），+1000 最优先杀；
- 老接口 `/proc/<pid>/oom_adj`（-17 即 OOM_DISABLE）仍兼容存在；
- 内核线程评分低（默认受保护），普通用户进程相对更易中枪。

## 动手实验

v2 统一层级通常已挂载在 `/sys/fs/cgroup`（systemd 时代默认），直接建组验证限制效果：

```bash
cd /sys/fs/cgroup
mkdir demo

# CPU：50%（quota=50000µs / period=100000µs）
echo "50000 100000" > demo/cpu.max

# 内存硬限 100M
echo "100M" > demo/memory.max

# 把一个忙循环进程放进组里
echo $$ > demo/cgroup.procs        # 当前 shell 进组（子进程继承）

# 观察：CPU 占用被压在 ~50%
dd if=/dev/zero of=/dev/null &     # 烧 CPU
top -p $!

# 观察内存：吃满 100M 后触发 cgroup OOM
cat /dev/zero | head -c 500M > /dev/shm/x   # 试着超限
dmesg | tail                        # Memory cgroup out of memory: Killed process ...
cat demo/memory.current             # 组内当前内存
cat demo/memory.events              # oom_kill 计数

# 收尾：进程退出后删组
cd / && rmdir /sys/fs/cgroup/demo
```

用 systemd 一行等价（不动 cgroupfs，生产推荐）：

```bash
systemd-run --scope -p CPUQuota=50% -p MemoryMax=100M stress --vm 1 --vm-bytes 300M
```

排错提示：写 `cgroup.procs` 报 device busy 通常是进程在子组里（递归移出）；`memory.max` 写 `max` 表示不限；OOM 事件也可以 `systemd-cgls`/`systemd-cgtop` 直接看层级与占用。

## 嵌入式实践

- 嵌入式 Linux 无 Swap 时 `memory.max` 就是硬墙，配合 `memory.oom.group` 可以整组同生共死（容器化部署常用）；
- 关键守护进程（看门狗喂狗进程、日志采集）务必设 `oom_score_adj=-1000`，否则内存紧张时最先乱掉的恰恰是救援机制；
- 常与 systemd 的 `MemoryMax=`、容器 runtime 的 memory limit 配合使用。
