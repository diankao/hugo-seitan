+++
title = '空指针NULL、nullptr与void指针对比'
date = 2026-05-11T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['C++', 'nullptr', 'NULL', 'void指针', '类型安全', 'C++11']
+++

# 空指针NULL、nullptr与void指针对比

## 题目

C++11中用 `nullptr` 替代 `NULL` 更安全，为什么？`void*` 和 `nullptr` 的区别是什么？

## 考察点

`NULL` 的定义缺陷、函数重载歧义、`nullptr` 的类型系统设计、`void*` 的角色与限制。

## 回答要点

### 1. 三者定位

| | `NULL` | `nullptr` | `void*` |
|---|--------|-----------|---------|
| 本质 | 宏 | 关键字 | 指针类型 |
| 用途 | 表示空指针 | 表示空指针 | 指向未知类型的指针 |
| 类型 | `int`（C++中） | `std::nullptr_t` | `void*`（泛型指针） |
| C++11 | 存在缺陷 | ✅ 推荐使用 | 仍可用，但限制增多 |

**一句话区分**：`NULL` 是"假的空指针"（类型是 int），`nullptr` 是"真正的空指针"（专有类型），`void*` 是"不知道指向什么的指针"（有地址但类型未知）。

### 2. NULL 的本质问题

`NULL` 在 C/C++ 中不是一个真正的关键字，而是一个宏定义：

```c
// 不同编译器的定义可能不同
// <cstddef> 或 <stddef.h>
#define NULL  0           // C++ 中通常是这个
#define NULL  ((void*)0)  // C 中通常是这个
```

**核心问题：`NULL` 的类型是 `int`（在 C++ 中），不是指针类型。**

```cpp
void func(int value) {
    std::cout << "调用了 int 版本" << std::endl;
}

void func(int* ptr) {
    std::cout << "调用了指针版本" << std::endl;
}

int main() {
    func(NULL);    // 调用了 int 版本！不是指针版本！
    func(0);       // 调用了 int 版本
    func(nullptr); // 调用了指针版本 ✓

    return 0;
}
```

### 3. 函数重载歧义

这是 `NULL` 最致命的问题——当存在重载函数时，`NULL` 会匹配到错误的版本：

```cpp
class Logger {
public:
    void log(const char* msg) {
        std::cout << "字符串: " << msg << std::endl;
    }

    void log(int level) {
        std::cout << "级别: " << level << std::endl;
    }
};

int main() {
    Logger logger;

    // 想传空指针，结果传了整数 0
    logger.log(NULL);     // 输出 "级别: 0"，调错了！
    logger.log(nullptr);  // 输出 "字符串: 0x0"，正确

    return 0;
}
```

**更危险的场景——模板推导：**

```cpp
template<typename T>
void process(T value) {
    std::cout << "T 的类型是: " << typeid(T).name() << std::endl;
}

int main() {
    process(NULL);     // T 被推导为 int，不是指针
    process(nullptr);  // T 被推导为 std::nullptr_t

    return 0;
}
```

如果模板内部对 `T` 做了指针相关的操作（如解引用），传 `NULL` 会编译报错或运行崩溃。

### 4. nullptr 的设计

`nullptr` 是 C++11 引入的**关键字**，它的类型是 `std::nullptr_t`：

```cpp
// C++11 标准定义（简化）
namespace std {
    typedef decltype(nullptr) nullptr_t;
}

// nullptr 的核心特性
const std::nullptr_t nullptr = {};
```

#### 4.1 nullptr 的类型转换规则

```cpp
// nullptr 可以隐式转换为任意指针类型
int*    p1 = nullptr;     // OK → int*
double* p2 = nullptr;     // OK → double*
void (*fp)() = nullptr;   // OK → 函数指针
int C::* mp = nullptr;    // OK → 成员指针

// 但不能转换为整数
int n = nullptr;           // 编译错误！
bool b = nullptr;          // 编译错误！（不是零初始值）

// 可以和 bool 比较
if (nullptr) { }           // false，但有些编译器会警告
if (p1 == nullptr) { }     // OK，标准用法
```

#### 4.2 转换优先级

```
nullptr_t → 任意指针类型  （隐式转换，优先级高）
nullptr_t → bool          （仅条件上下文中）
nullptr_t → 整数          （不允许！）
```

### 5. void* 的角色与限制

`void*` 是一种**泛型指针**，可以指向任意类型的数据，但不知道具体类型。

#### 5.1 void* 的用途

```c
// C 语言中 void* 是实现泛型编程的核心手段

// 1. malloc 返回 void*
void* p = malloc(100);
int* pi = (int*)p;

// 2. memset / memcpy 等函数使用 void*
void* memcpy(void* dest, const void* src, size_t n);

// 3. qsort 的比较函数使用 void*
int cmp(const void* a, const void* b) {
    return *(int*)a - *(int*)b;
}

// 4. 线程函数参数
void* thread_func(void* arg);
```

#### 5.2 void* 的限制

