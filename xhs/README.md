# 小红书自动运营系统

一个基于 Python 和 MCP 的小红书自动化运营工具，支持热门话题爬取、AI 内容生成、自动发布和评论监控。

## ✨ 功能特性

- 🔍 **智能话题爬取**：自动爬取小红书热门话题，筛选高互动内容
- 🤖 **AI 内容生成**：基于热门话题生成原创小红书爆款笔记
- 🖼️ **智能配图**：自动获取相关免版权图片，支持图片去重
- 📤 **自动发布**：通过 MCP Server 自动发布笔记到小红书
- 🔄 **内容去重**：智能检测和避免内容重复，保证原创性
- 📊 **定时任务**：支持定时自动运行（如每天 9:00）
- 💬 **评论监控**：自动监控笔记评论并生成 AI 回复
- 📝 **草稿管理**：本地保存草稿，支持手动发布

## 📁 文件结构

```
xhs/
├── xhs_operation_launcher.sh      # 主启动脚本
├── xhs_server_start.sh            # MCP Server 启动脚本
├── xhs_auto_operation.py          # 核心运营脚本
├── xhs_ai_content_generator.py    # AI 内容生成器
├── xhs_client.py                  # 小红书 MCP 客户端
└── README.md                      # 项目文档
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 1. 安装 Python 依赖
cd /root/.openclaw/scripts
python3 -m venv .venv
source .venv/bin/activate
pip install requests schedule

# 2. 下载小红书 MCP Server
# 从官方渠道获取 xiaohongshu-mcp 二进制文件
# 放置到 /root/.openclaw/bin/ 目录下
# 或通过环境变量 XHS_SERVER_BIN 指定路径
```

### 2. 配置环境变量（可选）

```bash
# 在 ~/.bashrc 或 ~/.zshrc 中添加
export XHS_SERVER_BIN="/path/to/xiaohongshu-mcp"  # MCP Server 路径
export XHS_CLIENT_PATH="/root/.openclaw/scripts/xhs_client.py"  # 客户端路径
export XHS_VENV_PATH="/root/.openclaw/scripts/.venv"  # 虚拟环境路径
export PIXABAY_API_KEY="your-pixabay-api-key"  # Pixabay API Key（可选）
```

### 3. 启动系统

```bash
# 授予执行权限
chmod +x /root/.openclaw/scripts/xhs_*.sh

# 启动 MCP Server（需要先登录小红书账号）
./xhs_server_start.sh

# 运行完整运营流程
./xhs_operation_launcher.sh run

# 启动定时任务（每天9点运行）
./xhs_operation_launcher.sh schedule
```

## 📋 使用方式

### 主启动脚本命令

```bash
# 运行一次完整流程
./xhs_operation_launcher.sh run

# 启动定时任务（每天9点）
./xhs_operation_launcher.sh schedule

# 仅爬取热门话题
./xhs_operation_launcher.sh fetch

# 仅生成笔记内容（保存为本地草稿）
./xhs_operation_launcher.sh generate

# 仅发布笔记（发布本地草稿）
./xhs_operation_launcher.sh publish

# 仅监控评论回复
./xhs_operation_launcher.sh monitor

# 查看运行日志
./xhs_operation_launcher.sh logs

# 检查系统状态
./xhs_operation_launcher.sh status
```

### 单步执行（Python脚本）

```bash
# 激活虚拟环境
source /root/.openclaw/scripts/.venv/bin/activate

# 运行完整流程
python3 xhs_auto_operation.py run

# 仅爬取热门话题
python3 xhs_auto_operation.py fetch-trending

# 仅生成笔记草稿
python3 xhs_auto_operation.py generate

# 仅发布草稿
python3 xhs_operation_launcher.py publish
```

## ⚙️ 高级配置

### 修改运营参数

编辑 `xhs_auto_operation.py` 中的 `CONFIG` 部分：

```python
CONFIG = {
    "daily_posts": 2,              # 每天发布笔记数
    "min_engagement": 1000,        # 最低互动数（点赞 + 评论 + 收藏）
    "trending_topics_count": 5,    # 爬取热门话题数
    "exclude_keywords": [          # 排除的敏感词
        "疫情", "政治", "成人", "骗局", "赌博",
        "非法", "暴力", "极端", "违规"
    ],
    "api_timeout": 60,             # API 超时时间
}
```

