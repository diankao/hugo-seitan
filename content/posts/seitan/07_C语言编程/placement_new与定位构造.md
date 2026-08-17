+++
title = 'placement new 与定位new'
date = 2026-09-23T00:00:00+08:00
draft = false
categories = ['技术文档']
tags = ['C++', '内存管理', 'placement new']
+++

# placement new 与定位 new

## 面试题目

什么是 placement new？

## 考察点

内存分配机制、new 操作符重载、定点构造、内存池

## 回答要点

### 1. 三种 new 的区别

C++ 中 `new` 有三种形式：

| 形式 | 作用 | 可否重载 |
|------|------|----------|
| `new` (plain new) | 分配内存 + 调用构造函数 | 是 |
| `nothrow new` | 分配失败返回 nullptr 而非抛异常 | 是 |
| `placement new` | 在已有内存上构造对象，不分配内存 | 是 |

```cpp
// plain new
int* p1 = new int(42);

// nothrow new
int* p2 = new(std::nothrow) int(42);

// placement new
char buffer[sizeof(int)];
int* p3 = new(buffer) int(42);
```

---

### 2. placement new 的用法

placement new 在已分配的内存地址上构造对象，**不分配新内存**，只调用构造函数。

```cpp
#include <new>

class MyClass {
public:
    int value;
    MyClass(int v) : value(v) {
        std::cout << "MyClass constructed: " << value << std::endl;
    }
    ~MyClass() {
        std::cout << "MyClass destroyed: " << value << std::endl;
    }
};

int main() {
    char buffer[sizeof(MyClass)];

    MyClass* obj = new(buffer) MyClass(42);

    std::cout << obj->value << std::endl;

    obj->~MyClass();

    return 0;
}
```

#### 关键要点

1. **需要预先分配内存**：buffer 由调用方提供
2. **需要手动调用析构函数**：不能用 `delete`，因为内存不是由 `new` 分配的
3. **不能对 buffer 用 `delete`**：buffer 通常是栈数组或内存池中的块

---

### 3. placement new 的典型应用

#### 3.1 内存池

```cpp
class MemoryPool {
private:
    std::vector<char*> chunks;
    size_t blockSize;
    size_t capacity;
    char* freePtr;

public:
    MemoryPool(size_t blockSz, size_t count)
        : blockSize(blockSz), capacity(count) {
        chunks.push_back(new char[blockSize * count]);
        freePtr = chunks.back();
    }

    ~MemoryPool() {
        for (auto chunk : chunks) {
            delete[] chunk;
        }
    }

    void* allocate() {
        if (freePtr >= chunks.back() + blockSize * capacity) {
            return nullptr;
        }
        void* ptr = freePtr;
        freePtr += blockSize;
        return ptr;
    }
};

class HeavyObject {
public:
    int data[100];
    HeavyObject(int val) {
        for (int i = 0; i < 100; i++) data[i] = val + i;
    }
    ~HeavyObject() {}
};

int main() {
    MemoryPool pool(sizeof(HeavyObject), 10);

    void* mem = pool.allocate();
    HeavyObject* obj = new(mem) HeavyObject(42);

    obj->~HeavyObject();
}
```

#### 3.2 自定义容器中的就地构造

STL 容器内部大量使用 placement new：

```cpp
template <typename T>
class SimpleVector {
    T* data;
    size_t size;
    size_t capacity;

public:
    SimpleVector(size_t cap) : size(0), capacity(cap) {
        data = static_cast<T*>(::operator new(sizeof(T) * capacity));
    }

    ~SimpleVector() {
        for (size_t i = 0; i < size; i++) {
            data[i].~T();
        }
        ::operator delete(data);
    }

    template <typename... Args>
    void emplace_back(Args&&... args) {
        new(data + size) T(std::forward<Args>(args)...);
        size++;
    }
};
```

#### 3.3 标准库的 `std::allocator`

```cpp
#include <memory>

std::allocator<int> alloc;
int* p = alloc.allocate(5);

for (int i = 0; i < 5; i++) {
    new(p + i) int(i * 10);
}

for (int i = 0; i < 5; i++) {
    std::cout << p[i] << std::endl;
    (p + i)->~int();
}

alloc.deallocate(p, 5);
```

---

### 4. 对齐问题

placement new 要求目标内存满足对象的对齐要求：

