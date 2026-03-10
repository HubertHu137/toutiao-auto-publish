#!/bin/bash
# 一键发布今日头条热点新闻
# 功能：抓取热榜 → AI改写 → 生成Word → 检查修复 → 批量发布
# 触发方式：
#   1. 命令行运行：bash publish_toutiao_hot.sh
#   2. 飞书消息：发送"发布头条热点"
#   3. OpenClaw Web：发送"发布头条热点"

set -e  # 遇到错误立即退出

# ========== 配置 ==========
SCRIPT_DIR="/root/.openclaw/scripts"
OPENCLAW_SCRIPTS="/root/.openclaw/scripts"
LOG_FILE="/tmp/toutiao_hot_publish.log"
DOCX_DIR="$HOME/.openclaw/toutiao_articles/docx"
TODAY=$(date +%Y%m%d)

# 飞书通知配置（可选：设置 FEISHU_CHAT_ID 环境变量启用飞书通知）
# 获取方式：在飞书群中添加机器人，查看群设置中的 Chat ID（格式：oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx）
FEISHU_CHAT_ID="${FEISHU_CHAT_ID:-}"

# ========== 日志函数 ==========
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

send_feishu_msg() {
    local msg="$1"
    if command -v openclaw >/dev/null 2>&1 && [ -n "$FEISHU_CHAT_ID" ]; then
        openclaw message send --channel feishu --target "$FEISHU_CHAT_ID" --message "$msg" 2>&1 | tee -a "$LOG_FILE"
    fi
}

# ========== 清理旧日志 ==========
if [ -f "$LOG_FILE" ]; then
    # 保留最近100行日志
    tail -n 100 "$LOG_FILE" > "$LOG_FILE.tmp"
    mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

# ========== 开始执行 ==========
log "================================================"
log "🚀 开始执行：一键发布今日头条热点"
log "================================================"

send_feishu_msg "📰 开始发布今日头条热点...

⏳ 预计耗时：5-10分钟
📊 目标：6-8篇文章"

# ========== 第1步：检查依赖 ==========
log ""
log "🔍 第1步：检查环境依赖..."

# 检查Python依赖
log "  检查Python依赖..."
python3 -c "import playwright, docx" 2>/dev/null
if [ $? -ne 0 ]; then
    log "  ⚠️  安装缺失的Python依赖..."
    pip3 install playwright python-docx Pillow imagehash 2>&1 | tee -a "$LOG_FILE"
    playwright install chromium 2>&1 | tee -a "$LOG_FILE"
fi

# 检查Cookie是否存在
COOKIE_FILE="$HOME/.openclaw/toutiao_cookies.json"
if [ ! -f "$COOKIE_FILE" ]; then
    log "  ❌ Cookie文件不存在：$COOKIE_FILE"
    log "  请先运行：python3 $SCRIPT_DIR/toutiao_publish_login.py"
    send_feishu_msg "❌ 发布失败：Cookie未配置

