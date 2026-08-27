+++
title = '线程调度机制对比CFS与Windows优先级'
date = 2026-08-27T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['Linux', 'Windows', '调度', 'CFS', '线程优先级']
+++

# 线程调度机制对比CFS与Windows优先级

## 题目

围绕调度的系列问题：nice 值和 Windows 的优先级是什么关系？CFS 的"完全公平"公平在哪？Windows 的优先级为什么要动态提升？两边的实时任务机制一样吗？

## 考察点

两套调度世界观（加权公平 vs 严格优先级+启发式）、优先级挂在进程还是线程上、交互性优化的不同手段、实时类任务的门槛差异

## 回答要点

### 1. 先对齐对象模型：两边都只调度线程

进程/线程在内核里是什么对象，两边走了完全不同的路（Linux task_struct+CLONE 标志 vs Windows EPROCESS/ETHREAD 两种内核对象，详见《教材Unix视角与各系统实现差异》第 2 节）。但对**调度器**而言结论一致：调度实体都是线程/任务，"进程"只是资源容器，永不被调度。因此本篇全部在"线程"粒度上对比。

### 2. Linux：加权公平的世界观

**CFS（完全公平调度器，2.6.23~6.5）**的核心量是 `vruntime`（虚拟运行时间）：

```
vruntime += 实际运行时间 × (NICE_0_LOAD / 该任务权重)
```

权重由 nice 值查表决定（-20~19），相邻一级权重比约 1.25——**nice 不是优先级，是 CPU 份额的旋钮**：nice 每 +1，能分到的 CPU 大约变成原来的 80%。调度器每次挑红黑树里 vruntime 最小的任务运行，权重大的人 vruntime 走得慢，于是能占更多时间。没有任何"时间片"概念，只有"谁最亏欠"。

6.6 起 CFS 被替换为 **EEVDF**：在公平的基础上给每个任务加"虚拟截止时间"，响应延迟敏感的任务（交互式）会被更早调度——思想上仍是一脉相承的虚拟时间公平。

实时类**整体压在**普通类之上：

| 策略 | 语义 |
|---|---|
| SCHED_FIFO | 无时间片，同优先级先到先占，只能被更高优先级抢占 |
| SCHED_RR | FIFO + 轮转（默认 100ms 片） |
| SCHED_DEADLINE | EDF + 带宽隔离，按周期/时限保证 |

关键点：Linux 实时任务**不需要任何特权**就能用 SCHED_FIFO，写错了可以把整个系统饿死到 ssh 都进不去（这也是排查"Linux 机器假死但负载不高"的一个方向）。

### 3. Windows：严格优先级 + 启发式修正

Windows 是教科书式的**多级反馈队列**：优先级 0~31 共 32 级，**数值越大越优先**，调度器永远从最高非空队列取就绪线程。

两个 Windows 特有的世界观差异：

**① 优先级挂在线程上，进程只是基线。** Linux 的 nice 挂在任务上没有进程/线程之分（顺带一提 nice 是"份额"不是"优先级"）；Windows 的进程选 Priority Class，线程在类内做相对微调：

| 进程 Priority Class | 基线 | 线程相对微调（SetThreadPriority） |
|---|---|---|
| IDLE | 4 | THREAD_PRIORITY_IDLE 直接降到 1 |
| BELOW_NORMAL | 6 | LOWEST -2 ~ HIGHEST +2 |
| NORMAL | 8 | 同上，TIME_CRITICAL 直接到 15 |
| ABOVE_NORMAL | 10 | 同上 |
| HIGH | 13 | 同上 |
| REALTIME | 24 | 可到 31 |

**② 1~15 级是"可变级"，会被动态调整。** 这是 Windows 调度器最有辨识度的部分：

- **优先级提升（boost）**：线程被唤醒且其所属进程拥有前台窗口时，优先级临时 +2~+5（比如 GUI 线程等到了输入），用完时间片后逐级降回基线——用"短暂插队"换交互响应
- **前台奖励**：前台进程的线程时间片放大约 3 倍（专业版），切窗口就能感觉到的原因之一
- **反饿死**：可变级线程就绪超过约 4 秒仍没跑上，被直接提到 15 跑一个片再降回去——严格优先级体系的补丁

16~31 是**实时级**：不参与 boost、不被降级，能抢占内核中大量代码路径。与之对应，REALTIME 优先级类需要 `SeIncreaseBasePriorityPrivilege` 特权才能设置——**和 Linux 正好相反：Windows 的实时调度有特权门槛，普通进程碰不到**。

### 4. 逐项对照

| 维度 | Linux（CFS/EEVDF） | Windows |
|---|---|---|
| 优先级层级 | 实时 0~99 + 普通任务（无层级，按 vruntime 排） | 0~31，数值大者优先 |
| 挂载对象 | task（无进程/线程之分） | 线程（进程只给基线） |
| "优先级"语义 | nice = CPU 份额旋钮（±1 ≈ ×0.8 份额） | 严格抢占序，先到先得 |
| 时间片 | 无显式时间片（vruntime 驱动） | 有（可变，前台放大） |
| 交互优化 | EEVDF 的延迟敏感加权；boost 机制没有直接对应 | priority boost + 前台奖励 |
| 饿死防护 | 公平性本身防饿死（实时任务除外） | 4 秒饥饿提升到 15 |
| 实时类 | SCHED_FIFO/RR/DEADLINE，无特权门槛 | 16~31 级，需特权 |
| 调整接口 | `nice`/`setpriority`/`sched_setscheduler` | `SetPriorityClass`/`SetThreadPriority` |

一句话总结世界观差异：**Linux 相信"公平份额"，Windows 相信"优先级 + 一层修正"**。所以"进程优先级越高分到的 CPU 越多"这种表述对 Linux 是不准确的（份额表述才对），而对 Windows 是准确的（抢占序表述）；两边的术语翻译必须在脑子里换算。

### 5. 亲和性：两边都有，但用法地位不同

`sched_setaffinity` 与 `SetThreadAffinityMask`/`SetProcessAffinityMask` 功能对应。差异在地位：Windows 上进程级亲和掩码是线程亲和的上限、和 Job Object 联动；Linux 上亲和性常和 cpuset/cgroup 组合做容器隔离。对实时/嵌入式背景的读者：两边都没有"绑核即独占"，要独占还得隔离中断和内存（Windows 有 Interrupt Affinity，Linux 有 isolcpus/irqbalance 配置）。

### 6. Qt 视角

`QThread::setPriority()` 文档明说"尽力而为"：Windows 上映射到线程优先级，Unix 上实现为 nice/sched 参数，两边的枚举值（QThread::IdlePriority~TimeCriticalPriority）到具体机制的映射是近似的、平台相关的。跨平台代码里要精确控制调度，只能下沉到各平台原生 API；Qt 的封装适合表达"这个后台线程不重要"这种弱意图。

## 扩展问题

可以进一步追问：

- vruntime 溢出怎么办？新任务/长睡眠任务的 vruntime 怎么设置才不会饿死别人或被饿死？（min_vruntime 机制）
- EEVDF 的 lag 和 virtual deadline 分别解决 CFS 的什么缺陷？
- Windows 的 quantum 单位是时钟中断次数，服务器版和客户端版的默认值为什么不同？
- 两个系统在多核负载均衡上分别怎么做（Linux 的 sched_domain vs Windows 的每处理器就绪队列 + 理想处理器）？
