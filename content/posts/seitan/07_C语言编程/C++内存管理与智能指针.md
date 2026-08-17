+++
title = 'C++内存管理与智能指针'
date = 2026-09-23T00:00:00+08:00
draft = false
categories = ['技术文档']
tags = ['C++', '内存管理', '智能指针', '内存泄漏', '内存碎片']
+++

# C++内存管理与智能指针

## 面试题目

1. 程序内存分布是怎样的
2. 内存泄漏是什么
3. 栈空间上有没有内存泄漏
4. 内存碎片是怎么来的
5. 栈空间上会有内存碎片吗
6. 栈空间会有什么内存问题
7. 内存碎片有哪些解决方法
8. 内存泄漏有哪些解决方法
9. 智能指针有哪些，如何做到自动管理内存的，怎么做到自动释放的

## 考察点

程序内存布局、堆与栈的区别、内存泄漏、内存碎片、智能指针、RAII 机制

## 回答要点

### 1. 程序内存分布是怎样的

一个 C++ 程序在运行时的内存通常分为以下几个区域：

```
┌──────────────────────────┐  高地址
│       内核空间            │  (用户代码不可访问)
├──────────────────────────┤
│       栈区 (Stack)        │  ↓ 向低地址增长
│          ↓               │
├──────────────────────────┤
│       共享库映射区         │  (动态链接库等)
├──────────────────────────┤
│          ↑               │
│       堆区 (Heap)         │  ↑ 向高地址增长
├──────────────────────────┤
│       BSS 段              │  未初始化的全局/静态变量 (默认为0)
├──────────────────────────┤
│       数据段 (Data)       │  已初始化的全局/静态变量
├──────────────────────────┤
│       代码段 (Text)       │  程序机器指令 (只读)
┌──────────────────────────┘  低地址
```

| 区域 | 存储内容 | 生命周期 | 管理方式 |
|------|----------|----------|----------|
| 代码段 | 可执行指令 | 程序运行期间 | 编译时确定 |
| 数据段 | 已初始化全局/静态变量 | 程序运行期间 | 编译时分配 |
| BSS 段 | 未初始化全局/静态变量 | 程序运行期间 | 编译时分配，默认填 0 |
| 堆区 | 动态分配的内存 | 手动 new/delete | 程序员管理 |
| 栈区 | 局部变量、函数参数、返回地址 | 函数调用期间 | 编译器自动管理 |

```cpp
int global_init = 42;
int global_uninit;

void func() {
    static int static_var = 10;
    int local_var = 5;
    int* heap_var = new int(100);
}
```

---

### 2. 内存泄漏是什么

**内存泄漏（Memory Leak）** 是指程序动态分配的内存未被正确释放，导致这部分内存在程序运行期间无法被再次使用。

#### 常见原因

```cpp
// 1. 忘记 delete
void leak1() {
    int* p = new int(42);
}
// p 离开作用域，内存泄漏

// 2. 异常导致跳过 delete
void leak2() {
    int* p = new int(42);
    throw std::runtime_error("error");
    delete p;
}

// 3. 指针被覆盖
void leak3() {
    int* p = new int(42);
    p = new int(100);
}
// 第一个 new 的内存泄漏

// 4. 基类析构函数非虚函数
class Base {
public:
    ~Base() {}
};

class Derived : public Base {
    int* data;
public:
    Derived() { data = new int[100]; }
    ~Derived() { delete[] data; }
};

void leak4() {
    Base* obj = new Derived();
    delete obj;
}
// 只调用 Base 析构函数，Derived::data 泄漏
```

---

### 3. 栈空间上有没有内存泄漏

**严格来说，栈空间不会发生传统意义上的内存泄漏。**

#### 原因

栈内存由编译器自动管理，函数返回时栈帧自动回收，局部变量随之销毁。

```cpp
void func() {
    int arr[1000];
    int x = 42;
}
// 函数返回后，arr 和 x 自动回收，不会泄漏
```

#### 但栈有以下问题

**1. 栈溢出（Stack Overflow）**

```cpp
void recursive(int depth) {
    int big[10000];
    if (depth < 100000) {
        recursive(depth + 1);
    }
}
// 深度递归或大数组可能导致栈溢出
```

**2. 悬挂指针（Dangling Pointer）**

```cpp
int* dangling() {
    int x = 42;
    return &x;
}
// 返回栈变量的地址，函数返回后该地址无效
```

**3. 栈上对象的资源泄漏**

```cpp
class ResourceHolder {
    FILE* fp;
public:
    ResourceHolder(const char* path) {
        fp = fopen(path, "r");
    }
    ~ResourceHolder() {
        if (fp) fclose(fp);
    }
};

void func() {
    ResourceHolder holder("test.txt");
    // 正常情况下析构函数会关闭文件
    // 但如果析构函数未正确释放资源，则存在"资源泄漏"
}
```

栈本身不泄漏，但栈上对象持有的堆资源如果未在析构中释放，仍然会泄漏。

---

### 4. 内存碎片是怎么来的

