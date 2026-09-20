+++
title = 'Windows命名管道与Unix管道对比'
date = 2026-09-20T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['Windows', '命名管道', 'IPC', 'NPFS', 'Qt']
+++

# Windows命名管道与Unix管道对比

## 题目

Windows 版的命名管道（Named Pipe）是什么样子？和 Unix 的 FIFO 有什么差异？为什么日常应用开发中几乎见不到它？

## 考察点

Windows 命名管道 API 家族与服务端/客户端模型、NPFS 内存伪文件系统、与 Unix FIFO 及域套接字的能力对比、命名管道在系统软件里的真实出场场景。

## 回答要点

### 1. API 家族与最小示例

服务端：创建管道 → 等待连接 → 读写：

```c
HANDLE hPipe = CreateNamedPipeA("\\\\.\\pipe\\demo",
    PIPE_ACCESS_DUPLEX,
    PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
    PIPE_UNLIMITED_INSTANCES, 4096, 4096, 0, NULL);

ConnectNamedPipe(hPipe, NULL);

char buf[128];
DWORD n;
ReadFile(hPipe, buf, sizeof(buf), &n, NULL);
WriteFile(hPipe, "pong", 4, &n, NULL);

DisconnectNamedPipe(hPipe);
CloseHandle(hPipe);
```

客户端就是一个普通的 `CreateFile`：

```c
HANDLE hPipe = CreateFileA("\\\\.\\pipe\\demo",
    GENERIC_READ | GENERIC_WRITE, 0, NULL,
    OPEN_EXISTING, 0, NULL);

char buf[128];
DWORD n;
WriteFile(hPipe, "ping", 4, &n, NULL);
ReadFile(hPipe, buf, sizeof(buf), &n, NULL);
CloseHandle(hPipe);
```

关键行为：

- `ConnectNamedPipe` 阻塞直到客户端 `CreateFile` 接入，语义类似 socket 的 `accept`
- `PIPE_UNLIMITED_INSTANCES` 允许同名管道开多个实例：服务端"建实例 → 等连接 → 交给线程 → 再建下一个"，每个客户端一条独立通道
- `PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE` 切到消息模式，一次 `WriteFile` 就是一条消息，读端按边界收，不会粘连

### 2. 与 Unix FIFO 的差异总表

| 维度 | Unix FIFO | Windows 命名管道 |
|------|-----------|----------------|
| 名字空间 | 借用文件系统路径 `/tmp/x.fifo` | 专用命名空间 `\\.\pipe\x`，不进文件系统 |
| 落盘 | inode 元数据落盘（tmpfs 除外），数据不落 | 完全不落盘（NPFS，见下节） |
| 方向 | 严格单向，双向要两条 | 可 `PIPE_ACCESS_DUPLEX` 双向 |
| 数据模式 | 纯字节流 | 字节流或消息模式（带边界）二选一 |
| 连接模型 | 双方 `open` 对等汇合 | 显式 C/S：`CreateNamedPipe`+`ConnectNamedPipe` vs `CreateFile` |
| 多客户端 | 共享同一条流（`PIPE_BUF` 原子写） | 多实例，每个连接一条独立通道 |
| 网络 | 仅本机 | 原生走 SMB：`\\服务器\pipe\x`，接口不变 |
| 权限 | 文件权限位 | 安全描述符（ACL），服务端还可 `ImpersonateNamedPipeClient` 扮演客户端身份 |
| 异步 | `O_NONBLOCK` | 非阻塞 + 超时 + 重叠 I/O，可挂完成端口（IOCP） |

能力上它是 Unix 侧几种机制的和：FIFO 的名字汇合 + 域套接字的 C/S 连接 + 消息队列的可选边界 + SMB 的网络透明。

### 3. NPFS：比 Unix 更彻底的"不落盘"

Unix FIFO 是借用通用文件系统的名字当门牌——inode 这点元数据还会落盘。Windows 专门造了一个**只有门牌、没有磁盘的伪文件系统**：内核驱动 `npfs.sys`（Named Pipe File System），挂在对象管理器 `\Device\NamedPipe` 下，`\\.\pipe\` 就是它的用户态映射，这个"文件系统"的卷就是内核内存本身。

顺带一提，`CreatePipe()` 创建的匿名管道在内核里同样走 NPFS，只是名字由系统随机生成。两家殊途同归：文件系统 API 是通用接口，后端可以是内存、是驱动、是管道——"一切皆文件"的真正含义。

### 4. 为什么应用开发几乎见不到它

因为它是**基础设施层的管子**，坐在应用层之下：

- 桌面应用之间的通信需求被更高层封装接管：COM/RPC（本地走 ALPC）、窗口消息（`WM_COPYDATA`）、localhost TCP
- 真正直接使用它的是服务型软件：数据库引擎、Windows 服务与 UI 客户端、容器与虚拟化、调试器
- 类比 Unix：应用工程师也很少手写 `mkfifo`，日常用的是 socket、gRPC、各种消息总线——管道在两个平台都住在底层

### 5. 其实你可能天天在用：它的常见马甲

- **Qt 的 QLocalServer/QLocalSocket**：Windows 底层就是命名管道（Unix 上是域套接字），同一个 API 两副面孔。Qt 程序的单实例检测（`listen` 失败即已有实例）走的就是它
- **Docker Desktop**：docker CLI 连的就是 `\\.\pipe\docker_engine`
- **SQL Server**：本地默认启用协议之一，连接串形如 `np:\\.\pipe\sql\query`
- **OpenSSH for Windows**：ssh-agent 暴露 `\\.\pipe\openssh-ssh-agent`
- **Chromium/Edge**：多进程架构的 IPC 通道在 Windows 上走命名管道
- **MSRPC**：`ncacn_np` 传输序列，SMB 生态的传统底座

"开发里从没见过"的真相是：见过它的次数远比以为的多，只是每次它都穿着别人的马甲。

### 6. 什么时候该亲手用它

- **本机 C/S**：UI 客户端与 Windows 后台服务通信，需要 ACL 控权和消息边界时，比裸 TCP 更省事（不占端口、不碰网络栈配置、自带客户端身份）
- **跨机又不想引 socket**：`\\服务器\pipe\x` 直接走 SMB，`ReadFile`/`WriteFile` 一个字不改
- 注意边界：Unix 域套接字能传 fd（SCM_RIGHTS），命名管道**不能传句柄**——Windows 侧传句柄要走继承或 `DuplicateHandle`

### 7. 一句话总结

Windows 命名管道把 Unix 里 FIFO、域套接字、消息队列三家的本事合成了一个对象，还附赠网络透明；代价是它长在基础设施层，被 Qt、数据库、容器、RPC 藏在身后——应用工程师天天用它而不自知。

## 扩展问题

- Unix FIFO 的语义与文件系统挂载细节 → 详见《命名管道为什么叫FIFO》
- 本机 IPC 与线程同步原语的全景对比 → 详见《本地IPC与线程同步原语对比》
- 句柄与文件描述符的 I/O 模型差异 → 详见《文件描述符与句柄的IO模型对比》
