#!/bin/bash
# 股东报告管理工具启动脚本

cd "$(dirname "$0")"

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3"
    exit 1
fi

# 安装 Python 依赖
echo "检查 Python 依赖..."
pip3 install fastapi uvicorn pandas requests python-multipart -q

# 检查 Node.js 环境
if ! command -v npm &> /dev/null; then
    echo "错误: 未找到 Node.js/npm"
    echo "请先安装 Node.js: https://nodejs.org/"
    exit 1
fi

# 安装前端依赖
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

# 启动后端 API (后台运行)
echo "启动后端 API..."
nohup python3 api.py > /tmp/shareholder_api.log 2>&1 &
API_PID=$!
echo "后端 API 已启动 (PID: $API_PID)"

# 等待 API 启动
sleep 3

# 启动前端 (后台运行)
echo "启动前端开发服务器..."
nohup npm run dev > /tmp/shareholder_frontend.log 2>&1 &
FRONTEND_PID=$!
echo "前端已启动 (PID: $FRONTEND_PID)"

echo "股东报告系统已完全启动"
echo "访问地址：http://localhost:5174"

# 保存 PID 以便停止
echo $API_PID > /tmp/shareholder_api.pid
echo $FRONTEND_PID > /tmp/shareholder_frontend.pid

# 等待
wait
