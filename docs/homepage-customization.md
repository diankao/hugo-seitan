# 首页定制指南

> 本文记录门户式首页(2026-08-27 改版)的结构、数据来源和常见修改方法。
> 想改首页,先读这篇,不用重新读模板源码。

## 一、首页结构

首页不是主题默认布局,而是项目级覆盖:`layouts/partials/home/custom.html`(由 `config/_default/params.toml` 里 `[homepage] layout = "custom"` 启用)。

自上而下三段:

| 区块 | 数据来源 | 说明 |
|------|---------|------|
| Hero 简介区 | `site.Title` + `site.Params.homepage.customSummary` + 动态统计 | 简介文案在 params.toml 里改,篇数/栏目数自动计算 |
| 最近更新 | 全站最新 6 篇(递归、过滤草稿),按 `Date` 倒序 | 标题 + 所属栏目徽章 + 日期 |
| 栏目导航 | `seitan.Sections`,按 `weight` 升序 | 每栏目一张卡:标题 + 简介 + 文章数(递归统计),空栏目不显示 |

点击卡片进入栏目聚合页。聚合页已通过项目级覆盖 `layouts/_default/list.html` 定制(复制自 `themes/blowfish/layouts/_default/list.html`):

- 顶部渲染**"子栏目"文件夹区块**(文件夹图标 + 名称 + 篇数),有非空二级子栏目的栏目才会显示;
- 文章网格只渲染本栏目普通文章,二级子栏目页不再作为"伪卡片"混入;
- 其余逻辑(分页、按年分组、卡片视图)与主题一致,主题升级时如改动 list.html 需手动同步此覆盖文件。

## 二、常见修改

### 1. 改 hero 一句话简介

编辑 `config/_default/params.toml`:

```toml
[homepage]
  customSummary = "嵌入式开发学习笔记:……"
```

### 2. 改"最近更新"篇数

编辑 `layouts/partials/home/custom.html`,`first 6` 改成想要的数量。

### 3. 改某个栏目的卡片简介

每个一级栏目的 `_index.md` front matter 里有 `description` 参数,改它即可:

```toml
+++
title = '操作系统'
date = 2026-02-27T00:00:00+08:00
draft = false
description = "收录操作系统方向的学习笔记"
weight = 3
+++
```

- 卡片简介**只读这个参数**,不会截取正文(正文格式历史上不统一,截取会混入标题和列表符号)
- 没写 description 时卡片只显示标题和篇数,不出简介行;新建栏目时建议都带上
- 简介最长两行(`assets/css/custom.css` 里的 `.home-clamp` 控制截断行数)

### 4. 栏目排序

排序看 `_index.md` 的 **weight**(值=文件夹名编号,已批量写入),与文件夹名前缀数字无关但保持一致最好。想让某栏目排前面,减小它的 weight 即可。

栏目标题显示时**不带编号前缀**(title 已统一去掉 `NN_`),URL 由文件夹名决定不受影响。

### 5. 日期格式

全站日期格式在 `config/_default/languages.en.toml`(语言层参数,优先级高于 params.toml):

```toml
[params]
  dateFormat = "2006-01-02"
```

主题默认是英文长日期("27 August 2026"),别删这个覆盖文件。

### 6. 文章卡片的字数/阅读时长

已在 `config/_default/params.toml` 的 `[article]` 关闭:

```toml
showWordCount = false
showReadingTime = false
```

想恢复改回 true。

## 三、新增 / 调整栏目的规矩

### 新增一级栏目

1. 在 `content/posts/seitan/` 下建文件夹,命名带编号前缀:`NN_名称`
2. 必须创建 `_index.md`,最小可用模板:

```markdown
+++
title = '名称'          # 不带编号,页面展示用
date = 2026-MM-DDT00:00:00+08:00
draft = false
description = "一句话简介"
weight = NN             # 与编号一致,决定导航顺序
+++
```

3. 往里放文章,命名格式 `中文标题YYYYMMDD.md`(日期用当天日期),首页卡片、文章数都会自动出现。

### ⚠️ 新增二级子目录(栏目里的栏目)

子目录**必须有 `_index.md`**,否则 Hugo 不生成栏目页,整个目录在站内不可达(首页/归档都不会出现链接)。这是 2026-08-27 修"Unix与Windows对比找不到入口"时的教训。

二级子栏目建好后**无需任何额外操作**:父栏目聚合页顶部会自动出现"子栏目"文件夹入口(2026-08-28 改为次级页面内嵌文件夹样式,替代最早的首页胶囊方案)。二级子栏目的文章计入父栏目的文章数与递归列表。

## 四、已知取舍与历史坑

- 旧版首页是"整墙手风琴"(所有栏目折叠块平铺全部文章),2026-08-27 换成门户式;当时所有折叠块的锚点 id 都是重复的 `section-_index`(Hugo 的 `File.BaseFileName` 对栏目页返回 `_index`),随旧布局一起移除
- `Page.RawContent` 在当前 Hugo 版本(0.161)对 `_index.md` 分支页返回空串,不要用它取栏目正文;要拿纯文本用 `.Plain`(含标题/列表杂质)或按本文方案落成 `description` 参数
- 语言层参数(languages.en.toml `[params]`)优先于全局 params.toml,日期格式只有在那儿覆盖才生效
- 栏目聚合页原本会把二级子栏目页混进文章网格当"伪卡片",且曾把子栏目入口做成首页卡片上的胶囊(被嫌丑)。2026-08-28 起通过项目级 `layouts/_default/list.html` 覆盖解决:聚合页顶部"子栏目"文件夹区块 + 网格过滤 branch page;注意主题升级时同步该文件

## 五、改动清单(本次涉及的全部文件)

| 文件 | 动作 |
|------|------|
| `layouts/partials/home/custom.html` | 重写为门户式布局 |
| `layouts/_default/list.html` | 项目级覆盖栏目聚合页:子栏目文件夹区块 + 网格过滤 branch page(2026-08-28) |
| `assets/css/custom.css` | 新建,`.home-clamp` 两行截断 |
| `config/_default/params.toml` | 加 `dateFormat`、`customSummary`;关闭字数/阅读时长 |
| `config/_default/languages.en.toml` | 新建,语言层覆盖 `dateFormat` |
| `content/posts/seitan/**/_index.md` | 批量注入 weight、清理 title 编号、写 description |
| `content/posts/seitan/00_未分类/_index.md` | 新建(原目录缺 index 文件) |
| `03_操作系统/缓存命中/_index.md` | 新建(旧文件缺失导致内容不可达) |
| `缓存命中/未命中并减少未命中率.md` | 补 front matter(原文无任何元数据) |
| `03_操作系统/` 二级分组 | 33 篇散落文章按主题归入 RTOS与FreeRTOS / 进程线程与IPC / 内存管理 / 中断与系统调用 / Windows与图形渲染 五个子目录(2026-08-28);清理文件名遗留编号(`00NN.`),补 RTOS概述 front matter;归档时文件名/URL 变化,旧链接会失效 |
| `18_RTOS/` 空目录 | 删除(12_RTOS 的重复遗留) |
| `03_操作系统/RTOS与FreeRTOS/` | 整体并入 `12_RTOS/`(2026-09-14):RTOS 内容不再按"基础教程/深入机制"拆在两个栏目;`Linux三种执行上下文`、`中断上下半部与workqueue机制` 移入 `19_Linux嵌入式开发/`;三个栏目 `_index.md` 简介同步更新;文件名/URL 变化,旧链接失效 |
