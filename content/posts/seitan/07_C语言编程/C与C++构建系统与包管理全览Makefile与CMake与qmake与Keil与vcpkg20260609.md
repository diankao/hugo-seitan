+++
title = 'C与C++构建系统与包管理全览：Makefile与CMake与qmake与Keil与vcpkg'
date = 2026-06-09T00:00:00+08:00
draft = false
categories = ['嵌入式']
tags = ['面试题', 'C++', 'Makefile', 'CMake', 'qmake', 'Keil', 'vcpkg', '构建系统', '包管理']
+++

# C与C++构建系统与包管理全览：Makefile与CMake与qmake与Keil与vcpkg

## 题目

C/C++ 项目有哪些构建工具？Makefile 和 CMake 有什么区别？Qt 为什么从 qmake 切换到 CMake？Keil 的构建系统是怎么工作的？vcpkg、conan 等 C++ 包管理器怎么选？不同操作系统上有什么差异？

## 考察点

构建系统理解、Makefile 与 CMake 与 qmake 的定位差异、Keil 构建机制、包管理工具选型、跨平台构建实践

## 回答要点

### 1. C/C++ 构建工具全景

```
源代码 (.c/.cpp/.h)
        │
        ▼
   ┌────────────────────┐
   │     构建系统         │  生成构建指令
   │ CMake / qmake       │
   │ Meson / Bazel       │
   │ Keil .uvprojx       │
   └──────┬─────────────┘
          │ 生成
          ▼
   ┌────────────────────┐
   │     构建引擎         │  执行编译链接
   │ Make / Ninja        │
   │ MSBuild / jom       │
   │ Keil Builder        │
   └──────┬─────────────┘
          │ 调用
          ▼
   ┌────────────────────┐
   │      编译器          │  GCC / Clang / MSVC
   │      链接器          │  armcc / armclang / ld
   └──────┬─────────────┘
          │ 产出
          ▼
   可执行文件 / 静态库 / 动态库 / .hex / .bin / .axf
```

| 工具类型 | 代表 | 作用 |
|---------|------|------|
| 构建系统（元构建） | CMake、qmake、Meson、Bazel | 生成构建指令 |
| 构建引擎 | Make、Ninja、MSBuild | 执行增量编译 |
| IDE 内置构建 | Keil µVision、IAR EWARM | 封装了完整的构建流程 |
| 包管理器 | vcpkg、conan、xmake | 管理第三方依赖 |
| 编译器 | GCC、Clang、MSVC、armcc/armclang | 编译源代码 |

### 2. Makefile —— 最基础的构建方式

Makefile 是 `make` 工具的输入文件，定义文件间的依赖关系和构建规则。

**基本语法：**

```makefile
# 变量定义
CC = gcc
CFLAGS = -Wall -O2 -g
TARGET = myapp
SRCS = main.c utils.c network.c
OBJS = $(SRCS:.c=.o)

# 默认目标
$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^

# 编译规则
%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# 清理
clean:
	rm -f $(OBJS) $(TARGET)

# 伪目标
.PHONY: clean
```

**关键概念：**

| 概念 | 说明 |
|------|------|
| 目标（target） | 要生成的文件名 |
| 依赖（prerequisites） | 目标依赖的文件 |
| 命令（recipe） | 生成目标的 shell 命令，**必须用 Tab 缩进** |
| 自动变量 `$@` | 当前目标名 |
| 自动变量 `$<` | 第一个依赖文件 |
| 自动变量 `$^` | 所有依赖文件 |
| 模式规则 `%` | 通配符，如 `%.o: %.c` |
| `.PHONY` | 声明伪目标（不对应实际文件） |

**嵌入式 Makefile 示例（交叉编译）：**

