## 7. 主问题：你负责烧录算法开发，基于PetaLinux平台UART/SPI/SWD/I2C多协议批量烧录。PetaLinux不是嵌入式Linux吗？烧录算法怎么在Linux下运行？SWD是ARM特有的，你怎么通过Linux去控制SWD的时序？

### 回答

核心思路是 **PS（ARM Cortex-A9）跑 PetaLinux 做调度管理，PL（FPGA可编程逻辑）做时序控制**，这是 Zynq SoC 的 PS+PL 异构架构决定的。

**为什么选 PetaLinux 而不是裸机：**
- 需要同时管理多路烧录通道（我们最多支持 16 路并行），裸机写多任务调度太痛苦
- 需要 USB Host 接口挂载固件文件、网络接口远程升级、文件系统管理烧录日志
- PetaLinux 本身就支持这些，而且 Xilinx 提供了完整的 BSP

**烧录算法在 Linux 下运行的架构：**

```
┌─────────────────────────────────────────────────┐
│                  PetaLinux (PS端)                │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ 烧录任务  │  │ 协议调度  │  │ 文件管理/日志  │  │
│  │ 调度器    │→│ 中间层    │→│               │  │
│  └──────────┘  └────┬─────┘  └───────────────┘  │
│                     │ AXI总线                     │
├─────────────────────┼────────────────────────────┤
│                     ▼                            │
│                  PL端 (FPGA)                      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │
│  │SWD引擎 │ │SPI引擎 │ │UART引擎│ │I2C引擎 │    │
│  └────────┘ └────────┘ └────────┘ └────────┘    │
└─────────────────────────────────────────────────┘
```

**SWD 时序控制的关键：不是 Linux 直接控制 GPIO 模拟时序，而是通过 AXI 总线操作 PL 端的寄存器。**

具体来说：
1. PL 端用 Verilog 实现了 SWD 协议状态机（包括 line reset、DP/AP 读写、parity 校验）
2. PS 端通过 `/dev/mem` 或自定义 UIO 驱动，映射 AXI 寄存器到用户空间
3. 用户态程序只需写寄存器（比如 `写入目标地址 + 数据 → 触发一次 SWD 传输`），PL 的硬件状态机自动完成 bit-level 的时序
4. SWD 的时钟频率由 PL 端的分频器控制，默认跑 4MHz，完全不受 Linux 调度影响

```c
// PS端用户态操作示例（通过UIO映射PL寄存器）
#define SWD_CTRL_REG   0x00
#define SWD_ADDR_REG   0x04
#define SWD_DATA_REG   0x08
#define SWD_STATUS_REG 0x0C

int swd_write(uint32_t addr, uint32_t data) {
    *(volatile uint32_t*)(base + SWD_ADDR_REG) = addr;
    *(volatile uint32_t*)(base + SWD_DATA_REG) = data;
    *(volatile uint32_t*)(base + SWD_CTRL_REG) = 0x01;
    while (*(volatile uint32_t*)(base + SWD_STATUS_REG) & 0x01);
    return *(volatile uint32_t*)(base + SWD_STATUS_REG) >> 1;
}
```

**总结：Linux 负责业务逻辑（调度、文件管理、用户交互），FPGA 负责物理层时序，两者通过 AXI 总线解耦。** 这就是为什么用 Zynq 平台做烧录器的核心优势——既有 Linux 的生态又有 FPGA 的确定性时序。


### 追问1：多协议批量烧录，你在PS端如何调度不同协议的算法？是每个芯片写一个驱动吗？

**不是每个芯片写一个驱动，而是三层架构：协议层 → 芯片抽象层 → 任务调度层。**

**第一层：协议驱动层（只按协议分类，不按芯片分类）**

```c
struct protocol_ops {
    int (*init)(int channel);
    int (*write)(int channel, uint32_t addr, const uint8_t *data, size_t len);
    int (*read)(int channel, uint32_t addr, uint8_t *data, size_t len);
    int (*deinit)(int channel);
};

struct protocol_ops swd_ops = { swd_init, swd_write, swd_read, swd_deinit };
struct protocol_ops spi_ops = { spi_init, spi_write, spi_read, spi_deinit };
struct protocol_ops uart_ops = { uart_init, uart_write, uart_read, uart_deinit };
struct protocol_ops i2c_ops = { i2c_init, i2c_write, i2c_read, i2c_deinit };
```

