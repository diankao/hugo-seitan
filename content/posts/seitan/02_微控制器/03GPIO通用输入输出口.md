+++
title = 'GPIO通用输入输出口'
date = 2026-03-17T00:00:00+08:00
draft = false
categories = ['微控制器']
tags = ['GPIO', '输出模式', '硬件设计']
+++
# 3 GPIO通用输入输出口

 [toc]

注：笔记主要参考B站 [江科大自化协](https://space.bilibili.com/383400717) 教学视频"[STM32入门教程-2023持续更新中](https://www.bilibili.com/video/BV1th411z7sn/)"。
注：工程及代码文件放在了本人的[Github仓库](https://github.com/jjejdhhd/Learn_stm32f103/tree/main)。
***

## 3.1 GPIO输入输出原理
 **GPIO**（General Purpose Input Output）**通用输入输出口** 可配置为8种输入输出模式。引脚电平范围为0V\~3.3V，部分引脚可容忍5V（图1-6中IO口电平为FT标识的）。**输出模式** 下可控制端口输出高低电平，用以驱动LED、控制蜂鸣器、模拟通信协议输出时序等，当然若驱动大功率设备还需要添加驱动电路。**输入模式** 下可读取端口的高低电平或电压，用于读取按键输入、外接模块电平信号输入、ADC电压采集、模拟通信协议接收数据等。

![图3-1 GPIO基本结构](https://raw.githubusercontent.com/jjejdhhd/Git_img2023/main/STM32F103_JKD/3-1GPIO%E5%9F%BA%E6%9C%AC%E7%BB%93%E6%9E%84.png)

上图给出了GPIO的基本结构图。在STM32中，所有的GPIO都挂载在APB2外设总线上。命名方式采用GPIOA、GPIOB、GPIOC...的方式来命名。每个GPIO模块内，主要包括寄存器、驱动器等。
> - 寄存器就是一段特殊的存储器，内核可以通过APB2总线对寄存器进行读写，从而完成输出电平和读取电平的功能。该寄存器的每一位都对应一个引脚，由于stm32是32位的单片机，所以所有的寄存器都是32位的，也就是说只有寄存器的低16位对应上了相应的GPIO口。
> - 驱动器就是增加信号的驱动能力的。
>
> 注：stm32f103c8t6芯片上48个引脚，除了基本的电源和晶振等维持系统正常运行的引脚外，分别包括PA0\~PA15、PB0\~PB15、PC13\~PC15。

![图3-2 GPIO位结构](https://raw.githubusercontent.com/jjejdhhd/Git_img2023/main/STM32F103_JKD/3-2GPIO%E4%BD%8D%E7%BB%93%E6%9E%84.png)

上图就是将"GPIO的基本结构"进行放大，得到的实际的位结构。
> **输入部分：**
> - 整体框架从左到右依次是寄存器、驱动器、IO引脚，从上到下分为"输入"、"输出"。
> - 最右侧的IO引脚上两个保护二极管，其作用是对IO引脚的输出电压进行限幅在0\~3.3V之间，进而可以避免过高的IO引脚输入电压对电路内部造成伤害。V\~DD\~=3.3V，V\~SS\~=0V。
> > 工作原理：上方二极管接V\_DD（3.3V），下方二极管接V\_SS（0V）。如果输入电压高于3.3V，上方二极管导通，输入电压产生的电流直接流入V\_DD，而不会流入内部电路，避免过高电压对内部电路造成伤害；如果输入电压低于0V（相对于V\_SS，所以可以有负电压），下方二极管导通，电流从V\_SS直接流出，同样保护内部电路。如果输入电压在0V~3.3V之间，两个二极管均不导通，对电路没有影响。
> - 输入驱动器的上、下拉电阻：相应的两个开关可以通过程序进行配置，分别有上拉输入模式（上开关导通&下开关断开）、下拉输入模式（下开关导通&上开关断开）、浮空输入模式（两个开关都断开）。上下拉电阻的作用就是给引脚输入提供一个默认的输入电平，进而避免引脚悬空导致的不确定。都属于弱上拉、弱下拉。
> > 详细作用：对于数字端口，输入不是高电平就是低电平。如果输入引脚什么也不接，输入就会处于一种浮空的状态，引脚的输入电平极易受外界干扰而改变，就像物体悬浮在太空中一样，位置不确定，受到一点扰动就会变化。为了避免引脚悬空导致的输入数据不确定，需要加上上拉或下拉电阻。如果接入上拉电阻，当引脚悬空时，还有上拉电阻保证引脚为高电平，所以上拉输入又可以称作是默认为高电平的输入模式。下拉也是同理，就是默认为低电平的输入方式。这就像是在太空的物体来到了地球上，如果不施加外力，由于重力的下拉作用，默认还是回到地面。上拉电阻和下拉电阻的阻值都是比较大的，是一种弱上拉和弱下拉，目的是尽量不影响正常的输入操作。
> - 输入驱动器的触发器：这里是用肖特基管构成的施密特触发器。只有高于上限、低于下限电压才进行变化，作用是对输入电压进行整形，可以消除电压波纹、使电压的上升沿/下降沿更加陡峭。也就是说，**stm32的GPIO端口会自动对输入的数字电压进行整形。**
> > 执行逻辑：如果输入电压大于某一阈值，输出就会瞬间升为高电平；如果输入电压小于某一阈值，输出就会瞬间降为低电平。由于IO引脚的波形是外界输入的，虽然是数字信号，实际情况下可能会产生各种失真。如果没有施密特触发器，很有可能因为干扰而导致误判。有了施密特触发器，比如设定一个上限和下限，高于上限输出高，低于下限输出低。施密特触发器的输出先是低于下限输出低，然后当高于上限时输出立即变为高。虽然信号由于波动可能再次低于上限，但是对于施密特触发器来说，只有高于上限或者低于下限输出才会变化，所以此时低于上限的情况输出并不会变化，而是继续维持高电平，直到下次低于下限时才会转为低电平。这里信号即使在下限附近来回横跳，因为没有跳到上限上面去，所以输出仍然是稳定的，直到下一次高于上限，输出才会变为高。可以看到相比较输入信号，经过整形的信号就很完美了。在这里使用了两个比较阈值来进行判断，中间留有一定的变化范围，这样可以有效地避免因信号波动造成的输出抖动现象。
> - "模拟输入"、"复用功能输入"：都是连接到片上外设的一些端口，前者用于ADC等需要模拟输入的外设，后者用于串口输入引脚等需要数字量的外设。
>
> **输出部分：**
> - 输出数据：可以由输出数据寄存器（普通的IO口输出）、片上外设来指定，数据选择器控制数据来源。
> - 位设置/清除寄存器：单独操作输出数据的某一位，而不影响其他位。
> - 驱动器中的MOS管：MOS管相当于一种开关，输出信号来控制这两个MOS管的开启状态，进而输出信号。可以选择推挽、开漏、关闭三种输出方式。
> > 1. 推挽输出模式：两个MOS管均有效，stm32对IO口有绝对的控制权，也称为强推输出模式。
> > > 详细工作原理：在推挽输出模式下，P-MOS和N-MOS均有效。数据寄存器为1时上管导通、下管断开，输出直接接到V\_DD，就是输出高电平；数据寄存器为0时上管断开、下管导通，输出直接接到V\_SS，就是输出低电平。这种模式下高低电平均有较强的驱动能力。在推挽输出模式下，STM32对IO口具有绝对的控制权，高低电平都由STM32说了算。
> > 2. 开漏输出模式：P-MOS无效。只有低电平有驱动能力，高电平输出高阻。
> > > 详细工作原理：在开漏输出模式下，P-MOS是无效的，只有N-MOS在工作。数据寄存器为1时下管断开，这时输出相当于断开，也就是高阻态；数据寄存器为0时下管导通，输出直接接到V\_SS，也就是输出低电平。这种模式下只有低电平有驱动能力，高电平是没有驱动能力的。
> > > 开漏模式的用途：开漏模式可以作为通信协议的驱动方式，比如I2C通信的引脚就是使用的开漏模式。在多机通信的情况下，这个模式可以避免各个设备的相互干扰。另外开漏模式还可以用于输出5V的电平信号，比如在IO外接一个上拉电阻到5V的电源，当输出低电平时，由内部的N-MOS直接接V\_SS；当输出高电平时，由外部的上拉电阻拉高至5V，这样就可以输出5V的电平信号，用于兼容一些5V电平的设备。
> > 3. 关闭模式：两个MOS管均无效，端口电平由外部信号控制。

额外补充：stm32如何将数据写入寄存器？
> 1. 通过软件的方式。由于stm32的寄存器只能进行整体读写，所以可以先将数据全部读出，然后代码中用``&=``清零、``|=``置位的方式改变单独某一位的数据，再将改写后的数据写回寄存器。此方法比较麻烦、效率不高，对于IO口进行操作不合适。
> 2. 通过**位设置/清除寄存器**。若对某一位 置1，只需对位设置寄存器的相应位 置1；若对某一位 清零，则对清除寄存器相应位 清零。这种方式通过内置电路完成操作，一步到位。
> > 详细说明：STM32的输出数据寄存器同时控制16个端口，并且这个寄存器只能整体读写，所以如果想单独控制其中某一个端口而不影响其他端口的话，就需要一些特殊的操作方式。第一种方式就是先读出这个寄存器，然后用按位与和按位或的方式更改某一位，最后再将更改后的数据写回去。在C语言中就是&=和|=的操作。这种方法比较麻烦，效率不高，对于IO口的操作而言不太合适。第二种方式就是通过设置位设置和位清除寄存器。如果我们要对某一位进行置1的操作，在位设置寄存器的对应位写1即可，剩下不需要操作的位写0。这样它内部就会有电路自动把输出数据寄存器对应位置1，而剩下的位的位置保持不变。这样就保证了只操作其中某一位而不影响其他位，并且这是一步到位的操作。如果想对某一位进行清零的操作，就在位清除寄存器的对应位写0即可，这样内部电路就会把这一位清零了。
> 3. 通过读写STM32中的"位带"区域。在STM32中，专门分配有一段地址区域，该区域映射了RAM和外设寄存器所有的位。读写这段地址中的数据，就相当于读写所映射位置的某一位。整体流程与51单片机中的位寻址作用差不多。本教程不涉及。

**表3-1 GPIO的8种模式**

| 模式名称 | 性质 | 特征 |
|---------|------|------|
| 浮空输入 | 数字输入 | 可读取引脚电平，若引脚悬空则电平不确定，需要连续驱动源 |
| 上拉输入 | 数字输入 | 可读取引脚电平，内部连接上拉电阻，悬空时默认高电平 |
| 下拉输入 | 数字输入 | 可读取引脚电平，内部连接下拉电阻，悬空时默认低电平 |
| 模拟输入 | 模拟输入 | GPIO无效，引脚直接接入内部ADC（ADC专属配置） |
| 开漏输出 | 数字输出 | 可输出引脚电平，高电平为高阻态，低电平接VSS |
| 推挽输出 | 数字输出 | 可输出引脚电平，高电平接VDD，低电平接VSS |
| 复用开漏输出 | 数字输出 | 由片上外设控制，高电平为高阻态，低电平接VSS |
| 复用推挽输出 | 数字输出 | 由片上外设控制，高电平接VDD，低电平接VSS |

上表给出了GPIO的8种模式，通过配置GPIO的端口配置寄存器即可选择相应的模式。
> 1. 每一个端口的模式由4位进行控制，16个端口就需要64位，也就是两个32位寄存器，即端口配置低寄存器、端口配置高寄存器。
> 2. 输入模式下，输出无效；而输出模式下，输入有效。这是因为一个IO口只能有一个输出，但只有一个输入，所以直接将输出信号输入回去也没问题。
> 3. GPIO输出速度：除了模式配置外，GPIO还有输出速度的配置参数。GPIO的输出速度可以限制输出引脚的最大翻转速度，这个设计出来是为了低功耗和稳定性的。一般要求不高的时候，直接配置成50MHz就可以了。

## 3.2 硬件介绍-LED、蜂鸣器、面包板

首先，简单介绍一下stm32芯片外围的电路。
> - LED：发光二极管，正向通电点亮，反向通电不亮。
> - 有源蜂鸣器（本实验）：内部自带振荡源，将正负极接上直流电压即可持续发声，频率固定。上图所示的蜂鸣器模块使用三极管作为开关。
> - 无源蜂鸣器：内部不带振荡源，需要控制器提供振荡脉冲才可发声，调整提供振荡脉冲的频率，可发出不同频率的声音。
> - 下面是其实物图：
> ![LED和有源蜂鸣器实物图](https://raw.githubusercontent.com/jjejdhhd/Git_img2023/main/STM32F103_JKD/3-3LED%E5%92%8C%E6%9C%89%E6%BA%90%E8%9C%82%E9%B8%A3%E5%99%A8%E5%AE%9E%E7%89%A9%E5%9B%BE.png)
> 注：LED长脚为正极、灯内部小头为正极。本实验的蜂鸣器低电平驱动。

![图3-3 LED和蜂鸣器驱动电路设计](https://raw.githubusercontent.com/jjejdhhd/Git_img2023/main/STM32F103_JKD/3-3LED%E5%92%8C%E8%9C%82%E9%B8%A3%E5%99%A8%E9%A9%B1%E5%8A%A8%E7%94%B5%E8%B7%AF%E8%AE%BE%E8%AE%A1.png)

上图则是给出了LED和蜂鸣器的驱动电路图。注意，**三极管的发射极一定要直接接正电源/地**，这是因为三极管的开启需要发射极和基极之间有一定的电压，如果接在负载侧有可能会导致三极管无法正常开启。

![图3-4 面包板实物图](https://raw.githubusercontent.com/jjejdhhd/Git_img2023/main/STM32F103_JKD/3-4%E9%9D%A2%E5%8C%85%E6%9D%BF%E5%AE%9E%E7%89%A9%E5%9B%BE.png)

上图给出了面包板的示意图。可以看出，面包板中间的金属爪是竖着排列的，用于插各种元器件；上下四排金属爪是横着排列的，一般用于供电。注意，**在使用面包板之前，一定要观察孔位的连接情况**。



## 3.3 实验：LED闪烁、LED流水灯、蜂鸣器提示
**需求1：** 面包板上的LED以1s为周期进行闪烁。亮0.5s、灭0.5s……
> - LED低电平驱动。
> - 需要用到延时函数``Delay.h``、``Delay.c``，在UP注提供的"程序源码"中，为了方便管理，应在工程内创建System文件夹，专门存放这些可以复用的代码。

![图3-5 LED闪烁-接线图](https://raw.githubusercontent.com/jjejdhhd/Git_img2023/main/STM32F103_JKD/3-5%E6%8E%A5%E7%BA%BF%E5%9B%BE-LED%E9%97%AA%E7%83%81.png)

注：实际上，应该在LED和驱动电源之间接上保护电阻，但是由于本电路过于简单，于是直接省略保护电阻。后面"LED流水灯"、"蜂鸣器提示"实验同样省略保护电阻。

![图3-6 LED闪烁-代码调用（除库函数之外）](https://raw.githubusercontent.com/jjejdhhd/Git_img2023/main/STM32F103_JKD/3-6%E4%BB%A3%E7%A0%81%E8%B0%83%E7%94%A8-LED%E9%97%AA%E7%83%81.png)

代码展示：
**- main.c**
```c
#include "stm32f10x.h"                  // Device header
#include "Delay.h"

int main(void){
    // 开启APB2-GPIOA的外设时钟RCC
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);
    // 初始化PA0端口：定义结构体及参数
    GPIO_InitTypeDef GPIO_InitStructure;
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_0;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_Init(GPIOA, &GPIO_InitStructure);

    //下面是对GPIO端口赋值的常用的四种方式
//    GPIO_ResetBits(GPIOA, GPIO_Pin_0);//复位PA0
//    GPIO_SetBits(GPIOA, GPIO_Pin_0);//将PA0置1
//    GPIO_WriteBit(GPIOA, GPIO_Pin_0, Bit_RESET);//将PA0清零
//    GPIO_Write(GPIO_TypeDef* GPIOx, uint16_t PortVal);//此函数可以对16位端口同时操作
    while(1){
        //正常思路
        GPIO_ResetBits(GPIOA, GPIO_Pin_0);//复位PA0
        Delay_ms(500);
        GPIO_SetBits(GPIOA, GPIO_Pin_0);//将PA0置1
        Delay_ms(500);

        //使用GPIO_WriteBit函数，且强制类型转换
        GPIO_WriteBit(GPIOA, GPIO_Pin_0, (BitAction)0);//把0类型转换成BitAction枚举类型
        Delay_ms(500);
        GPIO_WriteBit(GPIOA, GPIO_Pin_0, (BitAction)1);
        Delay_ms(500);
    };
}

```

**- Delay.h**
```c
#ifndef __DELAY_H
#define __DELAY_H

void Delay_us(uint32_t us);
void Delay_ms(uint32_t ms);
void Delay_s(uint32_t s);

#endif

```

**- Delay.c**
```c
#include "stm32f10x.h"

/**
  * @brief  微秒级延时
  * @param  xus 延时时长，范围：0\~233015
  * @retval 无
  */
void Delay_us(uint32_t xus)
{
	SysTick->LOAD = 72 * xus;            //设置定时器重装值
	SysTick->VAL = 0x00;                 //清空当前计数值
	SysTick->CTRL = 0x00000005;          //设置时钟源为HCLK，启动定时器
	while(!(SysTick->CTRL & 0x00010000));//等待计数到0
	SysTick->CTRL = 0x00000004;          //关闭定时器
}

/**
  * @brief  毫秒级延时
  * @param  xms 延时时长，范围：0\~4294967295
  * @retval 无
  */
void Delay_ms(uint32_t xms)
{
	while(xms--)
	{
		Delay_us(1000);
	}
}

/**
  * @brief  秒级延时
  * @param  xs 延时时长，范围：0\~4294967295
  * @retval 无
  */
void Delay_s(uint32_t xs)
{
	while(xs--)
	{
		Delay_ms(1000);
	}
}

```

注：此后``Delay.h``、``Delay.c``将作为常用函数长期存放于``System文件夹``中，后续如果使用到将直接调用不会再在笔记中展示源代码。

编程感想：
> 1. Keil编译过后，整个工程会比较大，不利于分享给别人。可以使用UP主提供的批处理程序，删掉工程中的中间文件后再分享给别人，其他人使用的时候只需要重新编译一下就行。
> 2. 本教程用到了RCC和GPIO两个外设，这些外设的库函数在Library中，一般存放在相应的 **.h** 文件的最后。
> 3. 将LED的短脚接负极，长脚接PA0口，就是高电平驱动方式，但是现象和低电平相同。
> 4. 将GPIO设置成开漏输出模式，可以发现高电平（高阻态）无驱动能力，低电平有驱动能力。



**需求2：** 面包板上的8个LED以0.5s切换一个的速度，实现流水灯。低电平驱动。

![图3-7 LED流水灯-接线图](https://raw.githubusercontent.com/jjejdhhd/Git_img2023/main/STM32F103_JKD/3-7%E6%8E%A5%E7%BA%BF%E5%9B%BE-LED%E6%B5%81%E6%B0%B4%E7%81%AF.png)

代码调用关系与"LED闪烁"实验相同，下面是代码展示：
**- main.c**
```c
#include "stm32f10x.h"                  // Device header
#include "Delay.h"

int main(void){
    // 开启APB2-GPIOA的外设时钟RCC
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);
    // 初始化PA的8个端口：定义结构体及参数
    GPIO_InitTypeDef GPIO_InitStructure;
    //同时定义某几个端口
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_0 | GPIO_Pin_1 | GPIO_Pin_2 | GPIO_Pin_3 |
                                  GPIO_Pin_4 | GPIO_Pin_5 | GPIO_Pin_6 | GPIO_Pin_7;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_Init(GPIOA, &GPIO_InitStructure);

    while(1){
        //使用GPIO_SetBits、GPIO_ResetBits进行赋值，这里仅用于演示"或操作"同时赋值
        GPIO_SetBits(GPIOA, GPIO_Pin_0 | GPIO_Pin_1 | GPIO_Pin_2 | GPIO_Pin_3 |
                            GPIO_Pin_4 | GPIO_Pin_5 | GPIO_Pin_6 | GPIO_Pin_7);
        GPIO_ResetBits(GPIOA, GPIO_Pin_0);
    //    //对指定的端口同时赋值
    //    GPIO_Write(GPIOA, \~0x01);
        Delay_ms(500);
        GPIO_Write(GPIOA, \~0x02);
        Delay_ms(500);
        GPIO_Write(GPIOA, \~0x04);
        Delay_ms(500);
        GPIO_Write(GPIOA, \~0x08);
        Delay_ms(500);
        GPIO_Write(GPIOA, \~0x10);
        Delay_ms(500);
        GPIO_Write(GPIOA, \~0x20);
        Delay_ms(500);
        GPIO_Write(GPIOA, \~0x40);
        Delay_ms(500);
        GPIO_Write(GPIOA, \~0x80);
        Delay_ms(500);
    };
}

```

编程感想：
> 1. 使用或操作 ``|`` 就可以实现只初始化定义某几个GPIO，或者某几个外设的时钟。

**需求3：** 蜂鸣器不断地发出滴滴、滴滴……的提示音。蜂鸣器低电平触发。
注：蜂鸣器执行四个动作为1个周期，分别是响0.1s、静0.1s、响0.1s、静0.7s。

![图3-8 蜂鸣器提示-接线图](https://raw.githubusercontent.com/jjejdhhd/Git_img2023/main/STM32F103_JKD/3-8%E6%8E%A5%E7%BA%BF%E5%9B%BE-%E8%9C%82%E9%B8%A3%E5%99%A8%E6%8F%90%E7%A4%BA.png)

代码调用关系与"LED闪烁"实验相同，下面是代码展示：
**- main.c**
```c
#include "stm32f10x.h"                  // Device header
#include "Delay.h"

int main(void){
    // 开启APB2-GPIOB的外设时钟RCC
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB, ENABLE);
    // 初始化PB12端口：定义结构体及参数
    GPIO_InitTypeDef GPIO_InitStructure;
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_12;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_Init(GPIOB, &GPIO_InitStructure);

    while(1){
        GPIO_ResetBits(GPIOB, GPIO_Pin_12);
        Delay_ms(100);
        GPIO_SetBits(GPIOB, GPIO_Pin_12);
        Delay_ms(100);
        GPIO_ResetBits(GPIOB, GPIO_Pin_12);
        Delay_ms(100);
        GPIO_SetBits(GPIOB, GPIO_Pin_12);
        Delay_ms(100);
        Delay_ms(600);
    };
}

```

编程感想：
> 1. 控制蜂鸣器的IO端口可以随便选，但是不要选择三个JTAG调试端口：PA15、PB3、PB4。本实验选择PB12端口进行输出。
> 2. 关于调用库函数，有以下几种方法：
> > - 直接查看每一个外设的```.h```函数，拖到最后就可以看到本外设的所有库函数，然后在对应的.c文件中查看函数定义和调用方式即可。
> > - 查看库函数的用户手册——"STM32F103xx固件函数库用户手册.pdf"，这个中文版比较老；新版本的用户手册可以在ST公司的帮助文档中查看，但只有英文版。
> > - 百度一下别人的代码。


## 3.4 硬件介绍-按键开关、光敏电阻
![图3-9 按键开关实物图](https://raw.githubusercontent.com/jjejdhhd/Git_img2023/main/STM32F103_JKD/3-10%E5%8E%9F%E7%90%86%E5%9B%BE-%E6%8C%89%E9%94%AE%E5%BC%80%E5%85%B3.png)

按键是最常见的输入设备，按下导通，松手断开。由于按键内部使用的是机械式弹簧片来进行通断的，所以在按下和松手的瞬间会伴随有一连串的抖动。
虽然前面已经说过，GPIO端口有专门的肖特基触发器对输入信号进行整形，但按键开关的抖动幅度大、时间长，所以还是 **需要"软件消抖"**。基本思路就是延迟5\~10ms，跳过抖动时间范围即可。

![图3-10 按键开关电路设计](https://raw.githubusercontent.com/jjejdhhd/Git_img2023/main/STM32F103_JKD/3-10%E7%94%B5%E8%B7%AF%E8%AE%BE%E8%AE%A1-%E6%8C%89%E9%94%AE%E5%BC%80%E5%85%B3.png)