内存碎片分为两种：**内部碎片** 和 **外部碎片**。

#### 内部碎片

分配的内存块大于实际需要的尺寸，多余部分无法利用。

```cpp
// 假设内存分配器以 16 字节为最小单位
char* p = new char[5];
// 实际分配了 16 字节，浪费了 11 字节（内部碎片）
```

#### 外部碎片

空闲内存被分割成不连续的小块，虽然总量足够，但无法满足大的分配请求。

```
初始堆：|─────────────── 空闲 ───────────────|

分配后：| A (64B) | B (32B) | C (64B) | 空闲 |
释放 B：| A (64B) |  空闲32B | C (64B) | 空闲 |

现在需要分配 48B：
虽然总空闲远超 48B，但最大连续空闲块只有 32B，分配失败。
```

#### 产生原因

1. **频繁的 new/delete**：大小不一的分配和释放导致空闲块不连续
2. **分配大小不均匀**：不同大小的块交替分配和释放
3. **分配顺序与释放顺序不匹配**

---

### 5. 栈空间上会有内存碎片吗

**不会。** 栈不会产生内存碎片。

#### 原因

栈采用**后进先出（LIFO）**的管理方式，内存分配和释放是连续的：

```cpp
void func() {
    int a;        // 栈指针移动 4 字节
    double b;     // 栈指针移动 8 字节
    char c[10];   // 栈指针移动 10 字节
}
// 函数返回，栈指针一次性恢复到调用前的位置
```

栈的分配和回收只是移动栈指针，不存在"中间挖洞"的情况，因此不会产生碎片。

#### 栈与堆的对比

| 特性 | 栈 | 堆 |
|------|----|----|
| 管理方式 | 编译器自动（LIFO） | 程序员手动 / 分配器 |
| 分配速度 | 极快（移动指针） | 较慢（搜索空闲块） |
| 碎片问题 | 无 | 有（外部碎片） |
| 大小限制 | 较小（通常 1-8 MB） | 较大（受系统内存限制） |
| 生命期 | 函数作用域 | 手动控制 |

---

### 6. 栈空间会有什么内存问题

| 问题 | 说明 |
|------|------|
| 栈溢出 | 分配超过栈大小（深递归、大数组） |
| 悬挂指针 | 返回栈变量的地址 |
| 缓冲区溢出 | 数组越界写入，破坏其他栈数据 |
| 返回地址篡改 | 缓冲区溢出覆盖返回地址（安全漏洞） |
| 栈空间不足 | 局部变量过多或过大 |

```cpp
// 1. 栈溢出
void infiniteRecurse() {
    int big[10000];
    infiniteRecurse();
}

// 2. 悬挂指针
int* badFunc() {
    int x = 10;
    return &x;
}

// 3. 缓冲区溢出
void overflow() {
    char buf[8];
    strcpy(buf, "this string is way too long");
}
```

---

### 7. 内存碎片有哪些解决方法

#### 1. 内存池（Memory Pool）

预先分配大块内存，自行管理分配和回收，避免频繁调用系统分配器。

```cpp
class MemoryPool {
private:
    std::vector<void*> freeList;
    size_t blockSize;
    size_t poolSize;
    char* pool;

public:
    MemoryPool(size_t blockSz, size_t count)
        : blockSize(blockSz), poolSize(blockSz * count) {
        pool = new char[poolSize];
        for (size_t i = 0; i < count; i++) {
            freeList.push_back(pool + i * blockSize);
        }
    }

    ~MemoryPool() {
        delete[] pool;
    }

    void* alloc() {
        if (freeList.empty()) return nullptr;
        void* block = freeList.back();
        freeList.pop_back();
        return block;
    }

    void free(void* block) {
        freeList.push_back(block);
    }
};
```

#### 2. 使用栈分配替代堆分配

```cpp
// 栈上分配，无碎片
std::array<int, 100> arr;

// 使用 arena/region 分配器
char buffer[4096];
// 在 buffer 上线性分配，整体释放
```

#### 3. 智能指针和 RAII

减少手动 new/delete，降低碎片产生概率。

#### 4. 定制分配器

```cpp
// STL 容器使用自定义分配器
template <typename T>
struct PoolAllocator {
    using value_type = T;
    T* allocate(size_t n);
    void deallocate(T* p, size_t n);
};

std::vector<int, PoolAllocator<int>> vec;
```

#### 5. 减少频繁分配

- 使用 `reserve()` 预分配容器空间
- 使用 `std::vector` 替代 `std::list`（连续内存）
- 复用对象而非反复创建销毁

---

### 8. 内存泄漏有哪些解决方法

#### 1. 智能指针（推荐）

```cpp
#include <memory>

void noLeak() {
    auto p = std::make_unique<int>(42);
    auto arr = std::make_unique<int[]>(100);
}
// 自动释放，不会泄漏
```

#### 2. RAII 惯用法

