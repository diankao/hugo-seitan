+++
title = 'malloc与new的区别及动态内存管理'
date = 2026-02-28T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['C语言', 'C++', 'malloc', 'new', '内存管理', 'MISRA']
+++

# malloc与new的区别及动态内存管理

## 题目

C 语言中 malloc 和 C++ 中 new 有何区别？为什么 MISRA C 禁止动态内存分配？现代 C++ 编译器自动管理内存了吗？

## 考察点

malloc/new 底层差异、动态内存的风险、MISRA 规范对动态分配的态度、RAII 机制。

## 回答要点

### 1. C++ 内存分配的三种方式

| 方式 | 时机 | 存储 | 典型变量 |
|------|------|------|---------|
| 静态存储区 | 编译时分配，程序结束释放 | .data / .bss | 全局变量、static 变量 |
| 栈区 | 代码执行时创建，函数返回时自动释放 | 栈 | 局部变量、函数参数 |
| 堆区 | 手动分配（malloc/new），手动释放（free/delete） | 堆 | 动态对象、大缓冲区 |

### 2. malloc 与 new 的区别

| 方面 | `malloc` | `new` |
|------|---------|-------|
| 语言 | C | C++ |
| 返回类型 | `void*`（需强转） | 具体类型指针（类型安全） |
| 构造/析构 | ❌ 不调用 | ✅ 自动调用 |
| 失败处理 | 返回 `NULL` | 抛出 `std::bad_alloc`（或 `nothrow` 版返回 `nullptr`） |
| 内存大小 | 必须手动计算 `sizeof` | 编译器自动计算 |
| 释放 | `free` | `delete` |
| 重载 | 不可重载 | 可重载 `operator new` |
| 数组 | `malloc(n * sizeof(T))` | `new T[n]` |

```c
// C 风格
int *p1 = (int *)malloc(10 * sizeof(int));
if (p1 == NULL) { /* 处理错误 */ }
free(p1);

// C++ 风格
int *p2 = new int[10];
delete[] p2;

// C++ 对象（malloc 无法正确处理）
MyClass *obj1 = (MyClass *)malloc(sizeof(MyClass));  // 不调用构造函数！
free(obj1);                                           // 不调用析构函数！

MyClass *obj2 = new MyClass();   // 分配内存 + 调用构造函数
delete obj2;                      // 调用析构函数 + 释放内存
```

### 3. 为什么 MISRA C 禁止动态内存分配（Dir 4.12）

**核心原因：动态内存分配是非确定性的，安全关键系统要求绝对的确定性。**

#### 3.1 内存碎片与资源耗尽

```c
// 反复 malloc/free 后，堆变得支离破碎
// 即使剩余总量足够，也可能没有连续空间满足请求
void *p = malloc(256);  // 可能返回 NULL，即使总空闲内存 > 256
```

**对比静态分配**：全局变量/静态数组在编译时就确定了大小，链接器保证有足够空间，不存在运行时分配失败。

#### 3.2 执行时间的非确定性

- 首次调用可能涉及向操作系统申请堆内存
- 碎片化后需要遍历空闲链表查找合适块，耗时不确定
- `free` 可能涉及合并相邻空闲块
- 硬实时系统中，`malloc` 耗时从几微秒漂移到几毫秒，可能导致任务错过截止时间

#### 3.3 内存泄漏风险

```c
void process(void) {
    uint8_t *buf = malloc(1024);
    if (error_condition) {
        return;  // 忘记 free！内存泄漏
    }
    free(buf);
}
```

内存泄漏是累积性错误，系统运行一个月后可能耗尽内存，且极难在测试中复现。

#### 3.4 MISRA 推荐的替代方案

**方案一：静态分配（推荐）**

```c
uint8_t *buffer = (uint8_t *)malloc(256);  // 不合规
uint8_t buffer[256];                        // 合规
```

**方案二：内存池**

```c
static MyObject pool[10];
static bool used[10];

MyObject *acquireObject(void) {
    for (int i = 0; i < 10; i++) {
        if (!used[i]) {
            used[i] = true;
            return &pool[i];
        }
    }
    return NULL;
}
```

**方案三：RTOS 启动阶段分配（唯一例外）**

```c
// 在调度器启动前分配，运行时不再分配
int main(void) {
    queue = xQueueCreate(10, sizeof(Message));  // 启动阶段，可以
    vTaskStartScheduler();                       // 此后不再 malloc
}
```

### 4. 现代 C++ 编译器自动管理内存了吗？

**没有。** 编译器不负责内存管理。真正提供"自动"能力的是 C++ 标准库通过 **RAII 机制**实现。

#### 4.1 RAII 机制

```cpp
// 智能指针：离开作用域自动 delete
{
    auto obj = std::make_unique<MyClass>();
    obj->doWork();
}  // 自动调用析构函数，delete 内存

// 容器：离开作用域自动释放内部数组
{
    std::vector<int> arr(1000);
    arr[0] = 42;
}  // 自动释放内部堆数组
```

#### 4.2 现代 C++ vs MISRA 的矛盾

| 传统 C 风格 | 现代 C++ 方式 | 原理 | MISRA 合规？ |
|------------|-------------|------|-------------|
| `malloc`/`free` | `std::unique_ptr` | 析构自动 delete | ❌ 底层仍是 new/delete |
| `malloc` 数组 | `std::vector` | 析构自动释放 | ❌ 动态增长不可控 |
| 返回指针 | 返回 `std::vector` | RVO + 移动语义 | ❌ 依赖堆 |

**核心矛盾**：现代 C++ 解决了**内存泄漏**问题，但没有解决**碎片和时间不确定**问题。MISRA 追求的是零妥协的确定性。

#### 4.3 安全关键 C++ 的折中

遵循 MISRA C++ / AUTOSAR C++ 规范时：
- 禁止 `std::vector` 动态增长（可预分配固定大小）
- 禁止 `std::string`（用静态大小的 `std::array<char, N>`）
- 使用 placement new + 静态内存池代替 new

### 5. malloc/free 与 new/delete 混用的后果

```c
int *p = (int *)malloc(sizeof(int));
delete p;     // 未定义行为！malloc 分配的必须用 free

int *q = new int;
free(q);      // 未定义行为！new 分配的必须用 delete

// new[] 和 delete 混用也是 UB
int *arr = new int[10];
delete arr;    // 未定义行为！必须 delete[] arr
```

### 6. 面试速记

- **malloc vs new**：malloc 是 C 函数只管分配内存，new 是 C++ 运算符还会调用构造函数
- **MISRA 禁止 malloc**：碎片化、时间不确定、内存泄漏——三大不可接受风险
- **替代方案**：静态分配 > 内存池 > 仅启动阶段分配
- **现代 C++**：RAII 解决了内存泄漏，但没解决碎片和确定性，MISRA 仍然不允许
- **铁律**：malloc 配 free，new 配 delete，new[] 配 delete[]，绝不能混用
