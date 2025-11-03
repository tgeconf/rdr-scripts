# arXiv 模块使用指南

## 概述

arXiv 模块是一个基于 arXiv API 的论文收集工具，专门为 RDR (Real Deep Research) 项目设计。该模块具有以下特点：

- **生产就绪**：包含完善的错误处理、重试机制和日志记录
- **与现有项目兼容**：输出数据结构与现有爬虫模块完全一致
- **鲁棒性**：支持网络故障恢复、速率限制遵守
- **可配置**：支持自定义搜索参数和输出格式

## 快速开始

### 基本使用

```python
from venue.arxiv import fetch_arxiv_papers

# 获取最近30天的论文
new_papers = fetch_arxiv_papers(
    categories=["cs.CV", "cs.RO", "cs.LG"],
    start_date="2024-01-01",
    end_date="2024-01-31",
    max_results=500,
    output_filename="arxiv_2024_01.json"
)

print(f"添加了 {new_papers} 篇新论文")
```

### 命令行使用

```bash
# 获取最近30天的默认类别论文
python venue/arxiv.py

# 自定义搜索参数
python venue/arxiv.py \
    --categories cs.CV cs.RO cs.LG \
    --start-date 2024-01-01 \
    --end-date 2024-01-31 \
    --max-results 1000 \
    --output arxiv_custom.json
```

## 配置选项

### 默认类别

模块默认搜索以下 arXiv 类别：
- `cs.CV` - 计算机视觉
- `cs.RO` - 机器人学  
- `cs.LG` - 机器学习
- `cs.AI` - 人工智能
- `cs.CL` - 计算与语言
- `stat.ML` - 机器学习（统计）

### 完整的类别列表

arXiv API 支持广泛的学科类别，主要分为以下领域：

#### 计算机科学 (cs)
- `cs.AI` - 人工智能
- `cs.AR` - 硬件架构
- `cs.CC` - 计算复杂性
- `cs.CE` - 计算工程、金融和科学
- `cs.CG` - 计算几何
- `cs.CL` - 计算与语言
- `cs.CR` - 密码学与安全
- `cs.CV` - 计算机视觉与模式识别
- `cs.CY` - 计算机与社会
- `cs.DB` - 数据库
- `cs.DC` - 分布式、并行和集群计算
- `cs.DL` - 数字图书馆
- `cs.DM` - 离散数学
- `cs.DS` - 数据结构与算法
- `cs.ET` - 新兴技术
- `cs.FL` - 形式语言与自动机理论
- `cs.GL` - 通用文献
- `cs.GR` - 图形学
- `cs.GT` - 计算机科学与博弈论
- `cs.HC` - 人机交互
- `cs.IR` - 信息检索
- `cs.IT` - 信息论
- `cs.LG` - 机器学习
- `cs.LO` - 计算机逻辑
- `cs.MA` - 多智能体系统
- `cs.MM` - 多媒体
- `cs.MS` - 数学软件
- `cs.NA` - 数值分析
- `cs.NE` - 神经与进化计算
- `cs.NI` - 网络与互联网架构
- `cs.OH` - 其他计算机科学
- `cs.OS` - 操作系统
- `cs.PF` - 性能
- `cs.PL` - 编程语言
- `cs.RO` - 机器人学
- `cs.SC` - 符号计算
- `cs.SD` - 声音
- `cs.SE` - 软件工程
- `cs.SI` - 社会与信息网络
- `cs.SY` - 系统与控制

#### 其他相关领域
- `eess.AS` - 音频与语音处理
- `eess.IV` - 图像与视频处理
- `eess.SP` - 信号处理
- `eess.SY` - 系统与控制
- `math.NA` - 数值分析
- `math.OC` - 优化与控制
- `stat.AP` - 统计应用
- `stat.ML` - 机器学习

