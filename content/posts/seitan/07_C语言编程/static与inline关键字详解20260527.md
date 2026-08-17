+++
title = 'static与inline关键字详解'
date = 2026-05-27T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['C语言', 'static', 'inline', '关键字', '编译']
+++

# static与inline关键字详解

## 题目

1. static 有什么作用？
2. inline 有什么作用？
3. static 和 inline 结合使用是什么含义？

## 考察点

C语言关键字语义、编译单元与链接、函数调用开销优化、嵌入式开发中的常见用法。

## 回答要点

### 1. static 关键字

`static` 在 C 语言中有三种用法，分别作用于**局部变量**、**全局变量**和**函数**。

#### 1.1 static 修饰局部变量

普通局部变量分配在栈上，函数返回后生命周期结束。加上 `static` 后，变量存储在 **.data 或 .bss 段**（静态存储区），生命周期延长到整个程序运行期间，但**作用域不变**（仍限函数内部）。

```c
void counter(void) {
    static int count = 0;  // 只初始化一次，值在调用间保持
    count++;
    printf("called %d times\n", count);
}

int main(void) {
    counter();  // called 1 times
    counter();  // called 2 times
    counter();  // called 3 times
    return 0;
}
```

| 特性 | 普通局部变量 | static 局部变量 |
|------|------------|----------------|
| 存储位置 | 栈 | .data / .bss 段 |
| 生命周期 | 函数调用期间 | 程序运行期间 |
| 初始化 | 每次进入函数 | 只在首次，默认为 0 |
| 作用域 | 函数内部 | 函数内部（不变） |

#### 1.2 static 修饰全局变量

全局变量本来对整个程序（所有编译单元）可见。加上 `static` 后，**链接可见性限制为当前编译单元（.c 文件）**，其他文件无法通过 `extern` 访问。

```c
// file1.c
static int module_state = 0;  // 只在 file1.c 内可见

int get_state(void) {
    return module_state;       // 通过函数间接访问
}

// file2.c
extern int module_state;      // 链接错误！找不到符号
```

#### 1.3 static 修饰函数

同理，`static` 修饰函数将该函数的可见性限制在当前编译单元内。其他文件不能调用它，可以安全地定义同名函数而不冲突。

```c
// uart.c
static void uart_set_baudrate(uint32_t baud) {
    // 内部辅助函数，外部不需要也不应该调用
}

void uart_init(uint32_t baud) {
    uart_set_baudrate(baud);
    // ...
}

// spi.c
static void uart_set_baudrate(uint32_t baud) {
    // 不同文件中可以定义同名 static 函数，不冲突
}
```

#### 1.4 static 三种用法总结

| 修饰对象 | 效果 |
|---------|------|
| 局部变量 | 生命周期延长到程序结束，只初始化一次 |
| 全局变量 | 链接可见性限制为当前 .c 文件 |
| 函数 | 链接可见性限制为当前 .c 文件 |

### 2. inline 关键字

#### 2.1 函数调用的开销

普通函数调用需要：保存寄存器 → 压参数 → 跳转 → 执行 → 返回 → 恢复寄存器。对于很小的函数，这个开销可能比函数体本身还大。

```c
// 这个函数体只有一条指令，但调用开销可能有好几条指令
int max(int a, int b) {
    return a > b ? a : b;
}
```

#### 2.2 inline 的作用

`inline` 建议**编译器将函数体直接嵌入调用点**，省去函数调用开销：

```c
// 不内联：调用过程
int result = max(3, 5);
// 编译为：push 5, push 3, call max, mov result, ax

// 内联后：直接展开
int result = 3 > 5 ? 3 : 5;
// 编译为：mov result, 5
```

#### 2.3 inline 只是建议

`inline` 关键字只是对编译器的**建议**，编译器可以选择忽略：

| 编译器行为 | 说明 |
|-----------|------|
| 可能内联 | 函数体小、无循环/递归、高优化级别（-O2/-O3） |
| 可能不内联 | 函数体大、有循环/递归、低优化级别（-O0） |
| 强制内联 | `__attribute__((always_inline))`（GCC）或 `__forceinline`（MSVC） |

#### 2.4 inline 与链接问题

`inline` 函数如果定义在头文件中被多个 .c 文件包含，可能导致**多重定义**链接错误。解决方法：

```c
// 方法一：static inline（最常用）
static inline int max(int a, int b) {
    return a > b ? a : b;
}
// 每个编译单元有自己的副本，不冲突

// 方法二：extern inline（C99）
// 头文件中声明
inline int max(int a, int b);
// 某一个 .c 文件中提供外部定义
extern inline int max(int a, int b);
```

### 3. static inline 组合

`static inline` 是嵌入式开发中**最常见的组合**：

```c
// drivers/gpio.h
static inline void gpio_set_high(uint32_t pin) {
    GPIO->ODR |= (1UL << pin);
}

static inline void gpio_set_low(uint32_t pin) {
    GPIO->ODR &= ~(1UL << pin);
}

static inline int gpio_read(uint32_t pin) {
    return (GPIO->IDR >> pin) & 1;
}
```

| 关键字组合 | 含义 |
|-----------|------|
| `static inline` | 建议内联 + 链接可见性限制在当前编译单元 |
| `static`（非 inline） | 链接可见性限制，但不建议内联 |
| `inline`（非 static） | 建议内联，但有链接问题 |

**为什么嵌入式喜欢用 `static inline`：**

- 放在头文件中安全（不会多重定义）
- 寄存器操作函数通常很小，内联后零开销
- 编译器可以在调用点做更多优化（常量传播等）
- 不产生单独的函数符号，节省空间

### 4. 对比总结

| 特性 | static | inline |
|------|--------|--------|
| 作用于 | 变量、函数 | 函数 |
| 核心效果 | 限制作用域/延长生命周期 | 建议编译器内联展开 |
| 链接影响 | 符号不导出 | 可能多重定义 |
| 嵌入式常见用法 | 模块内部函数/变量 | 头文件中的小函数 |
| 最佳实践 | 不对外暴露的辅助函数用 static | 热路径小函数用 static inline |
