/**
 * 股东报告管理组件
 * 可作为 Tab 集成到其他项目中
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Row,
  Col,
  Statistic,
  Button,
  Table,
  Tag,
  Space,
  Progress,
  Modal,
  Form,
  Input,
  Select,
  message,
  Tabs,
  List,
  Typography,
  Tooltip,
  Badge,
  Popconfirm,
  Drawer,
  Alert,
} from 'antd';
import HdyList from './HdyList';
import EhdList from './EhdList';
import ChemicalData from './ChemicalData';
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  ReloadOutlined,
  DownloadOutlined,
  DeleteOutlined,
  PlusOutlined,
  FileTextOutlined,
  FolderOutlined,
  SyncOutlined,
  ExportOutlined,
  ClearOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import axios from 'axios';

const { Title, Text } = Typography;
const { TabPane } = Tabs;
const { Option } = Select;

// ============== API 配置 ==============
const API_BASE = '/api';

const api = {
  // 任务管理
  getTaskStatus: () => axios.get(`${API_BASE}/task/status`),
  startTask: (data: { incremental: boolean; reset_all: boolean }) =>
    axios.post(`${API_BASE}/task/start`, data),
  stopTask: () => axios.post(`${API_BASE}/task/stop`),
  resetTask: () => axios.post(`${API_BASE}/task/reset`),

  // 统计
  getStats: () => axios.get(`${API_BASE}/stats/overview`),
  getCompanyStats: (params: any) => axios.get(`${API_BASE}/stats/companies`, { params }),
  getDistribution: () => axios.get(`${API_BASE}/stats/distribution`),

  // 公司管理
  getCompanies: (params: any) => axios.get(`${API_BASE}/companies`, { params }),
  addCompany: (data: any) => axios.post(`${API_BASE}/companies`, data),
  deleteCompany: (ticker: string) => axios.delete(`${API_BASE}/companies/${ticker}`),

  // 日志
  getLogs: (params: any) => axios.get(`${API_BASE}/logs`, { params }),
  clearLogs: () => axios.delete(`${API_BASE}/logs`),

  // 数据库
  getDbRecords: () => axios.get(`${API_BASE}/database/records`),
  deleteDbRecord: (ticker: string) => axios.delete(`${API_BASE}/database/records/${ticker}`),
  resetDatabase: () => axios.post(`${API_BASE}/database/reset`),

  // 文件
  browseFiles: (ticker?: string) => axios.get(`${API_BASE}/files/browse`, { params: { ticker } }),

  // 导出
  exportCsv: () => `${API_BASE}/export/csv`,
  exportJson: () => `${API_BASE}/export/json`,
};

// ============== 类型定义 ==============
interface TaskStatus {
  status: 'idle' | 'running' | 'completed' | 'failed';
  progress: number;
  total: number;
  downloaded: number;
  current_company: string;
  elapsed_seconds: number | null;
  error_message: string;
}

interface StatsOverview {
  total_companies: number;
  companies_with_files: number;
  companies_without_files: number;
  total_pdfs: number;
  db_records: number;
  last_download_date: string;
}

interface CompanyItem {
  ticker: string;
  company_name: string;
  exchange: string;
  industry_l1: string;
  industry_l2: string;
  industry_l3: string;
  local_count: number;
  last_sync_date: string;
}

// ============== 主组件 ==============
const ShareholderReports: React.FC = () => {
  // 状态
  const [taskStatus, setTaskStatus] = useState<TaskStatus>({
    status: 'idle',
    progress: 0,
    total: 0,
    downloaded: 0,
    current_company: '',
    elapsed_seconds: null,
    error_message: '',
  });
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [companies, setCompanies] = useState<CompanyItem[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  // 分页和筛选
  const [companyPage, setCompanyPage] = useState(1);
  const [companyPageSize, setCompanyPageSize] = useState(10);
  const [companyTotal, setCompanyTotal] = useState(0);
  const [companySearch, setCompanySearch] = useState('');
  const [companyExchange, setCompanyExchange] = useState<string | null>(null);

  // Modal 状态
  const [addCompanyVisible, setAddCompanyVisible] = useState(false);
  const [startTaskVisible, setStartTaskVisible] = useState(false);
  const [fileDrawerVisible, setFileDrawerVisible] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [fileList, setFileList] = useState<string[]>([]);

  const [addForm] = Form.useForm();
  const [taskForm] = Form.useForm();

  // ============== 数据加载 ==============
  const fetchTaskStatus = useCallback(async () => {
    try {
      const res = await api.getTaskStatus();
      setTaskStatus(res.data);
    } catch (e) {
      console.error('Failed to fetch task status:', e);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.getStats();
      setStats(res.data);
    } catch (e) {
      console.error('Failed to fetch stats:', e);
    }
  }, []);

  const fetchCompanies = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getCompanies({
        page: companyPage,
        page_size: companyPageSize,
        search: companySearch || undefined,
        exchange: companyExchange || undefined,
      });
      setCompanies(res.data.items);
      setCompanyTotal(res.data.total);
    } catch (e) {
      console.error('Failed to fetch companies:', e);
    } finally {
      setLoading(false);
    }
  }, [companyPage, companyPageSize, companySearch, companyExchange]);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await api.getLogs({ lines: 100 });
      setLogs(res.data.logs);
    } catch (e) {
      console.error('Failed to fetch logs:', e);
    }
  }, []);

  const fetchFiles = async (ticker: string) => {
    try {
      const res = await api.browseFiles(ticker);
      setFileList(res.data.files || []);
    } catch (e) {
      console.error('Failed to fetch files:', e);
      setFileList([]);
    }
  };

  // 轮询任务状态
  useEffect(() => {
    fetchTaskStatus();
    fetchStats();
    fetchCompanies();

    const interval = setInterval(() => {
      fetchTaskStatus();
      if (taskStatus.status === 'running') {
        fetchStats();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [fetchTaskStatus, fetchStats, fetchCompanies, taskStatus.status]);

  // ============== 操作处理 ==============
  const handleStartTask = async (values: { incremental: boolean; reset_all: boolean }) => {
    try {
      await api.startTask(values);
      message.success('任务已启动');
      setStartTaskVisible(false);
      taskForm.resetFields();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '启动失败');
    }
  };

  const handleStopTask = async () => {
    try {
      await api.stopTask();
      message.success('任务已停止');
    } catch (e: any) {
      message.error(e.response?.data?.detail || '停止失败');
    }
  };

  const handleAddCompany = async (values: any) => {
    try {
      await api.addCompany(values);
      message.success('添加成功');
      setAddCompanyVisible(false);
      addForm.resetFields();
      fetchCompanies();
      fetchStats();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '添加失败');
    }
  };

  const handleDeleteCompany = async (ticker: string) => {
    try {
      await api.deleteCompany(ticker);
      message.success('删除成功');
      fetchCompanies();
      fetchStats();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败');
    }
  };

  const handleResetDbRecord = async (ticker: string) => {
    try {
      await api.deleteDbRecord(ticker);
      message.success(`已重置 ${ticker} 的下载记录`);
      fetchCompanies();
    } catch (e: any) {
      message.error('重置失败');
    }
  };

  const handleClearLogs = async () => {
    try {
      await api.clearLogs();
      message.success('日志已清空');
      fetchLogs();
    } catch (e) {
      message.error('清空失败');
    }
  };

  const handleExport = (type: 'csv' | 'json') => {
    const url = type === 'csv' ? api.exportCsv() : api.exportJson();
    window.open(url, '_blank');
  };

  // ============== 表格列定义 ==============
  const companyColumns: ColumnsType<CompanyItem> = [
    {
      title: '股票代码',
      dataIndex: 'ticker',
      key: 'ticker',
      width: 120,
      render: (text) => (
        <Tag color={text.startsWith('sz') ? 'green' : text.startsWith('sh') ? 'blue' : 'orange'}>
          {text}
        </Tag>
      ),
    },
    {
      title: '公司名称',
      dataIndex: 'company_name',
      key: 'company_name',
      ellipsis: true,
    },
    {
      title: '交易所',
      dataIndex: 'exchange',
      key: 'exchange',
      width: 80,
      render: (text) => {
        const map: Record<string, { color: string; label: string }> = {
          sz: { color: 'green', label: '深圳' },
          sh: { color: 'blue', label: '上海' },
          bj: { color: 'orange', label: '北京' },
        };
        return <Tag color={map[text]?.color}>{map[text]?.label || text}</Tag>;
      },
    },
    {
      title: '本地文件',
      dataIndex: 'local_count',
      key: 'local_count',
      width: 100,
      render: (count) => (
        <Badge count={count} showZero color={count > 0 ? 'green' : 'default'} />
      ),
      sorter: (a, b) => a.local_count - b.local_count,
    },
    {
      title: '最后同步',
      dataIndex: 'last_sync_date',
      key: 'last_sync_date',
      width: 120,
      render: (date) => date || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="查看文件">
            <Button
              size="small"
              icon={<FolderOutlined />}
              onClick={() => {
                setSelectedTicker(record.ticker);
                fetchFiles(record.ticker);
                setFileDrawerVisible(true);
              }}
              disabled={record.local_count === 0}
            />
          </Tooltip>
          <Tooltip title="重新下载">
            <Popconfirm
              title="重置下载记录后将重新下载该公司的所有文件，确定？"
              onConfirm={() => handleResetDbRecord(record.ticker)}
            >
              <Button size="small" icon={<SyncOutlined />} />
            </Popconfirm>
          </Tooltip>
          <Tooltip title="下载ZIP">
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => window.open(`${API_BASE}/files/download/${record.ticker}`, '_blank')}
              disabled={record.local_count === 0}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除该公司？"
            onConfirm={() => handleDeleteCompany(record.ticker)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ============== 渲染 ==============
  const getStatusTag = () => {
    const statusMap = {
      idle: { color: 'default', text: '空闲' },
      running: { color: 'processing', text: '运行中' },
      completed: { color: 'success', text: '已完成' },
      failed: { color: 'error', text: '失败' },
    };
    const s = statusMap[taskStatus.status];
    return <Tag color={s.color}>{s.text}</Tag>;
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}时${m}分${s}秒`;
    if (m > 0) return `${m}分${s}秒`;
    return `${s}秒`;
  };

  return (
    <div className="shareholder-reports" style={{ padding: 24 }}>
      <Title level={3}>
        <FileTextOutlined /> 股东报告管理
      </Title>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="公司总数"
              value={stats?.total_companies || 0}
              suffix="家"
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="PDF 总数"
              value={stats?.total_pdfs || 0}
              suffix="份"
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="有文件公司"
              value={stats?.companies_with_files || 0}
              suffix={`/ ${stats?.total_companies || 0}`}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="最后下载"
              value={stats?.last_download_date || '-'}
              valueStyle={{ fontSize: 16 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 任务状态卡片 */}
      <Card
        title={
          <Space>
            <span>下载任务</span>
            {getStatusTag()}
          </Space>
        }
        extra={
          <Space>
            {taskStatus.status === 'running' ? (
              <Button
                type="primary"
                danger
                icon={<PauseCircleOutlined />}
                onClick={handleStopTask}
              >
                停止任务
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={() => setStartTaskVisible(true)}
              >
                启动任务
              </Button>
            )}
            <Button icon={<ReloadOutlined />} onClick={() => { fetchStats(); fetchCompanies(); }}>
              刷新
            </Button>
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        {taskStatus.status === 'running' && (
          <>
            <Progress
              percent={Math.round((taskStatus.progress / taskStatus.total) * 100)}
              status="active"
              format={() => `${taskStatus.progress} / ${taskStatus.total}`}
            />
            <Space style={{ marginTop: 16 }}>
              <Text>当前: {taskStatus.current_company}</Text>
              <Text type="secondary">|</Text>
              <Text>已下载: {taskStatus.downloaded} 份</Text>
              <Text type="secondary">|</Text>
              <Text>耗时: {formatDuration(taskStatus.elapsed_seconds)}</Text>
            </Space>
          </>
        )}
        {taskStatus.status === 'completed' && (
          <Alert
            message={`任务完成，共下载 ${taskStatus.downloaded} 份文件，耗时 ${formatDuration(taskStatus.elapsed_seconds)}`}
            type="success"
            showIcon
          />
        )}
        {taskStatus.status === 'failed' && (
          <Alert
            message={`任务失败: ${taskStatus.error_message}`}
            type="error"
            showIcon
          />
        )}
        {taskStatus.status === 'idle' && (
          <Text type="secondary">点击"启动任务"开始下载投资者关系活动记录表</Text>
        )}
      </Card>

      {/* 主内容区 */}
      <Tabs defaultActiveKey="ir">
        <TabPane
          tab={<span><FileTextOutlined /> 巨潮 IR</span>}
          key="ir"
        >
          <Card>
            <Space style={{ marginBottom: 16 }}>
              <Input.Search
                placeholder="搜索股票代码或公司名称"
                allowClear
                style={{ width: 250 }}
                onSearch={(value) => {
                  setCompanySearch(value);
                  setCompanyPage(1);
                }}
              />
              <Select
                placeholder="选择交易所"
                allowClear
                style={{ width: 120 }}
                onChange={(value) => {
                  setCompanyExchange(value);
                  setCompanyPage(1);
                }}
              >
                <Option value="sz">深圳</Option>
                <Option value="sh">上海</Option>
                <Option value="bj">北京</Option>
              </Select>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setAddCompanyVisible(true)}
              >
                添加公司
              </Button>
            </Space>

            <Table
              columns={companyColumns}
              dataSource={companies}
              rowKey="ticker"
              loading={loading}
              pagination={{
                current: companyPage,
                pageSize: companyPageSize,
                total: companyTotal,
                showSizeChanger: true,
                showQuickJumper: true,
                showTotal: (total) => `共 ${total} 条`,
                onChange: (page, pageSize) => {
                  setCompanyPage(page);
                  setCompanyPageSize(pageSize);
                },
              }}
              size="small"
            />
          </Card>
        </TabPane>

        <TabPane
          tab={<span><FileTextOutlined /> 互动易（深市）</span>}
          key="hdy"
        >
          <HdyList />
        </TabPane>

        <TabPane
          tab={<span><FileTextOutlined /> e 互动（沪市）</span>}
          key="ehd"
        >
          <EhdList />
        </TabPane>

        <TabPane
          tab={<span><ExportOutlined /> 化工数据</span>}
          key="chemical"
        >
          <ChemicalData />
        </TabPane>

        <TabPane
          tab={<span><FileTextOutlined /> 日志</span>}
          key="logs"
        >
          <Card
            extra={
              <Space>
                <Button icon={<ReloadOutlined />} onClick={fetchLogs}>
                  刷新
                </Button>
                <Popconfirm
                  title="确定清空所有日志？"
                  onConfirm={handleClearLogs}
                >
                  <Button icon={<ClearOutlined />} danger>
                    清空日志
                  </Button>
                </Popconfirm>
              </Space>
            }
          >
            <List
              dataSource={logs}
              renderItem={(item) => {
                let color = 'inherit';
                if (item.includes('[ERROR]')) color = '#ff4d4f';
                else if (item.includes('[WARNING]')) color = '#faad14';
                else if (item.includes('[成功]')) color = '#52c41a';

                return (
                  <List.Item style={{ padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}>
                    <Text style={{ fontSize: 12, color, fontFamily: 'monospace' }}>
                      {item}
                    </Text>
                  </List.Item>
                );
              }}
              style={{ maxHeight: 500, overflow: 'auto' }}
              locale={{ emptyText: '暂无日志' }}
            />
          </Card>
        </TabPane>

        <TabPane
          tab={<span><ExportOutlined /> 导出</span>}
          key="export"
        >
          <Card>
            <Space direction="vertical" size="large">
              <div>
                <Title level={5}>导出统计数据</Title>
                <Space>
                  <Button icon={<DownloadOutlined />} onClick={() => handleExport('csv')}>
                    导出 CSV
                  </Button>
                  <Button icon={<DownloadOutlined />} onClick={() => handleExport('json')}>
                    导出 JSON
                  </Button>
                </Space>
              </div>

              <div>
                <Title level={5}>危险操作</Title>
                <Space>
                  <Popconfirm
                    title="确定重置数据库？这将清除所有下载记录，下次运行将重新下载所有文件。"
                    onConfirm={async () => {
                      await api.resetDatabase();
                      message.success('数据库已重置');
                      fetchStats();
                    }}
                  >
                    <Button danger icon={<DeleteOutlined />}>
                      重置数据库
                    </Button>
                  </Popconfirm>
                </Space>
              </div>
            </Space>
          </Card>
        </TabPane>
      </Tabs>

      {/* 添加公司 Modal */}
      <Modal
        title="添加公司"
        open={addCompanyVisible}
        onCancel={() => setAddCompanyVisible(false)}
        onOk={() => addForm.submit()}
      >
        <Form form={addForm} layout="vertical" onFinish={handleAddCompany}>
          <Form.Item
            name="ticker"
            label="股票代码"
            rules={[{ required: true, message: '请输入股票代码' }]}
          >
            <Input placeholder="如: sz.300054" />
          </Form.Item>
          <Form.Item
            name="company_name"
            label="公司名称"
            rules={[{ required: true, message: '请输入公司名称' }]}
          >
            <Input placeholder="如: 鼎龙股份" />
          </Form.Item>
          <Form.Item
            name="exchange"
            label="交易所"
            rules={[{ required: true, message: '请选择交易所' }]}
          >
            <Select placeholder="选择交易所">
              <Option value="sz">深圳</Option>
              <Option value="sh">上海</Option>
              <Option value="bj">北京</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 启动任务 Modal */}
      <Modal
        title="启动下载任务"
        open={startTaskVisible}
        onCancel={() => setStartTaskVisible(false)}
        onOk={() => taskForm.submit()}
      >
        <Form
          form={taskForm}
          layout="vertical"
          onFinish={handleStartTask}
          initialValues={{ incremental: true, reset_all: false }}
        >
          <Form.Item
            name="incremental"
            label="下载模式"
            rules={[{ required: true }]}
          >
            <Select>
              <Option value={true}>增量下载（只下载新文件）</Option>
              <Option value={false}>全量下载</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="reset_all"
            label="重置记录"
            valuePropName="checked"
          >
            <Select>
              <Option value={false}>保留现有记录</Option>
              <Option value={true}>重置所有记录（重新下载）</Option>
            </Select>
          </Form.Item>
        </Form>
        <Alert
          message="提示"
          description="下载过程可能需要较长时间，请耐心等待。可以在日志标签页查看实时进度。"
          type="info"
          showIcon
        />
      </Modal>

      {/* 文件浏览 Drawer */}
      <Drawer
        title={`${selectedTicker} - 文件列表`}
        placement="right"
        width={400}
        onClose={() => setFileDrawerVisible(false)}
        open={fileDrawerVisible}
      >
        <List
          dataSource={fileList}
          renderItem={(item) => (
            <List.Item>
              <Space>
                <FileTextOutlined />
                <Text ellipsis style={{ maxWidth: 300 }}>{item}</Text>
              </Space>
            </List.Item>
          )}
          locale={{ emptyText: '暂无文件' }}
        />
      </Drawer>
    </div>
  );
};

export default ShareholderReports;
