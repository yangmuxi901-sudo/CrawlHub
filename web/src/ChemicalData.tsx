/**
 * 化工数据管理组件
 * 展示化工产品价格、开工率数据，支持爬取任务管理
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Row,
  Col,
  Statistic,
  Table,
  Tag,
  Button,
  Space,
  Input,
  Select,
  Typography,
  message,
  Tabs,
  Badge,
  Tooltip,
  Progress,
  Empty,
} from 'antd';
import {
  ExperimentOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  DownloadOutlined,
  RiseOutlined,
  FallOutlined,
  DashboardOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import axios from 'axios';

const { Text } = Typography;
const { TabPane } = Tabs;
const { Option } = Select;

// ============== API 配置 ==============
const API_BASE = '/api';

const chemApi = {
  // 化工数据
  getPrices: (params: any) => axios.get(`${API_BASE}/chemical/prices`, { params }),
  getUtilization: (params: any) => axios.get(`${API_BASE}/chemical/utilization`, { params }),
  getStats: () => axios.get(`${API_BASE}/chemical/stats`),
  // 爬取任务
  startCrawl: (data: { type: string }) => axios.post(`${API_BASE}/chemical/crawl/start`, data),
  getCrawlStatus: () => axios.get(`${API_BASE}/chemical/crawl/status`),
  // 导出
  exportPricesCsv: () => `${API_BASE}/chemical/export/prices`,
  exportUtilCsv: () => `${API_BASE}/chemical/export/utilization`,
};

// ============== 类型定义 ==============
interface PriceItem {
  product_name: string;
  product_category: string;
  price: number;
  price_change: number;
  unit: string;
  region: string;
  trade_date: string;
  source: string;
  tickers: string;
}

interface UtilizationItem {
  product_name: string;
  utilization_rate: number;
  week_change: number;
  stat_date: string;
  source: string;
}

interface ChemicalStats {
  total_products: number;
  total_categories: number;
  total_tickers: number;
  price_records: number;
  util_records: number;
  last_crawl_date: string;
}

interface CrawlStatus {
  status: 'idle' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
}

// 产品类别颜色映射
const CATEGORY_COLORS: Record<string, string> = {
  '化纤': 'blue',
  '氯碱': 'green',
  '煤化工': 'orange',
  '聚氨酯': 'purple',
  '氟化工': 'cyan',
  '钛白粉': 'magenta',
  '纯碱': 'gold',
  '磷化工': 'lime',
  '农药': 'red',
  '化肥': 'volcano',
  '橡胶': 'geekblue',
  '炼化': 'default',
  '民爆': 'warning',
  '精细化工': 'processing',
};

// ============== 模拟数据 ==============
const MOCK_PRICES: PriceItem[] = [
  { product_name: '涤纶POY', product_category: '化纤', price: 8500.00, price_change: 2.50, unit: '元/吨', region: '华东', trade_date: '2026-02-26', source: '隆众资讯', tickers: '601233,000703,002493' },
  { product_name: 'PVC', product_category: '氯碱', price: 6500.00, price_change: -0.50, unit: '元/吨', region: '华东', trade_date: '2026-02-26', source: '隆众资讯', tickers: '002092,600075,601216' },
  { product_name: 'MDI', product_category: '聚氨酯', price: 16800.00, price_change: 1.20, unit: '元/吨', region: '华东', trade_date: '2026-02-26', source: '隆众资讯', tickers: '600309' },
  { product_name: '甲醇', product_category: '煤化工', price: 2650.00, price_change: -1.80, unit: '元/吨', region: '华东', trade_date: '2026-02-26', source: '隆众资讯', tickers: '600989,600426' },
  { product_name: '钛白粉', product_category: '钛白粉', price: 17500.00, price_change: 0.80, unit: '元/吨', region: '全国', trade_date: '2026-02-26', source: '隆众资讯', tickers: '002601,002145' },
  { product_name: '纯碱', product_category: '纯碱', price: 1850.00, price_change: -2.10, unit: '元/吨', region: '华东', trade_date: '2026-02-26', source: '隆众资讯', tickers: '000683,000822' },
  { product_name: 'R22', product_category: '氟化工', price: 22000.00, price_change: 3.50, unit: '元/吨', region: '华东', trade_date: '2026-02-26', source: '隆众资讯', tickers: '600160,603379' },
  { product_name: '草甘膦', product_category: '磷化工', price: 28000.00, price_change: 0.30, unit: '元/吨', region: '华东', trade_date: '2026-02-26', source: '隆众资讯', tickers: '600141,600596' },
];

const MOCK_UTIL: UtilizationItem[] = [
  { product_name: '涤纶', utilization_rate: 85.0, week_change: -2.0, stat_date: '2026-02-26', source: '隆众资讯' },
  { product_name: 'PVC', utilization_rate: 78.5, week_change: 1.5, stat_date: '2026-02-26', source: '隆众资讯' },
  { product_name: 'MDI', utilization_rate: 92.0, week_change: 0.0, stat_date: '2026-02-26', source: '隆众资讯' },
  { product_name: '甲醇', utilization_rate: 72.3, week_change: -3.2, stat_date: '2026-02-26', source: '隆众资讯' },
  { product_name: '钛白粉', utilization_rate: 88.0, week_change: 2.0, stat_date: '2026-02-26', source: '隆众资讯' },
  { product_name: '纯碱', utilization_rate: 81.5, week_change: -1.0, stat_date: '2026-02-26', source: '隆众资讯' },
];

// ============== 主组件 ==============
const ChemicalData: React.FC = () => {
  const [prices, setPrices] = useState<PriceItem[]>(MOCK_PRICES);
  const [utilization, setUtilization] = useState<UtilizationItem[]>(MOCK_UTIL);
  const [stats, setStats] = useState<ChemicalStats | null>(null);
  const [crawlStatus, setCrawlStatus] = useState<CrawlStatus>({ status: 'idle', progress: 0, message: '' });
  const [loading, setLoading] = useState(false);

  // 筛选
  const [priceSearch, setPriceSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  // ============== 数据加载 ==============
  const fetchPrices = useCallback(async () => {
    setLoading(true);
    try {
      const res = await chemApi.getPrices({
        search: priceSearch || undefined,
        category: categoryFilter || undefined,
      });
      const items = res.data.items || res.data;
      if (items.length > 0) setPrices(items);
    } catch (e) {
      console.error('Failed to fetch prices:', e);
      setPrices(MOCK_PRICES);
    } finally {
      setLoading(false);
    }
  }, [priceSearch, categoryFilter]);

  const fetchUtilization = useCallback(async () => {
    try {
      const res = await chemApi.getUtilization({});
      const items = res.data.items || res.data;
      if (items.length > 0) setUtilization(items);
    } catch (e) {
      console.error('Failed to fetch utilization:', e);
      setUtilization(MOCK_UTIL);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const res = await chemApi.getStats();
      setStats(res.data);
    } catch (e) {
      setStats({
        total_products: 46, total_categories: 14, total_tickers: 73,
        price_records: MOCK_PRICES.length, util_records: MOCK_UTIL.length,
        last_crawl_date: '2026-02-26',
      });
    }
  }, []);

  const fetchCrawlStatus = useCallback(async () => {
    try {
      const res = await chemApi.getCrawlStatus();
      setCrawlStatus(res.data);
    } catch (e) {
      // 忽略
    }
  }, []);

  useEffect(() => {
    fetchPrices();
    fetchUtilization();
    fetchStats();
  }, [fetchPrices, fetchUtilization, fetchStats]);

  useEffect(() => {
    if (crawlStatus.status === 'running') {
      const interval = setInterval(fetchCrawlStatus, 3000);
      return () => clearInterval(interval);
    }
  }, [crawlStatus.status, fetchCrawlStatus]);

  // ============== 操作处理 ==============
  const handleStartCrawl = async (type: string) => {
    try {
      await chemApi.startCrawl({ type });
      message.success(`${type === 'price' ? '价格' : type === 'utilization' ? '开工率' : '全量'}爬取任务已启动`);
      setCrawlStatus({ status: 'running', progress: 0, message: '正在爬取...' });
      fetchCrawlStatus();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '启动失败');
    }
  };

  const handleExport = (type: string) => {
    const data = type === 'prices' ? prices : utilization;
    if (!data.length) {
      message.warning('暂无数据可导出');
      return;
    }
    const headers = Object.keys(data[0]);
    const csvRows = [
      headers.join(','),
      ...data.map(row => headers.map(h => {
        const val = (row as any)[h];
        const str = String(val ?? '');
        return str.includes(',') || str.includes('"') ? `"${str.replace(/"/g, '""')}"` : str;
      }).join(','))
    ];
    const blob = new Blob(['\uFEFF' + csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = type === 'prices' ? 'chemical_prices.csv' : 'chemical_utilization.csv';
    a.click();
    URL.revokeObjectURL(url);
    message.success('导出成功');
  };

  // ============== 表格列定义 - 价格 ==============
  const priceColumns: ColumnsType<PriceItem> = [
    {
      title: '产品',
      dataIndex: 'product_name',
      key: 'product_name',
      width: 120,
      fixed: 'left',
    },
    {
      title: '类别',
      dataIndex: 'product_category',
      key: 'product_category',
      width: 100,
      render: (cat) => <Tag color={CATEGORY_COLORS[cat] || 'default'}>{cat}</Tag>,
      filters: Object.keys(CATEGORY_COLORS).map(c => ({ text: c, value: c })),
      onFilter: (value, record) => record.product_category === value,
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      width: 120,
      align: 'right',
      render: (price) => <Text strong>{price?.toFixed(2)}</Text>,
      sorter: (a, b) => a.price - b.price,
    },
    {
      title: '涨跌幅(%)',
      dataIndex: 'price_change',
      key: 'price_change',
      width: 120,
      align: 'right',
      render: (change) => {
        if (change === 0 || change === null) return <Text>0.00</Text>;
        return change > 0
          ? <Text type="danger"><RiseOutlined /> +{change.toFixed(2)}</Text>
          : <Text type="success"><FallOutlined /> {change.toFixed(2)}</Text>;
      },
      sorter: (a, b) => a.price_change - b.price_change,
    },
    {
      title: '单位',
      dataIndex: 'unit',
      key: 'unit',
      width: 80,
    },
    {
      title: '地区',
      dataIndex: 'region',
      key: 'region',
      width: 80,
    },
    {
      title: '日期',
      dataIndex: 'trade_date',
      key: 'trade_date',
      width: 110,
    },
    {
      title: '关联股票',
      dataIndex: 'tickers',
      key: 'tickers',
      width: 200,
      ellipsis: true,
      render: (tickers) => {
        if (!tickers) return '-';
        const arr = tickers.split(',').slice(0, 3);
        return (
          <Space size={2} wrap>
            {arr.map((t: string) => <Tag key={t} color="blue">{t.trim()}</Tag>)}
            {tickers.split(',').length > 3 && <Tag>+{tickers.split(',').length - 3}</Tag>}
          </Space>
        );
      },
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (s) => <Tag>{s}</Tag>,
    },
  ];

  // ============== 表格列定义 - 开工率 ==============
  const utilColumns: ColumnsType<UtilizationItem> = [
    {
      title: '产品',
      dataIndex: 'product_name',
      key: 'product_name',
      width: 120,
    },
    {
      title: '开工率(%)',
      dataIndex: 'utilization_rate',
      key: 'utilization_rate',
      width: 200,
      render: (rate) => (
        <Space>
          <Progress
            percent={rate}
            size="small"
            style={{ width: 100 }}
            strokeColor={rate >= 80 ? '#52c41a' : rate >= 60 ? '#faad14' : '#ff4d4f'}
          />
          <Text strong>{rate?.toFixed(1)}%</Text>
        </Space>
      ),
      sorter: (a, b) => a.utilization_rate - b.utilization_rate,
    },
    {
      title: '周环比(%)',
      dataIndex: 'week_change',
      key: 'week_change',
      width: 120,
      align: 'right',
      render: (change) => {
        if (change === 0 || change === null) return <Text>0.00</Text>;
        return change > 0
          ? <Text type="danger"><RiseOutlined /> +{change.toFixed(2)}</Text>
          : <Text type="success"><FallOutlined /> {change.toFixed(2)}</Text>;
      },
      sorter: (a, b) => a.week_change - b.week_change,
    },
    {
      title: '统计日期',
      dataIndex: 'stat_date',
      key: 'stat_date',
      width: 110,
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (s) => <Tag>{s}</Tag>,
    },
  ];

  // ============== 渲染 ==============
  return (
    <div className="chemical-data" style={{ padding: 24 }}>
      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card size="small">
            <Statistic title="产品总数" value={stats?.total_products || 46} prefix={<ExperimentOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="产品类别" value={stats?.total_categories || 14} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="关联股票" value={stats?.total_tickers || 73} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="价格记录" value={stats?.price_records || prices.length} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="开工率记录" value={stats?.util_records || utilization.length} prefix={<DashboardOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="最后爬取" value={stats?.last_crawl_date || '-'} valueStyle={{ fontSize: 14 }} />
          </Card>
        </Col>
      </Row>

      {/* 爬取状态 */}
      {crawlStatus.status === 'running' && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space>
            <Text>正在爬取...</Text>
            <Progress percent={crawlStatus.progress} size="small" style={{ width: 200 }} />
            <Text type="secondary">{crawlStatus.message}</Text>
          </Space>
        </Card>
      )}

      {/* 主内容 Tabs */}
      <Tabs defaultActiveKey="prices">
        <TabPane
          tab={<span><RiseOutlined /> 产品价格</span>}
          key="prices"
        >
          <Card>
            <Space style={{ marginBottom: 16 }}>
              <Input.Search
                placeholder="搜索产品名称"
                allowClear
                style={{ width: 200 }}
                onSearch={(value) => setPriceSearch(value)}
              />
              <Select
                placeholder="选择类别"
                allowClear
                style={{ width: 140 }}
                onChange={(value) => setCategoryFilter(value)}
              >
                {Object.keys(CATEGORY_COLORS).map(cat => (
                  <Option key={cat} value={cat}>{cat}</Option>
                ))}
              </Select>
              <Button icon={<ReloadOutlined />} onClick={fetchPrices}>刷新</Button>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={() => handleStartCrawl('price')}
                disabled={crawlStatus.status === 'running'}
              >
                爬取价格
              </Button>
              <Button icon={<DownloadOutlined />} onClick={() => handleExport('prices')}>
                导出 CSV
              </Button>
            </Space>

            <Table
              columns={priceColumns}
              dataSource={prices.filter(p => {
                const matchSearch = !priceSearch || p.product_name.includes(priceSearch);
                const matchCat = !categoryFilter || p.product_category === categoryFilter;
                return matchSearch && matchCat;
              })}
              rowKey={(r) => `${r.product_name}_${r.trade_date}`}
              loading={loading}
              size="small"
              scroll={{ x: 1100 }}
              pagination={{
                showSizeChanger: true,
                showQuickJumper: true,
                showTotal: (total) => `共 ${total} 条`,
                defaultPageSize: 20,
              }}
            />
          </Card>
        </TabPane>

        <TabPane
          tab={<span><DashboardOutlined /> 开工率</span>}
          key="utilization"
        >
          <Card>
            <Space style={{ marginBottom: 16 }}>
              <Button icon={<ReloadOutlined />} onClick={fetchUtilization}>刷新</Button>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={() => handleStartCrawl('utilization')}
                disabled={crawlStatus.status === 'running'}
              >
                爬取开工率
              </Button>
              <Button icon={<DownloadOutlined />} onClick={() => handleExport('utilization')}>
                导出 CSV
              </Button>
            </Space>

            <Table
              columns={utilColumns}
              dataSource={utilization}
              rowKey={(r) => `${r.product_name}_${r.stat_date}`}
              size="small"
              pagination={{
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 条`,
                defaultPageSize: 20,
              }}
            />
          </Card>
        </TabPane>
      </Tabs>
    </div>
  );
};

export default ChemicalData;
