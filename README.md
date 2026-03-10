# 龙虾🦞上部署今日头条热点自动发布工具

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Shell](https://img.shields.io/badge/Shell-Bash-green.svg)](https://www.gnu.org/software/bash/)

一套全自动化的今日头条内容创作与发布工具。**无需手动操作**，每天自动抓取热榜 → AI 改写成爆款文章 → 生成 Word 文档 → 批量发布到头条号。

---

## ✨ 功能特性

- 🔥 **热榜抓取**：支持今日头条、微博、百度热搜三路来源，自动容错切换
- 🤖 **AI 改写**：调用大模型将热点标题改写为 500-700 字图文并茂的爆款文章
- 🖼️ **自动配图**：通过 Tavily 搜索匹配新闻配图，智能过滤广告图片
- 📝 **Word 生成**：自动生成符合头条格式的 `.docx` 文档（含嵌入图片）
- 🔍 **质量检查**：AI 自动检测乱码、敏感词、格式问题并修复
- 🚀 **批量发布**：通过 Playwright 操控浏览器，自动完成 Word 导入和发布流程
- 🔔 **飞书通知**（可选）：发布进度实时推送到飞书群
- 🗂️ **历史去重**：70% 相似度 Jaccard 算法，避免重复发布近期内容
- 🧹 **自动清理**：7 天前的旧文档自动清理，节省磁盘空间

---

## 📁 文件结构

```
toutiao/
├── publish_toutiao_hot.sh      # 🚀 主入口脚本（一键执行全流程）
├── toutiao_publisher.py        # 抓取热榜 + AI 改写 + 生成 Word 文档
├── toutiao_publish_word.py     # 通过 Playwright 自动发布 Word 到头条号
├── toutiao_publish_login.py    # 首次运行：扫码登录并保存 Cookie
├── check_word_articles.sh      # 文档质量检查封装脚本（Shell）
└── check_and_fix_word.py       # 文档质量检查 + AI 自动修复（Python）
```

**运行时生成目录：**

```
~/.openclaw/
├── toutiao_cookies.json            # 头条号登录 Cookie（首次登录后生成）
└── toutiao_articles/
    ├── docx/                       # 生成的 Word 文档
    ├── md/                         # Markdown 存档 + 本地图片
    └── history_titles.txt          # 历史标题记录（用于去重）
```

---

## 🚀 快速开始

### 1. 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | 运行 Python 脚本 |
| pip 包 | - | playwright、python-docx、Pillow、imagehash |
| Chromium | - | `playwright install chromium` |
| expect | - | 可选，用于自动确认发布（`apt install expect`） |

### 2. 安装依赖

```bash
pip3 install playwright python-docx Pillow imagehash
playwright install chromium
```

### 3. 配置环境变量

在服务器上设置以下环境变量（建议写入 `~/.bashrc` 或 `~/.zshrc`）：

```bash
# 必填：AI API Key（用于 AI 改写和质量检查）
export AI_API_KEY="your_ai_api_key_here"

# 必填：Tavily Search API Key（用于搜索新闻原文和配图）
# 申请地址：https://tavily.com
export TAVILY_API_KEY="your_tavily_api_key_here"

# 可选：飞书群 Chat ID（用于发布进度通知）
# 格式：oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export FEISHU_CHAT_ID="your_feishu_chat_id_here"
```

> 💡 **AI API** 是 OpenAI 兼容的代理服务，默认监听 `http://127.0.0.1:19999`。如需修改地址，编辑 `toutiao_publisher.py` 和 `check_and_fix_word.py` 中的 `AI_API_URL` 变量。

### 4. 首次登录（仅需一次）

```bash
python3 ~/.openclaw/scripts/toutiao_publish_login.py
```

按照提示在浏览器中完成头条号扫码登录，按 Enter 后 Cookie 自动保存。Cookie 有效期约 60 天，到期后重新运行此命令刷新。

### 5. 一键发布

```bash
bash ~/.openclaw/scripts/publish_toutiao_hot.sh
```

脚本会按顺序执行：
1. ✅ 检查环境依赖和 Cookie 有效性
2. 📝 抓取热榜并生成 5-6 篇 Word 文档（约 3-5 分钟）
3. 🔍 检查文档质量并自动修复
4. 🚀 批量发布到头条号（每篇约 30 秒）

---

## ⚙️ 高级配置

在 `toutiao_publisher.py` 顶部可以调整以下参数：

```python
TARGET_MIN   = 5   # 每次生成最少文章数
TARGET_MAX   = 6   # 每次生成最多文章数
FETCH_POOL   = 40  # 从热榜抓取的候选池大小
MIN_IMAGES   = 1   # 每篇文章至少需要的图片数量
MODEL_ID     = "gpt-4o-mini"  # 使用的 AI 模型
```

---

## 🛠️ 单独使用各子脚本

**仅生成 Word 文档（不发布）：**
```bash
cd ~/.openclaw/scripts
python3 toutiao_publisher.py
```

**检查今日文档质量：**
```bash
bash ~/.openclaw/scripts/check_word_articles.sh
```

**检查并自动修复：**
```bash
bash ~/.openclaw/scripts/check_word_articles.sh --fix
```

**检查单个文件：**
```bash
bash ~/.openclaw/scripts/check_word_articles.sh /path/to/article.docx --fix
```

**批量发布已生成的文档：**
```bash
bash ~/.openclaw/scripts/batch_publish_word.sh
```

**发布单篇 Word 文档：**
```bash
python3 ~/.openclaw/scripts/toutiao_publish_word.py /path/to/article.docx
# 仅保存为草稿：
python3 ~/.openclaw/scripts/toutiao_publish_word.py /path/to/article.docx --save-draft
```

---

## 🔧 部署到云端服务器

本项目设计为在云端服务器（root 用户）长期运行：

```bash
# 1. 将所有脚本上传至服务器
scp -r toutiao/ root@your-server:/root/.openclaw/scripts/

# 2. 添加执行权限
chmod +x /root/.openclaw/scripts/*.sh

# 3. 配置环境变量（写入 /root/.bashrc）
echo 'export AI_API_KEY="your_key"' >> /root/.bashrc
echo 'export TAVILY_API_KEY="your_key"' >> /root/.bashrc
source /root/.bashrc

# 4. 配置每日定时任务（每天上午 8 点自动发布）
crontab -e
# 添加：
# 0 8 * * * bash /root/.openclaw/scripts/publish_toutiao_hot.sh >> /tmp/toutiao_cron.log 2>&1
```

---

## 📋 内容过滤规则

脚本内置政治/政策类关键词过滤，以下类型内容会被自动跳过：
- 领导人相关报道
- 党政机构新闻
- 敏感外交、军事话题
- 宏观经济政策（GDP 目标、财政货币政策等）

保留：娱乐、科技、社会、生活、体育等民生类内容。

---

## 🐛 常见问题

**Q: 发布时提示"Cookie 不存在"？**  
A: 运行 `python3 toutiao_publish_login.py` 重新登录。

**Q: 文档生成失败，提示 TAVILY_API_KEY 未配置？**  
A: 确认 `TAVILY_API_KEY` 环境变量已正确设置，可运行 `echo $TAVILY_API_KEY` 验证。

**Q: AI 改写失败？**  
A: 确认 AI API 服务已在 `127.0.0.1:19999` 正常运行，并检查 `AI_API_KEY` 是否正确。

**Q: 发布过程中浏览器找不到按钮？**  
A: 头条号编辑器可能更新了 UI，查看 `/tmp/toutiao_*.png` 截图排查，或提交 Issue。

**Q: Cookie 多久过期？**  
A: 约 60 天，脚本会在 50 天时自动提醒，运行登录脚本时加 `--refresh-cookie` 参数刷新。

---

## 📄 License

MIT License — 仅供学习和个人使用，请遵守今日头条平台相关规范。
