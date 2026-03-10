#!/bin/bash

# 小红书自动运营系统启动脚本
# 支持一次性运行、定时任务、单步执行等模式

set -e

SCRIPT_DIR="/Users/huzezhi/Documents/test/Script/SaturnScript/npi-test/2025"
VENV_PATH="$SCRIPT_DIR/.venv"
OPERATION_SCRIPT="$SCRIPT_DIR/xhs_auto_operation.py"
SERVER_START_SCRIPT="$SCRIPT_DIR/xhs_server_start.sh"
LOG_DIR="$HOME/.openclaw/xhs_logs"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================
# 函数
# ============================================================

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║          🔥 小红书自动运营系统启动器                       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

show_usage() {
    print_header
    echo -e "${YELLOW}使用方式：${NC}"
    echo "  $0 run              # 运行一次完整流程"
    echo "  $0 schedule         # 启动定时任务（每天9点）"
    echo "  $0 fetch            # 仅爬取热门话题"
    echo "  $0 generate         # 仅生成笔记"
    echo "  $0 publish          # 仅发布笔记"
    echo "  $0 monitor          # 仅监控评论"
    echo "  $0 logs             # 查看运行日志"
    echo "  $0 status           # 检查系统状态"
    echo ""
    echo -e "${YELLOW}示例：${NC}"
    echo "  # 快速开始（运行一次）"
    echo "  $0 run"
    echo ""
    echo "  # 后台定时运行（每天早上9点）"
    echo "  $0 schedule"
    echo ""
    exit 1
}

check_environment() {
    echo "🔍 检查运行环境..."
    
    # 检查虚拟环境
    if [ ! -d "$VENV_PATH" ]; then
        echo -e "${RED}❌ 虚拟环境不存在：$VENV_PATH${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ 虚拟环境${NC}"
    
    # 检查脚本
    if [ ! -f "$OPERATION_SCRIPT" ]; then
        echo -e "${RED}❌ 运营脚本不存在：$OPERATION_SCRIPT${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ 运营脚本${NC}"
    
    # 检查 Server
    if ! pgrep -f "xiaohongshu-mcp-darwin-arm64" > /dev/null; then
        echo -e "${YELLOW}⚠️  MCP Server 未运行，正在启动...${NC}"
        bash "$SERVER_START_SCRIPT"
    else
        echo -e "${GREEN}  ✓ MCP Server 已运行${NC}"
    fi
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    echo -e "${GREEN}  ✓ 日志目录${NC}"
    
    echo -e "${GREEN}✅ 环境检查完成${NC}\n"
}

activate_venv() {
    source "$VENV_PATH/bin/activate"
}

run_operation() {
    echo -e "${BLUE}>>> 启动小红书自动运营流程${NC}\n"
    
    check_environment
    activate_venv
    
    python3 "$OPERATION_SCRIPT" run
    
    echo ""
    echo -e "${GREEN}✅ 运营流程已启动${NC}"
}

schedule_operation() {
    echo -e "${BLUE}>>> 启动定时任务调度器${NC}\n"
    
    check_environment
    activate_venv
    
    echo -e "${YELLOW}ℹ️  定时任务设定：每天早上 9:00${NC}"
    echo -e "${YELLOW}ℹ️  按 Ctrl+C 可暂停${NC}\n"
    
    python3 "$OPERATION_SCRIPT" schedule
}

fetch_trending() {
    echo -e "${BLUE}>>> 爬取热门话题${NC}\n"
    
    check_environment
    activate_venv
    
    python3 "$OPERATION_SCRIPT" fetch-trending
}

generate_notes() {
    echo -e "${BLUE}>>> 生成笔记内容${NC}\n"
    
    check_environment
    activate_venv
    
    python3 "$OPERATION_SCRIPT" generate
}

publish_notes() {
    echo -e "${BLUE}>>> 发布笔记${NC}\n"
    
    check_environment
    activate_venv
    
    python3 "$OPERATION_SCRIPT" publish
}

monitor_comments() {
    echo -e "${BLUE}>>> 监控评论回复${NC}\n"
    
    check_environment
    activate_venv
    
    python3 "$OPERATION_SCRIPT" monitor-comments
}

show_logs() {
    echo -e "${BLUE}>>> 查看运行日志${NC}\n"
    
    if [ ! -d "$LOG_DIR" ]; then
        echo -e "${YELLOW}还没有日志记录${NC}"
        exit 0
    fi
    
    echo -e "${YELLOW}📋 最近的日志：${NC}\n"
    ls -lh "$LOG_DIR" | tail -5
    
    echo ""
    echo -e "${YELLOW}📄 实时日志：${NC}\n"
    tail -100 "$LOG_DIR/xhs_operation.log"
}

check_status() {
    echo -e "${BLUE}>>> 系统状态检查${NC}\n"
    
    echo "📊 系统状态："
    
    # MCP Server
    if pgrep -f "xiaohongshu-mcp-darwin-arm64" > /dev/null; then
        echo -e "  ${GREEN}✓ MCP Server${NC} - 运行中"
    else
        echo -e "  ${RED}✗ MCP Server${NC} - 未运行"
    fi
    
    # 虚拟环境
    if [ -d "$VENV_PATH" ]; then
        echo -e "  ${GREEN}✓ Python 虚拟环境${NC} - 就绪"
    else
        echo -e "  ${RED}✗ Python 虚拟环境${NC} - 不存在"
    fi
    
    # 脚本文件
    if [ -f "$OPERATION_SCRIPT" ]; then
        echo -e "  ${GREEN}✓ 运营脚本${NC} - 就绪"
    else
        echo -e "  ${RED}✗ 运营脚本${NC} - 不存在"
    fi
    
    # 日志
    if [ -d "$LOG_DIR" ]; then
        log_count=$(find "$LOG_DIR" -type f | wc -l)
        echo -e "  ${GREEN}✓ 日志文件${NC} - $log_count 个"
    else
        echo -e "  ${YELLOW}~ 日志目录${NC} - 未创建"
    fi
    
    echo ""
    echo "📁 关键路径："
    echo "  脚本目录:    $SCRIPT_DIR"
    echo "  虚拟环境:    $VENV_PATH"
    echo "  日志目录:    $LOG_DIR"
    echo ""
}

# ============================================================
# 主程序
# ============================================================

if [ $# -eq 0 ]; then
    show_usage
fi

case "$1" in
    run)
        run_operation
        ;;
    schedule)
        schedule_operation
        ;;
    fetch)
        fetch_trending
        ;;
    generate)
        generate_notes
        ;;
    publish)
        publish_notes
        ;;
    monitor)
        monitor_comments
        ;;
    logs)
        show_logs
        ;;
    status)
        check_status
        ;;
    *)
        echo -e "${RED}❌ 未知命令：$1${NC}"
        show_usage
        ;;
esac