**第二层：芯片抽象层（用配置描述符区分芯片差异）**

每个芯片的差异不在驱动代码里，而是在 **烧录脚本（JSON描述）** 里：

```json
{
    "chip": "STM32F103C8T6",
    "protocol": "SWD",
    "init_sequence": [
        {"cmd": "write", "addr": "0xE000EDF0", "data": "0xA05F0001"},
        {"cmd": "write", "addr": "0xE000EDFC", "data": "0x01000000"}
    ],
    "erase_cmd": {"cmd": "write", "addr": "0x40022004", "data": "0x00000204"},
    "program_block_size": 1024
}
```

这样新增芯片支持只需要写一个新的 JSON 配置，不需要改任何 C 代码。

**第三层：任务调度层**

```c
struct burn_task {
    int channel;
    const char *firmware_path;
    const char *chip_config_path;
    enum protocol_type proto;
    int (*callback)(int channel, int progress, int status);
};

void *burn_worker(void *arg) {
    struct burn_task *task = (struct burn_task *)arg;
    struct protocol_ops *ops = get_protocol_ops(task->proto);
    struct chip_config *cfg = load_chip_config(task->chip_config_path);

    ops->init(task->channel);
    for (int i = 0; i < cfg->init_seq_count; i++)
        execute_cmd(ops, task->channel, &cfg->init_seq[i]);
    ops->deinit(task->channel);
}
```

实际调度用 **线程池 + 每通道独立状态机**，16 路并行烧录互不干扰。


### 追问2：SWD协议中有一个关键的DP和AP访问，你是怎么在PL中实现的？有没有考虑到SWD的回包超时？

**PL 端 SWD 引擎的实现是一个标准的 SWD 协议状态机：**

```verilog
module swd_engine (
    input wire clk,
    input wire [31:0] ctrl_reg,
    input wire [31:0] addr_reg,
    input wire [31:0] data_reg,
    output reg [31:0] status_reg,
    inout wire swdio,
    output wire swclk
);

localparam IDLE       = 3'd0;
localparam LINE_RESET = 3'd1;
localparam SEND_REQ   = 3'd2;
localparam ACK_PHASE  = 3'd3;
localparam DATA_PHASE = 3'd4;
localparam DONE       = 3'd5;

reg [2:0] state;
reg [7:0] bit_counter;
reg [31:0] shift_reg;
reg [2:0] ack_val;

wire [7:0] request = {1'b1, ctrl_reg[0], ctrl_reg[1], addr_reg[3:2],
                      ^{ctrl_reg[0], ctrl_reg[1], addr_reg[3:2]}, 1'b0, 1'b1};
```

**DP 和 AP 的访问流程：**

1. **DP 访问（Debug Port）：** 先发 line reset（≥50个1）建立连接，然后通过 `DPIDR` 读出 DP 的 ID 确认连接正常。常用操作是写 `DP.SELECT` 寄存器选择目标 AP，写 `DP.CTRL/STAT` 控制电源和传输。

2. **AP 访问（Access Port）：** 先通过 `DP.SELECT` 选中 AP 编号和地址 bank，然后发 AP 读写请求。每次 AP 读操作需要两轮：第一轮目标 AP 准备数据，第二轮才能通过 `DP.RDBUFF` 读到实际数据。

```c
uint32_t ap_read(uint8_t ap_num, uint8_t addr) {
    dp_write(DP_SELECT, (ap_num << 24) | (addr & 0xF0));
    ap_read_request(addr);
    return dp_read(DP_RDBUFF);
}
```

**回包超时的处理：**

```verilog
reg [15:0] ack_timeout_cnt;
localparam ACK_TIMEOUT_VAL = 16'd1000;

always @(posedge clk) begin
    if (state == ACK_PHASE) begin
        if (ack_timeout_cnt >= ACK_TIMEOUT_VAL) begin
            status_reg[2] <= 1'b1;
            state <= IDLE;
        end
        ack_timeout_cnt <= ack_timeout_cnt + 1;
    end else begin
        ack_timeout_cnt <= 0;
    end
end
```