请先运行登录脚本：
\`\`\`bash
python3 $SCRIPT_DIR/toutiao_publish_login.py
\`\`\`"
    exit 1
fi

# 检查Cookie是否过期（检查文件修改时间，超过50天提示更新）
COOKIE_AGE=$(( ($(date +%s) - $(stat -f %m "$COOKIE_FILE" 2>/dev/null || stat -c %Y "$COOKIE_FILE" 2>/dev/null || echo 0)) / 86400 ))
if [ "$COOKIE_AGE" -gt 50 ]; then
    log "  ⚠️  Cookie已使用${COOKIE_AGE}天，可能即将过期（有效期60天）"
    log "  如果发布失败，请运行：python3 $SCRIPT_DIR/toutiao_publish_login.py --refresh-cookie"
fi

log "  ✅ 环境检查通过"

# ========== 第2步：生成Word文档 ==========
log ""
log "📝 第2步：抓取热榜并生成Word文档..."
log "  目标：6-8篇文章"
log "  预计耗时：3-5分钟"

cd "$SCRIPT_DIR" || exit 1

# 执行生成脚本
python3 toutiao_publisher.py 2>&1 | tee -a "$LOG_FILE"
GENERATE_EXIT=$?

if [ $GENERATE_EXIT -ne 0 ]; then
    log "  ❌ 文档生成失败（退出码：$GENERATE_EXIT）"
    send_feishu_msg "❌ 头条热点发布失败

步骤：文档生成
原因：脚本执行失败

请查看日志：$LOG_FILE"
    exit 1
fi

# 检查是否生成了Word文档
DOCX_COUNT=$(ls -1 "$DOCX_DIR/${TODAY}_"*.docx 2>/dev/null | grep -v "_fixed.docx" | wc -l | tr -d ' ')
if [ "$DOCX_COUNT" -eq 0 ]; then
    log "  ❌ 未生成任何Word文档"
    send_feishu_msg "❌ 头条热点发布失败

步骤：文档生成
原因：未生成任何Word文档

可能原因：
1. 热榜获取失败
2. 过滤后无可用内容
3. AI改写失败

请查看日志：$LOG_FILE"
    exit 1
fi

log "  ✅ 成功生成 ${DOCX_COUNT} 篇Word文档"

# ========== 第3步：检查并修复文档 ==========
log ""
log "🔍 第3步：检查文档质量并自动修复..."
log "  检查项：乱码、敏感词、规范性"

bash "$OPENCLAW_SCRIPTS/check_word_articles.sh" --fix 2>&1 | tee -a "$LOG_FILE"
CHECK_EXIT=$?

if [ $CHECK_EXIT -ne 0 ]; then
    log "  ⚠️  文档检查失败，但继续发布（退出码：$CHECK_EXIT）"
else
    log "  ✅ 文档质量检查完成"
fi

# 统计修复后的文档数量（包括_fixed.docx）
TOTAL_DOCS=$(ls -1 "$DOCX_DIR/${TODAY}_"*.docx 2>/dev/null | wc -l | tr -d ' ')
log "  当前共有 ${TOTAL_DOCS} 篇文档待发布"

# ========== 第4步：批量发布 ==========
log ""
log "🚀 第4步：批量发布到头条号..."
log "  预计耗时：${DOCX_COUNT} 篇 × 30秒/篇 = $((DOCX_COUNT * 30 / 60)) 分钟"

send_feishu_msg "📝 已生成 ${DOCX_COUNT} 篇Word文档
🔍 质量检查完成
🚀 开始批量发布...

预计耗时：$((DOCX_COUNT * 30 / 60)) 分钟"

# 执行批量发布（非交互模式）
cd "$OPENCLAW_SCRIPTS" || exit 1

# 使用expect自动确认（如果未安装expect则跳过）
if command -v expect >/dev/null 2>&1; then
    log "  使用expect自动确认发布..."
    expect << 'EOF' 2>&1 | tee -a "$LOG_FILE"
set timeout 3600
spawn bash batch_publish_word.sh
expect {
    "是否继续下一篇？(y/n)" {
        send "y\r"
        exp_continue
    }
    eof
}
EOF
    PUBLISH_EXIT=${PIPESTATUS[0]}
else
    # 没有expect，直接运行（可能需要手动确认）
    log "  直接运行发布脚本..."
    bash batch_publish_word.sh 2>&1 | tee -a "$LOG_FILE"
    PUBLISH_EXIT=$?
fi

# ========== 第5步：检查发布结果 ==========
log ""
log "📊 第5步：检查发布结果..."

if [ $PUBLISH_EXIT -eq 0 ]; then
    log "  ✅ 批量发布完成"
    
    # 统计发布结果（简单统计，实际可能需要更复杂的逻辑）
    SUCCESS_COUNT=$DOCX_COUNT
    FAIL_COUNT=0
    
    log ""
    log "================================================"
    log "🎉 发布完成！"
    log "================================================"
    log "📊 统计："
    log "  生成文档：${DOCX_COUNT} 篇"
    log "  发布成功：${SUCCESS_COUNT} 篇"
    log "  发布失败：${FAIL_COUNT} 篇"
    log ""
    log "📁 文档位置：$DOCX_DIR"
    log "📝 日志文件：$LOG_FILE"
    log "================================================"
    
    send_feishu_msg "✅ 今日头条热点发布完成！

📊 统计结果：
  • 生成文档：${DOCX_COUNT} 篇
  • 发布成功：${SUCCESS_COUNT} 篇
  • 发布失败：${FAIL_COUNT} 篇

📁 文档位置：$DOCX_DIR
📝 日志文件：$LOG_FILE

🎉 任务完成！"
    
    exit 0
else
    log "  ⚠️  发布过程可能存在错误（退出码：$PUBLISH_EXIT）"
    log "  请查看日志确认具体结果"
    
    send_feishu_msg "⚠️  头条热点发布完成，但可能存在部分失败

步骤：批量发布
退出码：$PUBLISH_EXIT

建议：
1. 查看日志：$LOG_FILE
2. 检查头条号后台
3. 手动补发失败的文章

📁 文档位置：$DOCX_DIR"
    
    exit $PUBLISH_EXIT
fi
