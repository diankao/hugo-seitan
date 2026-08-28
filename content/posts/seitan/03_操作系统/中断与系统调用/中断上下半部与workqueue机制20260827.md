+++
title = '中断上下半部与workqueue机制'
date = 2026-08-27T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['Linux内核', '中断', '软中断', 'workqueue', '驱动开发']
+++

# 中断上下半部与 workqueue 机制

## 题目

哪些中断有上半部/下半部机制？workqueue 和 tasklet 有什么区别？

## 考察点

Linux 内核中断处理框架：上下半部的设计动机、软中断上下文与进程上下文的区别、下半部机制族的选型

## 回答要点

### 1. 上半部/下半部是软件框架，不是硬件机制

先明确概念边界：硬件中断本身只有"CPU 跳进 handler 执行"这一件事。**"拆成上下两半"是 Linux 内核为缩短关中断时间做的软件设计**：

- **上半部（hardirq）**：真正的硬件中断 handler，由 `request_irq()` 注册。此时关抢占、（通常）关本地中断，必须快进快出——只做应答硬件、收发关键数据、调度下半部
- **下半部（bottom half）**：中断返回后由内核择机执行的处理，处理耗时的主体工作。下半部执行时中断已开放，系统不再失响应

设计动机：如果全部工作都在 handler 里做，中断关闭时间随工作量线性增长，其他中断被拖延、系统抖动。拆开后上半部缩到最短，重活延后。

### 2. 哪些环境有这套机制

| 环境 | 上下半部机制 |
|---|---|
| Linux 硬中断（hardirq） | ✅ 完整框架：上半部 = `request_irq` 的 handler，下半部 = softirq / tasklet / workqueue |
| Linux 软中断、定时器等软件事件 | ✅ 直接走下半部框架（softirq 本身既是下半部之一，也是其他软件事件的延后处理通道） |
| RTOS（FreeRTOS） | 思想对应：ISR（上半部）+ 任务处理（下半部），用 `FromISR` API 通知任务，但没有 softirq/tasklet/workqueue 这套命名 |
| 裸机 MCU | 思想对应：ISR + 主循环处理（"前后台"系统就是最原始的上下半部） |
| Windows | 思想对应：ISR（上半部）+ DPC（下半部） |

一句话：**凡是"硬件中断 handler 里不能久留，需要把工作推迟"的环境，都演化出了这个模式**；Linux 只是把下半部做成了一个有三种选择的机制族。

### 3. 下半部机制族全景

三者是层次关系，不是并列的三选一：

- **softirq 是底座**：静态定义、编译期确定，只留给网络（NAPI 收包）、块设备、定时器、任务调度（`TASKLET_SOFTIRQ`）等核心子系统使用。可在多核上同时执行同一类型，性能最好，但驱动不能自己注册
- **tasklet 是 softirq 之上的驱动层包装**：动态创建、接口简单，核心卖点是**同一个 tasklet 保证不在多核上同时执行**（串行保证）。但这个设计被认为是个历史错误，**内核已将其标记废弃**（5.9 起逐步清理）
- **workqueue 是完全另一条路**：把工作交给内核线程（kworker）执行，因此处于**进程上下文，可以睡眠**

```c
// 概念关系
softirq（底座，核心子系统专用）
  └── tasklet（驱动友好的串行包装，正在退役）
workqueue（线程化、可睡眠，独立路径）
threaded IRQ（request_threaded_irq：把中断处理整体放进内核线程，现代驱动首选）
```

### 4. workqueue 和 tasklet 的核心区别

一句话：**tasklet 在软中断上下文运行（原子上下文），workqueue 在内核线程里运行（进程上下文，可以睡眠）**。

