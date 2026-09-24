+++
title = '侵入式链表与container_of原理'
date = 2026-09-23T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['侵入式链表', 'container_of', 'offsetof', '内核链表', '数据结构']
+++

# 侵入式链表与container_of原理

## 题目

什么是侵入式链表？它和普通链表有什么区别？如何通过 container_of 从链表节点指针拿到它所在的宿主结构体？

## 考察点

侵入式数据结构的设计思想、offsetof 与 container_of 宏的实现原理、结构体成员地址布局、Linux 内核 list_head 与 RTOS 中的实际应用。

## 回答要点

### 1. 从普通链表的痛点说起

教科书链表把数据塞进节点里：

```c
typedef struct node {
    int data;               // 数据类型定死在节点里
    struct node *next;
} node_t;
```

两个天生缺陷：

1. **与数据类型耦合**：换一种数据类型就要重写一整套插入/删除/遍历代码；改成 `void*` 存数据又丢了类型安全，还要为每个节点单独 malloc/free；
2. **一个结构体只能挂一条链**：想让一个对象同时在"就绪队列"和"超时队列"里，普通链表很难表达。

### 2. 侵入式链表的核心思想

侵入式链表把方向反过来：**链表节点不再包着数据，而是作为一个成员"嵌入"宿主结构体**。节点本身只有前后指针，不含任何数据：

```c
typedef struct list_head {
    struct list_head *prev;
    struct list_head *next;
} list_head_t;

typedef struct {
    int id;
    char name[16];
    list_head_t node;       // 链表节点嵌入宿主结构体
} student_t;
```

谁想进链表，谁就在自己结构体里放一个 `list_head_t` 成员——这就是"侵入"的含义。链表操作代码只搬动 `list_head_t`，对数据类型完全无感。

| 维度 | 普通链表（数据内嵌） | 侵入式链表（节点嵌入宿主） |
|------|-------------------|------------------------|
| 节点定义 | `node { data; next; }` | `list_head { prev; next; }`，宿主里放一个成员 |
| 内存分配 | 每个节点单独 malloc/free | 宿主整体分配，零额外节点分配 |
| 类型通用性 | 每类重写一套操作，或用 void* | 一套链表代码服务所有类型 |
| 类型安全 | void* 丢失类型 | container_of 编译期还原类型 |
| 已知节点删除 | 单链表要找前驱，O(n) | 前后指针都在手上，O(1) |
| 一物多链 | 困难 | 放多个 list_head 成员即可挂多条链 |
| 典型场景 | 教科书、业务数据结构 | 内核对象管理、RTOS 就绪链、内存池空闲链 |

### 3. 关键机制：offsetof 与 container_of

节点指针只知道自己在哪，怎么找回宿主？靠**成员在结构体内的偏移量是编译期确定的**这一事实：

```c
#define offsetof(TYPE, MEMBER) ((size_t)&((TYPE *)0)->MEMBER)
```

把 0 强转成 `TYPE *` 当作"位于地址 0 的宿主"，取其 MEMBER 成员的地址——这个地址值恰好就是 MEMBER 相对宿主起始处的偏移。它不会真的解引用地址 0，只是编译期算地址。

有了偏移量，反过来减一下就得到宿主指针：

```c
#define container_of(ptr, TYPE, MEMBER) \
    ((TYPE *)((char *)(ptr) - offsetof(TYPE, MEMBER)))
```

图示：

```
宿主起始地址 ──┬──────────────────────────────┐
               │ id / name / ...              │
               │ ← offsetof(student_t, node) →│
               │ ┌──────────────┐             │
               │ │ list_head_t  │ ← ptr（已知节点地址）
               │ └──────────────┘             │
宿主地址 = ptr - offsetof(student_t, node)
```

### 4. 完整可运行示例

