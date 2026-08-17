+++
title = 'RISC-V与ARM架构FreeRTOS移植对比'
date = 2026-05-11T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['FreeRTOS', 'RISC-V', 'ARM', '任务切换', '移植']
+++

# RISC-V与ARM架构FreeRTOS移植对比

## 题目

在RISC-V架构中移植FreeRTOS时，任务切换是怎么做的？与ARM架构的任务切换有什么区别？

## 考察点

FreeRTOS 移植层原理、ARM 与 RISC-V 异常/中断机制差异、上下文保存恢复机制。

## 回答要点

### 1. 总览对比

| 方面 | ARM Cortex-M | RISC-V |
|------|-------------|--------|
| 任务切换触发 | PendSV 中断（最低优先级） | Machine Software Interrupt（msip） |
| 硬件自动压栈 | ✅ 8 个寄存器（R0-R3, R12, LR, PC, xPSR） | ❌ **全部软件保存** |
| 栈模型 | 双栈（MSP + PSP） | 通常单栈（SP） |
| 需保存的寄存器 | 16 个通用（R0-R15） | 32 个通用（x0-x31）+ mepc |
| 上下文大小（无FPU） | 64 字节（硬件32 + 软件32） | 132 字节（33 × 4） |
| 上下文大小（有FPU） | 128 字节 | 260+ 字节（F32 寄存器更多） |
| 中断返回指令 | `BX LR`（EXC_RETURN 机制） | `mret` |
| 保存/恢复开销 | 较小（硬件辅助） | 较大（全部软件完成） |

### 2. ARM Cortex-M 任务切换流程

#### 2.1 触发

```c
// ARM: 通过设置 PendSV 悬起位触发任务切换
#define portYIELD() \
    portNVIC_INT_CTRL_REG = portNVIC_PENDSVSET_BIT

// SysTick 中断中也会触发
void xPortSysTickHandler(void) {
    // 更新系统时钟
    xTaskIncrementTick();
    // 触发 PendSV
    portYIELD();
}
```

#### 2.2 硬件自动压栈（进入 PendSV 时）

```
进入异常时，硬件自动将 8 个寄存器压入 PSP：

PSP + 0x1C  xPSR
PSP + 0x18  PC        ← 返回地址
PSP + 0x14  LR        ← R14
PSP + 0x10  R12
PSP + 0x0C  R3
PSP + 0x08  R2
PSP + 0x04  R1
PSP + 0x00  R0
```

#### 2.3 软件手动压栈

```arm
PendSV_Handler:
    MRS     R0, PSP               ; 获取任务栈指针
    STMDB   R0!, {R4-R11, R14}    ; 保存 R4-R11 和 EXC_RETURN

    LDR     R1, =pxCurrentTCB
    LDR     R2, [R1]
    STR     R0, [R2]              ; 保存 SP 到 TCB

    ; 调度器选择下一个任务
    BL      vTaskSwitchContext

    ; 恢复新任务
    LDR     R1, =pxCurrentTCB
    LDR     R2, [R1]
    LDR     R0, [R2]              ; 从 TCB 读取新 SP
    LDMIA   R0!, {R4-R11, R14}    ; 恢复 R4-R11
    MSR     PSP, R0               ; 更新 PSP
    BX      R14                   ; 异常返回，硬件自动弹出 8 个寄存器
```

### 3. RISC-V 任务切换流程

#### 3.1 触发

```c
// RISC-V: 通过触发 Machine Software Interrupt
#define portYIELD() \
    do { \
        *(volatile uint32_t *)(CLINT_MSIP_ADDR) = 1; \
    } while(0)
```

#### 3.2 全部软件保存（无硬件自动压栈）