| 维度 | tasklet | workqueue |
|---|---|---|
| 运行上下文 | 软中断上下文（atomic） | 内核线程（kworker） |
| 能否睡眠 | ❌ 绝对不能（不能 malloc、不能拿互斥锁、不能 `msleep`） | ✅ 可以睡眠、可以阻塞、可以用信号量 |
| 执行时机 | 尽快：中断返回后同一次软中断处理中调度，延迟微秒级 | 排队给 kworker 线程，由调度器决定，延迟略高 |
| 并发性 | 同一 tasklet 不会在多核上同时执行（串行保证），不同 tasklet 可以并行 | 同一 work 默认可被多核并发执行（可用有序 workqueue 限制） |
| 编程接口 | 结构体 + 回调，`tasklet_schedule()` | `INIT_WORK` + `queue_work()`，或 `schedule_work()` 进系统队列 |
| 现状 | 已废弃，仅存于老代码 | 现役主流 |

### 5. 代码对比

```c
// tasklet：原子上下文，不能睡眠
void my_tasklet_func(unsigned long data) {
    // 处理数据：不能 malloc、不能 mutex、不能 msleep
}
DECLARE_TASKLET(my_tasklet, my_tasklet_func, 0);

irqreturn_t my_isr(int irq, void *dev) {
    /* 上半部：应答硬件、收关键数据 */
    tasklet_schedule(&my_tasklet);   // 调度下半部
    return IRQ_HANDLED;
}
```

```c
// workqueue：进程上下文，可以睡眠
void my_work_func(struct work_struct *work) {
    struct my_dev *dev = container_of(work, struct my_dev, work);
    mutex_lock(&dev->lock);           // 可以拿互斥锁
    msleep(10);                       // 可以睡眠等待
    mutex_unlock(&dev->lock);
}
/* 初始化时：INIT_WORK(&dev->work, my_work_func); */

irqreturn_t my_isr(int irq, void *dev_id) {
    struct my_dev *dev = dev_id;
    queue_work(dev->wq, &dev->work);  // 交给 kworker
    return IRQ_HANDLED;
}
```

```c
// threaded IRQ：现代驱动首选，handler 与"下半部"一体线程化
irqreturn_t my_thread_fn(int irq, void *dev_id) {
    struct my_dev *dev = dev_id;
    // 运行在专用内核线程，可以睡眠
    handle_and_process(dev);
    return IRQ_HANDLED;
}

// request_irq(my_irq, my_isr_top, ..., ...)  可省略：
request_threaded_irq(my_irq, NULL, my_thread_fn,
                     IRQF_ONESHOT, "my_dev", dev);
```

`IRQF_ONESHOT` 保证线程执行完之前该中断线保持屏蔽，避免线程还没处理完、中断又涌进来。

### 6. 怎么选（现在的答案）

1. 下半部**需要睡眠、阻塞 IO、拿互斥锁** → workqueue 或 threaded IRQ
2. 只是快速处理内存数据、绝不睡眠、极致性能 → softirq（核心子系统专属）
3. tasklet → 新代码不再选用，只在做老代码维护时理解它

实际分布：网络收包走 softirq（NAPI），普通外设驱动如今多用 threaded IRQ 或 workqueue。

### 7. 和 MCU/RTOS 经验的对照

写过 FreeRTOS 的人可以这样映射理解：

| Linux | FreeRTOS 对应 |
|---|---|
| 上半部 hardirq | ISR（同样快进快出） |
| `FromISR` API 通知任务 | `queue_work` 把工作交给 kworker |
| kworker 内核线程 | 收到通知后做实际处理的普通任务 |
| 下半部不能假设原子性（workqueue 可睡眠） | 任务上下文可以拿锁、可以延时 |

区别在于：FreeRTOS 里"下半部"是你自己建的任务；Linux 里内核提供了现成的 kworker 线程池，省去每设备一个线程的成本。

## 扩展问题

可以进一步追问：
- softirq 的执行时机具体在哪些点（`do_softirq` 从哪些路径被调用）？
- NAPI 为什么在中断/轮询两种模式间切换？
- `WQ_UNBOUND`、有序 workqueue（ordered workqueue）分别适合什么负载？