```cpp
class FileGuard {
    FILE* fp;
public:
    FileGuard(const char* path, const char* mode)
        : fp(fopen(path, mode)) {}
    ~FileGuard() {
        if (fp) fclose(fp);
    }
    FileGuard(const FileGuard&) = delete;
    FileGuard& operator=(const FileGuard&) = delete;
};
```

#### 3. 内存检测工具

| 工具 | 平台 | 用途 |
|------|------|------|
| Valgrind | Linux | 检测内存泄漏、越界访问 |
| AddressSanitizer | 跨平台 | 编译器内嵌检测 |
| LeakSanitizer | 跨平台 | 专注泄漏检测 |
| Visual Studio CRT | Windows | `_CrtDumpMemoryLeaks()` |
| Dr. Memory | Windows/Linux | 动态内存检测 |

```cpp
// AddressSanitizer 使用
// g++ -fsanitize=address -g main.cpp

// Visual Studio 检测
#define _CRTDBG_MAP_ALLOC
#include <crtdbg.h>
int main() {
    _CrtSetDbgFlag(_CRTDBG_ALLOC_MEM_DF | _CRTDBG_LEAK_CHECK_DF);
}
```

#### 4. 编码规范

- 遵循"谁分配谁释放"原则
- 使用 `new`/`delete` 成对出现
- 析构函数中释放所有资源
- 基类析构函数声明为 `virtual`

---

### 9. 智能指针有哪些，如何做到自动管理内存的，怎么做到自动释放的

#### C++11 三种智能指针

##### std::unique_ptr

独占所有权，不可复制，只能移动。

```cpp
#include <memory>

// 创建
auto p1 = std::make_unique<int>(42);
// auto p2 = p1;                  // 编译错误：不可复制
auto p3 = std::move(p1);          // 所有权转移，p1 变为 nullptr

// 数组版本
auto arr = std::make_unique<int[]>(100);
arr[0] = 10;
```

**自动释放原理：** `unique_ptr` 在析构函数中调用 `delete`（或 `delete[]`），离开作用域时自动触发。

##### std::shared_ptr

共享所有权，通过引用计数管理生命周期。

```cpp
auto p1 = std::make_shared<int>(42);
auto p2 = p1;
auto p3 = p1;

std::cout << p1.use_count() << std::endl;
// 所有 shared_ptr 销毁后，引用计数归零，自动 delete
```

**自动释放原理：**
- 每次拷贝，引用计数 +1
- 每次析构，引用计数 -1
- 引用计数归零时，调用 `delete` 释放内存

```
p1 ──┐
     ├──> 控制块 ──> 引用计数 = 3
p2 ──┤         ──> 管理的对象 (int 42)
     │
p3 ──┘
```

##### std::weak_ptr

弱引用，不增加引用计数，用于打破循环引用。

```cpp
auto shared = std::make_shared<int>(42);
std::weak_ptr<int> weak = shared;

// 使用前需要提升为 shared_ptr
if (auto locked = weak.lock()) {
    std::cout << *locked << std::endl;
}
```

#### 循环引用问题

```cpp
class Node {
public:
    std::shared_ptr<Node> next;
    ~Node() { std::cout << "Node destroyed" << std::endl; }
};

auto a = std::make_shared<Node>();
auto b = std::make_shared<Node>();
a->next = b;
b->next = a;
// 循环引用！引用计数永远不为 0，内存泄漏

// 解决：使用 weak_ptr
class Node2 {
public:
    std::weak_ptr<Node2> next;
    ~Node2() { std::cout << "Node2 destroyed" << std::endl; }
};
```

#### RAII 机制

智能指针的核心是 **RAII（Resource Acquisition Is Initialization）**：

1. **资源获取即初始化**：在构造函数中获取资源
2. **析构函数释放资源**：对象生命周期结束时自动释放
3. **利用栈对象的确定性销毁**：编译器保证析构函数一定被调用

```cpp
template <typename T>
class UniquePtr {
    T* ptr;
public:
    explicit UniquePtr(T* p = nullptr) : ptr(p) {}
    ~UniquePtr() { delete ptr; }

    UniquePtr(const UniquePtr&) = delete;
    UniquePtr& operator=(const UniquePtr&) = delete;

    UniquePtr(UniquePtr&& other) noexcept : ptr(other.ptr) {
        other.ptr = nullptr;
    }

    T& operator*() { return *ptr; }
    T* operator->() { return ptr; }
};
```

#### 智能指针选择指南

| 场景 | 推荐 |
|------|------|
| 独占所有权 | `unique_ptr` |
| 共享所有权 | `shared_ptr` |
| 打破循环引用 | `weak_ptr` |
| 临时观察 | `weak_ptr` |
| 数组管理 | `unique_ptr<T[]>` |

---

## 扩展问题

面试官可能会追问：
- malloc/free 和 new/delete 的区别是什么？
- 什么是内存对齐？为什么需要内存对齐？
- shared_ptr 的控制块中还有什么信息？
- 如何实现线程安全的引用计数？
- 什么是 placement new？

---

## 来源

开立医疗 - C++软件工程师面经
