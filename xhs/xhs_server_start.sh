#!/bin/bash

# 小红书 MCP Server 启动脚本
# 用于启动和管理小红书 MCP Server
#
# 使用前请配置：
#   将 xiaohongshu-mcp 二进制文件放到 /root/.openclaw/bin/ 目录下
#   或通过环境变量 XHS_SERVER_BIN 指定路径

# MCP Server 二进制路径（优先使用环境变量，否则使用默认路径）
XHS_SERVER_BIN="${XHS_SERVER_BIN:-/root/.openclaw/bin/xiaohongshu-mcp}"
SERVER_LOG="/tmp/xhs_server.log"

# 检查二进制文件是否存在
if [ ! -f "$XHS_SERVER_BIN" ]; then
    echo "❌ MCP Server 二进制文件不存在：$XHS_SERVER_BIN"
    echo "💡 请将 xiaohongshu-mcp 二进制文件放置到上述路径，或设置环境变量："
    echo "   export XHS_SERVER_BIN=/your/path/to/xiaohongshu-mcp"
    exit 1
fi

# 检查 Server 是否已在运行
if pgrep -f "xiaohongshu-mcp" > /dev/null 2>&1; then
    echo "✅ MCP Server 已经在运行"
    curl -4 -s http://127.0.0.1:18060/api/v1/login/status 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "Server 响应缓慢，请稍后重试"
    exit 0
fi

# 启动 Server
echo "🚀 启动小红书 MCP Server..."
cd "$(dirname "$XHS_SERVER_BIN")"
nohup "$XHS_SERVER_BIN" > "$SERVER_LOG" 2>&1 &
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