```makefile
# 交叉编译工具链
CROSS = arm-none-eabi-
CC = $(CROSS)gcc
OBJCOPY = $(CROSS)objcopy
SIZE = $(CROSS)size

# 编译选项
MCU_FLAGS = -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
CFLAGS = $(MCU_FLAGS) -Wall -O2 -ffunction-sections -fdata-sections
LDFLAGS = -T STM32F407.ld -Wl,--gc-sections -specs=nano.specs

# 源文件
C_SRCS = main.c stm32f4xx_it.c system_stm32f4xx.c
ASM_SRCS = startup_stm32f407xx.s
OBJS = $(C_SRCS:.c=.o) $(ASM_SRCS:.s=.o)

TARGET = firmware.elf

all: $(TARGET).bin $(TARGET).hex

$(TARGET): $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $^
	$(SIZE) $@

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

%.o: %.s
	$(CC) $(MCU_FLAGS) -c $< -o $@

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@

%.hex: %.elf
	$(OBJCOPY) -O ihex $< $@

flash: $(TARGET).hex
	openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c "program $< verify reset exit"

.PHONY: all flash clean
clean:
	rm -f $(OBJS) $(TARGET) $(TARGET).bin $(TARGET).hex
```

**Makefile 的局限：**

- 跨平台困难（Windows 上需要 MinGW/MSYS2 的 make）
- 大型项目手写 Makefile 极其痛苦
- 依赖检测需要手动管理
- 没有内置的第三方库管理
- 调试困难（Tab vs 空格是经典坑）

### 3. CMake —— 事实标准的构建系统

CMake 不直接编译代码，而是**生成**对应平台的构建文件（Makefile、Ninja 文件、VS 工程、Xcode 工程等）。

**CMake vs Makefile：**

| 维度 | Makefile | CMake |
|------|----------|-------|
| 定位 | 构建引擎 | 构建系统（元构建） |
| 跨平台 | 差 | 好 |
| 生成器 | 无 | Make/Ninja/VS/Xcode |
| 依赖管理 | 手动 | `find_package` / vcpkg 集成 |
| IDE 支持 | 无 | VS Code / CLion / VS 原生支持 |
| 学习曲线 | 中等 | 中高 |
| 适用场景 | 小型/嵌入式项目 | 中大型项目 |

**基础 CMakeLists.txt：**

```cmake
cmake_minimum_required(VERSION 3.20)
project(MyApp VERSION 1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# 源文件
add_executable(myapp
    src/main.cpp
    src/utils.cpp
    src/network.cpp
)

# 头文件搜索路径
target_include_directories(myapp PRIVATE
    ${CMAKE_SOURCE_DIR}/include
)

# 链接库
target_link_libraries(myapp PRIVATE
    pthread
    m
)

# 编译选项
target_compile_options(myapp PRIVATE
    -Wall -Wextra -O2
)
```

**CMake 常用命令速查：**

```cmake
# 变量
set(MY_VAR "hello")
message(STATUS "value = ${MY_VAR}")

# 条件
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    target_compile_definitions(myapp PRIVATE DEBUG_MODE)
endif()

# 查找系统库
find_package(Threads REQUIRED)
target_link_libraries(myapp PRIVATE Threads::Threads)

# 添加子目录
add_subdirectory(lib/mylib)

# 构建静态库
add_library(mylib STATIC src/lib.cpp)
target_include_directories(mylib PUBLIC include/)

# 安装规则
install(TARGETS myapp DESTINATION bin)
install(FILES include/mylib.h DESTINATION include)

# 交叉编译工具链文件 (toolchain.cmake)
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_C_COMPILER arm-linux-gnueabihf-gcc)
set(CMAKE_CXX_COMPILER arm-linux-gnueabihf-g++)
```

**CMake 交叉编译（嵌入式）：**

```cmake
# toolchain_stm32.cmake
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR ARM)

set(CROSS_PREFIX arm-none-eabi-)
set(CMAKE_C_COMPILER ${CROSS_PREFIX}gcc)
set(CMAKE_CXX_COMPILER ${CROSS_PREFIX}g++)
set(CMAKE_ASM_COMPILER ${CROSS_PREFIX}gcc)
set(CMAKE_AR ${CROSS_PREFIX}ar)
set(CMAKE_OBJCOPY ${CROSS_PREFIX}objcopy)
set(CMAKE_SIZE ${CROSS_PREFIX}size)

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
```

