+++
title = 'work_struct与delayed_work延迟工作队列'
date = 2026-05-20T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['面试题', 'Linux', 'workqueue', 'work_struct', 'delayed_work', '内核定时器', '中断下半部']
+++

# work_struct 与 delayed_work 延迟工作队列

## 题目

Linux 内核中 `work_struct` 和 `delayed_work` 是什么？它们属于什么子系统？如何使用？两者有什么区别和联系？

## 考察点

Linux 内核工作队列（Workqueue）子系统、`work_struct` 与 `delayed_work` 的区别、内核定时器与延迟执行机制、驱动开发实践。

## 回答要点

### 1. 所属领域：Linux 内核工作队列子系统

`work_struct` 和 `delayed_work` 属于 Linux 内核的**工作队列（Workqueue）** 子系统，是中断下半部（Bottom Half）机制中最灵活的一种。

```
中断发生
  │
  ▼
上半部（硬中断，ISR）
  │  只做最紧急的事：读寄存器、ACK 硬件
  │
  ▼
下半部（延迟处理）
  │
  ├── softirq   （最高性能，不能睡眠，驱动一般不用）
  ├── tasklet   （中等性能，不能睡眠，驱动常用）
  └── workqueue （最灵活，可以睡眠，驱动常用）  ◀── 本文重点
        │
        ├── work_struct    （立即调度，尽快执行）
        └── delayed_work   （延迟调度，指定时间后执行）
```

**workqueue 的本质**：把"工作"提交给一个**内核线程（kworker）** 去执行。因为运行在进程上下文中，所以可以睡眠、可以使用 mutex、可以访问用户空间。

### 2. work_struct：立即执行的工作

`work_struct` 是最基础的工作单元，表示一个"需要尽快执行的延迟任务"。

#### 2.1 核心数据结构

```c
struct work_struct {
    atomic_long_t data;          // 标志位 + 指向 worker 的指针
    struct list_head entry;      // 挂在 workqueue 的链表上
    work_func_t func;            // 工作处理函数
};
```

其中 `work_func_t` 的类型定义：

```c
typedef void (*work_func_t)(struct work_struct *work);
```

#### 2.2 使用步骤

```c
#include <linux/workqueue.h>
#include <linux/module.h>

struct my_device {
    struct work_struct work;
    void __iomem *regs;
    spinlock_t lock;
    u32 pending_data;
};

static void my_work_handler(struct work_struct *work)
{
    struct my_device *dev = container_of(work, struct my_device, work);
    unsigned long flags;
    u32 data;

    spin_lock_irqsave(&dev->lock, flags);
    data = dev->pending_data;
    spin_unlock_irqrestore(&dev->lock, flags);

    // 进程上下文，可以睡眠
    // 可以使用 mutex、kmalloc(GFP_KERNEL)、msleep 等
    process_data(data);
}

static irqreturn_t my_isr(int irq, void *dev_id)
{
    struct my_device *dev = dev_id;

    // 上半部：快速读取硬件数据
    dev->pending_data = readl(dev->regs + DATA_REG);
    writel(0xFF, dev->regs + IRQ_CLEAR);

    // 提交 work 到系统默认 workqueue
    schedule_work(&dev->work);

    return IRQ_HANDLED;
}

static int my_probe(struct platform_device *pdev)
{
    struct my_device *dev;

    dev = devm_kzalloc(&pdev->dev, sizeof(*dev), GFP_KERNEL);
    if (!dev)
        return -ENOMEM;

    // 初始化 work_struct，绑定处理函数
    INIT_WORK(&dev->work, my_work_handler);

    spin_lock_init(&dev->lock);

    // ... 注册中断等
    return 0;
}

static void my_remove(struct platform_device *pdev)
{
    struct my_device *dev = platform_get_drvdata(pdev);

    // 取消未执行的 work，等待正在执行的 work 完成
    cancel_work_sync(&dev->work);
}
```

#### 2.3 调度方式

| API | 说明 |
|-----|------|
| `schedule_work(&work)` | 提交到系统默认 workqueue，尽快执行 |
| `queue_work(wq, &work)` | 提交到自定义 workqueue |
| `cancel_work_sync(&work)` | 取消 work，如果正在执行则等待完成 |
| `work_pending(&work)` | 检查 work 是否在队列中（未执行） |

### 3. delayed_work：延迟执行的工作

`delayed_work` 是在 `work_struct` 基础上增加了一个**内核定时器**，实现"延迟 N 毫秒后再提交到 workqueue"。

#### 3.1 核心数据结构

