# 股东报告项目 - 技术架构文档

**版本：** 2.0
**日期：** 2026-02-21

---

## 1. 项目概述

### 1.1 项目目标

开发一个 A 股上市公司投资者关系数据下载与展示系统，支持：
- 巨潮资讯网《投资者关系活动记录表》PDF 下载
- 深交所互动易投资者问答数据抓取
- 上证 e 互动投资者问答数据抓取
- Web 端查看管理

### 1.2 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户交互层                                │
│  ┌─────────────────────┐      ┌─────────────────────────────┐  │
│  │   命令行终端         │      │      Web 浏览器             │  │
│  │  (Python CLI)       │      │   (React + Ant Design)     │  │
│  └──────────┬──────────┘      └──────────────┬──────────────┘  │
└─────────────┼─────────────────────────────────┼─────────────────┘
              │                                 │
              ▼                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                         服务层                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              Python 下载器 (多脚本独立运行)                 ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        ││
│  │  │ 巨潮 IR 下载器 │  │ 互动易下载器 │  │ e 互动下载器 │        ││
│  │  │ (原有脚本)   │  │ (新增)      │  │ (新增)      │        ││
│  │  └─────────────┘  └─────────────┘  └─────────────┘        ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         数据层                                   │
│  ┌─────────────────────┐      ┌─────────────────────────────┐  │
│  │   SQLite 数据库      │      │     本地文件系统             │  │
│  │  - download_history (巨潮) │  │  - data/ir_pdfs/ (巨潮)   │  │
│  │  - hdy_history (互动易)    │  │  - data/hdy_attachments/  │  │
│  │  - ehd_history (e 互动)      │  │  - data/ehd_attachments/  │  │
│  └─────────────────────┘      └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         外部数据源                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ 巨潮资讯网  │  │ 深交所互动易 │  │ 上证 e 互动   │            │
│  │ (IR 记录表)  │  │ (深市投关)  │  │ (沪市投关)  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 技术架构

### 2.1 后端技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.8+ | 核心运行时 |
| HTTP 请求 | requests | 访问各数据源 API |
| 数据处理 | pandas | CSV 文件读取 |
| 数据库 | sqlite3 | 本地状态存储（标准库） |
| 数据源 | 巨潮资讯网 | 投资者关系活动记录表 PDF |
| 数据源 | 深交所互动易 | 深市投资者问答数据 |
| 数据源 | 上证 e 互动 | 沪市投资者问答数据 |

### 2.2 前端技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 框架 | React 18 | UI 框架 |
| UI 组件库 | Ant Design 5 | 企业级 React 组件库 |
| 语言 | TypeScript | 类型安全 |
| 构建工具 | Vite | 快速开发构建 |
| HTTP 客户端 | axios | API 请求 |
| 日期处理 | dayjs | 日期格式化 |

### 2.3 数据存储

- **SQLite 数据库**：`data/sync_record.db`
  - 表：`download_history` - 记录每只股票的高水位线日期（巨潮）
  - 表：`hdy_history` - 互动易高水位线记录
  - 表：`ehd_history` - e 互动高水位线记录

- **本地文件系统**：
  - `data/ir_pdfs/` - 存储巨潮 PDF 文件
  - `data/hdy_attachments/` - 存储互动易附件
  - `data/ehd_attachments/` - 存储 e 互动附件

---

## 3. 目录结构

```
股东报告/
├── standalone_ir_downloader.py   # Python 下载器主脚本（巨潮）
├── standalone_hdy_downloader.py  # 深交所互动易下载器（新增）
├── standalone_ehd_downloader.py  # 上证 e 互动下载器（新增）
├── 公司列表.csv                   # 股票列表（输入）
├── requirements.txt              # Python 依赖
├── requirements.md                # 需求规格说明书
├── README.md                     # 使用说明
├── ARCHITECTURE.md               # 本文档
│
├── data/                         # 数据存储目录
│   ├── ir_pdfs/                  # 巨潮 PDF 文件存储
│   │   ├── sz.300054/            # 按股票代码分类
│   │   │   └── sz.300054_2024-03-15_投资者关系活动记录表.pdf
│   │   ├── sh.600071/
│   │   └── ...
│   ├── hdy_attachments/          # 互动易附件存储（新增）
│   │   ├── sz.300054/            # 按深市股票代码分类
│   │   └── ...
│   ├── ehd_attachments/          # e 互动附件存储（新增）
│   │   ├── sh.600071/            # 按沪市股票代码分类
│   │   └── ...
│   ├── sync_record.db            # SQLite 数据库
│   └── download_log.txt          # 下载日志
│
└── web/                          # Web 前端
    ├── package.json               # npm 依赖配置
    ├── vite.config.ts             # Vite 配置
    ├── tsconfig.json              # TypeScript 配置
    ├── index.html                 # 入口 HTML
    ├── start.sh                   # 启动脚本
    │
    ├── src/
    │   ├── index.tsx              # React 入口
    │   ├── index.css              # 全局样式
    │   ├── ShareholderReports.tsx # 主组件（巨潮 IR）
    │   ├── HdyList.tsx            # 互动易列表（新增）
    │   └── EhdList.tsx            # e 互动列表（新增）
    │
    └── api/
        └── api.py                 # API 接口（可选）
```

