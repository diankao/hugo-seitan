+++
title = 'Qt与Electron的进程模型对比'
date = 2026-09-20T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['Qt', 'Electron', '进程模型', 'QProcess', 'QLocalServer']
+++

# Qt与Electron的进程模型对比

## 题目

为什么 Electron 程序一打开动辄十几个进程，而 Qt 程序通常只有一个？Qt 是不是不适合多进程架构？

## 考察点

Chromium 多进程架构的动机（沙箱与不可信内容）、Qt 的线程优先文化与信号槽总线、进程数量由宿主内容决定的规律、QProcess/QLocalSocket 拆分积木、多进程的固定成本。

## 回答要点

### 1. Electron 的进程群是框架自带的

Electron 等于直接内嵌一个 Chromium，任务管理器里那十几个进程是 Chromium 的固定班底：

| 进程 | 职责 |
|------|------|
| browser 进程 | UI、窗口、协调中枢 |
| renderer 进程 ×N | 每个页面/标签一个，跑不可信的 web 内容 |
| GPU 进程 | 所有合成与绘制 |
| network / storage 等 utility 进程 | 网络与磁盘 IO 服务化 |

renderer 必须独立成进程，因为它宿主的是**不可信的第三方代码**——网页、扩展、别人的 JS，必须关沙箱、崩溃只死自己。用"拆进程四信号"（第三方代码、异构运行时、崩溃不可连坐、独立重启）一套，全中。所以 Electron 程序的进程边界**不是应用作者的架构选择，是 Chromium 的安全架构**——任务管理器里看到的是它的沙箱围墙。

### 2. Qt 的默认单位是线程

Qt 是 toolkit 不是架构：拆进程的材料全套齐备（`QProcess`、`QLocalServer`/`QLocalSocket`、`QSharedMemory`、Linux 上的 QtDBus），但一个字不推你。默认的 Qt Widgets 程序宿主的是**自己写的代码**：没有不可信内容，四信号一个不响，拆进程的动机为零。

更关键的是 Qt 在进程内就把"消息传递的感觉"给足了：`QThread` + 队列连接的信号槽，跨线程通信自动排队投递、默认免锁——事件循环当总线、信号槽当消息，单进程就能把 UI 和重活分干净。开发者没有痛感，自然不会去碰进程。

| | Electron | Qt Widgets |
|---|---|---|
| 默认进程数 | 十几个，框架拆好 | 一个 |
| 谁决定的 | Chromium 安全架构 | 应用作者自己 |
| 默认并发单位 | 渲染进程 + JS 事件循环 | QThread + 队列连接信号槽 |
| 默认宿主内容 | 不可信 web 内容、第三方 JS | 你自己的代码 |
| 拆进程的材料 | 内置，躲不开 | QProcess/QLocalServer/QSharedMemory，按需自取 |

### 3. Qt 世界并不缺多进程

- **KDE Plasma** 是 Qt 写的最大家族：plasmashell、kwin、kwalletd、baloo……十几个常驻 Qt 进程全靠 D-Bus 对话，整个桌面就是一个巨型多进程 Qt 程序
- **QtWebEngine 就是 Chromium**：Qt 程序只要嵌了 `QWebEngineView`，任务管理器立刻冒出和 Electron 一模一样的进程群——Qt 一宿主 web 内容，自动长成 Electron 的形状
- **Qt Creator** 单进程编辑，但 gdb/cdb 是 `QProcess` 拉起来的独立进程，编译也走外部工具
- 上位机领域经典的**采集进程 + UI 进程**分家，`QProcess`/`QLocalSocket` 就是标准积木

规律很整齐：**进程边界出现在第三方代码进栈的地方**，与框架无关。

### 4. 什么时候 Qt 程序会长成 Electron 形状

四个触发条件，正是四信号在 Qt 语境下的翻译：加载用户写的插件（插件引擎跑不可信代码）、嵌 WebView（QWebEngine）、崩溃不可连坐的核心模块（采集不能跟 UI 死）、跨机分布。此外 Qt 官方还有现成的"跨进程信号槽"——Qt Remote Objects，把信号槽语义原样延伸到进程边界外。

### 5. 成本账

Electron 每个进程一套 V8 实例，几十 MB 起步，"内存大户"的名声由此而来——那是 Chromium 替每个程序强制支付的隔离固定成本。Qt 单进程轻快，把选择权留给作者：默认不拆，遇到四信号再动手。代价是必须自己想清楚要不要拆——"不知道从哪下手"的感觉，只是因为程序还没遇到不可信内容。

### 6. 一句话总结

**进程数由宿主的内容决定，不由框架决定。**Electron 的满屏进程是 Chromium 在替作者执行安全架构；Qt 的单进程是"你的代码你做主"。真拆起来，两边传消息用的都是同一类东西——管道和本地套接字，只是 Qt 里它叫 QLocalSocket。

## 扩展问题

- 队列连接为什么能当进程内消息总线 → 详见《信号槽是同步的还是异步的分别如何实现》
- UI 线程卡死的后果 → 详见《什么是UI线程UI线程阻塞后会怎样》
- 跨进程的信号槽：Qt Remote Objects → 详见《Qt Remote Object的序列化与反序列化》
- 拆进程的动机与判据 → 详见《进程线程与IPC的实际使用场景》
- 拆开之后怎么对话 → 详见《Windows命名管道与Unix管道对比》