超时后的恢复策略：
1. 先执行 line reset（发送 ≥50 个 1 + JTAG-to-SWD 切换序列）
2. 重试当前操作，最多重试 3 次
3. 3 次都失败则标记该通道异常，上报 PS 端记录日志


### 追问3：PetaLinux平台上，如何保证SWD信号的时序精度？Linux不是实时系统，会不会造成抖动影响烧录成功率？

**这个问题的核心答案是：SWD 的信号时序完全由 PL（FPGA）保证，Linux 的调度抖动根本不参与物理层时序生成。**

很多人对 Zynq 平台的理解有一个误区，以为 PS 端直接 bit-bang GPIO 来模拟 SWD 时序。实际上我们的架构是：

| 层级 | 负责模块 | 是否涉及时序精度 |
|------|---------|----------------|
| 物理层时序 | PL 端 FPGA 硬件状态机 | ✅ 完全由 FPGA 时钟保证 |
| 协议控制 | PL 端寄存器接口 | ❌ 只做命令触发 |
| 业务调度 | PS 端 PetaLinux | ❌ 只做任务管理 |

**具体来说，Linux 的调度抖动只会影响"什么时候发起下一次烧录操作"，但不会影响"这一次操作的 SWD 时序是否准确"。**

举个例子：
- PS 端发一个"写寄存器"命令到 AXI 寄存器，可能因为 Linux 调度延迟了 500μs 才执行
- 但一旦 PL 端收到命令，SWD 的每一个 bit 的时钟周期、数据建立/保持时间，都是 FPGA 时钟域下的确定性时序
- SWDCLK 由 PL 的分频器产生，频率固定 4MHz，每个 bit 的时序精度是纳秒级

**但有一个地方确实需要关注实时性：多通道并行烧录的通道间同步。**

我们的解决方案：
1. 每个通道独立的 PL 端协议引擎，互不干扰
2. PS 端用 **pthread + FIFO 调度策略**（`sched_setscheduler` 设置 `SCHED_FIFO`）提升烧录线程的调度优先级
3. 关键路径上使用 **UIO + mmap** 直接操作寄存器，绕过内核态的开销
4. 实测 PS→PL 单次命令延迟在 1-2μs，最坏情况（大负载）不超过 50μs，对烧录成功率没有任何影响

**实测数据：16 路并行烧录 STM32F103（64KB Flash），单路耗时约 3.2 秒，成功率 99.97%（1000 次循环测试中失败 3 次，均为接触不良导致，非时序问题）。**


---

## 8. 主问题：你做的EmbedCopilot，四个Agent协作实现"编码→审查→修复"自动闭环。你是怎么把LLM集成到嵌入式开发流程中的？审查规则里"中断安全"具体指什么？LLM生成的代码你怎么保证编译通过？

### 回答

**EmbedCopilot 的整体架构：**

```
┌────────────────────────────────────────────────────────┐
│                    用户输入需求                          │
│                        │                               │
│                        ▼                               │
│              ┌──────────────────┐                      │
│              │  Agent 1: Coder │ ← RAG检索芯片手册     │
│              │  生成初始代码     │ ← 项目上下文         │
│              └────────┬─────────┘                      │
│                       │                                │
│                       ▼                                │
│              ┌──────────────────┐                      │
│              │ Agent 2: Reviewer│ ← 中断安全等规则库    │
│              │ 代码审查+打标     │ ← MISRA-C 规则子集   │
│              └────────┬─────────┘                      │
│                       │                                │
│              ┌────────┴─────────┐                      │
│              │ 有问题？          │                      │
│              ├───Yes────────────┤                      │
│              │                  │ No                   │
│              ▼                  ▼                      │
│     ┌────────────────┐  ┌──────────────────┐          │
│     │Agent 3: Fixer  │  │Agent 4: Verifier │          │
│     │ 自动修复问题    │  │ 编译→烧录→运行   │          │
│     └───────┬────────┘  │ → 日志分析       │          │
│             │            └──────────────────┘          │
│             └──→ 回到 Reviewer                         │
└────────────────────────────────────────────────────────┘
```

**LLM 集成到嵌入式开发流程的关键设计：**