---

## 4. 模块设计

### 4.1 后端模块

#### 4.1.1 配置常量模块

文件：`standalone_ir_downloader.py` (第 29-63 行)

```python
# 核心配置
BASE_DIR         # 项目根目录
DATA_DIR         # 数据目录
PDF_DIR          # PDF 存储目录
DB_PATH          # SQLite 数据库路径
LOG_PATH         # 日志文件路径
COMPANY_LIST_PATH # 公司列表 CSV 路径

# 市场映射
MARKET_MAP = {
    "sz": "szse",  # 深交所
    "sh": "sse",   # 上交所
    "bj": "bse",   # 北交所
}
```

#### 4.1.2 日志模块

类：`Logger` (第 67-80 行)

| 方法 | 功能 |
|------|------|
| `log(message, level)` | 写入日志到文件和控制台 |

日志级别：`INFO`, `WARNING`, `ERROR`, `SUCCESS`

#### 4.1.3 orgId 映射模块

函数：`load_orgid_mapping()` (第 91-120 行)

功能：从巨潮资讯网下载股票代码到 orgId 的映射表

#### 4.1.4 数据库模块

| 函数 | 功能 |
|------|------|
| `init_db()` | 初始化 SQLite 数据库，创建 download_history 表 |
| `get_last_date(ticker)` | 获取指定股票的上次下载日期 |
| `update_last_date(ticker, date)` | 更新指定股票的下载日期 |

数据库表结构：

```sql
CREATE TABLE download_history (
    ticker TEXT PRIMARY KEY,           -- 股票代码 (如: sz.300054)
    last_publish_date TEXT NOT NULL,   -- 上次下载的发布日期
    updated_at TEXT                     -- 更新时间
);
```

#### 4.1.5 API 请求模块

| 函数 | 功能 |
|------|------|
| `fetch_ir_announcements(ticker, start_date, end_date)` | 获取指定时间范围的投资者关系公告 |
| `get_stock_orgid(ticker)` | 获取股票的 orgId |

API 端点：`http://www.cninfo.com.cn/new/hisAnnouncement/query`

#### 4.1.6 PDF 下载模块

| 函数 | 功能 |
|------|------|
| `download_pdf(url, ticker, publish_date, title)` | 下载单个 PDF 文件 |
| `sanitize_filename(title)` | 清洗文件名，移除非法字符 |

下载规则：
- 超时设置：15 秒
- 文件已存在：跳过
- 下载失败：记录日志，继续下一个

### 4.2 前端模块

#### 4.2.1 主组件

文件：`src/ShareholderReports.tsx`

| 组件 | 功能 |
|------|------|
| `ShareholderReports` | 主页面组件，包含 PDF 列表展示、筛选、下载功能 |

主要功能：
- 按股票代码/公司名称搜索
- 按日期范围筛选
- PDF 文件列表展示
- 文件下载

#### 4.2.2 API 集成

文件：`src/IntegrationExample.tsx`

示例代码：展示如何与后端 API 集成

---

## 5. 数据流程

### 5.1 增量下载流程