```bash
# 使用工具链文件构建
cmake -DCMAKE_TOOLCHAIN_FILE=toolchain_stm32.cmake -B build
cmake --build build
```

**CMake 生成器选择：**

| 生成器 | 平台 | 适用场景 |
|--------|------|---------|
| `Unix Makefiles` | Linux/macOS | 传统方式 |
| `Ninja` | 全平台 | **推荐**，比 Make 快很多 |
| `Visual Studio 17 2022` | Windows | VS 开发 |
| `NMake Makefiles` | Windows | 命令行构建 |
| `MinGW Makefiles` | Windows | MinGW 环境 |
| `Xcode` | macOS | Xcode 开发 |

```bash
# 推荐：用 Ninja 构建
cmake -G Ninja -B build
cmake --build build
```

### 4. qmake 与 .pro 文件 —— Qt 专属构建系统（已弃用）

qmake 是 Qt 自己的构建系统，通过 `.pro` 项目文件描述项目结构。

**典型 .pro 文件：**

```ini
# basic.pro
QT += core gui widgets

TARGET = myapp
TEMPLATE = app

SOURCES += \
    main.cpp \
    mainwindow.cpp

HEADERS += \
    mainwindow.h

FORMS += \
    mainwindow.ui

# 编译选项
CONFIG += c++17
CONFIG += debug_and_release

# 链接外部库
LIBS += -lpthread
INCLUDEPATH += $$PWD/include

# 条件判断
win32 {
    SOURCES += win_specific.cpp
}
unix {
    SOURCES += linux_specific.cpp
}
```

**qmake 的工作流程：**

```
.pro 文件 → qmake → Makefile → make → 可执行文件
```

qmake 本质上是一个 Makefile 生成器，只支持生成 Makefile（不能生成 Ninja/VS 工程）。

**Qt 为什么放弃 qmake 切换到 CMake？**

Qt 6 起官方全面切换到 CMake，原因如下：

| 维度 | qmake (.pro) | CMake (CMakeLists.txt) |
|------|-------------|----------------------|
| 通用性 | 仅 Qt 项目 | C++ 生态通用标准 |
| IDE 支持 | Qt Creator 专属 | VS / CLion / VS Code 全支持 |
| 包管理 | 无 | vcpkg / conan 集成 |
| 社区生态 | 小（仅 Qt 社区） | 巨大（C++ 标准构建系统） |
| 语言能力 | 自定义语法，功能有限 | 完整脚本语言 + 大量内置模块 |
| 第三方库集成 | 困难（手动写 LIBS/INCLUDEPATH） | `find_package` 一行搞定 |
| 跨平台构建 | 有限（只能生成 Makefile） | 生成 Make/Ninja/VS/Xcode |
| 现代工具链 | 不支持 | Presets、CCache、分析工具 |
| 未来维护 | Qt 官方不再投入 | 社区活跃，持续发展 |

**迁移建议：**

```cmake
# Qt 6 项目的 CMakeLists.txt（替代 .pro）
find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets)

add_executable(myapp
    main.cpp
    mainwindow.cpp
    mainwindow.h
    mainwindow.ui
)

target_link_libraries(myapp PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
)

# 自动处理 .ui 文件
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
```

**总结：新项目直接用 CMake，旧 Qt 5 项目可逐步迁移。qmake 已是过去式。**

### 5. Keil µVision 构建系统 —— MCU 开发的 IDE 方案

Keil 是 ARM Cortex-M 开发中最常用的 IDE，其构建系统是**完全封闭的 GUI 驱动**方式，不使用 Makefile 或 CMake。

**Keil 工程文件结构：**

| 文件 | 作用 |
|------|------|
| `.uvprojx` | 工程主文件（XML 格式），定义源文件、编译选项、链接选项 |
| `.uvoptx` | 工程选项（调试配置、下载设置等） |
| `.sct` | Scatter 文件（链接脚本），定义内存布局 |
| `RTE/` | Run-Time Environment，Keil 的组件管理目录 |

**Keil 的构建流程：**