1. **Prompt Engineering 嵌入式专用模板：** 不是通用 ChatGPT 对话，而是结构化的 system prompt，包含目标 MCU 型号、外设配置、编码规范、中断优先级规划等上下文信息

2. **RAG 检索芯片手册：** 把芯片手册按章节分块做向量索引，LLM 生成代码前先检索相关寄存器描述，避免"编造"寄存器地址

3. **工具调用（Function Calling）：** LLM 通过工具调用协议触发编译器、烧录器、串口监控，形成闭环验证

**"中断安全"规则是嵌入式领域特有的代码审查规则，指的是：在中断服务函数（ISR）中执行的代码必须满足一系列约束，保证不会导致系统死锁、优先级反转或时序异常。** 具体规则见追问1。

**LLM 生成代码保证编译通过的方法——自动编译-修复循环：**

```python
MAX_FIX_ROUNDS = 3

for round in range(MAX_FIX_ROUNDS):
    code = coder_agent.generate(requirement, context)
    compile_result = toolchain.compile(code)
    if compile_result.success:
        break
    fixer_agent.fix(code, compile_result.errors)
```

实测编译通过率从首轮 78% 提升到循环 3 轮后的 96%，剩下的 4% 通常是链接错误（比如 Flash 超限），需要人工介入调整。


### 追问1：你提到的"中断安全"规则有哪些？具体例子，比如禁止在中断中使用HAL\_Delay，你怎么在代码审查时检查出来？

**我们定义的中断安全规则集：**

| 规则编号 | 规则描述 | 违规后果 | 严重等级 |
|---------|---------|---------|---------|
| ISR-001 | 禁止在 ISR 中调用阻塞函数（HAL_Delay, osDelay, vTaskDelay） | 系统卡死、低优先级中断被饿死 | 致命 |
| ISR-002 | 禁止在 ISR 中使用动态内存分配（malloc, free, pvPortMalloc） | 堆碎片化、内存泄漏、不确定性延迟 | 致命 |
| ISR-003 | ISR 中禁止使用浮点运算（浮点寄存器在部分 Cortex-M 上不会自动保存） | 数据损坏、HardFault | 严重 |
| ISR-004 | ISR 中禁止调用 printf/sprintf 等格式化输出函数 | 栈溢出、阻塞 | 严重 |
| ISR-005 | ISR 函数体不超过 50 行，执行时间不超过 10μs | 中断延迟增大、丢中断 | 严重 |
| ISR-006 | ISR 中共享变量必须使用 volatile 修饰 | 编译器优化导致数据不一致 | 警告 |
| ISR-007 | ISR 中禁止调用可能阻塞的 API（如获取互斥锁） | 优先级反转、死锁 | 致命 |

**检测方法——两层检测机制：**

**第一层：静态模式匹配（正则表达式快速扫描）**

```python
ISR_BLOCKING_PATTERNS = [
    r'HAL_Delay\s*\(',
    r'osDelay\s*\(',
    r'vTaskDelay\s*\(',
    r'malloc\s*\(',
    r'free\s*\(',
    r'pvPortMalloc\s*\(',
    r'printf\s*\(',
    r'sprintf\s*\(',
    r'xSemaphoreTake\s*\([^,]+,[^)]+\)',
]

def scan_isr_function(func_code: str) -> list:
    violations = []
    for pattern in ISR_BLOCKING_PATTERNS:
        if re.search(pattern, func_code):
            violations.append(f"匹配到违规模式: {pattern}")
    return violations
```

**第二层：LLM 语义分析（处理间接调用链）**

正则只能抓直接调用，对于间接调用（比如 ISR 里调用了函数 A，函数 A 里调用了 `HAL_Delay`），需要 LLM 做调用链分析：

```
审查 Prompt 示例：
"以下是一个中断服务函数及其调用的所有子函数。请分析是否存在中断不安全的调用：
- 是否存在阻塞等待？
- 是否存在动态内存分配？
- 是否存在非重入函数调用？
- 函数体是否过长？
请按 ISR-001 ~ ISR-007 规则逐一检查并报告违规项。"
```

**实际案例：**