```
┌──────────────┐
│   开始运行    │
└──────┬───────┘
       ▼
┌──────────────┐
│ 加载公司列表  │
│ (公司列表.csv)│
└──────┬───────┘
       ▼
┌──────────────┐
│ 初始化数据库  │
│ (sync_record)│
└──────┬───────┘
       ▼
┌──────────────┐
 │ 遍历每只股票  │◄────────────┐
 └──────┬───────┘             │
        ▼                     │
┌──────────────┐              │
 │ 获取上次日期  │              │
 │ (高水位线)   │              │
 └──────┬───────┘              │
        ▼                     │
┌──────────────┐              │
 │ 调用巨潮 API │              │
 │ 获取新公告   │              │
 └──────┬───────┘              │
        ▼                     │
┌──────────────┐              │
 │ 过滤 IR 记录 │              │
 │ (标题含"投资 │              │
 │ 者关系")     │              │
 └──────┬───────┘              │
        ▼                     │
┌──────────────┐              │
 │ 下载 PDF    │              │
 └──────┬───────┘              │
        ▼                     │
┌──────────────┐              │
 │ 更新数据库   │              │
 │ (高水位线)   │              │
 └──────┬───────┘              │
        ▼                     │
   ┌────┴────┐                 │
   │ 下一只   │─────────────────┘
   │ 股票？   │
   └────┬────┘
    是 │
        ▼
┌──────────────┐
 │  结束运行   │
 └──────────────┘
```

### 5.2 高水位线机制

| 规则 | 描述 |
|------|------|
| HW-01 | 首次抓取：从 2024-01-01 开始 |
| HW-02 | 每次成功：更新 `last_publish_date` 为最新记录日期 |
| HW-03 | 增量查询：只下载 `发布日期 > last_publish_date` 的记录 |

---

## 6. 部署架构

### 6.1 运行方式

#### 后端（命令行）

```bash
# 安装依赖
pip install -r requirements.txt

# 运行下载器
python standalone_ir_downloader.py
```

#### 前端（Web）

```bash
cd web

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build
```

### 6.2 环境要求

| 环境 | 要求 |
|------|------|
| 操作系统 | Windows / macOS / Linux |
| Python | 3.8+ |
| Node.js | 16+ |
| 网络 | 可访问巨潮资讯网 |

### 6.3 数据目录

首次运行自动创建：

```
data/
├── ir_pdfs/           # PDF 存储
└── sync_record.db     # SQLite 数据库
```

---

## 7. 接口规范

### 7.1 巨潮资讯 API

**请求地址：**
```
POST http://www.cninfo.com.cn/new/hisAnnouncement/query
```

**请求头：**
```
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
```

**请求参数：**

| 参数 | 说明 | 示例 |
|------|------|------|
| pageNum | 页码 | 1 |
| pageSize | 每页数量 | 30 |
| column | 市场类型 | szse/sse/bse |
| tabName | 标签页 | fulltext |
| stock | 股票代码 | 空（全局搜索） |
| searchkey | 搜索关键词 | 投资者关系活动 |
| seDate | 日期范围 | 2024-01-01~2025-02-20 |
| sortName | 排序字段 | announcementTime |
| sortType | 排序方式 | desc |

**返回字段：**

| 字段 | 说明 |
|------|------|
| announcements[].secCode | 股票代码 |
| announcements[].announcementTitle | 公告标题 |
| announcements[].announcementTime | 发布时间（毫秒时间戳） |
| announcements[].adjunctUrl | PDF 相对路径 |

**PDF 下载地址：**
```
http://static.cninfo.com.cn/{adjunctUrl}
```

---

## 8. 安全性考虑

### 8.1 反爬措施

| 措施 | 实现 |
|------|------|
| User-Agent 伪装 | 模拟 Chrome 浏览器 |
| 请求间隔 | random.uniform(2, 5) 秒随机延迟 |
| 超时保护 | 15 秒超时设置 |

### 8.2 错误处理

- 单文件下载失败：记录日志，继续下一个
- API 请求失败：重试机制
- 数据库错误：异常捕获并记录

---

## 9. 附录

### 9.1 配置文件说明

| 文件 | 说明 |
|------|------|
| `公司列表.csv` | 输入文件，包含要下载的股票列表 |
| `data/sync_record.db` | SQLite 数据库，存储下载状态 |
| `data/download_log.txt` | 下载日志 |

### 9.2 CSV 格式

```csv
ticker,company_name,exchange
sz.300054,鼎龙股份,sz
sh.600071,凤凰光学,sh
bj.920001,纬达光电,bj
```

### 9.3 PDF 文件命名规则

```
{ticker}_{publish_date}_{sanitized_title}.pdf
```

示例：`sz.300054_2024-03-15_2024年投资者关系活动记录表.pdf`

---

*文档版本：1.0*
*最后更新：2025-02-21*