```
.uvprojx 工程文件
    │
    ├── 源文件列表 (.c / .s / .cpp)
    ├── 编译器选项 (armcc / armclang)
    │       ├── Include Paths
    │       ├── Define Macros
    │       ├── Optimization Level
    │       └── CPU Type (Cortex-M4/M7...)
    ├── 链接选项
    │       ├── Scatter File (.sct)
    │       └── 库文件
    └── 输出设置
            ├── .axf (ELF 可执行文件)
            ├── .hex (Intel HEX)
            └── .bin (二进制)
```

**Keil 的编译器演进：**

| 编译器 | 版本 | 特点 |
|--------|------|------|
| **armcc** (ARMCC v5) | Keil MDK 5 之前 | 旧版，AC5 like 语法，不支持 C++17+ |
| **armclang** (ARMClang v6) | Keil MDK 5.29+ | 基于 LLVM，支持 C11/C++14/C++17，**推荐** |

**Keil vs GCC + Makefile/CMake 对比：**

| 维度 | Keil µVision | GCC + CMake/Makefile |
|------|-------------|---------------------|
| 成本 | 商业授权（免费版 32KB 限制） | 免费 |
| IDE 体验 | GUI 一体化，上手快 | 需要 VS Code / CLion 配合 |
| 编译器 | armcc / armclang | arm-none-eabi-gcc |
| 调试 | 内置调试器 + ULINK/J-Link | OpenOCD / J-Link GDB |
| 项目管理 | .uvprojx（XML，合并冲突多） | CMakeLists.txt（纯文本，Git 友好） |
| 跨平台 | 仅 Windows | 全平台 |
| 代码体积优化 | armcc 优化好（尤其 -Oz） | GCC -Os 也不错 |
| CMSIS 支持 | 内置 RTE 一键添加 | 需手动下载/用 CMSIS Pack |
| 自动化 | 命令行 `UV4 -b project.uvprojx` | `cmake --build` |
| 包管理 | Pack Installer（CMSIS Pack） | vcpkg / 手动 |

**Keil 构建的关键配置项：**

```
工程配置（Project → Options for Target）：

1. Target 标签页
   - Xtal(MHz)：外部晶振频率（仅影响仿真）
   - Read/Only Memory Areas：Flash 起始地址和大小
   - Read/Write Memory Areas：RAM 起始地址和大小

2. C/C++ 标签页
   - Define：预定义宏（如 USE_HAL_DRIVER, STM32F407xx）
   - Include Paths：头文件搜索路径
   - Optimization：Level 0~3
   - Warnings：All Warnings / None

3. Linker 标签页
   - Use Memory Layout from Target Dialog：勾选则用 GUI 配置
   - Scatter File：自定义 .sct 链接脚本
   - Misc Controls：--map --list=map_report.map

4. Debug 标签页
   - 选择调试器：ULINK / J-Link / ST-Link
   - Initialization File：调试初始化脚本

5. Utilities 标签页
   - 选择下载工具
   - Programming Algorithm：Flash 烧录算法
```

**Keil 的 Scatter 文件（.sct）示例：**

```
; STM32F407 的 scatter 文件
LR_IROM1 0x08000000 0x00100000  {    ; Flash: 1MB @ 0x08000000
  ER_IROM1 0x08000000 0x00100000  {  ; 加载域 = Flash
   *.o (RESET, +First)               ; 启动代码放最前面
   *(InRoot$$Sections)
   .ANY (+RO)                         ; 所有只读代码
  }

  RW_IRAM1 0x20000000 0x00020000  {  ; SRAM: 128KB @ 0x20000000
   .ANY (+RW +ZI)                     ; 所有读写数据
  }

  RW_IRAM2 0x10000000 0x00010000  {  ; CCM: 64KB @ 0x10000000
   *.o (.ccm_data)                    ; 自定义段放 CCM
  }
}
```

**Keil 命令行构建（CI/CD 用）：**

```bash
# 命令行编译
UV4 -b project.uvprojx -o build_log.txt

# 命令行下载
UV4 -f project.uvprojx -o flash_log.txt

# 返回码：0=成功，1=警告，2=错误，3=致命错误
```