```asm
// RISC-V 的 FreeRTOS 上下文切换（简化）
SoftwareInterrupt_Handler:
    ; 保存当前任务的 mepc（相当于 PC）
    csrr    t0, mepc

    ; 保存所有通用寄存器
    addi    sp, sp, -132         ; 分配栈空间（33个寄存器）
    sw      x1,  0(sp)           ; ra (返回地址)
    sw      x3,  8(sp)           ; gp
    sw      x4,  12(sp)          ; tp
    sw      x5,  16(sp)          ; t0
    ; ... x6 - x31 ...
    sw      x31, 124(sp)         ; t6
    sw      t0,  128(sp)         ; mepc（第33个）

    ; 保存 SP 到当前 TCB
    la      t1, pxCurrentTCB
    lw      t2, 0(t1)
    sw      sp, 0(t2)

    ; 调度器选择下一个任务
    call    vTaskSwitchContext

    ; 恢复新任务
    la      t1, pxCurrentTCB
    lw      t2, 0(t1)
    lw      sp, 0(t2)            ; 从 TCB 读取新 SP

    ; 恢复所有寄存器
    lw      x1,  0(sp)
    lw      x3,  8(sp)
    ; ... x4 - x31 ...
    lw      x31, 124(sp)
    lw      t0,  128(sp)         ; 恢复 mepc
    csrw    mepc, t0

    addi    sp, sp, 132          ; 释放栈空间

    mret                         ; 返回，跳转到 mepc
```

### 4. 关键差异详解

#### 4.1 栈模型

```
ARM 双栈模型：
  MSP（主栈）── 用于 ISR 和异常处理
  PSP（进程栈）── 用于任务
  → CONTROL 寄存器控制当前使用哪个栈
  → ISR 自动切换到 MSP，任务使用 PSP

RISC-V 单栈模型：
  SP（唯一栈指针）
  → ISR 和任务共用一个栈
  → 移植层需要手动管理栈切换
  → 部分实现会模拟双栈（分配 ISR 专用栈）
```

#### 4.2 寄存器数量

```
ARM Cortex-M：
  R0-R15（16 个通用）+ xPSR + 特殊寄存器
  实际需要保存：R4-R11（8 个 callee-saved）
  硬件保存：R0-R3, R12, LR, PC, xPSR（8 个）

RISC-V：
  x0-x31（32 个通用）+ mepc + mstatus
  x0 恒为 0 不需要保存
  x1(ra) - x31 需要保存（31 个）
  + mepc = 32 个
  + mstatus 有时也需要保存
  → 保存量是 ARM 的 4 倍
```

#### 4.3 中断返回

```
ARM：
  BX LR    ; LR 中是特殊值 EXC_RETURN（如 0xFFFFFFFD）
            ; 硬件识别后自动从 PSP 弹出 8 个寄存器
            ; 并切换回 PSP

RISC-V：
  mret     ; 硬件将 mepc 写入 PC
            ; 恢复 mstatus 中的中断使能位
            ; 没有自动弹出寄存器的机制
```

### 5. 性能影响

| 指标 | ARM Cortex-M4 | RISC-V (RV32IMAC) |
|------|--------------|-------------------|
| 上下文保存 | 硬件 8 + 软件 8 = 16 个 | 软件 32 个 |
| 栈消耗 | 64 字节（无 FPU） | 128+ 字节 |
| 切换延迟 | ~30 周期 | ~80-120 周期 |
| FPU 切换 | 额外 64 字节 | 额外 128+ 字节 |

**结论**：RISC-V 的上下文切换开销显著大于 ARM，因为：
1. 没有硬件自动压栈
2. 寄存器数量多（32 vs 16）
3. 没有 MSP/PSP 双栈的硬件支持

### 6. 面试速记

- **ARM**：PendSV + 硬件压栈 8 个 + 软件压栈 8 个 + MSP/PSP 双栈
- **RISC-V**：Software Interrupt + 全部软件保存 32 个 + 单栈
- **开销**：RISC-V 切换开销约 ARM 的 2-4 倍
- **原因**：ARM 有硬件辅助（自动压栈、双栈），RISC-V 设计更简洁但需要更多软件工作
