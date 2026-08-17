+++
title = 'sizeof与strlen的区别'
date = 2026-02-28T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['C语言', 'sizeof', 'strlen', '字符串']
+++

# sizeof与strlen的区别

## 题目

sizeof 和 strlen 对字符串的区别是什么？修改字符串后两者的行为还一样吗？

## 考察点

编译时与运行时的区别、数组与指针的 sizeof 差异、函数参数退化。

## 回答要点

### 1. 核心区别

| | `sizeof` | `strlen` |
|---|---------|----------|
| 本质 | **运算符**（关键字） | **函数**（`<string.h>`） |
| 计算时机 | **编译时** | **运行时** |
| 计算对象 | 变量/类型占用的**内存大小** | 字符串的**实际长度**（到第一个 `\0`） |
| 是否含 `\0` | ✅ 包含 | ❌ 不包含 |
| 对 `NULL` | 不允许（编译错误） | 未定义行为（通常崩溃） |

```c
char str[] = "hello";
sizeof(str);  // 6（5个字符 + 1个'\0'）
strlen(str);  // 5（不含'\0'）
```

### 2. 修改字符串后行为不同

```c
char str[] = "hello";

str[0] = 'H';
sizeof(str);  // 6（不变，数组大小编译时就定了）
strlen(str);  // 5（不变，长度还是到第一个'\0'）

str[2] = '\0';
sizeof(str);  // 6（不变！数组大小不因内容改变）
strlen(str);  // 2（变了！从开头到第一个'\0'只有"He"）

strcpy(str, "world!");
sizeof(str);  // 6（不变！数组大小固定）
strlen(str);  // 会越界读取！str 只有 6 字节，"world!" 占 7 字节（含\0），
              // 实际写入了 7 字节，'\0' 写到了数组外面
```

**关键理解**：`sizeof` 在编译时就确定了，它看的是声明时的大小；`strlen` 在运行时从头遍历到第一个 `\0`，字符串内容变了结果就变。

### 3. 数组 vs 指针（最常见的坑）

```c
char str[] = "hello";     // 数组
char *ptr  = "hello";     // 指针（指向字符串字面量）

sizeof(str);  // 6（整个数组的大小）
sizeof(ptr);  // 4（32位）或 8（64位）—— 指针本身的大小，不是字符串长度
strlen(str);  // 5
strlen(ptr);  // 5（strlen 不关心数组还是指针，只从地址开始找'\0'）
```

### 4. 函数参数退化

```c
void func(char param[]) {
    // 数组参数退化为指针！
    sizeof(param);  // 4 或 8（指针大小，不是数组大小）
    strlen(param);  // 正常运行时计算
}

char arr[] = "hello";
func(arr);
// 调用前：sizeof(arr) = 6
// 函数内：sizeof(param) = 4 或 8
```

**原因**：C 语言中数组作为函数参数时，退化为指向首元素的指针。编译器丢失了数组长度信息。

### 5. 各种场景对比

```c
char s[] = "hello";
sizeof(s);        // 6
strlen(s);        // 5

char *p = s;
sizeof(p);        // 4 或 8（指针大小）
strlen(p);        // 5

char s2[10] = "hi";
sizeof(s2);       // 10（声明了 10 字节就是 10 字节）
strlen(s2);       // 2（到第一个'\0'）

char s3[] = {'a', 'b', 'c'};
sizeof(s3);       // 3（没有'\0'，就是 3 个 char）
strlen(s3);       // 不确定！没有'\0'，会一直读到内存中碰巧的 0x00

const char *msg = "hello\0world";
sizeof(msg);      // 4 或 8（指针大小）
strlen(msg);      // 5（遇到第一个'\0'就停）
```

### 6. sizeof 的其他用途

```c
sizeof(int);           // 4
sizeof(char);          // 1（C 标准规定 sizeof(char) == 1）
sizeof(double);        // 8
sizeof(void *);        // 4 或 8
sizeof(struct {...});   // 结构体大小（含对齐填充）

int arr[10];
sizeof(arr);           // 40（10 × 4）
sizeof(arr) / sizeof(arr[0]);  // 10（数组元素个数，经典写法）

// C++ 中
sizeof(nullptr);       // 和 sizeof(void*) 相同
sizeof("hello");       // 6（字符串字面量是 char[6] 类型）
```

### 7. 面试速记

- **sizeof**：编译时运算符，看声明大小，含 `\0`，数组/指针结果不同
- **strlen**：运行时函数，遍历到 `\0`，不含 `\0`，不区分数组/指针
- **最大坑**：函数参数中数组退化为指针，`sizeof` 变成指针大小
- **修改字符串**：`sizeof` 不变（编译时固定），`strlen` 可能变（运行时重算）
- **经典用法**：`sizeof(arr)/sizeof(arr[0])` 求数组元素个数（仅对数组有效，指无效）
