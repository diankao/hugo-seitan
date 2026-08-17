+++
title = 'MCU上实现类Linux selectpoll机制'
date = 2026-04-20T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['select', 'poll', '事件驱动', 'RTOS']
+++

# MCU上实现类Linux select/poll机制

## 题目

如果需要在MCU上实现类似Linux select/poll的机制，如何设计？

## 考察点

事件驱动设计、RTOS编程、系统设计能力

## 回答要点

### 1. Linux select/poll 的核心思想

```c
// Linux select：同时监听多个 fd，任一就绪即返回
fd_set readfds;
FD_ZERO(&readfds);
FD_SET(uart_fd, &readfds);
FD_SET(spi_fd, &readfds);
FD_SET(timer_fd, &readfds);

int ret = select(maxfd + 1, &readfds, NULL, NULL, &timeout);
if (ret > 0) {
    if (FD_ISSET(uart_fd, &readfds))  handle_uart();
    if (FD_ISSET(spi_fd, &readfds))   handle_spi();
    if (FD_ISSET(timer_fd, &readfds)) handle_timer();
}
```

**核心能力**：
- 同时等待多个事件源
- 任一事件就绪即唤醒
- 支持超时
- 避免忙轮询

### 2. MCU 上的事件源

| 事件源 | 触发条件 | 通知方式 |
|--------|---------|---------|
| UART 接收 | 收到数据/帧完成 | ISR → 信号量/队列 |
| SPI 传输 | DMA 完成 | ISR → 信号量 |
| ADC 采样 | 转换完成 | ISR → 信号量 |
| 定时器 | 周期超时 | 软件定时器回调 |
| GPIO | 外部中断 | ISR → 信号量 |
| 网络 | 数据到达 | 回调/信号量 |
| 用户按键 | 按下/释放 | ISR → 信号量 |

### 3. 方案一：基于 FreeRTOS 事件组（Event Group）

```c
#include "freertos/event_groups.h"

#define EVT_UART_RX     (1 << 0)
#define EVT_SPI_DONE    (1 << 1)
#define EVT_ADC_DONE    (1 << 2)
#define EVT_TIMER       (1 << 3)
#define EVT_KEY         (1 << 4)
#define EVT_NETWORK     (1 << 5)

static EventGroupHandle_t event_group;

void event_system_init(void) {
    event_group = xEventGroupCreate();
}

// ISR 中设置事件
void UART_IRQHandler(void) {
    BaseType_t woken = pdFALSE;
    xEventGroupSetBitsFromISR(event_group, EVT_UART_RX, &woken);
    portYIELD_FROM_ISR(woken);
}

void SPI_DMA_IRQHandler(void) {
    BaseType_t woken = pdFALSE;
    xEventGroupSetBitsFromISR(event_group, EVT_SPI_DONE, &woken);
    portYIELD_FROM_ISR(woken);
}

// 类似 select 的等待
void app_main_task(void *arg) {
    while (1) {
        EventBits_t bits = xEventGroupWaitBits(
            event_group,
            EVT_UART_RX | EVT_SPI_DONE | EVT_ADC_DONE |
            EVT_TIMER | EVT_KEY | EVT_NETWORK,
            pdTRUE,            // 退出时清除位
            pdFALSE,           // 任一事件即可（不要求全部）
            pdMS_TO_TICKS(100) // 超时
        );

        if (bits & EVT_UART_RX)   handle_uart_rx();
        if (bits & EVT_SPI_DONE)  handle_spi_done();
        if (bits & EVT_ADC_DONE)  handle_adc_done();
        if (bits & EVT_TIMER)     handle_timer();
        if (bits & EVT_KEY)       handle_key();
        if (bits & EVT_NETWORK)   handle_network();

        if (bits == 0) {
            handle_idle();
        }
    }
}
```

**Event Group 的限制**：
- 最多 24 个事件位（FreeRTOS 默认）
- 不携带数据，只有"发生了"的信息
- 需要另外的途径获取数据（如环形缓冲区）

### 4. 方案二：统一消息队列（推荐）

