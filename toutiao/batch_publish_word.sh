#!/bin/bash
# 批量发布今日生成的Word文档到头条号

DOCX_DIR="$HOME/.openclaw/toutiao_articles/docx"
TODAY=$(date +%Y%m%d)

echo "================================================"
echo "📰 头条号Word文档批量发布工具"
echo "================================================"
echo ""

# 查找今天生成的Word文档
files=$(ls -1 "$DOCX_DIR" | grep "^${TODAY}_")
count=$(echo "$files" | grep -v '^$' | wc -l)

if [ $count -eq 0 ]; then
    echo "❌ 未找到今天生成的Word文档"
    exit 1
fi

echo "📋 找到 $count 篇待发布文档："
echo "$files" | nl
echo ""

# 循环发布每篇文档
index=1
for file in $files; do
    filepath="$DOCX_DIR/$file"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📝 发布第 $index/$count 篇：$file"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # 调用发布脚本
    /usr/bin/python3 "$HOME/.openclaw/scripts/toutiao_publish_word.py" "$filepath"
    
    result=$?
    if [ $result -eq 0 ]; then
        echo "✅ 第 $index 篇发布成功"
    else
        echo "⚠️  第 $index 篇发布失败（退出码: $result）"
        read -p "是否继续下一篇？(y/n) " continue
        if [ "$continue" != "y" ]; then
            echo "❌ 用户取消，退出批量发布"
            exit 1
        fi
    fi
    
    # 发布间隔（避免频繁操作）
    if [ $index -lt $count ]; then
        echo ""
        echo "⏱️  等待10秒后继续下一篇..."
        sleep 10
    fi
    
    index=$((index + 1))
done

echo ""
echo "================================================"
echo "🎉 批量发布完成！共处理 $count 篇文档"
echo "================================================"