```cpp
// 1. 不能解引用（编译器不知道指向的数据大小）
void* vp = &x;
*vp;                // 编译错误！
*(int*)vp;          // OK，必须先强制转换

// 2. 不能做指针算术
vp + 1;             // 编译错误！编译器不知道步长
(int*)vp + 1;       // OK，步长为 sizeof(int)

// 3. 不能直接赋给其他类型的指针（C++ 中）
void* vp = &x;
int* ip = vp;       // C: OK  C++: 编译错误！
int* ip = (int*)vp; // OK，需要显式转换

// 4. C++ 中不能用 void* 指向成员函数
class Foo { void bar(); };
void (Foo::*fp)() = &Foo::bar;
void* vp = (void*)fp;  // 未定义行为！成员函数指针可能不是普通地址
```

#### 5.3 void* vs nullptr 的关系

```cpp
// nullptr 可以转为 void*
void* vp = nullptr;  // OK，nullptr 可以转为任意指针类型

// void* 变量可以被赋为 nullptr 表示"当前不指向任何东西"
void* vp = malloc(100);
// ... 使用 vp ...
free(vp);
vp = nullptr;  // 防止悬空指针

// 但 void* 不是 nullptr
// void* 是一个有类型的指针（只是不知道指向什么类型的数据）
// nullptr 是一个没有地址的值（不指向任何对象）
```

### 6. 四者完整对比

| 方面 | `NULL` | `0` | `nullptr` | `void*` |
|------|--------|-----|-----------|---------|
| 本质 | 宏（`#define NULL 0`） | 整数字面量 | 关键字 | 指针类型 |
| 类型 | `int` | `int` | `std::nullptr_t` | `void*` |
| 函数重载 | 匹配 `int` 版本 | 匹配 `int` 版本 | **匹配指针版本** | 匹配 `void*` 版本 |
| 模板推导 | `T = int` | `T = int` | `T = std::nullptr_t` | `T = void*` |
| 跨平台 | 定义不统一 | 统一 | **统一（关键字）** | 统一 |
| 可读性 | "空指针"但类型不对 | "零"不是"空指针" | **语义明确：空指针** | 泛型指针 |
| 能否解引用 | N/A | N/A | ❌ | ❌（需转换） |
| C 兼容 | ✅ | ✅ | ❌（C23 才引入） | ✅ |
| 典型用途 | 表示空指针 | 数值零 | **表示空指针** | 泛型/类型擦除 |

### 7. 实际工程中的坑

#### 7.1 嵌入式中的 NULL 宏冲突

```cpp
// 某些嵌入式头文件可能重定义 NULL
#ifdef NULL
#undef NULL
#endif
#define NULL ((void*)0)   // C 风格定义

// 在 C++ 中，这会导致：
void func(int);
void func(char*);

func(NULL);  // 歧义！((void*)0) 可以转 int 也可以转 char*
```

用 `nullptr` 完全避免这个问题——它是关键字，不受宏定义影响。

#### 7.2 auto 推导

```cpp
auto p1 = NULL;     // p1 的类型是 int，不是指针！
auto p2 = nullptr;  // p2 的类型是 std::nullptr_t
auto p3 = (void*)0; // p3 的类型是 void*

// 后续使用
*p1;  // 编译错误：不能解引用 int
*p2;  // 编译错误：std::nullptr_t 不支持解引用（符合预期）
*p3;  // 编译错误：不能解引用 void*（需先转换）

// p2 和 p3 可以赋给任意指针
int* p4 = p2;  // OK
int* p5 = p3;  // C++ 中编译错误！void* 不能隐式转 int*
```

#### 7.3 void* 在 C++ 中应尽量避免

```cpp
// C 风格：用 void* 实现泛型
void sort(void* base, size_t nmemb, size_t size,
          int (*cmp)(const void*, const void*));

// C++ 风格：用模板代替 void*
template<typename RandomIt, typename Compare>
void sort(RandomIt first, RandomIt last, Compare comp);

// 模板的优势：
// 1. 类型安全（编译期检查）
// 2. 无需手动强转
// 3. 可能内联优化
```

### 8. 总结

```
NULL 的问题：
  1. 类型是 int，不是指针 → 重载匹配错误
  2. 宏定义，跨平台不统一
  3. 模板推导出 int 类型

nullptr 的解决：
  1. 独立类型 std::nullptr_t → 重载匹配正确
  2. 关键字，无宏问题
  3. 可隐式转为任意指针类型，不能转为整数
  4. 语义明确，代码可读性更好

void* 的定位：
  1. 泛型指针，可指向任意类型数据
  2. 不能解引用，不能做指针算术
  3. C 中实现泛型的核心手段，C++ 中应优先用模板
  4. nullptr 可以转为 void*，但 void* 不是空指针

一句话速记：
  NULL → 假的空指针（类型是 int）
  nullptr → 真正的空指针（专有类型）
  void* → 不知道类型的指针（有地址但类型未知）
```
