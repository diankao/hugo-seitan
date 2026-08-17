+++
title = 'Bootloader设计升级可靠性与断电保护'
date = 2026-04-20T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['Bootloader', 'OTA升级', '断电保护', 'AB分区']
+++

# Bootloader设计升级可靠性与断电保护

## 题目

如果让我设计一个Bootloader，如何保证升级过程的可靠性，比如断电保护？

## 考察点

固件升级设计、可靠性工程、Flash管理

## 回答要点

### 1. 升级过程的可靠性威胁

```
OTA 升级流程：
下载固件 ──▶ 传输到设备 ──▶ 写入 Flash ──▶ 校验 ──▶ 重启切换
   │              │              │            │          │
   │              │              │            │          │
   ├─网络中断     ├─传输错误     ├─断电        ├─校验失败  ├─新固件无法启动
   ├─固件损坏     ├─丢包        ├─Flash写入错误 ├─被篡改   └─设备变砖
   └─版本错误     └─超时        └─写半截
```

**断电是最恶劣的场景**：Flash 写入到一半断电，该扇区数据可能处于不确定状态（既不是旧数据也不是新数据）。

### 2. 核心设计原则

**原子性**：固件切换是一个原子操作，要么完全成功，要么完全回退
**可恢复性**：任何时候断电，重启后都能进入一个已知的安全状态
**可验证性**：新固件写入后必须校验完整性

### 3. AB 分区方案

#### 3.1 Flash 布局

```
┌──────────────────────────────────────┐
│           Bootloader                  │  只读，永不更新
├──────────────────────────────────────┤
│           分区元数据（分区表）          │  记录哪个分区可启动
├──────────────────┬───────────────────┤
│   分区 A（主分区） │   分区 B（备份分区）│  交替使用
│   firmware_a.bin  │   firmware_b.bin  │
├──────────────────┴───────────────────┤
│           用户数据区                   │
└──────────────────────────────────────┘
```

#### 3.2 分区元数据结构

```c
typedef struct {
    uint32_t magic;            // 0x4F544131 ("OTA1")
    uint32_t version;          // 固件版本号
    uint32_t size;             // 固件大小
    uint32_t crc32;            // 固件 CRC32
    uint8_t  partition;        // 'A' 或 'B'
    uint8_t  state;            // 分区状态
    uint8_t  reserved[2];
    uint32_t upgrade_count;    // 升级次数
    uint32_t header_crc;       // 本头部 CRC
} partition_meta_t;

typedef enum {
    PART_STATE_INVALID = 0,    // 无效/空
    PART_STATE_WRITING = 1,    // 正在写入（升级中）
    PART_STATE_VERIFY  = 2,    // 写入完成待验证
    PART_STATE_VALID   = 3,    // 验证通过，可启动
    PART_STATE_BOOTING = 4,    // 尝试启动中
    PART_STATE_ACTIVE  = 5,    // 当前运行
} partition_state_t;
```

#### 3.3 升级流程（断电安全）

```
初始状态：
  A: ACTIVE（正在运行）    B: INVALID

步骤1：标记 B 为 WRITING
  A: ACTIVE                B: WRITING
  │                         │
  │    写入元数据到 B 分区头部
  │    如果此处断电 → B 仍是 INVALID，A 继续运行 ✓

步骤2：将新固件写入 B 分区
  A: ACTIVE                B: WRITING
  │                         │
  │    逐块写入，每块写完做 CRC 校验
  │    如果此处断电 → B 的 state=WRITING，Bootloader 不会从 B 启动
  │    重启后继续从 A 运行，可重新升级 ✓

步骤3：校验 B 分区完整性
  A: ACTIVE                B: VERIFY
  │                         │
  │    全量 CRC32 校验
  │    校验通过则标记为 VALID

步骤4：标记 B 为 VALID，准备切换
  A: ACTIVE                B: VALID
  │                         │
  │    如果此处断电 → B 已 VALID，重启后 Bootloader 选择 B 启动 ✓

步骤5：重启，Bootloader 从 B 启动
  A: ACTIVE                B: BOOTING → ACTIVE
  │                         │
  │    应用层确认新固件正常后，标记 B 为 ACTIVE
  │    标记 A 为 INVALID（或保留为回退备份）
```

### 4. 断电安全的关键机制

#### 4.1 状态机保护