```cpp
class AlignTest {
    double d;
    int i;
};

// 可能有问题：char 数组不保证对齐
char buffer1[sizeof(AlignTest)];
// AlignTest* p1 = new(buffer1) AlignTest();  // 可能未对齐

// 正确做法：使用 alignas
alignas(AlignTest) char buffer2[sizeof(AlignTest)];
AlignTest* p2 = new(buffer2) AlignTest();

// C++17：使用 std::aligned_storage
using Storage = std::aligned_storage<sizeof(AlignTest), alignof(AlignTest)>::type;
Storage storage;
AlignTest* p3 = new(&storage) AlignTest();
```

---

### 5. placement new 与普通 new 的完整对比

| 维度 | plain new | placement new |
|------|-----------|---------------|
| 分配内存 | 是 | 否 |
| 调用构造函数 | 是 | 是 |
| 释放方式 | `delete` | 手动调用析构函数 |
| 失败行为 | 抛出 `std::bad_alloc` | 不分配，不会失败 |
| 典型用途 | 一般对象创建 | 内存池、自定义容器、就地构造 |
| 性能 | 较慢（涉及系统调用） | 快（跳过内存分配） |

---

## 扩展问题

面试官可能会追问：
- 如何重载 operator new？
- `::operator new` 和 `new` 有什么区别？
- 为什么 placement new 不能用 delete 释放？
- 内存池如何回收使用 placement new 构造的对象？
- `std::vector::emplace_back` 是如何利用 placement new 的？

### 如何重载 operator new

可以重载全局或类级别的 `operator new`，实现自定义内存分配策略。

#### 类级别重载

```cpp
class MyClass {
public:
    void* operator new(size_t size) {
        std::cout << "Custom new for MyClass, size: " << size << std::endl;
        return ::operator new(size);
    }

    void operator delete(void* ptr) {
        std::cout << "Custom delete for MyClass" << std::endl;
        ::operator delete(ptr);
    }

    void* operator new[](size_t size) {
        std::cout << "Custom new[] for MyClass, size: " << size << std::endl;
        return ::operator new(size);
    }

    void operator delete[](void* ptr) {
        std::cout << "Custom delete[] for MyClass" << std::endl;
        ::operator delete(ptr);
    }
};
```

#### 全局重载（慎用）

```cpp
void* operator new(size_t size) {
    std::cout << "Global new, size: " << size << std::endl;
    void* p = malloc(size);
    if (!p) throw std::bad_alloc();
    return p;
}

void operator delete(void* ptr) noexcept {
    std::cout << "Global delete" << std::endl;
    free(ptr);
}
```

#### 带额外参数的重载

```cpp
class MyClass {
public:
    void* operator new(size_t size, const char* file, int line) {
        std::cout << "Allocated at " << file << ":" << line << std::endl;
        return ::operator new(size);
    }
};

#define MY_NEW new(__FILE__, __LINE__)

MyClass* obj = MY_NEW MyClass();
```

---

### `::operator new` 和 `new` 有什么区别

```cpp
MyClass* p1 = new MyClass;
MyClass* p2 = (MyClass*)::operator new(sizeof(MyClass));
```

| 维度 | `new MyClass` | `::operator new(sizeof(...))` |
|------|---------------|-------------------------------|
| 分配内存 | 是 | 是 |
| 调用构造函数 | 是 | 否 |
| 返回类型 | `MyClass*` | `void*` |
| 本质 | 关键字，两步操作 | 函数调用，仅分配内存 |

`new MyClass` 等价于：

```cpp
void* raw = ::operator new(sizeof(MyClass));
MyClass* p = static_cast<MyClass*>(raw);
p->MyClass();
```

`::operator new` 只做第一步（分配原始内存），等价于 C 的 `malloc`，但失败时抛 `std::bad_alloc` 而非返回 `NULL`。

---

### 为什么 placement new 不能用 delete 释放

```cpp
char buffer[sizeof(MyClass)];
MyClass* obj = new(buffer) MyClass(42);

// delete obj;  // 错误！
```

原因：

1. **内存不是 new 分配的**：`buffer` 是栈上的数组，`delete` 会尝试释放不属于堆的内存，导致未定义行为。
2. **`delete` 做两件事**：先调用析构函数，再调用 `operator delete` 释放内存。placement new 的内存由外部管理，`operator delete` 的释放操作是多余的。
3. **正确做法**：只手动调用析构函数，内存由 buffer 的生命周期管理。