```c
struct delayed_work {
    struct work_struct work;       // 基础的工作结构
    struct timer_list timer;       // 内核定时器
    struct workqueue_struct *wq;   // 目标 workqueue
    int cpu;                       // 目标 CPU
};
```

`delayed_work` 本质上是 **work_struct + timer_list** 的组合体。

#### 3.2 工作原理

```
schedule_delayed_work(&dw, delay)
        │
        ▼
  启动内核定时器，设置 delay jiffies 后到期
        │
        │  （delay 时间内，什么都不会发生）
        │
        ▼
  定时器到期回调 → 将 work_struct 提交到 workqueue
        │
        ▼
  kworker 线程调度执行 work 处理函数
```

**关键区别**：`schedule_delayed_work` 并不是让 work "延迟执行"，而是"延迟**提交**"。定时器到期后才把 work 放入 workqueue 队列，之后还需要等 kworker 线程被调度到才能执行。

#### 3.3 使用步骤

```c
struct my_device {
    struct delayed_work poll_work;
    struct delayed_work timeout_work;
    void __iomem *regs;
};

#define POLL_INTERVAL_MS    100
#define TIMEOUT_MS          5000

static void poll_handler(struct work_struct *work)
{
    struct my_device *dev = container_of(work, struct my_device, poll_work.work);
    u32 status;

    status = readl(dev->regs + STATUS_REG);

    if (status & READY_BIT) {
        // 设备就绪，处理数据
        handle_ready_device(dev);
    } else {
        // 设备未就绪，重新调度轮询
        schedule_delayed_work(&dev->poll_work,
                              msecs_to_jiffies(POLL_INTERVAL_MS));
    }
}

static void timeout_handler(struct work_struct *work)
{
    struct my_device *dev = container_of(work, struct my_device, timeout_work.work);

    dev_err(dev->dev, "操作超时！\n");
    reset_device(dev);
}

static void start_operation(struct my_device *dev)
{
    // 发起操作
    writel(START_CMD, dev->regs + CMD_REG);

    // 启动超时检测：5 秒后如果还没完成就触发超时处理
    schedule_delayed_work(&dev->timeout_work,
                          msecs_to_jiffies(TIMEOUT_MS));
}

static void operation_complete_handler(struct work_struct *work)
{
    struct my_device *dev = ...;

    // 操作正常完成，取消超时检测
    cancel_delayed_work_sync(&dev->timeout_work);

    process_result(dev);
}

static int my_probe(struct platform_device *pdev)
{
    struct my_device *dev;

    dev = devm_kzalloc(&pdev->dev, sizeof(*dev), GFP_KERNEL);
    if (!dev)
        return -ENOMEM;

    // 初始化 delayed_work
    INIT_DELAYED_WORK(&dev->poll_work, poll_handler);
    INIT_DELAYED_WORK(&dev->timeout_work, timeout_handler);

    return 0;
}

static void my_remove(struct platform_device *pdev)
{
    struct my_device *dev = platform_get_drvdata(pdev);

    // 取消所有 delayed_work
    cancel_delayed_work_sync(&dev->poll_work);
    cancel_delayed_work_sync(&dev->timeout_work);
}
```

#### 3.4 调度方式

| API | 说明 |
|-----|------|
| `schedule_delayed_work(&dw, delay)` | 延迟 delay 个 jiffies 后提交到默认 workqueue |
| `queue_delayed_work(wq, &dw, delay)` | 延迟提交到自定义 workqueue |
| `cancel_delayed_work(&dw)` | 仅取消定时器（不等待已提交的 work 完成） |
| `cancel_delayed_work_sync(&dw)` | 取消定时器 + 等待正在执行的 work 完成 |
| `mod_delayed_work(wq, &dw, delay)` | 修改延迟时间（重新启动定时器） |
| `delayed_work_pending(&dw)` | 检查定时器是否在运行或 work 是否在队列中 |

### 4. work_struct vs delayed_work 对比

| 特性 | `work_struct` | `delayed_work` |
|------|--------------|----------------|
| **触发时机** | 立即提交到 workqueue | 延迟指定时间后提交 |
| **内部结构** | `work_struct` | `work_struct` + `timer_list` |
| **内存开销** | 较小（约 32 字节） | 较大（约 80 字节，多了定时器） |
| **初始化宏** | `INIT_WORK()` | `INIT_DELAYED_WORK()` |
| **调度函数** | `schedule_work()` | `schedule_delayed_work()` |
| **取消函数** | `cancel_work_sync()` | `cancel_delayed_work_sync()` |
| **取容器宏** | `container_of(work, ...)` | `container_of(work, ..., work)` 或用 `.work` 成员 |
| **典型场景** | 中断下半部即时处理 | 定时轮询、超时检测、周期性任务 |
| **能否替代定时器** | 不能 | 能（精度为 jiffies 级，约 1~4ms） |

