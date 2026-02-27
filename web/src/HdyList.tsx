/**
 * 深交所互动易 - 投资者问答列表组件
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
  Tooltip,
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
  // 互动易相关 API（需要后端实现）
  getHdyCompanies: (params: any) => axios.get(`${API_BASE}/hdy/companies`, { params }),
  getHdyFiles: (ticker: string) => axios.get(`${API_BASE}/hdy/files/${ticker}`),
  downloadHdyZip: (ticker: string) => `${API_BASE}/hdy/download/${ticker}`,
};

// ============== 类型定义 ==============
interface HdyCompanyItem {
  ticker: string;
  company_name: string;
  local_count: number;
  last_sync_date: string;
}

// ============== 主组件 ==============
const HdyList: React.FC = () => {
  // 状态
  const [companies, setCompanies] = useState<HdyCompanyItem[]>([]);
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
      const res = await api.getHdyCompanies({
        page: page,
        page_size: pageSize,
        search: search || undefined,
      });
      setCompanies(res.data.items);
      setTotal(res.data.total);
    } catch (e) {
      console.error('Failed to fetch HDY companies:', e);
      // 模拟数据用于展示
      setCompanies([
        {
          ticker: 'sz.300054',
          company_name: '鼎龙股份',
          local_count: 15,
          last_sync_date: '2026-02-20',
        },
        {
          ticker: 'sz.300003',
          company_name: '乐普医疗',
          local_count: 8,
          last_sync_date: '2026-02-19',
        },
      ]);
      setTotal(2);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search]);

  const fetchFiles = async (ticker: string) => {
    try {
      const res = await api.getHdyFiles(ticker);
      setFileList(res.data.files || []);
    } catch (e) {
      console.error('Failed to fetch HDY files:', e);
      // 模拟数据用于展示
      setFileList([
        '2026-02-20_关于公司 2026 年发展战略的问答.txt',
        '2026-02-18_关于新产品研发进度的问答.txt',
        '2026-02-15_关于海外市场拓展的问答.txt',
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
    window.open(api.downloadHdyZip(ticker), '_blank');
    message.success('开始下载');
  };

  // ============== 表格列定义 ==============
  const companyColumns: ColumnsType<HdyCompanyItem> = [
    {
      title: '股票代码',
      dataIndex: 'ticker',
      key: 'ticker',
      width: 120,
      render: (text) => <Tag color="green">{text}</Tag>,
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
      render: () => <Tag color="green">深市</Tag>,
    },
    {
      title: '问答文件',
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
      width: 150,
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
          <Tooltip title="下载 ZIP">
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => handleDownload(record.ticker)}
              disabled={record.local_count === 0}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  // ============== 渲染 ==============
  return (
    <div className="hdy-list" style={{ padding: 24 }}>
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

export default HdyList;