```cpp
obj->~MyClass();
```

如果 buffer 本身是堆分配的：

```cpp
char* buffer = new char[sizeof(MyClass)];
MyClass* obj = new(buffer) MyClass(42);

obj->~MyClass();
delete[] buffer;
```

---

### 内存池如何回收使用 placement new 构造的对象

```cpp
template <typename T>
class ObjectPool {
private:
    struct Block {
        Block* next;
    };
    Block* freeList;
    std::vector<char*> chunks;

public:
    ObjectPool(size_t count) : freeList(nullptr) {
        char* chunk = new char[sizeof(T) * count];
        chunks.push_back(chunk);

        for (size_t i = 0; i < count; i++) {
            Block* node = reinterpret_cast<Block*>(chunk + i * sizeof(T));
            node->next = freeList;
            freeList = node;
        }
    }

    ~ObjectPool() {
        for (auto chunk : chunks) {
            delete[] chunk;
        }
    }

    template <typename... Args>
    T* create(Args&&... args) {
        if (!freeList) return nullptr;

        void* mem = freeList;
        freeList = freeList->next;

        return new(mem) T(std::forward<Args>(args)...);
    }

    void destroy(T* obj) {
        obj->~T();

        Block* node = reinterpret_cast<Block*>(obj);
        node->next = freeList;
        freeList = node;
    }
};

class Widget {
public:
    int id;
    Widget(int i) : id(i) {
        std::cout << "Widget " << id << " created" << std::endl;
    }
    ~Widget() {
        std::cout << "Widget " << id << " destroyed" << std::endl;
    }
};

int main() {
    ObjectPool<Widget> pool(10);

    Widget* w1 = pool.create(1);
    Widget* w2 = pool.create(2);

    pool.destroy(w1);
    pool.destroy(w2);
}
```

回收流程：
1. 手动调用析构函数 `obj->~T()`
2. 将内存块归还到空闲链表
3. 下次 `create` 时用 placement new 在该块上重新构造

---

### `std::vector::emplace_back` 是如何利用 placement new 的

`emplace_back` 在 vector 已分配的内存上直接构造对象，避免了临时对象的创建和拷贝。

```cpp
template <typename T>
class SimpleVector {
    T* data;
    size_t sz;
    size_t cap;

public:
    SimpleVector() : data(nullptr), sz(0), cap(0) {}

    ~SimpleVector() {
        clear();
        ::operator delete(data);
    }

    void reserve(size_t newCap) {
        if (newCap <= cap) return;

        T* newData = static_cast<T*>(::operator new(sizeof(T) * newCap));

        for (size_t i = 0; i < sz; i++) {
            new(newData + i) T(std::move(data[i]));
            data[i].~T();
        }

        ::operator delete(data);
        data = newData;
        cap = newCap;
    }

    template <typename... Args>
    void emplace_back(Args&&... args) {
        if (sz >= cap) {
            reserve(cap == 0 ? 4 : cap * 2);
        }
        new(data + sz) T(std::forward<Args>(args)...);
        sz++;
    }

    void push_back(const T& val) {
        if (sz >= cap) {
            reserve(cap == 0 ? 4 : cap * 2);
        }
        new(data + sz) T(val);
        sz++;
    }

    void clear() {
        for (size_t i = 0; i < sz; i++) {
            data[i].~T();
        }
        sz = 0;
    }
};
```

**`emplace_back` vs `push_back` 的区别：**

```cpp
class Heavy {
public:
    Heavy(int a, int b) { std::cout << "构造" << std::endl; }
    Heavy(const Heavy&) { std::cout << "拷贝" << std::endl; }
    Heavy(Heavy&&) { std::cout << "移动" << std::endl; }
};

SimpleVector<Heavy> vec;

vec.push_back(Heavy(1, 2));
// 输出：构造 → 移动（或拷贝）

vec.emplace_back(1, 2);
// 输出：构造（原地构造，无额外移动/拷贝）
```

| 操作 | 过程 | 构造/拷贝次数 |
|------|------|--------------|
| `push_back(Heavy(1,2))` | 先构造临时对象，再移动到容器 | 2 次 |
| `emplace_back(1, 2)` | 直接在容器内存上构造 | 1 次 |

---

## 来源

开立医疗 - C++软件工程师面经（扩展问题）