#### container_of 的区别

```c
// work_struct 的 handler
static void my_work_handler(struct work_struct *work)
{
    struct my_device *dev = container_of(work, struct my_device, work);
    //                                                        ^^^^
    //                                              直接用 work 成员名
}

// delayed_work 的 handler
static void my_delayed_handler(struct work_struct *work)
{
    struct my_device *dev = container_of(work, struct my_device, poll_work.work);
    //                                                        ^^^^^^^^^^^^^
    //                                          delayed_work 中嵌套的 .work 成员
}
```

### 5. 自定义 Workqueue

系统默认的 workqueue（`system_wq`）是所有驱动共享的。如果对性能、并发度、执行顺序有特殊要求，应该创建**专用 workqueue**。

```c
struct my_device {
    struct work_struct immediate_work;
    struct delayed_work periodic_work;
    struct workqueue_struct *my_wq;
};

static int my_probe(struct platform_device *pdev)
{
    struct my_device *dev;

    dev = devm_kzalloc(&pdev->dev, sizeof(*dev), GFP_KERNEL);

    // 创建专用 workqueue
    // WQ_UNBOUND:     不绑定特定 CPU，可以在任意 CPU 上执行
    // WQ_HIGHPRI:     高优先级 kworker 线程
    // WQ_CPU_INTENSIVE: 标记为 CPU 密集型，不参与普通 work 的并发控制
    // max_active = 1: 同一时刻最多 1 个 work 在执行（串行化）
    dev->my_wq = alloc_workqueue("my_device_wq",
                                  WQ_UNBOUND | WQ_HIGHPRI,
                                  1);
    if (!dev->my_wq)
        return -ENOMEM;

    INIT_WORK(&dev->immediate_work, immediate_handler);
    INIT_DELAYED_WORK(&dev->periodic_work, periodic_handler);

    return 0;
}

static void submit_work(struct my_device *dev)
{
    // 使用自定义 workqueue 提交
    queue_work(dev->my_wq, &dev->immediate_work);
    queue_delayed_work(dev->my_wq, &dev->periodic_work,
                       msecs_to_jiffies(200));
}

static void my_remove(struct platform_device *pdev)
{
    struct my_device *dev = platform_get_drvdata(pdev);

    cancel_work_sync(&dev->immediate_work);
    cancel_delayed_work_sync(&dev->periodic_work);

    // 销毁专用 workqueue（会等待所有 work 完成）
    destroy_workqueue(dev->my_wq);
}
```

### 6. 典型应用场景

#### 6.1 硬件状态轮询

```c
// 某些传感器没有中断引脚，需要定时轮询
static void sensor_poll(struct work_struct *work)
{
    struct sensor_dev *s = container_of(work, struct sensor_dev,
                                         poll_work.work);
    int val;

    // I2C 读取可能睡眠，必须在进程上下文（workqueue）中
    val = i2c_smbus_read_byte_data(s->client, DATA_REG);
    if (val >= 0) {
        input_report_abs(s->input, ABS_X, val);
        input_sync(s->input);
    }

    // 重新调度，形成周期轮询
    schedule_delayed_work(&s->poll_work, msecs_to_jiffies(50));
}
```

#### 6.2 操作超时检测

```c
static void cmd_timeout_handler(struct work_struct *work)
{
    struct my_dev *dev = container_of(work, struct my_dev,
                                       timeout_work.work);
    dev_err(dev->dev, "命令超时，执行复位\n");
    reset_and_reinit(dev);
}

static void send_command(struct my_dev *dev, u32 cmd)
{
    writel(cmd, dev->regs + CMD_REG);

    // 1 秒超时保护
    schedule_delayed_work(&dev->timeout_work, msecs_to_jiffies(1000));
}

static void cmd_complete_isr(struct my_dev *dev)
{
    // 命令完成，取消超时
    cancel_delayed_work_sync(&dev->timeout_work);
    handle_result(dev);
}
```

#### 6.3 防抖处理

```c
// 按键防抖：中断触发后延迟 20ms 再读取状态
static void debounce_handler(struct work_struct *work)
{
    struct my_dev *dev = container_of(work, struct my_dev,
                                       debounce_work.work);
    int val = gpio_get_value(dev->gpio);

    if (val == 0) {
        dev_info(dev->dev, "按键按下\n");
        input_report_key(dev->input, KEY_POWER, 1);
    } else {
        input_report_key(dev->input, KEY_POWER, 0);
    }
    input_sync(dev->input);
}

static irqreturn_t gpio_isr(int irq, void *dev_id)
{
    struct my_dev *dev = dev_id;
    // 不立即读取，延迟 20ms 等抖动稳定
    schedule_delayed_work(&dev->debounce_work, msecs_to_jiffies(20));
    return IRQ_HANDLED;
}
```