### 配置 Pixabay API

1. 访问 [Pixabay API 注册页面](https://pixabay.com/api/docs/)
2. 注册账号获取免费 API Key
3. 配置环境变量：
   ```bash
   export PIXABAY_API_KEY="your-pixabay-api-key"
   ```

### 自定义话题关键词

修改 `xhs_auto_operation.py` 中的 `trending_keywords` 列表：

```python
trending_keywords = [
    "AI工具", "OpenClaw", "副业赚钱", "职场技能",
    "小红书运营", "工作效率", "创业", "自媒体"
]
```

## 🏗️ 云端部署

### 1. 上传文件到云端

```bash
# 将 xhs 目录上传到云端服务器
scp -r xhs/ root@your-server:/root/.openclaw/scripts/
```

### 2. 配置云端环境

```bash
# 登录云端服务器
ssh root@your-server

# 安装 Python 环境
cd /root/.openclaw/scripts
apt-get update && apt-get install -y python3 python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install requests schedule

# 配置 MCP Server
# 下载 xiaohongshu-mcp 二进制文件到 /root/.openclaw/bin/
```

### 3. 设置定时任务

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天9点运行）
0 9 * * * cd /root/.openclaw/scripts && ./xhs_operation_launcher.sh run >> /var/log/xhs_operation.log 2>&1
```

## 🔧 子脚本说明

### `xhs_ai_content_generator.py`

- **功能**：AI 内容生成器，基于模板生成小红书风格的爆款内容
- **特点**：多样化模板、随机化数字、符合小红书风格
- **使用**：`from xhs_ai_content_generator import AIContentGenerator`

### `xhs_client.py`

- **功能**：小红书 MCP 客户端，提供 REST API 接口
- **接口**：登录状态检查、笔记搜索、详情获取、发布笔记
- **使用**：`python3 xhs_client.py <command> [options]`

### `xhs_auto_operation.py`

- **功能**：核心运营脚本，包含完整自动化流程
- **流程**：爬取 → 筛选 → 生成 → 配图 → 发布 → 监控
- **特点**：内容去重、图片去重、失败重试、本地草稿

## 📊 数据存储

系统自动在以下目录保存数据：

```
~/.openclaw/
├── xhs_logs/              # 运行日志
│   ├── xhs_operation.log  # 操作日志
│   └── xhs_topics.log     # 话题日志
├── xhs_articles/          # 笔记草稿
│   ├── 20250101_090000_draft.json
│   └── 20250101_090100_published.json
└── xhs_images/            # 图片缓存
```

## ⚠️ 注意事项

1. **合规使用**：请遵守小红书平台规则，避免发布违规内容
2. **频率控制**：避免频繁操作，建议每天发布 1-3 篇笔记
3. **内容原创**：系统已内置去重机制，但仍需确保内容原创性
4. **账号安全**：MCP Server 需要登录小红书账号，请妥善保管
5. **图片版权**：系统使用 Pixabay 免版权图片，请遵守使用条款

## 🔍 常见问题

### Q: MCP Server 启动失败？
A: 检查二进制文件权限：`chmod +x /path/to/xiaohongshu-mcp`

### Q: 无法连接到 MCP Server？
A: 确保 Server 已启动：`curl http://127.0.0.1:18060/api/v1/login/status`

### Q: 图片获取失败？
A: 检查网络连接，或配置 Pixabay API Key 获取更多图片

### Q: 内容重复率高？
A: 系统已内置去重机制，可调整 `check_content_duplicate` 函数的相似度阈值

### Q: 如何查看运行日志？
A: 使用 `./xhs_operation_launcher.sh logs` 或查看 `~/.openclaw/xhs_logs/`

## 📄 License

本项目基于 MIT 许可证开源，仅供学习和研究使用。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进项目！

## 📞 支持

如有问题，请：
1. 查看 [常见问题](#常见问题) 部分
2. 检查运行日志：`./xhs_operation_launcher.sh logs`
3. 提交 Issue 报告问题

---

**免责声明**：本项目为自动化工具，使用前请了解并遵守小红书平台规则。不当使用可能导致账号受限，作者不承担任何责任。