**Keil 项目迁移到 CMake 的建议：**

很多团队在项目变大后选择从 Keil 迁移到 GCC + CMake，理由：
- Keil 工程文件是 XML，多人协作合并困难
- CI/CD 自动化不如命令行工具链灵活
- 32KB 免费限制在商业项目中不可接受
- GCC 生态更开放，第三方库集成方便

迁移时注意 armcc 和 GCC 的差异：
- `__attribute__((at(address)))` → `__attribute__((section(".my_section")))` + 链接脚本
- `#pragma arm` / `#pragma thumb` → `-mthumb` 编译选项
- Keil 的 `__inline` → 标准 `inline`
- 启动文件 `.s` 可能需要替换为 GCC 版本

### 6. 各操作系统的构建环境

**Windows：**

| 工具链 | 安装方式 | 说明 |
|--------|---------|------|
| MSVC | Visual Studio Installer | 微软官方编译器 |
| MinGW-w64 | `choco install mingw` / MSYS2 | GCC 的 Windows 移植 |
| Clang | Visual Studio Installer / LLVM | 可搭配 MSVC 或 MinGW 使用 |
| CMake | Visual Studio 内置 / `choco install cmake` | |
| Ninja | Visual Studio 内置 / `choco install ninja` | |

```powershell
# Windows 上典型构建流程
cmake -G "Visual Studio 17 2022" -B build
cmake --build build --config Release

# 或用 Ninja + MSVC（需要先打开 Developer Command Prompt）
cmake -G Ninja -B build
cmake --build build
```

**Linux：**

```bash
# Debian/Ubuntu
sudo apt install build-essential cmake ninja-build

# Fedora
sudo dnf install gcc gcc-c++ cmake ninja-build

# Arch
sudo pacman -S base-devel cmake ninja

# 构建流程
cmake -G Ninja -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
sudo cmake --install build
```

**macOS：**

```bash
# Xcode Command Line Tools（包含 Clang、Make）
xcode-select --install

# Homebrew 安装工具
brew install cmake ninja

# 构建
cmake -G Ninja -B build
cmake --build build
```

### 7. C++ 包管理器

C++ 长期缺少统一的包管理器（不像 Python 的 pip、Node 的 npm），目前主流方案：

| 包管理器 | 维护方 | 特点 |
|---------|--------|------|
| **vcpkg** | Microsoft | 仓库最大、与 CMake 集成好、三平台支持 |
| **conan** | JFrog（社区） | 灵活、去中心化、支持多种构建系统 |
| **xmake** | 国内开发者 | 构建系统 + 包管理一体化、中文友好 |
| **Bazel** | Google | 大型项目、支持多语言、学习曲线高 |
| **system packages** | 操作系统 | apt / yum / brew / vcpkg |

**vcpkg 实战（推荐方案）：**

```bash
# 安装 vcpkg
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg && bootstrap-vcpkg.bat   # Windows
# 或: ./bootstrap-vcpkg.sh        # Linux/macOS

# 安装库
./vcpkg install fmt
./vcpkg install boost-asio
./vcpkg install nlohmann-json
./vcpkg install opencv4

# 集成到 CMake（方式一：CMakePresets.json）
```

```json
// CMakePresets.json
{
    "version": 3,
    "configurePresets": [
        {
            "name": "default",
            "binaryDir": "${sourceDir}/build",
            "cacheVariables": {
                "CMAKE_TOOLCHAIN_FILE": "$env{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake"
            }
        }
    ]
}
```

```cmake
# CMakeLists.txt 中使用 vcpkg 安装的库
find_package(fmt CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(Boost COMPONENTS asio CONFIG REQUIRED)

target_link_libraries(myapp PRIVATE
    fmt::fmt
    nlohmann_json::nlohmann_json
    Boost::asio
)
```

```bash
# 构建流程
cmake --preset default
cmake --build build
```

**vcpkg 在 CMakeLists.txt 中声明依赖（manifest 模式）：**

