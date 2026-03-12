# A 股投资者关系数据下载器 + 化工数据爬虫

## 目录

1. [化工数据爬虫](#化工数据爬虫)
2. [投资者关系数据下载器](#投资者关系数据下载器)
3. [调度服务（后台自动运行）](#调度服务)

---

## 化工数据爬虫

### 功能说明

自动爬取化工产品价格和开工率数据，支持：

1. **化工产品价格** - 基于 AkShare 期货现货价格接口（✅ 可用）
2. **开工率数据** - 隆众资讯行业报告（❌ 需付费会员）

### 数据源状态

| 数据类型 | 数据源 | 状态 | 覆盖产品 |
|---------|--------|------|---------|
| 价格数据 | AkShare 期货现货价格 | ✅ 可用 | 20 种化工产品 |
| 开工率 | 隆众资讯 | ❌ 需登录 | 暂不可用 |

### 价格数据覆盖

| 类别 | 产品 |
|------|------|
| **化纤** | PTA、短纤、乙二醇 |
| **氯碱** | PVC、烧碱 |
| **煤化工** | 甲醇、尿素、焦炭、焦煤 |
| **橡胶** | 橡胶、合成橡胶 |
| **炼化** | 燃油、沥青、聚丙烯 |
| **建材** | 玻璃、纯碱 |
| **其他** | 纸浆、硅铁、锰硅、苯乙烯 |

### 使用方法

```bash
# 运行全部任务（价格 + 开工率）
python main.py

# 仅爬取价格数据
python main.py --price-only

# 仅爬取开工率数据
python main.py --util-only

# 爬取但不导入数据库
python main.py --no-import
```

### 输出文件

- `output/chemical_prices_YYYYMMDD.csv` - 价格数据（带日期）
- `output/chemical_prices.csv` - 价格数据（最新版）
- `output/chemical_utilization_YYYYMMDD.csv` - 开工率数据（带日期）
- `output/chemical_utilization.csv` - 开工率数据（最新版）

### 数据示例

```csv
product_name,product_category,price,price_change,unit,region,trade_date,source,tickers
PTA，化纤，4967.27,0.0，元/吨，全国，2025-02-27,AkShare,"600346,000703,002493"
短纤，化纤，7218.33,0.0，元/吨，全国，2025-02-27,AkShare,"600346,002493"
```

### 项目结构

```
<项目根目录>/
├── main.py                         # 爬虫调度入口
├── crawlers/
│   ├── base.py                     # 基类、日志、数据库
│   ├── akshare_chem_crawler.py     # AkShare 价格爬虫
│   ├── oilchem_price.py            # 价格爬虫封装
│   └── oilchem_utilization.py      # 开工率爬虫
├── storage/
│   └── csv_exporter.py             # CSV 导出模块
├── scripts/
│   └── import_chemical_data.py     # 数据库导入脚本
├── config/
│   └── products.yaml               # 产品配置（13 大类）
└── output/
    ├── chemical_prices_*.csv       # 价格数据
    └── chemical_utilization_*.csv  # 开工率数据
```

---

## 投资者关系数据下载器

### 功能说明

自动下载 A 股上市公司的投资者关系数据，支持四个下载器：

1. **巨潮资讯网** - 《投资者关系活动记录表》PDF 下载
2. **深交所互动易** - 深市上市公司投资者问答数据（原始 API 版）
3. **上证 e 互动** - 沪市上市公司投资者问答数据（原始 API 版）
4. **AKShare 互动平台** - 深市互动易 + 沪市 e 互动整合版（推荐）

所有下载器均支持增量下载（高水位线机制）。

### 安装依赖

```bash
pip install -r requirements.txt
# 如果使用 AKShare 下载器，需要额外安装：
pip install akshare
```

### 使用方法

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

### 目录结构

```
<项目根目录>/
├── standalone_ir_downloader.py       # 巨潮 IR 下载器
├── standalone_hdy_downloader.py      # 互动易下载器（原始 API）
├── standalone_ehd_downloader.py      # e 互动下载器（原始 API）
├── standalone_ak_irm_downloader.py   # AKShare 互动平台下载器（推荐）
├── 公司列表.csv                       # 输入文件
├── requirements.txt                  # 依赖列表
├── ARCHITECTURE.md                   # 架构文档
├── test_*.py                         # 测试脚本
└── data/
    ├── ir_pdfs/                      # 巨潮 PDF 存储目录
    ├── hdy_attachments/              # 互动易附件存储
    ├── ehd_attachments/              # e 互动附件存储
    ├── ak_irm/                       # AKShare 互动平台数据存储
    └── sync_record.db                # SQLite 数据库（4 张表）
```

### 核心特性

1. **增量下载**：使用 SQLite 记录每只股票上次抓取日期，避免重复下载
2. **批量获取**：一次性获取所有市场数据，然后按股票代码过滤
3. **防御性编程**：
   - 反爬休眠（2-5 秒随机延迟）
   - 网络超时（15 秒）
   - 单文件下载失败不中断整体流程
4. **文件名清洗**：自动移除非法字符（`\ / : * ? " < > |`）

### 输入文件格式

`公司列表.csv` 必须包含以下字段：

```csv
ticker,company_name,exchange
sz.300054，鼎龙股份，sz
sh.600071，凤凰光学，sh
bj.920001，纬达光电，bj
```

- `ticker`: 股票代码（格式：交易所。代码）
- `company_name`: 公司名称
- `exchange`: 交易所（sz/sh/bj）

### 注意事项

1. 首次运行会下载所有历史数据（从 2024-01-01 开始）
2. 再次运行只会下载新增的 PDF
3. 网络不好时可能需要较长时间，请耐心等待
4. 如需重新下载所有数据，删除 `data/sync_record.db` 即可

---

## 调度服务

### 功能说明

常驻后台调度服务，自动定时执行全部爬虫任务，无需手动运行。基于 APScheduler 实现，支持 cron 表达式、错过补跑。

### 调度计划

| 任务 | 调度时间 | 状态 |
|------|----------|------|
| 化工产品价格 | 工作日 09:30、18:00 | ✅ 启用 |
| 化工开工率 | 工作日 18:30 | ❌ 暂未启用 |
| AKShare 互动平台 | 每天 02:00 | ✅ 启用 |
| 巨潮 PDF | 每天 03:00 | ✅ 启用 |

调度配置文件：`config/scheduler.yaml`，可自由修改 cron 表达式和启用/禁用开关。

### 安装依赖

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 如需化工价格爬虫，额外安装 akshare
pip install akshare
```

### 启动服务

```bash
# 激活虚拟环境
source venv/bin/activate

# 前台启动（调试用，Ctrl+C 停止）
python scheduler_service.py

# 后台启动
nohup python scheduler_service.py > /dev/null 2>&1 &
```

### 手动执行单个任务

```bash
# 立即执行化工价格爬虫
python scheduler_service.py --run-now chemical_price

# 立即执行 AKShare 互动平台
python scheduler_service.py --run-now ak_irm

# 立即执行巨潮 PDF 下载
python scheduler_service.py --run-now ir_pdf

# 指定配置文件
python scheduler_service.py --config /path/to/scheduler.yaml
```

---

### 日常运维

```bash
# 查看调度日志
tail -f data/scheduler.log

# 查看进程状态
ps aux | grep scheduler_service

# 停止服务
kill $(ps aux | grep scheduler_service | grep -v grep | awk '{print $2}')

# 查看任务执行记录
sqlite3 data/sync_record.db "SELECT job_name, start_time, status, records_count FROM scheduler_run_log ORDER BY id DESC LIMIT 10;"
```

### macOS launchd 部署（开机自启）

```bash
# 1. 编辑 plist，替换路径占位符
vim deploy/com.crawlhub.scheduler.plist

# 2. 安装服务
cp deploy/com.crawlhub.scheduler.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.crawlhub.scheduler.plist

# 3. 查看服务状态
launchctl list | grep crawlhub

# 4. 停止服务
launchctl unload ~/Library/LaunchAgents/com.crawlhub.scheduler.plist
```
