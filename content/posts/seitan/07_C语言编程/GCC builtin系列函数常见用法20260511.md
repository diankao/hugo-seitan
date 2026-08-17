+++
title = 'GCC __builtin系列函数常见用法'
date = 2026-05-11T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['GCC', '__builtin', '编译器内置函数', '优化']
+++

# GCC \_\_builtin系列函数常见用法

## 题目

GCC 中 `__builtin` 系列函数有哪些常见用法？

## 考察点

编译器内置函数的用途、性能优化手段、分支预测/位操作/内存屏障等底层能力。

## 回答要点

### 1. 什么是 __builtin

`__builtin_xxx` 是 GCC（和兼容 GCC 的 Clang）提供的**编译器内置函数**。它们不是库函数，而是编译器直接识别并生成最优机器码的特殊调用。

**核心优势**：编译器比程序员更清楚目标架构的指令集，可以直接生成单条指令，而非通过函数调用。

### 2. 分支预测提示

#### `__builtin_expect`

```c
#define likely(x)   __builtin_expect(!!(x), 1)
#define unlikely(x) __builtin_expect(!!(x), 0)

// 告诉编译器：error 通常不会发生
int parse_packet(const uint8_t *data, size_t len) {
    if (unlikely(data == NULL)) {
        return -1;
    }

    if (unlikely(len < HEADER_SIZE)) {
        return -2;
    }

    // 正常路径（likely）
    process_header(data);
    return 0;
}
```

**原理**：编译器会将 `likely` 分支的代码放在顺序执行路径上，`unlikely` 分支放到远处。提高 CPU 分支预测命中率，减少流水线冲刷。

```c
// FreeRTOS 源码中的实际使用
#define configASSERT(x) if ((x) == 0) { taskDISABLE_INTERRUPTS(); for(;;); }

// Linux 内核中大量使用
if (unlikely(ptr == NULL))
    goto error_handler;
```

**适用场景**：错误处理路径、调试断言、冷路径标记。

### 3. 位操作

#### `__builtin_clz` / `__builtin_ctz`

```c
// __builtin_clz(x)：前导零数量（Count Leading Zeros）
// __builtin_ctz(x)：末尾零数量（Count Trailing Zeros）
// 注意：x = 0 时行为未定义！

int a = __builtin_clz(0x00000010);  // = 27（32位中前导27个0）
int b = __builtin_ctz(0x00000010);  // = 4（末尾4个0，即最低位1的位置）

// 实际应用：FreeRTOS 就绪列表查找最高优先级
// 用 clz 实现 O(1) 查找最高位
UBaseType_t uxTopReadyPriority = 0;

// 位图中每个 bit 代表一个优先级是否有就绪任务
// 32 位值中找最高位的 1：
int highest = 31 - __builtin_clz(uxTopReadyPriority);

// 手动实现对比（没有 clz 时）
int find_highest_bit(uint32_t x) {
    for (int i = 31; i >= 0; i--) {
        if (x & (1u << i)) return i;
    }
    return -1;  // O(32) vs O(1)
}
```

#### `__builtin_popcount`

```c
// 统计二进制中 1 的个数
int count = __builtin_popcount(0xFF00);  // = 8

// 应用：统计中断挂起位
uint32_t pending = NVIC->ISPR[0];
int irq_count = __builtin_popcount(pending);  // 有多少个中断在挂起
```

#### `__builtin_parity`

```c
// 1 的个数是奇数返回 1，偶数返回 0
int p = __builtin_parity(0b1011);  // = 0（3个1，奇数→1）
// 等价于 __builtin_popcount(x) & 1，但更快

// 应用：校验位计算
```

### 4. 内存操作

#### `__builtin_prefetch`

```c
// 预取数据到 Cache，减少后续访问的 Cache Miss
void process_array(int *data, int n) {
    for (int i = 0; i < n; i++) {
        // 提前预取下一个要用的数据
        if (i + 8 < n) {
            __builtin_prefetch(&data[i + 8], 0, 1);
        }
        process(data[i]);
    }
}

// 参数：
// addr:  要预取的地址
// rw:    0=读，1=写（默认0）
// locality: 0=不保留，1=保留在L3，2=保留在L2，3=保留在L1
```

**适用场景**：遍历大数组、链表遍历、DMA 传输前预热 Cache。

#### `__builtin_memcpy` / `__builtin_memset`

```c
// 编译器会在编译期判断长度，如果长度是小的常量，
// 直接生成内联的赋值指令而非调用 memcpy 函数
__builtin_memcpy(dst, src, 4);  // 可能生成一条 LDR + STR
__builtin_memcpy(dst, src, 16); // 可能生成四条 LDR + STR

// 对比标准 memcpy：小的常量长度调用 memcpy 函数反而有函数调用开销
```