```c
// 所有事件源统一封装为消息，发往同一个队列

typedef enum {
    MSG_UART_RX,
    MSG_SPI_DONE,
    MSG_ADC_DONE,
    MSG_TIMER,
    MSG_KEY_PRESS,
    MSG_KEY_RELEASE,
    MSG_NETWORK_RX,
    MSG_ERROR,
} msg_type_t;

typedef struct {
    msg_type_t type;
    uint32_t   timestamp;
    union {
        struct { uint16_t len; uint8_t channel; } uart;
        struct { uint16_t len; } spi;
        struct { uint32_t value; uint8_t channel; } adc;
        struct { uint32_t period_ms; } timer;
        struct { uint8_t key_id; } key;
        struct { uint16_t len; uint8_t *data; } net;
        struct { uint8_t code; const char *msg; } error;
    } data;
} system_msg_t;

#define MSG_QUEUE_SIZE  32
static QueueHandle_t msg_queue;

void event_system_init(void) {
    msg_queue = xQueueCreate(MSG_QUEUE_SIZE, sizeof(system_msg_t));
}

// ISR 中发送消息
void UART_IRQHandler(void) {
    uint16_t len = uart_dma_get_count();
    BaseType_t woken = pdFALSE;
    system_msg_t msg = {
        .type = MSG_UART_RX,
        .timestamp = xTaskGetTickCount(),
        .data.uart.len = len,
    };
    xQueueSendFromISR(msg_queue, &msg, &woken);
    portYIELD_FROM_ISR(woken);
}

// 类似 select 的主循环
void app_main_task(void *arg) {
    system_msg_t msg;

    while (1) {
        if (xQueueReceive(msg_queue, &msg, pdMS_TO_TICKS(100))) {
            switch (msg.type) {
            case MSG_UART_RX:
                handle_uart_rx(msg.data.uart.len);
                break;
            case MSG_SPI_DONE:
                handle_spi_done(msg.data.spi.len);
                break;
            case MSG_ADC_DONE:
                handle_adc_done(msg.data.adc.value, msg.data.adc.channel);
                break;
            case MSG_TIMER:
                handle_timer(msg.data.timer.period_ms);
                break;
            case MSG_KEY_PRESS:
                handle_key(msg.data.key.key_id);
                break;
            case MSG_NETWORK_RX:
                handle_network(msg.data.net.data, msg.data.net.len);
                break;
            case MSG_ERROR:
                handle_error(msg.data.error.code, msg.data.error.msg);
                break;
            }
        } else {
            handle_idle();
        }
    }
}
```

### 5. 方案三：任务通知（Task Notify）— 最轻量

```c
// FreeRTOS 任务通知：每个任务有一个 32-bit 通知值
// 类似 Event Group 但更快，不需要额外创建对象

#define NOTIFY_UART_RX   (1 << 0)
#define NOTIFY_SPI_DONE  (1 << 1)
#define NOTIFY_ADC_DONE  (1 << 2)
#define NOTIFY_TIMER     (1 << 3)

static TaskHandle_t main_task_handle;

// ISR 中通知
void UART_IRQHandler(void) {
    BaseType_t woken = pdFALSE;
    xTaskNotifyFromISR(main_task_handle, NOTIFY_UART_RX,
                        eSetBits, &woken);
    portYIELD_FROM_ISR(woken);
}

// 等待
void app_main_task(void *arg) {
    main_task_handle = xTaskGetCurrentTaskHandle();
    uint32_t notified;

    while (1) {
        if (xTaskNotifyWait(0, 0xFFFFFFFF, &notified,
                            pdMS_TO_TICKS(100))) {
            if (notified & NOTIFY_UART_RX)   handle_uart_rx();
            if (notified & NOTIFY_SPI_DONE)  handle_spi_done();
            if (notified & NOTIFY_ADC_DONE)  handle_adc_done();
            if (notified & NOTIFY_TIMER)     handle_timer();
        } else {
            handle_idle();
        }
    }
}
```

### 6. 三种方案对比

| 方面 | Event Group | 消息队列 | Task Notify |
|------|-----------|---------|-------------|
| 最大事件数 | 24 bit | 无限制（枚举） | 32 bit |
| 携带数据 | 不能 | 能 | 有限（32-bit 值） |
| 性能 | 中 | 中 | 最高 |
| 内存开销 | 需创建对象 | 需创建队列 | 零额外开销 |
| 多消费者 | 支持 | 队列自然支持 | 仅单任务 |
| 适用场景 | 少量事件标志 | 通用事件驱动 | 高性能单任务 |

### 7. 完整的 select-like 框架

```c
// 统一事件驱动框架

typedef struct {
    uint8_t id;
    void (*handler)(void *ctx);
} event_handler_t;

static const event_handler_t handlers[] = {
    { MSG_UART_RX,    handle_uart_rx_wrapper },
    { MSG_SPI_DONE,   handle_spi_done_wrapper },
    { MSG_ADC_DONE,   handle_adc_done_wrapper },
    { MSG_TIMER,      handle_timer_wrapper },
    { MSG_KEY_PRESS,  handle_key_wrapper },
};

#define HANDLER_COUNT  (sizeof(handlers) / sizeof(handlers[0]))

void event_loop_run(void) {
    system_msg_t msg;

    while (1) {
        if (xQueueReceive(msg_queue, &msg, pdMS_TO_TICKS(100))) {
            for (int i = 0; i < HANDLER_COUNT; i++) {
                if (handlers[i].id == msg.type) {
                    handlers[i].handler(&msg);
                    break;
                }
            }
        } else {
            handle_idle();
        }
    }
}

// 这就是 MCU 版的 "event loop"
// 类似 Linux 的 epoll_wait + 事件分发
```

### 8. 设计总结

```
MCU select/poll 的实现本质：

Linux:  select/poll/epoll
         ↓
MCU:    统一等待 + 事件分发

核心要素：
1. 统一的事件源抽象（消息/位/通知）
2. 阻塞等待机制（信号量/队列/通知）
3. 超时支持
4. 事件分发到对应处理函数

推荐：
- 简单场景：Task Notify（最快）
- 需要携带数据：消息队列
- 少量标志位：Event Group
```
