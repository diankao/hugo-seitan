+++
title = 'Linux网络设备驱动与net_device'
date = 2026-09-04T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['Linux', '网络设备驱动', 'net_device', 'sk_buff', '驱动开发']
+++

# Linux网络设备驱动与net_device

## 题目

围绕 Linux 网络设备驱动的系列问题：

1. `net_device` 结构体的 `name`、`base_addr`、`dev_addr`、`mem_start`、`mtu` 等成员分别是什么含义？
2. 硬件帧头填充函数 `hard_header()` 会填充哪些信息？设备需要的 I/O 地址是在哪里获取的？

## 考察点

`net_device` 结构体关键成员的含义（尤其 `base_addr` 与 `dev_addr` 的区别）、`hard_header()` 硬件帧头填充函数的参数构成、网络设备驱动与字符/块设备驱动的差异。

## 回答要点

### 1. net_device 关键成员辨析

`net_device` 在内核中指代一个网络设备，是一个巨型结构体，同时包含**属性描述**和**操作接口**两大部分。网络设备驱动程序只需通过填充 `net_device` 的具体成员并注册，即可实现硬件操作函数与内核的挂接。关键成员：

| 成员 | 含义 | 说明 |
|------|------|------|
| `name[]` | 设备名 | 如 `eth0`、`wlan0`；注册时写 `eth%d` 可让内核自动编号 |
| `base_addr` | **设备 I/O 基地址** | 寄存器空间起始地址（IORESOURCE_MEM 映射后） |
| `dev_addr[]` | **设备硬件地址（MAC）** | 6 字节数组，`eth_type_trans()` 等会使用 |
| `broadcast[]` | 广播地址 | 同为字节数组 |
| `irq` | 设备使用的中断号 | `request_irq()` 时用 |
| `mem_start` / `mem_end` | 设备共享内存的起始/结束 | 与网卡共享 RAM 通信时使用 |
| `mtu` | 最大传输单元 | 以太网默认 1500 字节 |
| `ifindex` | 接口序号 | 内核分配的唯一编号 |
| `netdev_ops` | 操作函数集 | `ndo_open/ndo_stop/ndo_start_xmit` 等回调的入口 |

其中最容易搞混的是 `base_addr` 和 `dev_addr[]`：**前者是"寄存器在哪"（I/O 基地址），后者是"网卡身份证号"（MAC 硬件地址）**——名字里带 `dev` 的管设备身份，带 `base` 的管地址空间。

### 2. hard_header() 填充什么

`hard_header()` 完成硬件帧头填充，返回填充的字节数。函数原型：

```c
int (*hard_header)(struct sk_buff *skb,
                   struct net_device *dev,
                   unsigned short type,
                   void *daddr,
                   void *saddr,
                   unsigned int len);
```

| 参数 | 填充的内容 |
|------|-----------|
| `type` | 协议类型（如 `ETH_P_IP`、`ETH_P_ARP`） |
| `daddr` | 目的硬件地址（目的 MAC） |
| `saddr` | 源硬件地址（源 MAC） |
| `len` | 数据长度（写入帧头中的长度字段） |
| `skb` / `dev` | 报文缓冲区、出接口设备 |

可见帧头里装的是**协议类型 + 目的地址 + 源地址（+长度）**这些"路上寻址"信息。**I/O 地址与帧头无关**：设备需要的 I/O 地址是在 `open()`（`ndo_open`）里通过 `request_mem_region()` + `ioremap()`（或 `request_region()`）获取并映射的，属于驱动初始化阶段的事，不会出现在每个数据包的帧头里。

### 3. 网络设备驱动的整体流程

驱动的基本套路：

```mermaid
flowchart LR
    A[alloc_etherdev<br/>分配 net_device] --> B[填充成员<br/>netdev_ops/irq/base_addr 等]
    B --> C[register_netdev<br/>注册到内核]
    C --> D[ndo_open<br/>申请资源/映射 I/O/启动队列]
    D --> E[ndo_start_xmit<br/>发送：填帧头后丢给硬件]
    E --> F[RX 中断<br/>收包构建 sk_buff 上送协议栈]
    F --> G[ndo_stop<br/>释放资源]
```

```c
static const struct net_device_ops my_netdev_ops = {
    .ndo_open       = my_open,
    .ndo_stop       = my_stop,
    .ndo_start_xmit = my_xmit,
};

static int __init my_init(void)
{
    struct net_device *ndev = alloc_etherdev(0);

    ndev->netdev_ops = &my_netdev_ops;
    ndev->irq        = MY_IRQ;
    ndev->base_addr  = MY_IO_BASE;

    return register_netdev(ndev);
}
```

### 4. 与字符/块设备驱动的对比

网络设备在 Linux 设备模型里是"第三类设备"，与前两类差异很大：

| 对比项 | 字符设备 | 块设备 | 网络设备 |
|--------|---------|--------|---------|
| 核心结构 | `cdev` / `file_operations` | `gendisk` / `request_queue` | `net_device` / `netdev_ops` |
| 数据单位 | 字节流 | 块（扇区倍数） | **sk_buff 报文** |
| 访问方式 | 用户直接 read/write | 文件系统缓存回写 | **用户不直接访问设备节点**，经协议栈/socket |
| 注册接口 | `cdev_add()` | `add_disk()` | `register_netdev()` |
| 并发方向 | 单向 | 单向 | **同时收发，异步中断驱动** |

正因为网络设备没有 `/dev` 节点、数据要经过协议栈加工，才需要 `hard_header()` 这类"为报文穿衣裳"的回调，以及 `sk_buff` 这个贯穿协议栈的数据载体。

### 5. 小结

- `base_addr` 是 **I/O 基地址**，`dev_addr[]` 才是 **MAC 硬件地址**，`mem_start/mem_end` 是共享内存范围，`mtu` 是最大传输单元；
- `hard_header()` 填的是**帧头**：协议类型 + 目的地址 + 源地址（+长度），与 I/O 地址无关，I/O 资源在 `open()` 里申请；
- 网络设备驱动 = 分配 `net_device` → 填成员和 `netdev_ops` → `register_netdev()`，收发全部围绕 `sk_buff` 展开。