### 5. 类型相关

#### `__builtin_types_compatible_p`

```c
// 编译期判断两个类型是否兼容（兼容 C 的类型系统规则）
int a = __builtin_types_compatible_p(int, int);           // 1
int b = __builtin_types_compatible_p(int, unsigned int);  // 0
int c = __builtin_types_compatible_p(char*, const char*); // 0

// 应用：泛型宏中根据类型选择不同实现（C11 _Generic 之前的方法）
#define print_value(x) _Generic((x), \
    int: print_int, \
    float: print_float, \
    const char*: print_string \
)(x)
```

#### `__builtin_choose_expr`

```c
// 编译期条件选择（不会两个分支都求值）
#define GET_SIZE(x) \
    __builtin_choose_expr( \
        sizeof(x) <= sizeof(int), \
        (int)(x), \
        (long)(x) \
    )
```

### 6. 控制流

#### `__builtin_unreachable`

```c
// 告诉编译器：这个点永远不会被执行到
// 编译器据此可以优化掉不可达路径

int classify(int x) {
    switch (x) {
        case 0: return 0;
        case 1: return 1;
        case 2: return 2;
        default: __builtin_unreachable();
        // 编译器知道 x 只能是 0/1/2，
        // 可以省掉范围检查代码
    }
}

// 应用：switch 覆盖所有枚举值时，default 标记为不可达
typedef enum { RED, GREEN, BLUE } color_t;
int to_value(color_t c) {
    switch (c) {
        case RED:   return 0;
        case GREEN: return 1;
        case BLUE:  return 2;
    }
    __builtin_unreachable();
}
```

#### `__builtin_assume_aligned`

```c
// 告诉编译器：这个指针已按 N 字节对齐
void process(int *data) {
    int *aligned = (int *)__builtin_assume_aligned(data, 16);
    // 编译器可以使用 SIMD 指令（要求 16 字节对齐）
    for (int i = 0; i < 256; i++) {
        aligned[i] += 1;
    }
}
```

### 7. 数学相关

#### `__builtin_abs` / `__builtin_fabs`

```c
// 编译器可能生成无条件跳转的优化版本
int x = __builtin_abs(-42);  // 直接生成条件取反指令
```

#### `__builtin_mul_overflow` / `__builtin_add_overflow`

```c
// 安全运算：检测溢出
int result;
bool overflow = __builtin_mul_overflow(a, b, &result);
if (overflow) {
    // 处理溢出
}

// 应用：嵌入式中的安全计算
uint32_t size;
if (__builtin_mul_overflow(count, elem_size, &size)) {
    return ERROR_OVERFLOW;
}
void *buf = malloc(size);
```

### 8. 内存屏障

#### `__builtin_is_constant_evaluated`（C++）

```cpp
// C++20：判断当前是否在编译期求值
constexpr int factorial(int n) {
    if (std::is_constant_evaluated()) {
        // 编译期：用递归（不担心性能）
        return n <= 1 ? 1 : n * factorial(n - 1);
    } else {
        // 运行期：用迭代（更快）
        int result = 1;
        for (int i = 2; i <= n; i++) result *= i;
        return result;
    }
}
```

### 9. 常用 __builtin 速查表

| 函数 | 功能 | 典型场景 |
|------|------|---------|
| `__builtin_expect` | 分支预测提示 | 错误路径标记 `unlikely()` |
| `__builtin_clz` | 前导零计数 | RTOS 优先级查找、对齐计算 |
| `__builtin_ctz` | 末尾零计数 | 找最低位1的位置 |
| `__builtin_popcount` | 1的个数统计 | 中断挂起计数、校验 |
| `__builtin_prefetch` | 预取到Cache | 大数组遍历优化 |
| `__builtin_unreachable` | 标记不可达 | switch 覆盖全部枚举值 |
| `__builtin_mul_overflow` | 乘法溢出检测 | 安全计算 |
| `__builtin_assume_aligned` | 对齐假设 | SIMD 优化 |
| `__builtin_memcpy` | 内联内存拷贝 | 小块常量拷贝 |
| `__builtin_parity` | 奇偶校验 | 校验位计算 |

### 10. 面试速记

- **`__builtin` 不是库函数**，是编译器内置函数，直接生成最优机器指令
- **分支预测**：`likely/unlikely` 用 `__builtin_expect` 实现，FreeRTOS 和 Linux 内核大量使用
- **位操作**：`clz/ctz/popcount` 一条指令完成，FreeRTOS 用 `clz` 实现 O(1) 最高优先级查找
- **安全运算**：`__builtin_mul_overflow` 检测溢出，嵌入式安全计算必备
- **编译器提示**：`__builtin_unreachable` 和 `__builtin_assume_aligned` 帮助编译器做更激进的优化
