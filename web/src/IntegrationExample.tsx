/**
 * 集成示例：如何在其他 React 项目中使用股东报告 Tab
 *
 * 使用方法：
 * 1. 将 web/src/ShareholderReports.tsx 复制到你的项目
 * 2. 安装依赖: npm install antd @ant-design/icons axios dayjs
 * 3. 在你的路由或 Tab 组件中引入
 */

import React from 'react';
import { Tabs } from 'antd';
import { FileTextOutlined, HomeOutlined, SettingOutlined } from '@ant-design/icons';

// 导入股东报告组件
import ShareholderReports from './ShareholderReports';

// 假设这是你的其他页面组件
const HomePage: React.FC = () => <div>首页内容</div>;
const SettingsPage: React.FC = () => <div>设置页面</div>;

/**
 * 集成示例：作为 Tab 使用
 */
const AppWithTabs: React.FC = () => {
  return (
    <Tabs defaultActiveKey="home" style={{ padding: 16 }}>
      <Tabs.TabPane
        tab={<span><HomeOutlined /> 首页</span>}
        key="home"
      >
        <HomePage />
      </Tabs.TabPane>

      {/* 股东报告 Tab */}
      <Tabs.TabPane
        tab={<span><FileTextOutlined /> 股东报告</span>}
        key="shareholder-reports"
      >
        <ShareholderReports />
      </Tabs.TabPane>

      <Tabs.TabPane
        tab={<span><SettingOutlined /> 设置</span>}
        key="settings"
      >
        <SettingsPage />
      </Tabs.TabPane>
    </Tabs>
  );
};

/**
 * 集成示例：作为路由页面使用
 *
 * // 在路由配置中:
 * // {
 * //   path: '/shareholder-reports',
 * //   element: <ShareholderReports />,
 * // }
 */

export default AppWithTabs;
