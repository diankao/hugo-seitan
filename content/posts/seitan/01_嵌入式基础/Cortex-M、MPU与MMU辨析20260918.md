+++
title = 'Cortex-M、MPU与MMU辨析'
date = 2026-09-18T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['ARM', 'Cortex-M', 'MPU', 'MMU', '选型']
+++

# Cortex-M、MPU与MMU辨析

## 题目

Cortex-M 是指令集还是别的什么？高级版本的 Cortex-M 不是有 MMU 吗？

## 考察点

Arm 架构的三层命名体系（ISA / 核心 / 芯片）、A/R/M 三个 profile 的分工、MPU 与 MMU 的机制差异。

## 回答要点

### 1. Cortex-M 是核心产品名，不是指令集

Arm 的命名有三层，经常被混在一起谈：

| 层次 | 例子 | 类比 x86 世界 |
|------|------|--------------|
| 指令集架构（ISA） | Armv6-M / Armv7-M / Armv8-M / Armv8-A / Armv9-A | x86、x86-64 |
| 核心产品（微架构，IP 核） | Cortex-M0/M3/M4/M7/M33/M55/M85、Cortex-A53/A78 | Core i7、Zen 4 |
| 芯片（厂商集成） | STM32F103、GD32、i.MX6 | 某款整机 |

- Cortex-M 是 Arm 公司设计的核心 IP 产品线，实现的是 Arm 架构中的 M profile（M = Microcontroller）
- Armv8-M : Cortex-M4 的关系，就是 x86-64 : 某 CPU 型号的关系
- 各代 M 核心的流水线、FPU、DSP 差异与选型，详见《ARM Cortex-M系列对比与应用场景》

### 2. A / R / M 三个 profile 的分工

| Profile | 含义 | 内存机制 | 典型场景 |
|---------|------|---------|---------|
| A（Application） | 应用处理器 | MMU，跑 Linux/Android | 手机、路由器、车机 |
| R（Real-time） | 实时处理器 | MPU + 锁步核 | 线控底盘、安全气囊 |
| M（Microcontroller） | 微控制器 | 无 MMU，可选 MPU | STM32 类 MCU |

### 3. 顶配 Cortex-M 也没有 MMU

2022 年的顶配 Cortex-M85（Armv8.1-M，带 Helium 向量扩展）依然是 PMSA 架构：MPU + 可选 SAU（TrustZone-M 隔离），从头到尾没有地址翻译。容易犯的错是把 MPU 记成 MMU，两者只差一个字母，机制完全不同：

| | MPU | MMU |
|---|-----|-----|
| 地址翻译 | 无，程序直接用物理地址 | VA → PA |
| 机制 | 若干区域（M4 8 个，M7 16 个）的权限检查 | 多级页表 + TLB + 硬件走表 |
| 访问延迟 | 恒定 O(1) | TLB 命中快，miss 走表不定 |
| 跑标准 Linux | 不能 | 能 |
| 典型用法 | FreeRTOS-MPU 任务隔离 | 通用操作系统 |

### 4. M profile 为什么拒绝 MMU

不是做不到，是设计哲学拒绝：

- 走表与 TLB miss 引入不确定延迟，与硬实时冲突
- MCU 几百 KB 内存，没有换页（swap）的需求场景
- MPU 区域检查恒定时间，最坏执行时间（WCET）分析简单，利于安全认证
- 少了 TLB 和走表器，硅面积与功耗更小

### 5. 想要 MMU：往 A profile 走，或者用异构芯片

最典型的例子是 STM32MP1：一颗芯片里双核 Cortex-A7（带 MMU，跑 Linux）+ Cortex-M4（无 MMU，跑 RTOS）。Linux + RTOS 异构混合是当前"既要生态又要实时"的主流解法。

### 6. 一个例外注脚

R profile 里最新的 Cortex-R82（Armv8-R AArch64）加了地址翻译单元（支持两级翻译，为的是虚拟化跑混合负载）——但那是 R 的事，M 至今守着"无翻译"这条线。

## 扩展问题

- 各架构的地址翻译方案全景（硬件走表 / 软件走表 / 散列表）→ 详见《非x86架构也用多级页表吗》
- 无 MMU 与硬实时的关系、带 MMU 如何做硬实时 → 详见《硬实时系统能用MMU吗》
