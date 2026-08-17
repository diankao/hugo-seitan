# 批量添加 Hugo front matter 的脚本

$files = @(
    "d:\source\blog\content\posts\seitan\03_操作系统\0002.互斥锁原理与原子操作20260226.md",
    "d:\source\blog\content\posts\seitan\05_通信协议\0001.I2C协议生效机制20260226.md",
    "d:\source\blog\content\posts\seitan\05_通信协议\0002.CAN帧内容与格式验证20260226.md",
    "d:\source\blog\content\posts\seitan\05_通信协议\0003.SPI协议与菊花链通信20260226.md",
    "d:\source\blog\content\posts\seitan\05_通信协议\0004.TCP协议应用场景20260226.md",
    "d:\source\blog\content\posts\seitan\05_通信协议\0005.TCP三次握手四次挥手与TIME_WAIT20260226.md",
    "d:\source\blog\content\posts\seitan\05_通信协议\0006.epoll工作原理与selectpoll区别20260226.md",
    "d:\source\blog\content\posts\seitan\05_通信协议\0007.高性能TCP服务器实现20260227.md",
    "d:\source\blog\content\posts\seitan\07_C语言编程\0001.C++设计模式与应用20260227.md",
    "d:\source\blog\content\posts\seitan\07_C语言编程\0002.C++多态与虚函数20260227.md",
    "d:\source\blog\content\posts\seitan\07_C语言编程\0003.C++容器vector与list对比20260227.md",
    "d:\source\blog\content\posts\seitan\08_项目经验\简历.md",
    "d:\source\blog\content\posts\seitan\09_算法与数据结构\0001.链表基础与识别方法20260226.md",
    "d:\source\blog\content\posts\seitan\10_综合问题\0001.自我介绍与项目介绍20260227.md",
    "d:\source\blog\content\posts\seitan\10_综合问题\0002.职业规划与未来发展20260227.md",
    "d:\source\blog\content\posts\seitan\10_综合问题\0003.实习工作经验与成果20260227.md",
    "d:\source\blog\content\posts\seitan\10_综合问题\0004.反问环节高质量问题20260227.md"
)

foreach ($file in $files) {
    if (Test-Path $file) {
        $content = Get-Content $file -Raw -Encoding UTF8
        
        if (-not $content.StartsWith("+++")) {
            $filename = [System.IO.Path]::GetFileNameWithoutExtension($file)
            
            $frontmatter = @"

+++
title = '$filename'
date = 2026-02-27T00:00:00+08:00
draft = false
categories = ['技术文档']
tags = []
+++

"@
            
            $newContent = $frontmatter + $content
            $newContent | Set-Content $file -Encoding UTF8 -NoNewline
            Write-Host "已处理: $file" -ForegroundColor Green
        } else {
            Write-Host "跳过 (已有 front matter): $file" -ForegroundColor Yellow
        }
    } else {
        Write-Host "文件不存在: $file" -ForegroundColor Red
    }
}

Write-Host "`n处理完成!" -ForegroundColor Cyan