```c
void TIM2_IRQHandler(void) {
    if (TIM2->SR & TIM_SR_UIF) {
        TIM2->SR &= ~TIM_SR_UIF;
        HAL_Delay(1);              // ISR-001: 正则直接捕获
        process_sensor_data();
    }
}

void process_sensor_data(void) {
    char buf[64];
    sprintf(buf, "val=%d", sensor_val);  // ISR-004: LLM调用链分析捕获
    uint8_t *p = malloc(32);             // ISR-002: LLM调用链分析捕获
}
```

正则只能抓到 `HAL_Delay`，但 LLM 能通过分析 `process_sensor_data` 的函数体，发现 ISR 中间接调用了 `sprintf` 和 `malloc`。


### 追问2：你RAG索引芯片手册片段，具体索引了哪些内容？怎么检索的？如果手册更新了，索引同步怎么做？

**索引的内容——按嵌入式开发实际需要选择性索引：**

| 索引内容 | 为什么需要 | 索引粒度 |
|---------|-----------|---------|
| 寄存器描述（地址、位域定义、复位值） | LLM 生成外设初始化代码时需要准确的寄存器地址和位定义 | 每个寄存器一个 chunk |
| 外设功能描述（UART/SPI/TIM/ADC等章节） | 理解外设工作模式、配置流程 | 按功能小节分 chunk |
| 引脚复用表（Pinmux/AFIO） | 配置 GPIO 时需要知道哪个引脚支持哪个复用功能 | 按引脚分组 |
| 中断向量表和优先级 | 配置 NVIC 时需要正确的中断号 | 整表一个 chunk |
| 电气特性（供电电压、时钟频率范围） | 代码中配置时钟树、判断参数合法性 | 按章节分 chunk |
| 典型应用电路/初始化流程 | 作为代码生成的参考模板 | 每个应用笔记一个 chunk |
| 存储器映射（Flash/SRAM 地址范围） | 链接脚本、Bootloader 地址规划 | 整表一个 chunk |

**不索引的内容：** 封装尺寸、焊接温度曲线、订货信息——这些和代码生成无关。

**检索流程：**

```
用户需求: "配置TIM3的CH1输出PWM，频率10kHz"
        │
        ▼
┌─────────────────────────────┐
│ Step 1: 查询改写             │
│ "TIM3 CH1 PWM 频率配置"      │
│ + "TIM3_CCMR1 OC1M 位域"    │
│ + "TIM3_PSC ARR 计算公式"   │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Step 2: 向量检索 (Top-5)     │
│ Embedding Model: text2vec    │
│ 相似度阈值: 0.75             │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Step 3: 注入 LLM Context    │
│ system_prompt + 检索到的     │
│ 寄存器描述 + 外设功能描述    │
└─────────────────────────────┘
```

```python
def rag_query(user_requirement: str, chip: str) -> list:
    queries = rewrite_query(user_requirement)
    results = []
    for q in queries:
        q_embedding = embed(q)
        chunks = vector_db.search(
            collection=f"chip_{chip}",
            embedding=q_embedding,
            top_k=5,
            threshold=0.75
        )
        results.extend(chunks)
    return deduplicate(results)
```

**手册更新的索引同步策略：**

1. **版本检测：** 维护一个 `manual_version.json`，记录每个芯片手册的当前版本号和文件 hash

```json
{
    "STM32F103": {
        "version": "RM0008_Rev20",
        "file_hash": "sha256:a1b2c3...",
        "last_indexed": "2025-03-15"
    }
}
```

2. **增量更新：** 不是全量重新索引，而是：
   - 对比新旧手册的章节级 hash，找出变化的章节
   - 只删除变化章节的旧 chunk，重新索引变化章节
   - 通常手册更新只涉及勘误修正或新增外设描述，变化量很小

3. **定时任务：** 每周检查一次芯片厂商官网的勘误表和手册版本号，有更新时触发增量索引流程


### 追问3：你说"自研工具调用协议，打通编译→烧录→运行→日志分析的自动化验证流程"，这个协议具体怎么设计的？怎么判断运行结果是否正确？

**工具调用协议的设计——基于 JSON-RPC 2.0 的扩展：**

