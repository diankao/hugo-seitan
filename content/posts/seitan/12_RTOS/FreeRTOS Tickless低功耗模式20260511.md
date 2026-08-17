+++
title = 'FreeRTOS Tickless低功耗模式'
date = 2026-05-11T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['FreeRTOS', 'Tickless', '低功耗', 'RTOS']
+++

# FreeRTOS Tickless低功耗模式

## 题目

FreeRTOS的tickless模式是什么？它如何实现低功耗？

## 考察点

Tickless Idle 模式原理、SysTick 与低功耗的关系、FreeRTOS 时钟补偿机制。

## 回答要点

### 1. 问题：正常模式下 SysTick 的功耗浪费

FreeRTOS 默认使用 SysTick 定时器产生周期性中断（通常 1ms 一次），驱动任务调度：

```
正常模式（configUSE_TICKLESS_IDLE = 0）：

SysTick 中断每 1ms 触发一次：
  │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │
  ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼

问题：所有任务都在阻塞（等待事件），空闲任务在运行
      CPU 每 1ms 被 SysTick 唤醒一次
      但实际上没有任何事情要做！
      → 白白浪费功耗
```

**典型场景**：传感器节点每 10 秒采集一次数据，其余时间全部空闲。正常模式下每秒 1000 次 SysTick 中断全是浪费。

### 2. Tickless 模式的核心思想

**当所有任务都阻塞时，停止 SysTick，让 CPU 进入低功耗模式，直到下一个任务需要被唤醒。**

```
Tickless 模式（configUSE_TICKLESS_IDLE = 1）：

任务 A 阻塞到 t=500ms
任务 B 阻塞到 t=2000ms
空闲任务运行中...

空闲钩子检测到：最近一个任务唤醒时间是 500ms 后
  → 停止 SysTick
  → 配置 RTC/低功耗定时器在 500ms 后唤醒
  → CPU 进入 Stop/Sleep 模式

          500ms 后
  ┌──────────────────────────────┐
  │ CPU 在睡觉，没有中断打扰      │
  │ 功耗从 mA 级降到 μA 级       │
  └──────────────────────────────┘
                                ▼
                          RTC 唤醒 CPU
                          恢复 SysTick
                          补偿系统时钟
                          任务 A 就绪，开始执行
```

### 3. 实现机制

#### 3.1 配置

```c
#define configUSE_TICKLESS_IDLE          1    // 启用 Tickless
#define configEXPECTED_IDLE_TIME_BEFORE_SLEEP  2  // 最少空闲 2 个 tick 才进入
```

#### 3.2 自动 Tickless 流程

```c
// FreeRTOS 内部的空闲任务（简化）
void prvIdleTask(void *pvParameters) {
    while (1) {
        // 1. 计算预计空闲时间
        TickType_t xExpectedIdleTime = prvGetExpectedIdleTime();

        if (xExpectedIdleTime >= configEXPECTED_IDLE_TIME_BEFORE_SLEEP) {
            // 2. 进入 Tickless（由 port 层实现）
            vPortSuppressTicksAndSleep(xExpectedIdleTime);
            // 里面做了：
            //   a. 关闭 SysTick
            //   b. 计算需要睡眠的 tick 数
            //   c. 配置唤醒定时器（LPTIM/RTC）
            //   d. 进入 WFI（CPU 睡眠）
            //   e. 被唤醒后恢复 SysTick
            //   f. 补偿系统时钟（vTaskStepTick）
        }
    }
}
```

#### 3.3 时钟补偿

```c
// 唤醒后必须补偿系统时间
// 否则任务的 vTaskDelay 会不准

void vPortSuppressTicksAndSleep(TickType_t xExpectedIdleTime) {
    // ... 进入低功耗 ...

    // 被唤醒（可能是预期唤醒，也可能是外部中断提前唤醒）
    uint32_t ulCompletedTicks = 计算实际睡眠了多少 tick;

    // 关键：补偿系统时钟
    vTaskStepTick(ulCompletedTicks);
    // 相当于告诉 FreeRTOS：
    // "虽然 SysTick 没有中断，但实际上已经过去了 ulCompletedTicks 个 tick"
}
```