```c
#include <stdio.h>
#include <stddef.h>

typedef struct list_head {
    struct list_head *prev;
    struct list_head *next;
} list_head_t;

#define LIST_HEAD_INIT(name) { &(name), &(name) }
#define LIST_HEAD(name)      list_head_t name = LIST_HEAD_INIT(name)

static void list_init(list_head_t *head)
{
    head->prev = head;
    head->next = head;
}

static void list_add_tail(list_head_t *n, list_head_t *head)
{
    n->next = head;
    n->prev = head->prev;
    head->prev->next = n;
    head->prev = n;
}

static void list_del(list_head_t *entry)
{
    entry->prev->next = entry->next;
    entry->next->prev = entry->prev;
}

#define container_of(ptr, TYPE, MEMBER) \
    ((TYPE *)((char *)(ptr) - offsetof(TYPE, MEMBER)))

#define list_for_each_entry(pos, head, member)                           \
    for (pos = container_of((head)->next, typeof(*pos), member);         \
         &pos->member != (head);                                         \
         pos = container_of(pos->member.next, typeof(*pos), member))

typedef struct {
    int id;
    char name[16];
    list_head_t node;
} student_t;

LIST_HEAD(stu_list);

int main(void)
{
    student_t a = { 1, "Alice" };
    student_t b = { 2, "Bob" };

    list_add_tail(&a.node, &stu_list);
    list_add_tail(&b.node, &stu_list);

    student_t *pos;
    list_for_each_entry(pos, &stu_list, node)
        printf("id=%d name=%s\n", pos->id, pos->name);

    list_del(&a.node);
    return 0;
}
```

输出：

```
id=1 name=Alice
id=2 name=Bob
```

`list_for_each_entry` 把 container_of 藏进遍历宏：迭代变量直接是宿主指针 `pos`，业务代码完全感知不到节点的存在。已知 `&a.node` 删除时不需要遍历找前驱，这就是"O(1) 删除"。

### 5. 在内核与 RTOS 中的实际应用

- **Linux 内核**：`list_head` 是内核最基础的数据结构，`task_struct` 里嵌了多个 list_head，同一个进程能同时挂在就绪队列、父子链、哈希桶等多条链上；`work_struct`、`kobj` 等机制同样靠它串接，见《work_struct与delayed_work延迟工作队列》
- **FreeRTOS**：就绪/延时列表用的 `ListItem_t`（含 `pxNext`、`pxPrevious`、`pvContainer`）就是侵入式设计，任务控制块 TCB 里放着列表项，调度器搬列表项即完成任务切换登记
- **RT-Thread**：`rt_list_node` 同构于 list_head；内存池的空闲块也常用侵入式空闲链串起来——空闲块自己就是链表节点，不需要额外管理内存

### 6. 使用注意与可移植性

- **offsetof 手工版依赖"空指针偏移"技巧**，属未定义行为的形式，但被所有主流编译器接受；标准 C 里 `<stddef.h>` 直接提供 offsetof，优先用库版本
- **typeof 是 GCC/Clang 扩展**：MSVC 不支持，需要遍历时要么显式传类型，要么用宿主内偏移换算的其他写法——这是侵入式链表跨平台时最常见的坑
- **container_of 无任何校验**：传入野指针、传错 MEMBER 名都编译不报错、运行期静默出错；内核版宏额外做了 `__same_type` 类型一致性检查
- **调试直观性差**：看不到"链表里有什么"，需要靠 offsetof 换算心智模型，或者借助调试器脚本

### 7. 一句话总结

**侵入式链表 = 只含前后指针的节点嵌入宿主结构体 + offsetof 算偏移 + container_of 反解宿主**；代价是"侵入"宿主定义，换来零分配、O(1) 删除、一套代码管所有类型和一物多链，所以成为内核与 RTOS 对象管理的标配。

## 扩展问题

- container_of 在延迟工作队列中的应用 → 详见《work_struct与delayed_work延迟工作队列》
- 数组与链表的选型对比 → 详见《数组与链表的区别》
- 结构体成员布局受对齐规则影响 → 详见《结构体内存对齐与pragma pack》
- FreeRTOS 列表项与调度 → 详见《FreeRTOS任务抢占与调度机制》
