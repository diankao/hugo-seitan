+++
title = 'CubeMX配置光敏传感器GPIO输入'
date = 2026-05-03T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['STM32', 'CubeMX', 'GPIO', '光敏传感器', '传感器', '嵌入式']
+++

# CubeMX配置光敏传感器GPIO输入

在之前搭建的 FreeRTOS 多任务工程基础上，给 **PB13** 引脚添加一个光敏传感器（GPIO Input），读取光照状态。

## 第一步：CubeMX 配置 PB13 为 GPIO 输入

### 1.1 打开已有工程

- 打开 STM32CubeMX，加载之前的 FreeRTOS LED 闪烁工程

### 1.2 配置 PB13 引脚

- 在 **Pinout view** 芯片图上，点击 **PB13**
- 在弹出的复用功能列表中选择 **`GPIO_Input`**
- 右键 PB13，选 `Enter User Label`，命名为 `LIGHT_SENSOR`

### 1.3 调整 GPIO 参数

- 左侧 **System Core** → **GPIO**，找到刚配置的 `LIGHT_SENSOR`（PB13）
- 在下方 **GPIO Mode and Configuration** 中调整参数：

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| GPIO mode | `Input mode` | 外部输入信号 |
| GPIO Pull-up/Pull-down | `Pull-up`（上拉）或 `No pull-up and no pull-down` | 取决于传感器模块的输出电路 |
| User Label | `LIGHT_SENSOR` | 代码中会用到的宏名 |

> **上拉还是无上下拉？**
>
> - 如果光敏传感器模块（如四针光敏模块）自带**上拉电阻**并有**比较器输出数字信号**，选 `No pull-up and no pull-down`
> - 如果是**裸的光敏电阻分压电路**直接接到 PB13，选 `Pull-up`，默认拉高，有光时拉低

### 1.4 重新生成代码

- 点右上角 **GENERATE CODE**
- CubeMX 会自动在 `main.h` 中生成宏定义：
  - `LIGHT_SENSOR_Pin` → `GPIO_PIN_13`
  - `LIGHT_SENSOR_GPIO_Port` → `GPIOB`

---

## 第二步：在 FreeRTOS 任务中读取传感器

### 2.1 添加读取函数

打开 `main.c`，在 `/* USER CODE BEGIN 4 */` 区域添加一个读取任务：

```c
/* USER CODE BEGIN 4 */

void StartLightSensor(void *argument)
{
  for(;;)
  {
    GPIO_PinState state = HAL_GPIO_ReadPin(LIGHT_SENSOR_GPIO_Port, LIGHT_SENSOR_Pin);

    if (state == GPIO_PIN_RESET)
    {
      // 有光照（传感器输出低电平）
    }
    else
    {
      // 无光照（传感器输出高电平）
    }

    osDelay(100);
  }
}

/* USER CODE END 4 */
```

### 2.2 在 CubeMX 中注册新任务

回到 CubeMX：

1. **System Core** → **Tasks and Queues** → 点 **Add**
2. 配置：
   - **Task Name**：`LightSensor`
   - **Entry Function**：`StartLightSensor`
   - **Priority**：`osPriorityNormal`
   - **Code Generation Option**：勾选 `As weak`
3. 重新 **GENERATE CODE**

> 和之前创建 LED 任务一样，**Entry Function 必须和 `main.c` 中的函数名一致**。

### 2.3 编译下载

- 保存、编译、下载到开发板

---

## 第三步：验证

### 3.1 接线

| 光敏模块引脚 | STM32 引脚 |
|-------------|-----------|
| VCC | 3.3V |
| GND | GND |
| DO（数字输出） | PB13 |

> AO（模拟输出）接 ADC 输入引脚，本篇只讲数字输出，ADC 方式后续再补充。

### 3.2 预期现象

- 遮挡光敏传感器 → PB13 读取到低电平（`GPIO_PIN_RESET`）
- 光照正常 → PB13 读取到高电平（`GPIO_PIN_SET`）
- 可以在 `StartLightSensor` 任务中加入 LED 控制逻辑，实现"暗了就亮灯"的效果

### 3.3 扩展：光照控制 LED 示例

```c
void StartLightSensor(void *argument)
{
  for(;;)
  {
    GPIO_PinState state = HAL_GPIO_ReadPin(LIGHT_SENSOR_GPIO_Port, LIGHT_SENSOR_Pin);

    if (state == GPIO_PIN_RESET)
    {
      HAL_GPIO_WritePin(LED_GREEN_GPIO_Port, LED_GREEN_Pin, GPIO_PIN_SET);
    }
    else
    {
      HAL_GPIO_WritePin(LED_GREEN_GPIO_Port, LED_GREEN_Pin, GPIO_PIN_RESET);
    }

    osDelay(100);
  }
}
```

---

## 什么时候需要信号量？

当前示例是**轮询读取 GPIO**，`HAL_GPIO_ReadPin()` 本身是原子操作，各任务也没有共享资源，所以不需要信号量。但后续扩展到以下场景就需要同步机制了：

| 场景 | 需要的同步机制 |
|------|---------------|
| 传感器任务读数据，通过**共享变量**传给显示任务 | **互斥锁（Mutex）** 保护共享变量 |
| 传感器用 **EXTI 中断**触发，通知任务处理 | **二值信号量（Binary Semaphore）** |
| 多个任务抢同一个 **ADC** 做不同采集 | **互斥锁** 保护 ADC 外设 |
| 传感器数据通过**队列**传给其他任务 | **队列（Queue）** 自带阻塞/同步 |

简单总结：**轮询读 GPIO → 不需要；涉及共享资源或中断通知 → 需要。**

---

## 关键 API 速查

| 函数 | 用途 |
|------|------|
| `HAL_GPIO_ReadPin(GPIOx, GPIO_Pin)` | 读取引脚电平，返回 `GPIO_PIN_SET`（高）或 `GPIO_PIN_RESET`（低） |
| `HAL_GPIO_WritePin(GPIOx, GPIO_Pin, PinState)` | 设置引脚输出电平 |
| `HAL_GPIO_TogglePin(GPIOx, GPIO_Pin)` | 翻转引脚电平 |
