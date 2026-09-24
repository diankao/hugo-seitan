+++
title = 'GCC __attribute__ 常用属性'
date = 2026-09-21T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['GCC', 'attribute', 'C语言', '链接器', '对齐']
+++

# GCC __attribute__ 常用属性

## 题目

什么是 `__attribute__` 机制？嵌入式开发中常用的属性有哪些？

## 考察点

GCC 扩展语法的设计动机（不新增关键字、占用 `__` 保留区）、函数/变量/类型三类属性、packed 的对齐陷阱、weak+alias 与启动文件中断机制的配合、section 与链接脚本的组合、CMSIS 宏马甲的展开。

## 回答要点

### 1. 它是什么，为什么长这样

`__attribute__((属性列表))` 是 GCC/Clang 的语言扩展插口，给函数、变量、类型附加编译器可读的元数据，双括号强制。设计动机有两条：

- **不新增关键字**——新关键字会砸烂存量代码（比如某程序拿 `packed` 当变量名）
- `__attribute__` 本身姓 `__`，住在标准保留区；属性名（weak、packed）只在双括号内部出现，不需要独立保留

MSVC 不认它（用 `__declspec`），这是跨编译器代码都要裹宏的根源。

### 2. 常用属性速查

| 属性 | 修饰对象 | 作用 | 典型场景 |
|------|---------|------|---------|
| packed | 类型 | 成员对齐降为 1、去掉填充 | 协议帧、寄存器覆盖结构 |
| section("名字") | 函数/变量 | 放进指定段，交给链接脚本摆布 | `.isr_vector` 向量表、RAM 函数、DMA 缓冲 |
| weak / alias | 函数 | 弱符号、别名 | 启动文件的中断默认处理 |
| always_inline | 函数 | `-O0` 也强制内联 | HAL 头文件单函数库、临界区原语 |
| noreturn | 函数 | 声明永不返回 | fault 死循环、`Error_Handler` |
| format(printf,1,2) | 函数 | 按 printf 规则检查格式串 | 日志封装 `%d/%s` 错配编译期就抓 |
| used | 函数/变量 | 没人引用也不许删 | 配 `--gc-sections` 保住向量表 |
| naked | 函数 | 不生成 prologue/epilogue | 上下文切换蹦床 |
| pure / const | 函数 | 结果可缓存复用 | 标错是未定义行为，慎用 |
| cleanup(f) | 变量 | 离开作用域自动调 f | C 语言的 RAII，Linux 新内核的 `__free` 玩法 |

### 3. weak + alias：启动文件的机关

STM32Cube 生成的 GCC 启动文件里，每个中断处理都是这样一行：

```c
void NMI_Handler(void)        __attribute__((weak, alias("Default_Handler")));
void USART1_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
```

弱符号意味着"有强符号就别用我"——用户在自己文件里写一个同名函数，链接器自动替换。这就是"不写中断处理就死循环、写了就接管"整台戏的机关。

### 4. packed：协议帧的刚需与未对齐陷阱

```c
typedef struct __attribute__((packed)) {
    uint8_t  type;
    uint32_t seq;
    uint16_t len;
} frame_hdr_t;
```

没有 packed，`seq` 前会被填 3 个字节，`sizeof` 从 7 变 11，协议直接对不上。代价是**未对齐访问**：

- M3/M4/M7 硬件容忍未对齐的 LDR/STR（有性能损耗）
- **M0/M0+ 上未对齐访问直接 HardFault**——编译器知道 packed 后会拆成字节访问或调 `__aeabi_memcpy`，但把 packed 结构成员的地址转成普通指针再用就危险了

### 5. section：与链接脚本的组合拳

`__attribute__((section(".ramfunc")))` 把函数扔进命名段，链接脚本决定这个段落在哪（Flash 还是 RAM、要不要拷贝）。`.isr_vector` 向量表、CCM RAM 的利用、MPU/缓存策略分区全是这套组合拳——Reset_Handler 搬运的那张清单，就是链接脚本按段名写的。

### 6. 其他高频属性

- `always_inline`：`-O0` 也展开，HAL 头文件里一个函数一个 `__STATIC_INLINE` 的写法靠它
- `noreturn`：fault 死循环专用，让编译器放心优化调用点；标准等价物是 C11 的 `_Noreturn`、C++11/C23 的 `[[noreturn]]`
- `format(printf, 1, 2)`：日志封装必配，`my_log("%d", str)` 这类错配编译期就抓出来

```c
void my_log(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
```

- `used`：配 `--gc-sections` 使用，向量表没人"调用"，不标就被当死代码删掉
- `naked`：不生成函数序幕尾声，上下文切换蹦床在 C 文件里写纯汇编入口
- `cleanup(f)`：变量离开作用域自动调 f，C 语言版的 RAII，Linux 6.x 内核的 `__free` 属性就是它
- `pure`/`const`：声明结果可缓存（const 更强，只依赖参数），标错属于对优化器撒谎，是未定义行为

### 7. CMSIS 的马甲

`__WEAK` 在 GCC 上展开成 `__attribute__((weak))`，在 armclang 上是 `__weak`；`__PACKED`、`__ALIGNED(4)`、`__NO_RETURN` 同理。所以"没用过 `__attribute__`"大概率是假的——嵌入式工程师天天在用它的宏马甲。

### 8. 位置语法之丑与标准化归宿

`__attribute__` 的摆放位置出了名的别扭：修饰类型要贴在 `struct` 关键字后或花括号后，修饰函数贴声明尾，放错位置就修饰到别的东西上——所以人人都裹宏。这也是它最终被标准收编的原因之一：C11/C++11 的 `[[属性]]` 统一了写法（`[[noreturn]]`、`[[deprecated]]`，GCC/Clang 还接受 `[[gnu::always_inline]]`）。注意 `[[` 这个标点本身也是保留的——和 `__` 前缀同一个设计逻辑：扩展语言之前，先在保留区划地。

### 9. 一句话总结

`__attribute__` 是"带元数据的声明"：**weak 决定链接、section 决定位置、packed 决定布局、always_inline 决定展开、format 替你查错**。GCC 的四种语言扩展插口（`__attribute__`、`__builtin`、`#pragma`、`[[...]]`）里，它是用得最勤的那个。

## 扩展问题

- 编译器内建函数（`__builtin_expect`/clz 家族）→ 详见《GCC builtin系列函数常见用法》
- 语句级扩展与操作数约束 → 详见《GCC内嵌汇编与操作数约束》
- 启动文件与弱符号的运行现场 → 详见《MCU启动流程与汇编代码使用》