```c
// Bootloader 启动时的决策逻辑
void bootloader_main(void) {
    partition_meta_t meta_a, meta_b;
    read_meta(PART_A, &meta_a);
    read_meta(PART_B, &meta_b);

    bool a_bootable = (meta_a.state == PART_STATE_VALID ||
                       meta_a.state == PART_STATE_BOOTING);
    bool b_bootable = (meta_b.state == PART_STATE_VALID ||
                       meta_b.state == PART_STATE_BOOTING);

    if (a_bootable && !b_bootable) {
        boot_partition(PART_A);
    } else if (b_bootable && !a_bootable) {
        boot_partition(PART_B);
    } else if (a_bootable && b_bootable) {
        // 两个都有效，选版本新的
        if (meta_b.version >= meta_a.version) {
            boot_partition(PART_B);
        } else {
            boot_partition(PART_A);
        }
    } else {
        // 两个都无效，进入恢复模式
        enter_recovery_mode();
    }
}
```

#### 4.2 Flash 写入的原子性

```c
// Flash 擦除是不可逆的（整个扇区变 0xFF）
// 关键：先写数据，最后写状态

int write_partition_data(partition_t part, const uint8_t *data, uint32_t len) {
    uint32_t addr = get_partition_addr(part);

    // 1. 擦除目标分区
    flash_erase_range(addr, len);

    // 2. 逐块写入数据
    for (uint32_t offset = 0; offset < len; offset += FLASH_BLOCK_SIZE) {
        uint32_t chunk = min(FLASH_BLOCK_SIZE, len - offset);
        flash_write(addr + offset, data + offset, chunk);
    }

    // 3. 写入元数据（标记为 VERIFY）
    //    这一步是"提交点"
    partition_meta_t meta = {
        .magic = META_MAGIC,
        .state = PART_STATE_VERIFY,
        .size = len,
        .crc32 = calc_crc32(data, len),
    };
    flash_write(get_meta_addr(part), &meta, sizeof(meta));

    return 0;
}

// 4. 校验通过后，再更新 state 为 VALID
//    这两个状态转换是"原子提交点"
```

#### 4.3 断电恢复策略

```
断电发生在不同阶段：

写入元数据前断电：
  → 分区状态不变（仍是 INVALID 或 ACTIVE）
  → 重启后不受影响，可重新升级

写入固件中途断电：
  → 分区状态为 WRITING
  → Bootloader 不选择 WRITING 状态的分区启动
  → 从另一个有效分区启动，可重新升级

写入 VALID 状态时断电：
  → 最坏情况：状态可能写了一半
  → 对策：状态字段用冗余编码（写两次，取一致的那个）
  → 或用 Flash 的 "0→1 需擦除，1→0 直接写" 特性做状态位

启动验证阶段断电：
  → 分区状态为 BOOTING
  → Bootloader 重新尝试启动
  → 如果连续失败 N 次，自动回退到旧分区
```

### 5. 回退机制（Failsafe）

```c
// 应用启动后的确认机制
void app_main(void) {
    partition_meta_t meta;
    read_meta(current_partition, &meta);

    if (meta.state == PART_STATE_BOOTING) {
        // 这是新固件第一次启动
        // 执行自检
        if (self_test_pass() && peripheral_check_ok()) {
            // 确认正常，标记为 ACTIVE
            meta.state = PART_STATE_ACTIVE;
            write_meta(current_partition, &meta);
        } else {
            // 新固件有问题，标记为 INVALID 并重启
            meta.state = PART_STATE_INVALID;
            write_meta(current_partition, &meta);
            system_reboot();   // Bootloader 会回退到旧分区
        }
    }
}

// Bootloader 中的启动计数器
// 如果同一个分区连续 BOOTING 失败 3 次，自动切换到另一个分区
```

### 6. 完整升级流程

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ 接收固件 │───▶│ 写入备份 │───▶│ 校验固件 │───▶│ 标记有效 │
│  分区    │    │  分区    │    │  CRC32  │    │  VALID  │
└─────────┘    └─────────┘    └─────────┘    └────┬────┘
                                                  │
                                                  ▼
                                           ┌─────────┐
                                           │ 重启    │
                                           │ 切换分区 │
                                           └────┬────┘
                                                │
                                                ▼
                                           ┌─────────┐    ┌─────────┐
                                           │ 新固件   │───▶│ 自检通过 │
                                           │ 启动     │    │ 标ACTIVE│
                                           └────┬────┘    └─────────┘
                                                │
                                           自检失败 │
                                                ▼
                                           ┌─────────┐
                                           │ 标记无效 │
                                           │ 重启回退 │
                                           └─────────┘
```

### 7. 设计总结

| 设计要点 | 实现方式 |
|---------|---------|
| 断电不坏 | AB 分区 + 状态机，任何时候断电都有安全分区可启动 |
| 写入不乱 | 先写数据后写状态，状态转换是原子提交点 |
| 启动不砖 | 启动计数器 + 自动回退，新固件异常自动切回旧版本 |
| 数据不篡改 | CRC32 + 签名校验，确保固件完整性 |
| 恢复有路 | 两个分区都坏时进入 recovery 模式（串口/USB 强制刷入） |
