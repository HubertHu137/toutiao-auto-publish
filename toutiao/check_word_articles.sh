#!/bin/bash
# Word文档内容检查工具 - Shell封装脚本
# 用法：
#   bash check_word_articles.sh                    # 批量检查今天的所有文档
#   bash check_word_articles.sh --fix              # 批量检查并自动修复
#   bash check_word_articles.sh <文件路径>         # 检查单个文件
#   bash check_word_articles.sh <文件路径> --fix   # 检查并修复单个文件

SCRIPT_DIR="/root/.openclaw/scripts"
CHECK_SCRIPT="$SCRIPT_DIR/check_and_fix_word.py"

echo "================================================"
echo "📋 Word文档内容检查工具"
echo "================================================"
echo ""

# 检查脚本是否存在
if [ ! -f "$CHECK_SCRIPT" ]; then
    echo "❌ 检查脚本不存在：$CHECK_SCRIPT"
    exit 1
fi

# 确保依赖已安装
echo "🔍 检查依赖..."
python3 -c "import docx, PIL, imagehash" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  安装缺失的依赖..."
    pip3 install python-docx Pillow imagehash
fi

# 根据参数运行
if [ $# -eq 0 ]; then
    # 无参数：批量检查（不修复）
    echo "🔍 批量检查今天生成的所有Word文档..."
    echo ""
    python3 "$CHECK_SCRIPT" --batch
elif [ "$1" = "--fix" ]; then
    # --fix：批量检查并自动修复
    echo "🔍 批量检查并自动修复..."
    echo ""
    python3 "$CHECK_SCRIPT" --batch --fix
elif [ -f "$1" ]; then
    # 文件路径：检查单个文件
    if [ "$2" = "--fix" ]; then
        echo "🔍 检查单个文件并自动修复..."
        echo ""
        python3 "$CHECK_SCRIPT" "$1" --fix
    else
        echo "🔍 检查单个文件..."
        echo ""
        python3 "$CHECK_SCRIPT" "$1"
    fi
else
    echo "❌ 无效的参数：$1"
    echo ""
    echo "用法："
    echo "  bash $0                    # 批量检查今天的所有文档"
    echo "  bash $0 --fix              # 批量检查并自动修复"
    echo "  bash $0 <文件路径>         # 检查单个文件"
    echo "  bash $0 <文件路径> --fix   # 检查并修复单个文件"
    exit 1
fi

echo ""
echo "================================================"
echo "✅ 检查完成"
echo "================================================"
