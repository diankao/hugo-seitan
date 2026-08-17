+++
title = 'C++并发编程层次从thread到QtConcurrent'
date = 2026-06-12T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['C++', '多线程', 'future', '线程池', 'QtConcurrent', '并发编程']
+++

# C++并发编程层次：从thread到QtConcurrent

## 题目

async、线程池为什么和 future、concurrent 有关？这些东西和 thread 的级别/场景是什么关系？

## 考察点

C++ 并发编程体系的整体认知、各层封装的关系与演进动机、不同场景下的选型。

## 回答要点

### 1. 层次关系总览

它们不是并列关系，而是**层层封装**的层次关系：

```
┌─────────────────────────────────────┐
│  QtConcurrent / QFuture（最高层封装）│ ← 批量并行、进度监控、回调链
├─────────────────────────────────────┤
│  std::async / 线程池（中层封装）     │ ← 提交任务，自动返回 future
├─────────────────────────────────────┤
│  std::future / promise（结果传递）   │ ← 异步拿结果的"容器"
├─────────────────────────────────────┤
│  std::thread（最底层原语）           │ ← 就是创建一个线程
└─────────────────────────────────────┘
```

每一层都是在下一层基础上，解决上一层的痛点：

| 痛点 | 谁解决的 |
|------|---------|
| 子线程结果怎么传回主线程？ | `future` |
| 手写 thread+promise 太麻烦？ | `async` / 线程池 |
| 频繁创建销毁线程开销大？ | 线程池（复用线程） |
| 大量任务要批量并行+看进度？ | `QtConcurrent` |

### 2. 第0层：std::thread —— 最原始的线程

`thread` 只管"在新线程跑代码"，**不管结果怎么拿回来**。

```cpp
std::thread t([]{
    int result = doWork();
    // 问题：result 怎么传回主线程？
});
// 只能通过全局变量/引用传结果，很容易出竞态条件
```

### 3. 第1层：future —— 解决"结果怎么传回来"

`future` 是一个**异步结果的容器**，它本身不创建线程，只是一个"放结果的盒子"。

```cpp
// promise 是"写入端"，future 是"读取端"
std::promise<int> p;
std::future<int> f = p.get_future();  // 拿到读取端

std::thread t([&p]{
    p.set_value(42);  // 子线程把结果放进去
});

int v = f.get();  // 主线程取出来（阻塞等待）
t.join();
```

**为什么 future 和 thread 有关**：多线程最大的痛点之一就是"子线程算完的结果怎么安全地传回主线程"，future 就是专门解决这个问题的。

### 4. 第2层：async / 线程池 —— 把 thread + future 打包

每次手写 `thread` + `promise` + `future` 太麻烦，所以封装了更高层的接口。

#### 4.1 std::async = 自动创建线程 + 自动创建 promise/future

```cpp
// std::async 帮你做了三件事：
// 1. 创建线程
// 2. 创建 promise
// 3. 返回 future
std::future<int> f = std::async(std::launch::async, []{ return 42; });
int v = f.get();  // 等价于手写 thread+promise 那一坨
```

#### 4.2 线程池 = 复用线程 + 自动管理 future

```cpp
// 线程池更进一步：不是每次新建线程，而是复用已有线程
pool.submit([]{ return 42; });  // 内部用 packaged_task 生成 future
```

#### 4.3 三者对比

| | std::thread | std::async | 线程池 |
|--|------------|------------|--------|
| 线程创建 | 每次新建 | 每次新建 | 复用固定数量 |
| 结果获取 | 手动搞 | 自动返回 future | 自动返回 future |
| 资源开销 | 创建/销毁开销 | 创建/销毁开销 | 一次创建持续复用 |
| 并发控制 | 无 | 无 | 可控（固定线程数） |
| 适用 | 极少数场景 | 少量异步任务 | 大量短任务 |

### 5. 第3层：QtConcurrent —— 再封装"批量并行"

Qt 在线程池 + future 基础上，又封装了"提交一批任务"的能力：

```cpp
// QtConcurrent = 线程池 + future + 批量 + 进度监控
QFuture results = QtConcurrent::mapped(list, transformFunc);
//            ↑ 自动用 Qt 全局线程池
//                   ↑ 自动批量分发
//         ↑ 自动返回所有结果
```

### 6. 场景选型速查

| 场景 | 用什么 | 原因 |
|------|--------|------|
| 只需要一个后台线程跑个任务 | `std::thread` | 简单直接，但结果难传回 |
| 后台任务需要拿结果 | `std::async` | 自动返回 future |
| 大量短任务并发 | 线程池 | 复用线程，避免频繁创建销毁 |
| Qt 项目 UI 相关异步 | `QtConcurrent` + `QFutureWatcher` | `finished` 信号天然结合事件循环 |
| 批量数据处理/映射 | `QtConcurrent::mapped` | 一行代码批量并行 |
| 需要进度/取消/暂停 | Qt6 `QFuture` | 原生支持 progress/cancel/pause |

### 7. 一句话总结

> **thread** 是底层原语 → **future** 解决结果传回 → **async/线程池** 把两者打包简化使用 → **QtConcurrent** 再封装成批量并行 + 进度监控

它们是**层层封装**的关系，不是并列关系。每一层解决上一层的痛点。