```json
// vcpkg.json（放在项目根目录）
{
    "name": "myapp",
    "version": "1.0.0",
    "dependencies": [
        "fmt",
        "nlohmann-json",
        {
            "name": "boost-asio",
            "version>=": "1.82.0"
        }
    ]
}
```

manifest 模式下 vcpkg 会自动安装 `vcpkg.json` 中声明的依赖，无需手动 `vcpkg install`。

**vcpkg 交叉编译：**

```bash
# ARM Linux 交叉编译
./vcpkg install boost-asio:arm-linux
cmake -DCMAKE_TOOLCHAIN_FILE=toolchain_arm.cmake \
      -DVCPKG_CHAINLOAD_TOOLCHAIN_FILE=toolchain_arm.cmake \
      -DVCPKG_TARGET_TRIPLET=arm-linux \
      -B build
```

**conan 实战：**

```ini
# conanfile.txt
[requires]
fmt/10.1.1
nlohmann_json/3.11.2
boost/1.83.0

[generators]
CMakeDeps
CMakeToolchain

[options]
boost/*:without_python=True
```

```cmake
# CMakeLists.txt
find_package(fmt REQUIRED)
find_package(nlohmann_json REQUIRED)
target_link_libraries(myapp PRIVATE fmt::fmt nlohmann_json::nlohmann_json)
```

```bash
# 安装依赖并构建
conan install . --output-folder=build --build=missing
cmake -B build -DCMAKE_TOOLCHAIN_FILE=build/conan_toolchain.cmake
cmake --build build
```

### 8. 构建系统选型决策

| 项目规模 | 推荐方案 |
|---------|---------|
| MCU 裸机（单芯片） | Makefile（Keil/IAR 自带构建） |
| MCU 裸机（多模块） | CMake + 自定义工具链 |
| 嵌入式 Linux | CMake + vcpkg/conan |
| 桌面应用（跨平台） | CMake + vcpkg |
| 大型多语言项目 | Bazel |
| 快速原型 | xmake |

**嵌入式项目的典型构建工具链：**

| 场景 | 编译器 | 构建系统 | 包管理 |
|------|--------|---------|--------|
| STM32 裸机 | arm-none-eabi-gcc | Makefile / CMake | 手动管理 |
| ESP32 | xtensa-esp32-elf-gcc | CMake（ESP-IDF 内置） | ESP-IDF 组件管理器 |
| 嵌入式 Linux | arm-linux-gnueabihf-gcc | CMake + Ninja | vcpkg（交叉编译） |
| 上位机（Windows） | MSVC | CMake + VS | vcpkg |
| 上位机（跨平台） | Clang/GCC/MSVC | CMake + Ninja | vcpkg |

### 9. 常见面试追问

**Q：CMake 的 `find_package` 怎么找到库的？**

两种模式：
- **Module 模式**：搜索 `CMAKE_MODULE_PATH` 下的 `FindXXX.cmake` 文件
- **Config 模式**：搜索 `XXXConfig.cmake` 或 `xxx-config.cmake` 文件（vcpkg 安装的库都是这种）

优先 Module，找不到则尝试 Config。

**Q：静态库和动态库在构建时有什么区别？**

```cmake
# 静态库：链接时复制到可执行文件中
add_library(mylib STATIC src/lib.cpp)

# 动态库：运行时加载
add_library(mylib SHARED src/lib.cpp)

# 嵌入式通常用静态库，避免运行时依赖
```

**Q：vcpkg 和 conan 怎么选？**

| 维度 | vcpkg | conan |
|------|-------|-------|
| 上手难度 | 低 | 中 |
| 仓库数量 | 多 | 多 |
| CMake 集成 | 原生（toolchain） | 通过生成器 |
| 二进制缓存 | 有 | 有（更灵活） |
| 私有仓库 | 注册表模式 | 直接推 Artifactory |
| 推荐场景 | Windows/CMake 项目 | 需要灵活配置的项目 |

**嵌入式项目推荐 vcpkg**：与 CMake 集成最简单，manifest 模式依赖声明清晰，交叉编译支持好。
