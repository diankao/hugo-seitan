+++
title = '嵌入式Linux内核panic排查步骤'
date = 2026-04-20T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['Linux内核', 'kernel panic', 'crash调试', 'oops']
+++

# 嵌入式Linux内核panic排查步骤

## 题目

在嵌入式Linux系统中，如果发生内核panic，如何一步步排查问题？

## 考察点

Linux内核调试、驱动开发、问题定位方法论

## 回答要点

### 1. Kernel Panic 是什么

内核遇到了无法恢复的致命错误，主动停止系统运行以防止数据损坏。

**常见触发原因**：
- 访问了非法地址（NULL 指针解引用、野指针）
- 非法指令（函数指针被覆盖）
- 无法处理的异常（未对齐访问、缺页异常在中断上下文中）
- 驱动中的严重 bug
- 内存损坏（越界写、use-after-free）
- 硬件故障（内存位翻转、总线错误）

### 2. 第一步：获取 Panic 信息

#### 2.1 串口日志

```bash
# 确保 console 输出到串口
# 内核启动参数：
console=ttyS0,115200 console=tty0

# panic 时打印详细信息
# 内核配置：
CONFIG_PANIC_TIMEOUT=0          # 不自动重启，保留现场
CONFIG_MAGIC_SYSRQ=y            # 启用 SysRq
CONFIG_KALLSYMS=y               # 符号地址解析
CONFIG_KALLSYMS_ALL=y
```

#### 2.2 pstore（Persistent Store）

```bash
# 内核配置
CONFIG_PSTORE=y
CONFIG_PSTORE_RAM=y

# 使用 RAM 保留区域存储 panic 日志，重启后可读取
# 设备树中配置 ramoops：
reserved-memory {
    ramoops@bf000000 {
        compatible = "ramoops";
        reg = <0xbf000000 0x100000>;
        record-size = <0x20000>;
        console-size = <0x20000>;
    };
};

# 重启后读取
mount -t pstore /sys/fs/pstore
cat /sys/fs/pstore/dmesg-ramoops-0
```

### 3. 第二步：分析 Oops/Panic 日志

#### 3.1 典型 Oops 日志结构

```
Unable to handle kernel NULL pointer dereference at virtual address 00000000
pgd = c0004000
[00000000] *pgd=00000000

PC is at my_driver_ioctl+0x24/0x80
LR is at vfs_ioctl+0x30/0x60
pc : [<bf000124>]    lr : [<c0108430>]    psr: 60000013
sp : c0a1be28  ip : c0a1be48  fp : c0a1be44
r10: 00000000  r9 : c0a1c000  r8 : bf000100
r7 : c0a1be70  r6 : 00000001  r5 : c7893400  r4 : 00000000
Flags: Nzcv  IRQs on  FIQs on  Mode SVC_32
Control: 00c5007f  Table: 00000000

Process my_app (pid: 123, stack limit = 0xc0a1a018)
Stack: (0xc0a1be28 to 0xc0a1c000)
...
Call trace:
[<bf000124>] my_driver_ioctl+0x24/0x80
[<c0108430>] vfs_ioctl+0x30/0x60
[<c0108560>] do_vfs_ioctl+0x80/0xa0
[<c0108600>] sys_ioctl+0x40/0x60
```

#### 3.2 关键信息提取

| 信息 | 含义 | 如何利用 |
|------|------|---------|
| `PC is at ...` | 崩溃发生的函数和偏移 | 定位到具体代码行 |
| `NULL pointer dereference` | 错误类型 | NULL 指针解引用 |
| `r4 : 00000000` | 寄存器值 | r4 为 NULL，可能就是问题变量 |
| `Process my_app (pid: 123)` | 触发的用户进程 | 缩小排查范围 |
| `Call trace` | 调用栈 | 还原调用路径 |

#### 3.3 反汇编定位代码行