完整类别列表请参考 [arXiv 分类法](https://arxiv.org/category_taxonomy)。

### 搜索参数

- `categories`: arXiv 类别列表
- `start_date`: 开始日期 (YYYY-MM-DD)
- `end_date`: 结束日期 (YYYY-MM-DD)  
- `max_results`: 最大获取论文数（默认 1000）
- `output_filename`: 输出文件名（默认 "arxiv.json"）

## 输出格式

输出文件格式与现有项目完全兼容：

```json
[
  {
    "paper_id": "2401.12345",
    "authors": "Author One, Author Two",
    "title": "Paper Title",
    "paper_url": "https://arxiv.org/abs/2401.12345",
    "pdf_link": "https://arxiv.org/pdf/2401.12345.pdf",
    "abstract": "Paper abstract text..."
  }
]
```

## 高级用法

### 使用 ArxivFetcher 类

```python
from venue.arxiv import ArxivFetcher, PaperDatabase

# 初始化获取器
fetcher = ArxivFetcher(max_results=500, delay=3.0)

# 获取论文
papers = fetcher.fetch_papers(
    categories=["cs.CV", "cs.RO"],
    start_date="2024-01-01", 
    end_date="2024-01-31"
)

# 手动管理数据库
db = PaperDatabase(filename="custom_arxiv.json")
for paper in papers:
    if not db.has_paper(paper.paper_id):
        db.save_paper(paper)
```

### 错误处理

模块包含完善的错误处理：

- **网络错误**：自动重试机制（最多3次）
- **解析错误**：跳过无法解析的条目并记录警告
- **文件错误**：自动备份损坏的数据文件
- **速率限制**：请求间延迟以避免被限制
- **API异常**：智能batch_size调整处理空feed但有totalResults的异常

#### 智能batch_size调整机制

当arXiv API返回包含`totalResults`但没有`entry`元素的异常响应时，模块会自动：

1. **检测异常**：检查`totalResults`是否大于当前`start_index`
2. **逐级缩小batch_size**：从100开始，逐步缩小到50、25
3. **重试机制**：使用更小的batch_size重新请求相同范围
4. **跳过处理**：如果最小batch_size仍无数据，跳过问题范围
5. **恢复机制**：成功获取数据后自动恢复原始batch_size

```python
# batch_size调整策略
if batch_size > 25:
    new_batch_size = max(25, batch_size // 2)  # 逐级缩小
    batch_size = new_batch_size
    continue  # 重试相同范围
else:
    # 跳过问题范围，恢复原始batch_size
    start_index += original_batch_size
    batch_size = original_batch_size
```

这种机制能有效处理arXiv API的异常情况，最大化数据获取成功率。

## 集成到 RDR 管道

### 数据收集阶段

arXiv 模块可以直接替代或补充现有的会议爬虫：

```python
# 在数据收集管道中使用
from venue.arxiv import fetch_arxiv_papers
from venue.rss22 import scrape_rss_papers

# 收集 arXiv 论文
arxiv_papers = fetch_arxiv_papers(
    categories=["cs.RO", "cs.CV"],
    start_date="2024-01-01",
    end_date="2024-12-31",
    output_filename="arxiv_2024.json"
)

# 收集会议论文
scrape_rss_papers()
```

### 后续处理

收集的 arXiv 论文可以直接用于后续的：

1. **领域筛选**：使用现有的过滤逻辑
2. **内容推理**：应用相同的视角分析
3. **嵌入投影**：与会议论文一起处理
4. **聚类分析**：统一的分析流程

## 最佳实践

### 1. 速率限制

- 默认延迟 3 秒，遵守 arXiv API 的礼貌使用政策
- 避免设置过高的 `max_results` 值
- 考虑在非高峰时段运行

### 2. 数据管理

- 定期清理旧的备份文件
- 监控日志文件 `arxiv_fetcher.log`
- 使用有意义的输出文件名

### 3. 错误监控

```python
import logging

# 设置更详细的日志记录
logging.getLogger('venue.arxiv').setLevel(logging.DEBUG)
```

## 故障排除

### 常见问题

1. **网络连接失败**
   - 检查网络连接
   - 验证 arXiv API 可访问性
   - 调整重试参数

2. **解析错误**
   - 检查 arXiv API 响应格式
   - 验证 XML 解析

3. **文件写入错误**
   - 检查目录权限
   - 验证磁盘空间

### 调试模式

启用详细日志记录：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 贡献

欢迎提交问题和改进建议！

---

*此模块设计为与 RDR 项目的其他组件无缝集成，确保数据格式和流程的一致性。*