### 4. 两种唤醒情况

```
情况一：按时唤醒（下一个任务到期）
  预期睡眠 500 tick → 实际睡眠 500 tick
  → vTaskStepTick(500)
  → 任务就绪，正常调度

情况二：被外部中断提前唤醒
  预期睡眠 500 tick → 实际只睡了 200 tick（按键中断）
  → vTaskStepTick(200)
  → 处理中断
  → 重新计算空闲时间，可能再次进入 Tickless
```

### 5. 自定义 Tickless（应用层实现）

FreeRTOS 提供了钩子函数让用户自定义低功耗策略：

```c
// 方法一：定义宏（在 FreeRTOSConfig.h 中）
#define configPRE_SLEEP_PROCESSING(x)  pre_sleep_hook(x)
#define configPOST_SLEEP_PROCESSING(x) post_sleep_hook(x)

// 方法二：覆盖 vPortSuppressTicksAndSleep
void vPortSuppressTicksAndSleep(TickType_t xExpectedIdleTime) {
    // 1. 检查是否真的可以睡眠
    if (xExpectedIdleTime < 2) return;

    // 2. 关闭 SysTick
    SysTick->CTRL &= ~SysTick_CTRL_ENABLE_Msk;

    // 3. 配置低功耗定时器
    LPTIM_SetCompare(xExpectedIdleTime * (LPTIM_CLOCK_HZ / configTICK_RATE_HZ));

    // 4. 进入 Stop 模式
    HAL_PWR_EnterSTOPMode(PWR_LOWPOWERREGULATOR_ON, PWR_STOPENTRY_WFI);

    // 5. 唤醒后恢复时钟
    SystemClock_Config();

    // 6. 计算实际睡眠时间
    uint32_t slept_ticks = LPTIM_GetCounter() / (LPTIM_CLOCK_HZ / configTICK_RATE_HZ);

    // 7. 补偿系统时钟
    if (slept_ticks > 0) {
        vTaskStepTick(slept_ticks);
    }

    // 8. 重启 SysTick
    SysTick->CTRL |= SysTick_CTRL_ENABLE_Msk;
}
```

### 6. 功耗对比

| 模式 | 空闲时功耗 | 唤醒延迟 | 时钟保持 |
|------|-----------|---------|---------|
| 正常模式 | ~10 mA（1000 Hz SysTick） | 0 | SysTick 持续运行 |
| Tickless + Sleep | ~1 mA | ~10 μs | SysTick 停止，RTC 补偿 |
| Tickless + Stop | ~10 μA | ~10-100 μs | 需要恢复时钟 |
| Tickless + Standby | ~0.1 μA | ~1-10 ms | 系统时钟丢失（需 RTC） |

### 7. 注意事项

| 问题 | 说明 |
|------|------|
| 外设状态 | 进入 Stop 前需保存外设状态，唤醒后恢复 |
| 时钟恢复 | Stop 模式唤醒后需重新配置 PLL 和系统时钟 |
| 临界区保护 | 进入睡眠前需关中断，防止竞态 |
| 调试影响 | 调试器连接时 Tickless 可能导致断点异常 |
| 看门狗 | 如果看门狗靠 SysTick 喂狗，Tickless 会停止喂狗 |

### 8. 面试速记

- **Tickless** = 空闲时停止 SysTick，CPU 进入低功耗，用低功耗定时器唤醒
- **核心操作**：停 SysTick → 配唤醒源 → WFI → 唤醒 → 恢复时钟 → `vTaskStepTick()` 补偿
- **两种唤醒**：按时唤醒（任务到期）和提前唤醒（外部中断）
- **功耗收益**：从 mA 级降到 μA 级，适合电池供电的 IoT 设备