```bash
# 使用 addr2line 将地址转换为源码行号
arm-linux-gnueabihf-addr2line -e vmlinux bf000124
# 输出: /home/user/driver/my_driver.c:42

# 或使用 objdump 反汇编
arm-linux-gnueabihf-objdump -d -S my_driver.ko | grep -A 20 "my_driver_ioctl"
```

### 4. 第三步：根据错误类型深入分析

#### 4.1 NULL 指针解引用

```c
// 最常见的 panic 原因
static long my_driver_ioctl(struct file *filp, unsigned int cmd, unsigned long arg) {
    struct my_device *dev = filp->private_data;
    // 如果 open 时没有正确设置 private_data，dev 就是 NULL
    return dev->ops->ioctl(dev, cmd, arg);   // PANIC! 解引用 NULL->ops
}

// 修复：加 NULL 检查
if (!dev) return -EINVAL;
```

#### 4.2 Use-After-Free

```
Bug:   内存已释放，但仍有指针指向它，后续访问触发 panic
日志特征: SLUB error、 poisoned object、 redzone overwritten

排查方法:
1. 开启 CONFIG_SLUB_DEBUG
2. 开启 CONFIG_KASAN（Kernel Address Sanitizer）
3. KASAN 会报告被释放的地址在哪里被 free，在哪里被再次访问
```

#### 4.3 越界访问

```
日志特征: BUG: unable to handle kernel paging request
          或 slab corruption detected

排查方法:
1. CONFIG_KASAN 可以精确定位越界读写
2. CONFIG_DEBUG_KMEMLEAK 检测内核内存泄漏
3. CONFIG_DEBUG_SLUB 检查 slab 对象完整性
```

### 5. 第四步：高级调试手段

#### 5.1 KGDB（内核 GDB）

```bash
# 内核配置
CONFIG_KGDB=y
CONFIG_KGDB_SERIAL_CONSOLE=y

# 启动参数
kgdboc=ttyS0,115200 kgdbwait

# 开发机上连接
arm-linux-gnueabihf-gdb vmlinux
(gdb) target remote /dev/ttyUSB0
(gdb) break my_driver_ioctl
(gdb) continue
```

#### 5.2 Ftrace 动态追踪

```bash
# 追踪函数调用
echo function > /sys/kernel/debug/tracing/current_tracer
echo my_driver_ioctl > /sys/kernel/debug/tracing/set_ftrace_filter
echo 1 > /sys/kernel/debug/tracing/tracing_on
# 复现问题后
cat /sys/kernel/debug/tracing/trace
```

#### 5.3 Kprobes 动态插桩

```bash
# 在不修改内核代码的情况下插入探测点
# 通过 perf 或 ftrace 使用
perf probe -a 'my_driver_ioctl cmd arg'
perf record -e probe_my_driver_ioctl -a sleep 10
```

### 6. 第五步：可靠性增强

#### 6.1 Panic 后自动收集信息

```bash
# 内核启动参数
panic=10                          # 10 秒后自动重启
softlockup_panic=1                # 软死锁时 panic
hardlockup_panic=1                # 硬死锁时 panic

# 重启后通过 pstore 获取上次 panic 日志
```

#### 6.2 核心转储（Kdump）

```bash
# 内核配置
CONFIG_CRASH_DUMP=y
CONFIG_KEXEC=y

# 加载 crash kernel
kexec -p /boot/vmlinux-crash --append="root=... console=ttyS0"

# panic 时自动启动 crash kernel
# 在 crash kernel 中保存 dump
```

### 7. 排查流程总结

```
Kernel Panic 发生
       │
       ▼
┌──────────────┐
│ 获取完整日志  │──── 串口 / pstore / dmesg
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 解析错误类型  │──── NULL解引用 / 越界 / UAF / 非法指令
│ 和崩溃地址   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ addr2line    │──── 定位到源码文件和行号
│ 反汇编定位   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 分析调用栈   │──── 还原崩溃时的调用路径
│ 和寄存器     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 必要时开启   │──── KASAN / SLUB_DEBUG / KGDB
│ 调试功能     │
└──────┬───────┘
       │
       ▼
    修复并验证
```
