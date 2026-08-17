+++
title = 'std::future与QFuture用法对比'
date = 2026-06-12T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['C++', 'Qt', 'future', '异步编程', 'QtConcurrent']
+++

# std::future与QFuture用法对比

## 题目

聊聊 std::future 和 Qt 的 QFuture 的用法？

## 考察点

C++ 标准库异步编程机制、Qt 异步编程体系、两种 future 的核心差异与选型。

## 回答要点

### 1. std::future（C++11）

`std::future` 是标准库提供的异步结果获取机制，本身**不能直接创建**，需要配合异步任务产生。

#### 1.1 三种获取方式

```cpp
#include <future>

// 方式1：std::async —— 最简单
std::future<int> f1 = std::async(std::launch::async, []{
    return 42;  // 在新线程执行
});
int v1 = f1.get();  // 阻塞等待结果

// 方式2：std::promise —— 手动设值，适合跨线程传结果
std::promise<int> p;
std::future<int> f2 = p.get_future();
std::thread t([&p]{
    p.set_value(100);  // 子线程设值
});
int v2 = f2.get();  // 主线程取值
t.join();

// 方式3：std::packaged_task —— 包装可调用对象
std::packaged_task<int(int)> task([](int x){ return x * 2; });
std::future<int> f3 = task.get_future();
std::thread(std::move(task), 21).detach();
int v3 = f3.get();
```

#### 1.2 关键方法

| 方法 | 行为 |
|------|------|
| `get()` | 阻塞等待并取结果，只能调一次 |
| `wait()` | 阻塞等待，不取结果 |
| `wait_for(timeout)` | 等待指定时间，返回 status |
| `valid()` | 是否关联了共享状态 |

#### 1.3 局限性

`std::future` 不支持**回调链**（then）、不支持**组合**（when_all/when_any），这些需要手动管理或借助第三方库（如 Facebook 的 Folly::Future）。C++20 的 `std::future` 仍未加入 `then`。

### 2. QFuture（Qt）

`QFuture` 是 Qt 自己的异步结果类，配合 `QtConcurrent` 或 `QFutureWatcher` 使用。

#### 2.1 基本用法

```cpp
#include <QtConcurrent>
#include <QFuture>

// 方式1：QtConcurrent::run —— 在线程池执行
QFuture<int> future = QtConcurrent::run([]{
    return heavyComputation();
});

// 阻塞获取（和 std::future 类似）
int result = future.result();

// 方式2：QtConcurrent::mapped —— 批量并行处理
QList<int> inputs = {1, 2, 3, 4, 5};
QFuture<int> futures = QtConcurrent::mapped(inputs, [](int x){
    return x * x;
});
QList<int> results = futures.results();  // [1, 4, 9, 16, 25]
```

#### 2.2 QFutureWatcher —— 非阻塞通知

这是 `std::future` 没有的能力，可以**监听异步任务完成**并发 Qt 信号：

```cpp
QFutureWatcher<int> *watcher = new QFutureWatcher<int>;

// 任务完成时自动触发（Qt 信号槽）
QObject::connect(watcher, &QFutureWatcher<int>::finished, []{
    qDebug() << "任务完成！";
});

QFuture<int> future = QtConcurrent::run([]{
    return heavyWork();
});

watcher->setFuture(future);  // 绑定监听
// 主线程不阻塞，继续处理 UI 事件
```

#### 2.3 Qt6 新增：then 回调链

Qt6 给 `QFuture` 加了 `then()`，支持链式回调：

```cpp
// Qt6：链式回调
QtConcurrent::run([]{ return 10; })
    .then([](int v){ return v * 2; })       // 20
    .then([](int v){ qDebug() << v; });      // 输出 20
```

### 3. 核心对比

| 特性 | std::future | QFuture |
|------|-------------|---------|
| 阻塞取结果 | `get()` | `result()` |
| 取多次 | 不行（get 只能一次） | `results()` 可以 |
| 完成回调 | 无原生支持 | `QFutureWatcher::finished` 信号 |
| 回调链 then | 无（C++20 也没加） | Qt6 原生支持 |
| 批量并行 | 需自己写 | `QtConcurrent::mapped` 直接支持 |
| 取消任务 | 不支持 | `cancel()` / `pause()` |
| 进度查询 | 不支持 | `progressValue()` / `progressMaximum()` |
| 线程池 | 需自己管理 | 自动用 Qt 全局线程池 |
| 异常传递 | `get()` 重新抛出 | `result()` 抛出（Qt6 起支持） |

### 4. 选型建议

| 场景 | 推荐 | 原因 |
|------|------|------|
| 纯 C++ 项目 / 嵌入式 | `std::future` + `std::async` | 不引入额外依赖 |
| Qt 项目中 UI 相关异步 | `QFuture` + `QFutureWatcher` | `finished` 信号天然结合 Qt 事件循环，不用手动切线程更新 UI |
| 需要回调链 / 进度监控 | Qt6 `QFuture` | 原生 `then`、`progressValue` |
| 需要取消 / 暂停任务 | Qt6 `QFuture` | `cancel()` / `pause()` |
| 自定义线程池 | `std::future` + `packaged_task` | 配合自写线程池使用 |

**一句话总结**：`std::future` 是最基础的异步原语，`QFuture` 在 Qt 生态里做了更多上层封装（Watcher 通知、进度监控、批量并行、链式回调），UI 项目里更好用。
