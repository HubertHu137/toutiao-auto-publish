#!/bin/bash

# 小红书 MCP Server 启动脚本
# 用于启动和管理小红书 MCP Server

SERVER_BIN="/Users/huzezhi/xiaohongshu-mcp/xiaohongshu-mcp-darwin-arm64"
SERVER_LOG="/tmp/xhs_server.log"

# 检查 Server 是否已在运行
if pgrep -f "xiaohongshu-mcp-darwin-arm64" > /dev/null 2>&1; then
    echo "✅ MCP Server 已经在运行"
    curl -4 -s http://127.0.0.1:18060/api/v1/login/status 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "Server 响应缓慢，请稍后重试"
    exit 0
fi

# 启动 Server
echo "🚀 启动小红书 MCP Server..."
cd /Users/huzezhi/xiaohongshu-mcp
nohup "$SERVER_BIN" > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# 等待 Server 启动
echo "⏳ 等待 Server 启动..."
for i in {1..10}; do
    sleep 1
    if curl -4 -s -m 1 http://127.0.0.1:18060/api/v1/login/status > /dev/null 2>&1; then
        echo "✅ Server 启动成功！"
        echo ""
        echo "📊 Server 状态："
        curl -4 -s http://127.0.0.1:18060/api/v1/login/status 2>/dev/null | python3 -m json.tool
        exit 0
    fi
done

echo "⚠️  Server 启动中，请等待..."
tail -f "$SERVER_LOG"