```json
{
    "jsonrpc": "2.0",
    "method": "tool.call",
    "params": {
        "tool": "compile",
        "args": {
            "source_dir": "/tmp/embed_copilot/gen_20250101",
            "toolchain": "arm-none-eabi-gcc",
            "target": "STM32F103C8T6",
            "optimization": "-O2"
        },
        "timeout_ms": 30000
    },
    "id": 1
}
```

```json
{
    "jsonrpc": "2.0",
    "result": {
        "status": "success",
        "output": "Build finished: 0 errors, 0 warnings",
        "artifact": "/tmp/embed_copilot/gen_20250101/build/firmware.bin",
        "size": {
            "text": 12340,
            "data": 1024,
            "flash_used_pct": 18.8
        }
    },
    "id": 1
}
```

**四个工具的定义：**

```python
TOOLS = {
    "compile": {
        "description": "调用 arm-none-eabi-gcc 编译项目",
        "input_schema": {
            "source_dir": "str",
            "toolchain": "str",
            "target": "str",
            "optimization": "str"
        },
        "output_schema": {
            "status": "success|error",
            "errors": "list[str]",
            "artifact": "str",
            "size": "dict"
        }
    },
    "flash": {
        "description": "通过 OpenOCD/JLink 烧录固件到目标板",
        "input_schema": {
            "firmware": "str",
            "interface": "str",
            "target": "str"
        },
        "output_schema": {
            "status": "success|error",
            "verify": "pass|fail"
        }
    },
    "serial_monitor": {
        "description": "启动串口监控，收集运行日志",
        "input_schema": {
            "port": "str",
            "baudrate": "int",
            "duration_s": "float"
        },
        "output_schema": {
            "status": "success|timeout",
            "logs": "list[str]"
        }
    },
    "verify_result": {
        "description": "根据预期输出模式验证运行日志",
        "input_schema": {
            "logs": "list[str]",
            "expected_patterns": "list[str]",
            "timeout_patterns": "list[str]"
        },
        "output_schema": {
            "verdict": "pass|fail|unknown",
            "matched": "list[str]",
            "unmatched": "list[str]"
        }
    }
}
```

**完整的自动化验证流程：**

```python
def auto_verify(requirement: str, code: str) -> dict:
    compile_result = tool_call("compile", {
        "source_dir": save_code(code),
        "target": "STM32F103C8T6"
    })
    if compile_result["status"] == "error":
        return {"verdict": "compile_fail", "errors": compile_result["errors"]}

    flash_result = tool_call("flash", {
        "firmware": compile_result["artifact"],
        "interface": "stlink"
    })
    if flash_result["status"] == "error":
        return {"verdict": "flash_fail"}

    serial_result = tool_call("serial_monitor", {
        "port": "/dev/ttyUSB0",
        "baudrate": 115200,
        "duration_s": 10.0
    })

    expected = generate_expected_patterns(requirement)
    verify_result = tool_call("verify_result", {
        "logs": serial_result["logs"],
        "expected_patterns": expected["must_see"],
        "timeout_patterns": expected["must_not_see"]
    })

    return verify_result
```

**怎么判断运行结果是否正确——三种验证策略：**

| 策略 | 适用场景 | 示例 |
|------|---------|------|
| **字符串模式匹配** | 有明确串口输出的功能 | 期望 `"[PASS] UART init OK"`，检查日志中是否出现 |
| **异常模式检测** | 不应该出现的错误 | 不应出现 `"HardFault"`、`"Stack Overflow"`、`"Assertion failed"` |
| **LLM 语义判断** | 复杂行为验证 | 将日志交给 Verifier Agent，由 LLM 判断行为是否符合需求描述 |

**示例——验证 PWM 输出是否正确：**

```json
{
    "expected_patterns": [
        "System init OK",
        "TIM3 CH1 PWM started",
        "PWM freq=10000Hz"
    ],
    "timeout_patterns": [
        "HardFault",
        "Error",
        "Timeout"
    ]
}
```

如果日志中出现所有 expected_patterns 且没有 timeout_patterns，则判定 PASS。如果 LLM 发现日志显示的频率和需求不匹配（比如日志说 5kHz 但需求要求 10kHz），Verifier Agent 会报告具体差异，触发 Fixer Agent 修正定时器配置。
