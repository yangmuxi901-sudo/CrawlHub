import React from 'react';
import ReactDOM from 'react-dom/client';
import ShareholderReports from './ShareholderReports';
import './index.css';

// 如果作为独立应用运行
const App: React.FC = () => {
  return (
    <div style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <ShareholderReports />
    </div>
  );
};

// 如果作为组件导出
export { ShareholderReports };

// 独立运行时挂载
if (document.getElementById('root')) {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

export default App;
