+++
title = 'Cortex-M中断优先级与NVIC分组'
date = 2026-09-03T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['Cortex-M', 'NVIC', '中断', '优先级分组', 'STM32']
+++

# Cortex-M 中断优先级与 NVIC 分组

Cortex-M 的中断管理由 NVIC（Nested Vectored Interrupt Controller）承担：优先级寄存器、嵌套与抢占、尾链等技术细节都藏在里面。其中"优先级分组"决定多少位给抢占、多少位给子优先级，是配置中断体系的第一步，也是 RTOS 移植时最容易踩坑的地方。本文以 Cortex-M3/M4（STM32 为主）展开。

## 优先级的基本规则

- 架构上每个中断有 8 位优先级（256 级），但**芯片实际实现的位数因型号而异**——STM32F1/F4 只实现**高 4 位**（16 级），低位读出恒 0；
- **数值越小，优先级越高**（0 最高）。复位后所有优先级默认 0，要在程序里显式排布；
- 优先级影响两件事：能否**抢占**正在执行的低优先级中断（嵌套），以及多个 pending 时**谁先执行**。

## 抢占优先级与子优先级

优先级字段被拆成两段：

```
8位优先级寄存器（M3/M4 实现高4位为例）
┌────┬────┐
│ PRIGROUP 分组值决定分割点（SCB->AIRCR 的 PRIGROUP 位段）
│ 抢占优先级位 │ 子优先级位 │
└────┴────┘
```

- **抢占优先级（preempt priority）**：不同的抢占级之间可以互相打断——高抢占级中断能打断正在执行的低抢占级 ISR，形成嵌套；
- **子优先级（sub priority）**：抢占级相同时，决定多个同时 pending 的中断谁先得到响应；**子优先级不产生嵌套打断**，只是排队顺序。

## 分组配置

分组值写入 SCB->AIRCR 的 PRIGROUP 位段，CMSIS 封装为 `NVIC_SetPriorityGrouping()`，HAL 封装为 `HAL_NVIC_SetPriorityGrouping()`。以高 4 位为例的五种分组：

| 分组 | 抢占位:子位 | 抢占级数 | 子级数 | 典型场景 |
| --- | --- | --- | --- | --- |
| Group 0 | 0:4 | 1 | 16 | 无嵌套，全靠排队 |
| Group 1 | 1:3 | 2 | 8 | |
| Group 2 | 2:2 | 4 | 4 | |
| Group 3 | 3:1 | 8 | 2 | |
| **Group 4** | **4:0** | **16** | **1** | **全部用于抢占——RTOS 标配** |

两个要点：

1. **分组是全局设置**，影响所有中断的位含义；改分组前要先想清楚整个系统的优先级布局；
2. **FreeRTOS 等内核要求 Group 4（全部抢占位）**：内核通过 BASEPRI 屏蔽"优先级数值 ≥ 某阈值"的中断来保护临界区，只有纯抢占分组语义下该机制才正确。STM32 CubeMX 生成的工程默认就是 `NVIC_PRIORITYGROUP_4`。

```c
// CMSIS 原生
NVIC_SetPriorityGrouping(3);            // 3 = SCB->AIRCR PRIGROUP 设置
NVIC_SetPriority(USART1_IRQn, 1 << 4);  // 注意：优先级值要左移到实现的最高位

// HAL（STM32 常用）
HAL_NVIC_SetPriorityGrouping(NVIC_PRIORITYGROUP_4);
HAL_NVIC_SetPriority(USART1_IRQn, 5, 0);  // 抢占5 子0（group4 下子级无效）
HAL_NVIC_EnableIRQ(USART1_IRQn);
```

## 嵌套、尾链与迟到中断

NVIC 硬件做了几层优化，理解它们有助于分析时序：

- **嵌套**：高抢占级请求到达时，硬件自动压栈 xPSR/PC/LR/R12/R3-R0（8 个寄存器）后直接进入高优先级 ISR；
- **尾链（tail-chaining）**：一个 ISR 退出时若还有 pending 中断，跳过出栈/压栈直接进入下一个 ISR，开销从 12 周期降到 6 周期；
- **迟到（late-arriving）**：压栈期间来了更高优先级请求，先执行高的；
- 进入 ISR 的总延迟固定 **12 个周期**（此时总线不慢、无更高优先级屏蔽）——这是 Cortex-M 实时性的卖点。

## BASEPRI 与中断屏蔽层级

| 手段 | 作用域 | 场景 |
| --- | --- | --- |
| PRIMASK（`__disable_irq`） | 关所有可屏蔽中断 | 极短临界区 |
| **BASEPRI**（`__set_BASEPRI(n<<4)`） | 屏蔽优先级数值 ≥ n 的中断 | **FreeRTOS 临界区：只挡配置为 ≥ 内核最低优先级（常为 5<<4）的中断**，高优先级中断不受影响 |
| FAULTMASK | 连 HardFault 一起关 | 极少用 |

这就是 FreeRTOS 要求"**调用内核 API 的中断优先级必须低于（数值大于）`configMAX_SYSCALL_INTERRUPT_PRIORITY`**"的硬件根源——BASEPRI 屏蔽不到的中断里不能进内核临界区。

## 实践清单

- 列一张中断优先级表再写代码：谁可以打断谁、谁绝对不能被打断（如电机 PWM 紧急保护）；
- ISR 里调 FreeRTOS API 的中断，优先级数值必须 ≥ `configMAX_SYSCALL_INTERRUPT_PRIORITY`（常为 5）；
- 不要在中断里动态改分组；优先级运行期可用 `NVIC_SetPriority` 调整；
- 向量表重定位（VTOR）在 bootloader 跳应用时别忘改，否则中断还进 bootloader 的表。

相关：[中断向量表嵌套机制与数据一致性](../01_嵌入式基础/0013.中断向量表嵌套机制与数据一致性20260423.md)、[中断中不能做和不建议做的事](../01_嵌入式基础/中断中不能做和不建议做的事20260527.md)、[不同级别设备的中断含义与误区](../01_嵌入式基础/不同级别设备的中断含义与误区20260826.md)
