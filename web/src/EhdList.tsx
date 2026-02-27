/**
 * 上证 e 互动 - 投资者问答列表组件
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Input,
  Typography,
  List,
  Badge,
  Drawer,
  Empty,
  message,
} from 'antd';
import {
  FileTextOutlined,
  FolderOutlined,
  DownloadOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import axios from 'axios';

const { Text } = Typography;

// ============== API 配置 ==============
const API_BASE = '/api';

const api = {
  // e 互动相关 API（需要后端实现）
  getEhdCompanies: (params: any) => axios.get(`${API_BASE}/ehd/companies`, { params }),
  getEhdFiles: (ticker: string) => axios.get(`${API_BASE}/ehd/files/${ticker}`),
  downloadEhdZip: (ticker: string) => `${API_BASE}/ehd/download/${ticker}`,
};

// ============== 类型定义 ==============
interface EhdCompanyItem {
  ticker: string;
  company_name: string;
  local_count: number;
  last_sync_date: string;
}

// ============== 主组件 ==============
const EhdList: React.FC = () => {
  // 状态
  const [companies, setCompanies] = useState<EhdCompanyItem[]>([]);
  const [loading, setLoading] = useState(false);

  // 分页和筛选
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');

  // Drawer 状态
  const [fileDrawerVisible, setFileDrawerVisible] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [fileList, setFileList] = useState<string[]>([]);

  // ============== 数据加载 ==============
  const fetchCompanies = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getEhdCompanies({
        page: page,
        page_size: pageSize,
        search: search || undefined,
      });
      setCompanies(res.data.items);
      setTotal(res.data.total);
    } catch (e) {
      console.error('Failed to fetch EHD companies:', e);
      // 模拟数据用于展示
      setCompanies([
        {
          ticker: 'sh.600071',
          company_name: '凤凰光学',
          local_count: 12,
          last_sync_date: '2026-02-20',
        },
        {
          ticker: 'sh.600000',
          company_name: '浦发银行',
          local_count: 6,
          last_sync_date: '2026-02-18',
        },
      ]);
      setTotal(2);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search]);

  const fetchFiles = async (ticker: string) => {
    try {
      const res = await api.getEhdFiles(ticker);
      setFileList(res.data.files || []);
    } catch (e) {
      console.error('Failed to fetch EHD files:', e);
      // 模拟数据用于展示
      setFileList([
        '2026-02-20_关于公司 2026 年经营计划的问答.txt',
        '2026-02-17_关于数字化转型的问答.txt',
      ]);
    }
  };

  useEffect(() => {
    fetchCompanies();

    const interval = setInterval(() => {
      fetchCompanies();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchCompanies]);

  // ============== 操作处理 ==============
  const handleDownload = (ticker: string) => {
    window.open(api.downloadEhdZip(ticker), '_blank');
    message.success('开始下载');
  };

  // ============== 表格列定义 ==============
  const companyColumns: ColumnsType<EhdCompanyItem> = [
    {
      title: '股票代码',
      dataIndex: 'ticker',
      key: 'ticker',
      width: 120,
      render: (text) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '公司名称',
      dataIndex: 'company_name',
      key: 'company_name',
      ellipsis: true,
    },
    {
      title: '市场',
      key: 'market',
      width: 80,
      render: () => <Tag color="blue">沪市</Tag>,
    },
    {
      title: '问答文件',
      dataIndex: 'local_count',
      key: 'local_count',
      width: 100,
      render: (count) => (
        <Badge count={count} showZero color={count > 0 ? 'blue' : 'default'} />
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
      width: 150,
      render: (_, record) => (
        <Space size="small">
          <Button
            size="small"
            icon={<FolderOutlined />}
            onClick={() => {
              setSelectedTicker(record.ticker);
              fetchFiles(record.ticker);
              setFileDrawerVisible(true);
            }}
            disabled={record.local_count === 0}
          >
            查看
          </Button>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => handleDownload(record.ticker)}
            disabled={record.local_count === 0}
          >
            下载
          </Button>
        </Space>
      ),
    },
  ];

  // ============== 渲染 ==============
  return (
    <div className="ehd-list" style={{ padding: 24 }}>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Input.Search
            placeholder="搜索股票代码或公司名称"
            allowClear
            style={{ width: 250 }}
            onSearch={(value) => {
              setSearch(value);
              setPage(1);
            }}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchCompanies}>
            刷新
          </Button>
        </Space>

        <Table
          columns={companyColumns}
          dataSource={companies}
          rowKey="ticker"
          loading={loading}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => {
              setPage(page);
              setPageSize(pageSize);
            },
          }}
          size="small"
        />
      </Card>

      {/* 文件浏览 Drawer */}
      <Drawer
        title={`${selectedTicker} - 问答文件列表`}
        placement="right"
        width={500}
        onClose={() => setFileDrawerVisible(false)}
        open={fileDrawerVisible}
      >
        {fileList.length > 0 ? (
          <List
            dataSource={fileList}
            renderItem={(item) => (
              <List.Item>
                <Space>
                  <FileTextOutlined />
                  <Text ellipsis style={{ maxWidth: 380 }}>{item}</Text>
                </Space>
              </List.Item>
            )}
          />
        ) : (
          <Empty description="暂无文件" />
        )}
      </Drawer>
    </div>
  );
};

export default EhdList;
