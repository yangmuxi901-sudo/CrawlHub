# A 股投资者关系数据下载器

## 功能说明

自动下载 A 股上市公司的投资者关系数据，支持四个下载器：

1. **巨潮资讯网** - 《投资者关系活动记录表》PDF 下载
2. **深交所互动易** - 深市上市公司投资者问答数据（原始 API 版）
3. **上证 e 互动** - 沪市上市公司投资者问答数据（原始 API 版）
4. **AKShare 互动平台** - 深市互动易 + 沪市 e 互动整合版（推荐）

所有下载器均支持增量下载（高水位线机制）。

## 安装依赖

```bash
pip install -r requirements.txt
# 如果使用 AKShare 下载器，需要额外安装：
pip install akshare
```

## 使用方法

### 1. 巨潮资讯网 - 投资者关系活动记录表 PDF 下载

```bash
python standalone_ir_downloader.py
```

### 2. 深交所互动易 - 投资者问答数据下载（原始 API 版）

```bash
python standalone_hdy_downloader.py
```

### 3. 上证 e 互动 - 投资者问答数据下载（原始 API 版）

```bash
python standalone_ehd_downloader.py
```

### 4. AKShare 互动平台 - 深市 + 沪市整合下载（推荐）

```bash
python standalone_ak_irm_downloader.py
```

### 5. Web 前端查看

```bash
cd web
npm install
npm run dev
```

## 目录结构

```
<项目根目录>/
├── standalone_ir_downloader.py       # 巨潮 IR 下载器
├── standalone_hdy_downloader.py      # 互动易下载器（原始 API）
├── standalone_ehd_downloader.py      # e 互动下载器（原始 API）
├── standalone_ak_irm_downloader.py   # AKShare 互动平台下载器（推荐）
├── 公司列表.csv                       # 输入文件
├── requirements.txt                  # 依赖列表
├── README.md                         # 说明文档
├── ARCHITECTURE.md                   # 架构文档
├── test_*.py                         # 测试脚本
└── data/
    ├── ir_pdfs/                      # 巨潮 PDF 存储目录
    │   ├── sz.300054/
    │   │   └── sz.300054_2024-03-15_投资者关系活动记录表.pdf
    │   └── ...
    ├── hdy_attachments/              # 互动易附件存储
    │   ├── sz.300054/
    │   └── ...
    ├── ehd_attachments/              # e 互动附件存储
    │   ├── sh.600071/
    │   └── ...
    ├── ak_irm/                       # AKShare 互动平台数据存储
    │   ├── hdy/                      # 互动易数据
    │   │   └── sz.300054_鼎龙股份/
    │   └── ehd/                      # e 互动数据
    │       └── sh.600071_凤凰光学/
    └── sync_record.db                # SQLite 数据库（4 张表）
```

## 核心特性

1. **增量下载**：使用 SQLite 记录每只股票上次抓取日期，避免重复下载
2. **批量获取**：一次性获取所有市场数据，然后按股票代码过滤
3. **防御性编程**：
   - 反爬休眠（2-5 秒随机延迟）
   - 网络超时（15 秒）
   - 单文件下载失败不中断整体流程
4. **文件名清洗**：自动移除非法字符（`\ / : * ? " < > |`）

## 数据源

- 巨潮资讯网 (www.cninfo.com.cn)
- API: http://www.cninfo.com.cn/new/hisAnnouncement/query

## 输入文件格式

`公司列表.csv` 必须包含以下字段：

```csv
ticker,company_name,exchange
sz.300054,鼎龙股份，sz
sh.600071，凤凰光学，sh
bj.920001，纬达光电，bj
```

- `ticker`: 股票代码（格式：交易所。代码）
- `company_name`: 公司名称
- `exchange`: 交易所（sz/sh/bj）

## 输出日志示例

```
============================================================
A 股投资者关系活动记录表 PDF 下载器
============================================================
[系统] 数据库初始化完成：/path/to/data/sync_record.db
[系统] 加载公司列表，共 495 家公司

[系统] 获取 2024-01-01 至今的所有投资者关系记录...
[系统] 正在获取 szse 市场数据...
[系统] 正在获取 sse 市场数据...
[系统] 正在获取 bse 市场数据...
[系统] 共获取 50 只股票的记录

[sz.300054] 鼎龙股份 - 发现 3 份新纪要
  下载：2024 年投资者关系活动记录表...
  [成功] sz.300054_2024-03-15_2024 年投资者关系活动记录表.pdf
  下载：投资者调研纪要...
  [成功] sz.300054_2024-04-01_投资者调研纪要.pdf
[sz.300054] 完成：下载 2 份文件

--- 进度：10/495 | 已下载：5 份 ---

============================================================
下载任务完成
处理公司数：495
无数据公司数：445
成功下载：50 份 PDF
保存目录：/path/to/data/ir_pdfs
============================================================
```

## 注意事项

1. 首次运行会下载所有历史数据（从 2024-01-01 开始）
2. 再次运行只会下载新增的 PDF
3. 网络不好时可能需要较长时间，请耐心等待
4. 如需重新下载所有数据，删除 `data/sync_record.db` 即可