#### 6.4 周期性任务

```c
// 用 delayed_work 实现简单周期任务（每 500ms 执行一次）
static void periodic_handler(struct work_struct *work)
{
    struct my_dev *dev = container_of(work, struct my_dev,
                                       periodic_work.work);

    update_statistics(dev);
    check_health(dev);

    // 重新调度自己
    schedule_delayed_work(&dev->periodic_work,
                          msecs_to_jiffies(500));
}
```

### 7. 常见陷阱与注意事项

#### 7.1 重复调度

```c
// 错误：delayed_work 已经在定时器中等待，再次 schedule 会重置定时器
schedule_delayed_work(&dev->work, msecs_to_jiffies(100));
// ... 50ms 后 ...
schedule_delayed_work(&dev->work, msecs_to_jiffies(100));
// 结果：从第二次调用开始重新计时 100ms，第一次的 100ms 被丢弃

// 如果需要"只在未调度时才调度"，先检查
if (!delayed_work_pending(&dev->work))
    schedule_delayed_work(&dev->work, msecs_to_jiffies(100));
```

#### 7.2 cancel 与 race condition

```c
// cancel_delayed_work_sync 必须在能安全睡眠的上下文中调用
// 不能在中断上下文中调用 _sync 版本！

static irqreturn_t my_isr(int irq, void *dev_id)
{
    // 错误！ISR 中不能调用 _sync 函数（会睡眠）
    // cancel_delayed_work_sync(&dev->work);

    // 正确：ISR 中使用非阻塞版本
    cancel_delayed_work(&dev->work);

    return IRQ_HANDLED;
}

// 在 remove / close 等进程上下文中用 _sync 版本
static void my_remove(struct platform_device *pdev)
{
    cancel_delayed_work_sync(&dev->work);   // 安全
}
```

#### 7.3 work 处理函数中的重入

```c
static void my_handler(struct work_struct *work)
{
    struct my_dev *dev = container_of(work, struct my_dev, work);

    // 如果处理过程中被调度了新的 work，处理函数可能被并发执行
    // 需要加锁保护共享数据
    mutex_lock(&dev->mtx);
    do_something(dev);
    mutex_unlock(&dev->mtx);

    // 如果需要禁止重入，可以在 handler 末尾重新调度
    // schedule_work(&dev->work);  // 不要这样做
}
```

### 8. delayed_work 与其他延迟机制对比

| 机制 | 执行上下文 | 能否睡眠 | 精度 | 适用场景 |
|------|-----------|---------|------|---------|
| `delayed_work` | 进程上下文 | ✅ 可以 | jiffies 级（1~4ms） | 轮询、超时、防抖、周期任务 |
| `timer_list` | 软中断上下文 | ❌ 不能 | jiffies 级 | 精确定时、硬件看门狗 |
| `hrtimer` | 硬中断上下文 | ❌ 不能 | 纳秒级 | 高精度定时、PWM |
| `msleep()` | 当前进程 | ✅ 可以 | jiffies 级 | 简单延迟（阻塞当前线程） |
| `usleep_range()` | 当前进程 | ✅ 可以 | 微秒级 | 精确短延迟 |
| `schedule_timeout()` | 当前进程 | ✅ 可以 | jiffies 级 | 配合等待队列使用 |

**选择原则**：

- 需要睡眠 + 延迟执行 → `delayed_work`
- 不需要睡眠 + 高精度 → `hrtimer`
- 不需要睡眠 + 普通精度 → `timer_list`
- 简单阻塞延迟当前线程 → `msleep()` / `usleep_range()`

### 9. 面试回答模板

> "`work_struct` 和 `delayed_work` 都属于 Linux 内核的**工作队列（Workqueue）** 子系统，是中断下半部机制中最灵活的一种。它们的工作在**进程上下文**（kworker 内核线程）中执行，因此可以睡眠、使用 mutex、执行 I/O 操作。`work_struct` 是基础的立即执行工作，调用 `schedule_work()` 后会尽快被 kworker 执行；`delayed_work` 在 `work_struct` 基础上封装了一个内核定时器，调用 `schedule_delayed_work()` 后会等待指定的延迟时间再提交到 workqueue，常用于硬件轮询、超时检测、按键防抖、周期性任务等场景。"
