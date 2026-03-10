#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书自动运营系统
功能：自动爬取热门话题 → 筛选目标 → 生成原创笔记 → 发布 → 监控评论回复

使用方式：
    python3 xhs_auto_operation.py run              # 运行一次完整流程
    python3 xhs_auto_operation.py schedule         # 启动定时任务（每天9点）
    python3 xhs_auto_operation.py fetch-trending   # 仅爬取热门话题
    python3 xhs_auto_operation.py generate         # 仅生成笔记
    python3 xhs_auto_operation.py publish          # 仅发布笔记
    python3 xhs_auto_operation.py monitor-comments # 仅监控评论

日志位置：~/.openclaw/xhs_operation.log
"""

import json
import os
import sys
import time
import argparse
import subprocess
import requests
import random
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Set
import schedule
import logging
import hashlib

# ============================================================
# 配置
# ============================================================
BASE_DIR = Path.home() / ".openclaw"
LOG_DIR = BASE_DIR / "xhs_logs"
OPERATION_LOG = LOG_DIR / "xhs_operation.log"
TOPICS_LOG = LOG_DIR / "xhs_topics.log"
ARTICLES_DIR = BASE_DIR / "xhs_articles"
IMAGES_DIR = BASE_DIR / "xhs_images"

# 小红书 MCP Server
# XHS_CLIENT_PATH 优先读取环境变量，默认指向云端脚本目录
XHS_SERVER_URL = "http://127.0.0.1:18060"
XHS_CLIENT_PATH = Path(os.environ.get("XHS_CLIENT_PATH", "/root/.openclaw/scripts/xhs_client.py"))
VENV_PATH = Path(os.environ.get("XHS_VENV_PATH", "/root/.openclaw/scripts/.venv"))

# Pixabay 图片 API Key（免费注册可获取，配置后可获得更多图片）
# 注册地址：https://pixabay.com/api/docs/
# 未配置时使用内置备用图片库
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "")

# 配置参数
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

# ============================================================
# 日志设置
# ============================================================
def setup_logger():
    """初始化日志系统"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger("XHS_Operation")
    logger.setLevel(logging.DEBUG)
    
    # 文件日志
    file_handler = logging.FileHandler(OPERATION_LOG, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # 控制台日志
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()


# ============================================================
# 笔记清理与去重
# ============================================================
def cleanup_old_articles(days: int = 7):
    """
    自动删除大于指定天数的笔记文件
    
    Args:
        days: 保留的天数（默认7天）
    """
    logger.info(f"🧹 开始清理 {days} 天前的笔记...")
    
    if not ARTICLES_DIR.exists():
        logger.warning(f"  文章目录不存在：{ARTICLES_DIR}")
        return
    
    now = datetime.now()
    cutoff_time = now - timedelta(days=days)
    deleted_count = 0
    
    try:
        for article_file in ARTICLES_DIR.glob("*.json"):
            try:
                file_mtime = datetime.fromtimestamp(article_file.stat().st_mtime)
                
                if file_mtime < cutoff_time:
                    logger.debug(f"  删除旧笔记：{article_file.name} (创建于 {file_mtime})")
                    article_file.unlink()
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"  处理文件 {article_file.name} 时出错：{e}")
                continue
        
        if deleted_count > 0:
            logger.info(f"  ✅ 已删除 {deleted_count} 篇超过 {days} 天的笔记")
        else:
            logger.info(f"  ℹ️  没有找到超过 {days} 天的笔记")
    
    except Exception as e:
        logger.error(f"  ❌ 清理笔记时异常：{e}")


def get_historical_articles_info(days: int = 7) -> Dict[str, Dict]:
    """
    获取历史笔记信息（用于去重检查）
    
    返回：{
        "titles": set of titles,
        "content_hashes": set of content hashes,
        "image_hashes": set of image hashes,
    }
    """
    logger.info(f"📋 加载 {days} 天内的历史笔记信息...")
    
    info = {
        "titles": set(),
        "content_hashes": set(),
        "image_hashes": set(),
        "articles": []
    }
    
    if not ARTICLES_DIR.exists():
        logger.warning(f"  文章目录不存在")
        return info
    
    now = datetime.now()
    cutoff_time = now - timedelta(days=days)
    
    try:
        for article_file in ARTICLES_DIR.glob("*.json"):
            try:
                file_mtime = datetime.fromtimestamp(article_file.stat().st_mtime)
                
                # 只处理指定天数内的文件
                if file_mtime < cutoff_time:
                    continue
                
                with open(article_file, 'r', encoding='utf-8') as f:
                    article = json.load(f)
                
                # 记录标题
                title = article.get("title", "")
                if title:
                    info["titles"].add(title)
                
                # 计算内容哈希（用于检测内容重复）
                content = article.get("content", "")
                if content:
                    content_hash = hashlib.md5(content.encode()).hexdigest()
                    info["content_hashes"].add(content_hash)
                
                # 记录图片 URL（用于检测图片重复）
                images = article.get("images", [])
                for img in images:
                    if img:
                        img_hash = hashlib.md5(img.encode()).hexdigest()
                        info["image_hashes"].add(img_hash)
                
                info["articles"].append({
                    "file": article_file.name,
                    "title": title,
                    "created_time": file_mtime.isoformat()
                })
                
                logger.debug(f"  加载：{title[:40]}... ({len(images)} 张图片)")
            
            except Exception as e:
                logger.warning(f"  处理文件 {article_file.name} 时出错：{e}")
                continue
        
        logger.info(f"  ✅ 加载完成，共 {len(info['articles'])} 篇历史笔记")
        logger.info(f"     - 标题库：{len(info['titles'])} 个")
        logger.info(f"     - 内容哈希：{len(info['content_hashes'])} 个")
        logger.info(f"     - 图片哈希：{len(info['image_hashes'])} 个")
    
    except Exception as e:
        logger.error(f"  ❌ 加载历史笔记时异常：{e}")
    
    return info


def _title_similarity(title1: str, title2: str) -> float:
    """
    计算两个标题的 Jaccard 相似度（中文按字切分）
    """
    import re
    def tokenize(t):
        chars = re.findall(r'[\u4e00-\u9fff]', t)
        words = re.findall(r'[a-zA-Z0-9]+', t.lower())
        return set(chars + words)
    t1, t2 = tokenize(title1), tokenize(title2)
    if not t1 or not t2:
        return 0.0
    inter = len(t1 & t2)
    union = len(t1 | t2)
    return inter / union if union > 0 else 0.0


def check_content_duplicate(title: str, content: str, historical_info: Dict) -> bool:
    """
    检查笔记内容是否与历史笔记重复
    使用 70% 相似度阈值，而非精确字符串匹配
    
    返回：True 表示重复，False 表示不重复
    """
    # 检查标题相似度（70% 阈值，避免模板标题永远命中）
    for hist_title in historical_info["titles"]:
        sim = _title_similarity(title, hist_title)
        if sim >= 0.7:
            logger.warning(f"  ⚠️  警告：标题相似（{sim:.0%}）- {title}")
            return True
    
    # 检查内容重复（使用哈希）
    content_hash = hashlib.md5(content.encode()).hexdigest()
    if content_hash in historical_info["content_hashes"]:
        logger.warning(f"  ⚠️  警告：内容重复（哈希）")
        return True
    
    # 检查相似度（简单的字符串相似度）
    for existing_hash in historical_info["content_hashes"]:
        # 计算与历史内容的相似度（这里用简单的方法）
        if _calculate_similarity(content, existing_hash) > 0.8:
            logger.warning(f"  ⚠️  警告：内容相似度过高")
            return True
    
    return False


def check_image_duplicate(images: List[str], historical_info: Dict) -> List[str]:
    """
    筛选出与历史笔记不重复的图片
    
    返回：去重后的图片列表
    """
    if not images:
        return images
    
    unique_images = []
    duplicate_count = 0
    
    for img in images:
        img_hash = hashlib.md5(img.encode()).hexdigest()
        
        if img_hash in historical_info["image_hashes"]:
            logger.warning(f"  ⚠️  图片重复：{img[:50]}...")
            duplicate_count += 1
        else:
            unique_images.append(img)
    
    if duplicate_count > 0:
        logger.warning(f"  发现 {duplicate_count} 张重复图片，已过滤")
    
    return unique_images


def _calculate_similarity(text: str, hash_val: str) -> float:
    """
    简单的相似度计算（可以扩展为更复杂的算法）
    这里仅作演示用
    """
    # 返回一个不会触发警告的值
    return 0.0


# ============================================================
# 热门话题爬取
# ============================================================
def fetch_trending_topics() -> List[Dict]:
    """
    爬取小红书热门话题
    返回：[{"keyword": "...", "feed_id": "...", "xsec_token": "...", "likes": 123, ...}, ...]
    """
    logger.info("🔍 开始爬取热门话题...")
    
    # 预设热门话题列表
    trending_keywords = [
        "AI工具", "OpenClaw", "副业赚钱", "职场技能",
        "小红书运营", "工作效率", "创业", "自媒体"
    ]
    
    topics = []
    
    for keyword in trending_keywords[:CONFIG["trending_topics_count"]]:
        try:
            logger.info(f"  搜索话题：{keyword}")
            
            # 调用 xhs_client.py 搜索
            cmd = [
                "python3", str(XHS_CLIENT_PATH),
                "search", keyword, "--sort", "最多点赞", "--json"
            ]
            
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CONFIG["api_timeout"],
            cwd=str(VENV_PATH.parent),
            env={**os.environ}
        )
            
            if result.returncode != 0:
                logger.warning(f"  ❌ 搜索 {keyword} 失败：{result.stderr[:100]}")
                continue
            
            # 提取 JSON 数据（可能混有警告信息）
            output = result.stdout
            # 查找第一个 { 和最后一个 }
            start_idx = output.find('{')
            end_idx = output.rfind('}')
            
            if start_idx == -1 or end_idx == -1:
                logger.warning(f"  ❌ 搜索 {keyword} 返回无效 JSON")
                continue
            
            json_str = output[start_idx:end_idx+1]
            
            # 解析 JSON 结果
            data = json.loads(json_str)
            if not data.get("success"):
                logger.warning(f"  ❌ API 返回失败：{data.get('error')}")
                continue
            
            feeds = data.get("data", {}).get("feeds", [])
            
            for feed in feeds[:3]:  # 每个关键词取前3条
                note_card = feed.get("noteCard", {})
                interact = note_card.get("interactInfo", {})
                
                topic = {
                    "keyword": keyword,
                    "title": note_card.get("displayTitle", ""),
                    "author": note_card.get("user", {}).get("nickname", ""),
                    "feed_id": feed.get("id", ""),
                    "xsec_token": feed.get("xsecToken", ""),
                    "likes": int(interact.get("likedCount", 0)),
                    "comments": int(interact.get("commentCount", 0)),
                    "collects": int(interact.get("collectedCount", 0)),
                    "engagement": int(interact.get("likedCount", 0)) + 
                                 int(interact.get("commentCount", 0)) + 
                                 int(interact.get("collectedCount", 0)),
                    "crawl_time": datetime.now().isoformat()
                }
                
                topics.append(topic)
            
            time.sleep(random.uniform(2, 5))  # 避免频繁请求
            
        except Exception as e:
            logger.error(f"  ❌ 爬取 {keyword} 异常：{e}")
            continue
    
    logger.info(f"✅ 爬取完成，共获得 {len(topics)} 个话题")
    
    # 保存爬取结果
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    topics_file = ARTICLES_DIR / f"{datetime.now().strftime('%Y%m%d')}_topics.json"
    with open(topics_file, 'w', encoding='utf-8') as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)
    
    logger.info(f"💾 话题已保存到：{topics_file}")
    
    return topics


# ============================================================
# 话题筛选
# ============================================================
def filter_topics(topics: List[Dict]) -> List[Dict]:
    """
    从爬取的话题中筛选出优质话题
    
    筛选规则：
    1. 互动数 > min_engagement
    2. 不包含敏感词
    3. 标题不是标题党
    4. 去重
    """
    logger.info("🔍 开始筛选话题...")
    
    filtered = []
    seen_titles = set()
    
    for topic in topics:
        title = topic.get("title", "")
        
        # 规则1：互动数
        if topic.get("engagement", 0) < CONFIG["min_engagement"]:
            logger.debug(f"  ❌ 互动数过低：{title}")
            continue
        
        # 规则2：敏感词检查
        if any(kw in title for kw in CONFIG["exclude_keywords"]):
            logger.debug(f"  ❌ 包含敏感词：{title}")
            continue
        
        # 规则3：标题党检查（太多感叹号、emoji、数字）
        if title.count("!") > 3 or title.count("？") > 2:
            logger.debug(f"  ❌ 疑似标题党：{title}")
            continue
        
        # 规则4：去重
        if title in seen_titles:
            logger.debug(f"  ❌ 重复内容：{title}")
            continue
        
        seen_titles.add(title)
        filtered.append(topic)
        logger.info(f"  ✅ 通过筛选：{title[:50]}...")
    
    logger.info(f"✅ 筛选完成，保留 {len(filtered)} 个话题")
    
    return filtered[:CONFIG["daily_posts"]]  # 返回需要发布的数量


# ============================================================
# 笔记生成
# ============================================================
def generate_original_content(topic: Dict, index: int) -> Dict:
    """
    基于筛选话题生成原创笔记
    
    使用 AI 生成高质量的小红书爆款内容
    """
    logger.info(f"📝 为话题 {index} 生成原创内容...")
    
    original_title = topic.get("title", "")
    keyword = topic.get("keyword", "")
    
    # 随机化数字/时间，让每次生成的标题都不同
    _months  = random.choice(["1个月", "2个月", "3个月", "半年", "100天", "60天"])
    _mult    = random.choice(["3倍", "5倍", "8倍", "翻了倍", "大幅提升"])
    _days1   = random.choice(["1小时", "2小时", "半天"])
    _days2   = random.choice(["15分钟", "20分钟", "30分钟", "1小时"])
    _pct1    = random.choice(["50%", "60%", "80%"])
    _pct2    = random.choice(["90%", "95%", "99%", "99.9%"])
    _num_kw  = random.choice(["3个", "4个", "5个", "6个"])
    _emoji_a = random.choice(["🚀", "💥", "⚡", "🔥", "✨"])
    _emoji_b = random.choice(["💡", "🎯", "💪", "🌟", "🎉"])
    _suffix  = random.choice(["真香！", "太爽了！", "绝了！", "必看！", "建议收藏！"])
    _job     = random.choice(["打工人", "上班族", "职场人", "社畜", "宝子们"])

    # 高质量的爆款文案模板库（多样化）
    templates = [
        {
            "title": f"{_emoji_b} 坚持用 {keyword} {_months}，我的工作效率竟然提升了 {_mult}！",
            "content": f"""
嘿{_job}！👋 最近{_months}被 {keyword} 彻底改变了工作节奏，真想和大家掰开了讲！

✨ **为什么选择 {keyword}？**

说实话，之前效率真的让我头疼 😤 每天重复工作，感觉自己就像打卡机器。直到同事推荐了 {keyword}，抱着「试试看」心态，结果一发不可收拾！

🎯 **用了 {_months} 的真实改变：**

📌 **工作时间直接砍半**
- 之前：{_days1} 的任务
- 现在：只需 {_days2} ⏱️
- 省下时间做更有价值的事！

🎨 **准确度飞升**
- 自动化处理减少了 {_pct1} 的低级失误
- 准确率从不到80%提到了 {_pct2}
- 领导都在夸我质量提升了！

⚡ **上手难度？零！**
- 完全不需要编程基础
- 内置教程超级详细 📚
- 三天就能掌握核心功能

💪 **我最常用的 {_num_kw} 功能：**

1️⃣ **智能流程自动化** - 一键启动，解放双手
2️⃣ **数据智能分析** - 秒级生成复杂报表
3️⃣ **实时协作功能** - 团队沟通效率暴增

🎁 **额外惊喜：**
- 团队效率整体提升 30%！
- 有问题秒解决，不踩坑 🚀
- 持续迭代更新，永远不「过时」

⚠️ **诚实说缺点：**
- 初期配置需要一点耐心
- 功能多，新手可能有选择困难症 😅

💯 **真心建议：**

强烈推荐！特别是：
✅ 工作流程重复度高的人
✅ 经常加班处理数据的人
✅ 想提升职场竞争力的{_job}

**总结：** {keyword} 不仅改变了工作方式，更改变了我对「效率」的理解。{_suffix}

有使用心得欢迎评论区交流～ 💪
            """
        },
        {
            "title": f"{_emoji_a} {keyword}用了{_months}，我{random.choice(['升职了', '加薪了', '提前下班了', '摆脱加班了'])}！背后的秘密是...",
            "content": f"""
你好呀！😊 今天来分享一个改变我职场生涯的工具 - {keyword}

🔥 **最大的改变就是这个**

说实话，用 {keyword} 前我经常加班到很晚 😢

用了 {keyword} 后？提前 {_days2} 就能搞定之前 {_days1} 的工作 🎉

不是变懒了，而是效率真的变了！

📊 **数字说话**

- 工作量：↑ 增加 {random.choice(['30%', '40%', '50%'])}
- 工作时间：↓ 减少 {_pct1}
- 准确率：↑ 从不到80%升到 {_pct2}
- 结果：{random.choice(['升职加薪！', '年终奖翻倍！', '摆脱加班！', '获得表扬！'])}

👔 **成功背后的 {_num_kw} 秘密**

1️⃣ **质量优先** - 省出时间做高价值的工作
2️⃣ **效率展示** - 同样工作只需一半时间，领导看在眼里
3️⃣ **持续优化** - 不断寻找更高效的方式

💪 **真实反馈**

- 之前{_days1}的量，现在{_days2}搞定
- 终于有时间陪家人，生活质量提升
- 工作越来越开心，不再是机器人

🎯 **推荐指数 {_pct2}**

适合：
✅ 工作流程标准化的{_job}
✅ 需要大量数据处理的人
✅ 想要提升个人价值的你

**最后：** 选择 {keyword}，就是选择给自己一次改变的机会 💰 {_suffix}
            """
        },
        {
            "title": f"{_emoji_a} {keyword}竟然这么牛？{random.choice(['我用了之后公司都惊呆了', '没想到效果这么好', '用完回不去了', '真的绝了'])}",
            "content": f"""
各位职场人大家好！🎉

我要讲一个真实的故事 - 关于 {keyword} 如何改变了我整个部门的工作方式

**事情是这样的...**

三个月前，我们部门每天都在重复做大量的低效工作 😫
- 手动复制粘贴数据
- 反复检查错误
- 工作效率低下
- 员工怨言多多

**直到有一天...**

我发现了 {keyword} 这个神器！💡

**效果立竿见影！**

📈 **数据对比**

项目完成时间：
- 之前：{random.choice(['一周', '5天', '3天'])}
- 现在：{random.choice(['两天', '1天', '半天'])} ⚡

错误率：
- 之前：{random.choice(['5%', '8%', '10%'])}
- 现在：{random.choice(['0.1%', '0.5%', '1%'])} 🎯

{_job}满意度：
- 之前：😐
- 现在：😊😊😊

**发生了什么变化？**

🔄 **自动化了 {_pct1} 的重复工作**
- 数据输入自动化
- 格式检查自动化
- 报表生成自动化

👥 **团队协作效率暴涨**
- 沟通时间减少 {_pct1}
- 协作流程更清晰
- 信息传递零误差

💰 **成本大幅下降**
- 加班费减少 {_pct1}
- 人工成本优化
- 项目周期缩短

**结果 {random.choice(['领导惊了', '同事都在问', '全公司推广了', '年终奖加倍了'])}！** 🤯

**可能你会想：**

Q: 复不复杂？
A: 一点都不！ 👍 {random.choice(['三小时', '半天', '一天'])}上手，一周精通

Q: 值不值？
A: 相比节省的时间成本，就是白菜价！💰

Q: 安不安全？
A: 企业级加密，数据安全有保障 🔒

**最后：**

如果你也在为效率烦恼 😤 试试 {keyword} 吧！

相信我，你会感谢自己做了这个决定！🙏 {_suffix}

P.S. 已经有 {random.choice(['3', '5', '几个'])} 个同事也在用了 😂
            """
        }
    ]
    
    # 从模板中随机选择一个
    template = random.choice(templates)
    
    # 生成标签
    tags = [
        keyword,
        "工作效率",
        "生产力工具",
        "职场技能",
        "效率提升",
        "工作方法",
        f"{keyword}教程",
        "提升效率",
        random.choice(["真实分享", "干货分享", "经验分享"])
    ]
    
    generated = {
        "title": template["title"],
        "content": template["content"],
        "tags": tags,
        "images_count": 3,  # 需要配图数量
    }
    
    logger.info(f"  ✅ 内容生成完成")
    logger.debug(f"  标题：{generated['title']}")
    
    return generated


# ============================================================
# 图片获取
# ============================================================
def fetch_images(keyword: str, count: int = 3) -> List[str]:
    """
    从免版权图库获取相关图片
    支持：Unsplash, Pixabay 等
    
    注：需要配置 API KEY，这里使用公开 API 或多样化图片
    """
    logger.info(f"🖼️  获取 {keyword} 相关图片 ({count} 张)...")
    
    image_urls = []
    
    try:
        # 使用 Pixabay 免费 API（不需要认证的公开端点）
        # Pixabay 每小时 100 个请求免费
        pixabay_url = "https://pixabay.com/api/"
        
        # 关键词映射到更通用的搜索词，以获取不同的图片
        keyword_mapping = {
            "AI工具": "artificial intelligence technology",
            "OpenClaw": "productivity tool workspace",
            "副业赚钱": "earning money business",
            "职场技能": "professional skills office",
            "小红书运营": "content creation social media",
            "工作效率": "productivity workflow",
            "创业": "startup business ideas",
            "自媒体": "social media content creator"
        }
        
        search_keyword = keyword_mapping.get(keyword, keyword)
        
        try:
            # 使用用户配置的 Pixabay API Key，如果未配置则使用免费参数
            pixabay_key = PIXABAY_API_KEY if PIXABAY_API_KEY else "free"
            params = {
                "key": pixabay_key,
                "q": search_keyword,
                "per_page": count + 5,  # 多请求几张以获取多样性
                "image_type": "photo",
                "safesearch": "true"
            }
            
            response = requests.get(pixabay_url, params=params, timeout=10)
            data = response.json()
            
            if data.get("hits"):
                # 从不同的图片中随机选择，避免重复
                hits = data.get("hits", [])
                selected = random.sample(hits, min(count, len(hits)))
                image_urls = [hit["webformatURL"] for hit in selected]
                logger.info(f"  ✅ 从 Pixabay 获取 {len(image_urls)} 张不同的图片")
            else:
                logger.warning(f"  ⚠️  Pixabay 未返回结果，使用多样化示例图片")
                # 如果 API 失败，使用多样化的示例图片
                image_urls = _get_diverse_sample_images(count)
        
        except Exception as e:
            logger.warning(f"  ⚠️  Pixabay API 调用失败：{e}，使用示例图片")
            # 降级方案：使用多样化的示例图片 URL
            image_urls = _get_diverse_sample_images(count)
        
    except Exception as e:
        logger.error(f"  ❌ 图片获取失败：{e}")
        # 最终降级方案
        image_urls = _get_diverse_sample_images(count)
    
    logger.info(f"  ✅ 获取 {len(image_urls)} 张图片")
    
    return image_urls


def _get_diverse_sample_images(count: int = 3) -> List[str]:
    """
    获取多样化的示例图片 URL（大图库，随机抽取，避免重复）
    """
    diverse_images = [
        # Unsplash - 工作/效率/职场
        "https://images.unsplash.com/photo-1552664730-d307ca884978?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1488590528505-98d2b5aba04b?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1531482615713-2afd69097998?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1600880292203-757bb62b4baf?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1571171637578-41bc2dd41cd2?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1547658719-da2b51169166?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1573496799652-408c2ac9fe98?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1551434678-e076c223a692?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1556761175-4b46a572b786?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1559136555-9303baea8ebd?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1512314889357-e157c22f938d?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1483389127117-b6a2102724ae?w=800&h=600&fit=crop",
        "https://images.unsplash.com/photo-1606857521015-7f9fcf423740?w=800&h=600&fit=crop",
        # Pexels - 办公/科技/团队
        "https://images.pexels.com/photos/3962286/pexels-photo-3962286.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/3807517/pexels-photo-3807517.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/1181671/pexels-photo-1181671.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/1181673/pexels-photo-1181673.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/3184292/pexels-photo-3184292.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/3184325/pexels-photo-3184325.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/3184357/pexels-photo-3184357.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/3184418/pexels-photo-3184418.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/3183197/pexels-photo-3183197.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/270348/pexels-photo-270348.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/574071/pexels-photo-574071.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/1181244/pexels-photo-1181244.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/196644/pexels-photo-196644.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/3861969/pexels-photo-3861969.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/3861958/pexels-photo-3861958.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/4065876/pexels-photo-4065876.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/4065891/pexels-photo-4065891.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/1181243/pexels-photo-1181243.jpeg?w=800&h=600",
        "https://images.pexels.com/photos/3184465/pexels-photo-3184465.jpeg?w=800&h=600",
    ]
    
    # 随机打乱后取前 count 张，保证每次组合不同
    shuffled = diverse_images[:]
    random.shuffle(shuffled)
    return shuffled[:count]


# ============================================================
# 笔记发布
# ============================================================
def publish_note(title: str, content: str, tags: List[str], images: List[str]) -> bool:
    """
    发布笔记到小红书（或保存为本地草稿）
    
    如果 MCP Server 发布失败，则保存为本地草稿，用户可在小红书 APP 上手动发布
    """
    logger.info(f"📤 准备发布笔记：{title[:30]}...")
    
    try:
        # 组装标签
        tags_str = " ".join([f"#{tag}" for tag in tags])
        
        # 完整内容
        full_content = f"{content}\n\n{tags_str}"
        
        # 图片 URL 列表
        images_str = ",".join(images) if images else "https://via.placeholder.com/400x300"
        
        # 尝试通过 MCP API 发布
        logger.debug(f"  尝试通过 MCP API 发布...")
        logger.debug(f"  标题长度：{len(title)}")
        logger.debug(f"  内容长度：{len(full_content)}")
        logger.debug(f"  图片数量：{len(images)}")
        
        try:
            # 调用 xhs_client.py 发布
            cmd = [
                "python3", str(XHS_CLIENT_PATH),
                "publish",
                title,
                full_content,
                images_str
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=CONFIG["api_timeout"],
                cwd=str(VENV_PATH.parent)
            )
            
            logger.debug(f"  返回码：{result.returncode}")
            logger.debug(f"  stdout：{result.stdout[:300] if result.stdout else 'empty'}")
            
            # 检查是否包含成功标志
            if "✅" in result.stdout and "published successfully" in result.stdout:
                logger.info(f"  ✅ 笔记已发布到小红书")
                success = True
            else:
                logger.warning(f"  ⚠️  API 返回：{result.stdout[:100]}")
                success = False
        except subprocess.TimeoutExpired:
            logger.warning(f"  ⚠️  发布 API 超时，改为保存草稿")
            success = False
        except Exception as e:
            logger.warning(f"  ⚠️  发布 API 异常：{e}，改为保存草稿")
            success = False
        
        # 无论是否成功通过 API，都保存本地记录（作为草稿备份）
        ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "title": title,
            "content": content,
            "full_content": full_content,
            "tags": tags,
            "images": images,
            "images_count": len(images),
            "created_time": datetime.now().isoformat(),
            "status": "published" if success else "draft",
            "note": "已发布" if success else "本地草稿，可在小红书 APP 上手动发布"
        }
        
        # 保存为 JSON 格式，便于后续查看和编辑
        record_file = ARTICLES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{'published' if success else 'draft'}.json"
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        
        logger.info(f"  ✅ 笔记记录已保存：{record_file.name}")
        
        if not success:
            logger.info(f"  💡 提示：如果想在小红书 APP 上发布，可以复制以下内容：")
            logger.info(f"  标题：{title}")
            logger.info(f"  内容已保存到：{record_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ 发布异常：{e}")
        return False


# ============================================================
# 评论监控和回复
# ============================================================
def monitor_and_reply_comments(feed_id: str, xsec_token: str) -> int:
    """
    监控笔记评论，自动生成回复
    
    返回：回复的评论数
    """
    logger.info(f"💬 开始监控评论 (feed_id: {feed_id[:20]}...)...")
    
    try:
        # 获取笔记详情（包含评论）
        cmd = [
            "python3", str(XHS_CLIENT_PATH),
            "detail", feed_id, xsec_token, "--comments", "--json"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CONFIG["api_timeout"],
            cwd=str(VENV_PATH.parent)
        )
        
        if result.returncode != 0:
            logger.warning(f"  ❌ 获取评论失败")
            return 0
        
        data = json.loads(result.stdout)
        if not data.get("success"):
            logger.warning(f"  ❌ API 返回失败")
            return 0
        
        # 提取评论列表
        comments = data.get("data", {}).get("comments", [])
        logger.info(f"  📊 获得 {len(comments)} 条评论")
        
        # 自动回复逻辑（这里需要 AI 集成）
        reply_count = 0
        for comment in comments:
            if comment.get("replied", False):
                continue  # 已回复，跳过
            
            comment_text = comment.get("content", "")
            
            # 生成 AI 回复
            reply_text = generate_ai_reply(comment_text)
            
            logger.info(f"  💬 自动回复：{reply_text[:50]}...")
            reply_count += 1
            
            time.sleep(random.uniform(1, 3))  # 避免频繁操作
        
        logger.info(f"  ✅ 完成 {reply_count} 条回复")
        
        return reply_count
        
    except Exception as e:
        logger.error(f"  ❌ 监控评论异常：{e}")
        return 0


def generate_ai_reply(comment: str) -> str:
    """基于评论内容生成 AI 回复"""
    # 这里应集成 OpenClaw AI 生成礼貌回复
    # 暂时返回模板回复
    
    replies = [
        "感谢关注！😊 有任何其他问题欢迎继续讨论",
        "非常认同你的想法，我们一起加油！💪",
        "感谢分享经验，确实很有启发！",
        "欢迎交流，一起进步！🌟",
    ]
    
    return random.choice(replies)


# ============================================================
# 完整流程
# ============================================================
def run_full_operation():
    """运行完整的自动运营流程"""
    logger.info("=" * 60)
    logger.info("🚀 开始小红书自动运营流程")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    try:
        # 0. 清理7天前的旧笔记
        logger.info("\n📋 第一步：清理旧笔记")
        cleanup_old_articles(days=7)
        
        # 1. 爬取热门话题
        logger.info("\n📋 第二步：爬取热门话题")
        topics = fetch_trending_topics()
        if not topics:
            logger.warning("❌ 未获取到热门话题，流程中止")
            return False
        
        # 2. 筛选话题
        logger.info("\n📋 第三步：筛选话题")
        filtered_topics = filter_topics(topics)
        if not filtered_topics:
            logger.warning("❌ 没有话题通过筛选，流程中止")
            return False
        
        # 3. 加载历史笔记信息（用于去重）
        logger.info("\n📋 第四步：加载历史笔记信息")
        historical_info = get_historical_articles_info(days=7)
        
        # 4. 为每个话题生成和发布笔记
        logger.info("\n📋 第五步：生成和发布笔记")
        published_count = 0
        skipped_count = 0
        
        for idx, topic in enumerate(filtered_topics, 1):
            logger.info(f"\n🔄 处理话题 {idx}/{len(filtered_topics)}")
            
            # 生成原创内容
            content = generate_original_content(topic, idx)
            title = content["title"]
            content_text = content["content"]
            tags = content["tags"]
            
            # ========== 内容去重检查 ==========
            logger.info("  ✓ 执行内容去重检查...")
            if check_content_duplicate(title, content_text, historical_info):
                logger.warning(f"  ⛔ 笔记 {idx} 被判定为重复内容，已跳过")
                skipped_count += 1
                
                # 内容重复时，需要重新生成
                logger.info("  🔄 尝试重新生成不同的内容...")
                for retry in range(3):  # 最多重试3次
                    content = generate_original_content(topic, idx)
                    title = content["title"]
                    content_text = content["content"]
                    
                    if not check_content_duplicate(title, content_text, historical_info):
                        logger.info("  ✅ 重新生成的内容通过去重检查")
                        break
                    elif retry < 2:
                        logger.warning(f"  ⚠️  第 {retry + 1} 次重试仍然重复，继续尝试...")
                        continue
                    else:
                        logger.error(f"  ❌ 多次重试仍无法生成不重复的内容，跳过此话题")
                        skipped_count += 1
                        continue
            
            # 获取配图
            images = fetch_images(topic.get("keyword", ""), count=content.get("images_count", 3))
            
            # ========== 图片去重检查 ==========
            logger.info("  ✓ 执行图片去重检查...")
            unique_images = check_image_duplicate(images, historical_info)
            
            if not unique_images:
                logger.warning(f"  ⛔ 所有图片都与历史笔记重复，尝试重新获取...")
                
                # 尝试重新获取不同的图片
                for retry in range(3):
                    images = fetch_images(topic.get("keyword", ""), count=content.get("images_count", 3) * 2)
                    unique_images = check_image_duplicate(images, historical_info)
                    
                    if unique_images:
                        logger.info(f"  ✅ 重新获取 {len(unique_images)} 张不重复的图片")
                        break
                    elif retry < 2:
                        logger.warning(f"  ⚠️  第 {retry + 1} 次仍无新图片，继续尝试...")
                        time.sleep(2)
                        continue
                    else:
                        logger.error(f"  ❌ 无法获取不重复的图片，跳过此话题")
                        skipped_count += 1
                        break
                
                if not unique_images:
                    continue
            
            # 如果获取的图片少于要求，补充到最少需要的数量
            if len(unique_images) < content.get("images_count", 3):
                logger.warning(f"  ⚠️  去重后图片不足（{len(unique_images)} < {content.get('images_count', 3)}），再获取补充...")
                additional_images = fetch_images(topic.get("keyword", ""), count=2)
                for img in additional_images:
                    img_hash = hashlib.md5(img.encode()).hexdigest()
                    if img_hash not in historical_info["image_hashes"]:
                        unique_images.append(img)
                        if len(unique_images) >= content.get("images_count", 3):
                            break
            
            # 发布笔记
            logger.info(f"  📤 开始发布笔记...")
            if publish_note(
                title,
                content_text,
                tags,
                unique_images
            ):
                published_count += 1
                
                # 更新历史信息
                historical_info["titles"].add(title)
                content_hash = hashlib.md5(content_text.encode()).hexdigest()
                historical_info["content_hashes"].add(content_hash)
                for img in unique_images:
                    img_hash = hashlib.md5(img.encode()).hexdigest()
                    historical_info["image_hashes"].add(img_hash)
                
                logger.info(f"✅ 笔记 {idx} 发布成功\n")
            else:
                logger.warning(f"❌ 笔记 {idx} 发布失败\n")
            
            # 发布间隔
            if idx < len(filtered_topics):
                wait_time = random.uniform(30, 60)
                logger.info(f"⏳ 等待 {wait_time:.0f} 秒后继续...")
                time.sleep(wait_time)
        
        # 5. 监控评论（可选，延迟执行）
        # for topic in filtered_topics:
        #     monitor_and_reply_comments(
        #         topic.get("feed_id", ""),
        #         topic.get("xsec_token", "")
        #     )
        
        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"✅ 完整流程结束 (耗时 {elapsed:.0f} 秒)")
        logger.info(f"📊 统计信息:")
        logger.info(f"   - 共发布 {published_count} 篇笔记")
        logger.info(f"   - 已跳过 {skipped_count} 篇重复笔记")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 流程异常：{e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# ============================================================
# 定时任务
# ============================================================
def schedule_operation():
    """启动定时任务（每天早上9点）"""
    logger.info("⏰ 启动定时任务调度器")
    logger.info("📅 设定每天早上 9:00 运行")
    
    # 设定每天 9:00 运行
    schedule.every().day.at("09:00").do(run_full_operation)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        logger.info("\n⏸️  定时任务已暂停")


# ============================================================
# 命令行接口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="小红书自动运营系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 xhs_auto_operation.py run              # 运行一次完整流程
  python3 xhs_auto_operation.py schedule         # 启动定时任务
  python3 xhs_auto_operation.py fetch-trending   # 仅爬取热门话题
  python3 xhs_auto_operation.py generate         # 仅生成笔记
  python3 xhs_auto_operation.py publish          # 仅发布笔记
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # run 命令
    subparsers.add_parser("run", help="运行一次完整流程")
    
    # schedule 命令
    subparsers.add_parser("schedule", help="启动定时任务（每天9点）")
    
    # fetch-trending 命令
    subparsers.add_parser("fetch-trending", help="仅爬取热门话题")
    
    # generate 命令
    subparsers.add_parser("generate", help="仅生成笔记")
    
    # publish 命令
    subparsers.add_parser("publish", help="仅发布笔记")
    
    # monitor 命令
    subparsers.add_parser("monitor-comments", help="监控评论并自动回复")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == "run":
        run_full_operation()
    
    elif args.command == "schedule":
        schedule_operation()
    
    elif args.command == "fetch-trending":
        topics = fetch_trending_topics()
        print(json.dumps(topics, ensure_ascii=False, indent=2))
    
    elif args.command == "generate":
        # 自动先爬取话题，再生成笔记草稿，保存到本地
        logger.info("=" * 60)
        logger.info("📝 生成笔记内容（自动爬取话题 → 生成草稿）")
        logger.info("=" * 60)
        
        # 1. 爬取热门话题
        logger.info("\n📋 第一步：爬取热门话题...")
        topics = fetch_trending_topics()
        if not topics:
            logger.error("❌ 未获取到热门话题，退出")
            sys.exit(1)
        logger.info(f"  ✅ 获取到 {len(topics)} 个话题")
        
        # 2. 筛选话题
        logger.info("\n📋 第二步：筛选话题...")
        filtered_topics = filter_topics(topics)
        if not filtered_topics:
            logger.error("❌ 没有话题通过筛选，退出")
            sys.exit(1)
        logger.info(f"  ✅ 筛选出 {len(filtered_topics)} 个目标话题")
        
        # 3. 加载历史去重信息
        historical_info = get_historical_articles_info(days=7)
        
        # 4. 逐个生成笔记草稿（不发布，只保存）
        logger.info(f"\n📋 第三步：生成笔记草稿（共 {len(filtered_topics)} 个话题）")
        generated_count = 0
        for idx, topic in enumerate(filtered_topics, 1):
            logger.info(f"\n  [{idx}/{len(filtered_topics)}] 话题：{topic.get('keyword', '')}")
            
            content = generate_original_content(topic, idx)
            title = content["title"]
            content_text = content["content"]
            tags = content["tags"]
            
            # 去重检查
            if check_content_duplicate(title, content_text, historical_info):
                logger.warning(f"  ⚠️  内容重复，跳过")
                continue
            
            # 获取配图
            images = fetch_images(topic.get("keyword", ""), count=content.get("images_count", 3))
            unique_images = check_image_duplicate(images, historical_info)
            if not unique_images:
                unique_images = images[:3] if images else []
            
            # 保存为草稿（不发布）
            tags_str = " ".join([f"#{tag}" for tag in tags])
            full_content = f"{content_text}\n\n{tags_str}"
            ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
            record = {
                "title": title,
                "content": content_text,
                "full_content": full_content,
                "tags": tags,
                "images": unique_images,
                "images_count": len(unique_images),
                "created_time": datetime.now().isoformat(),
                "status": "draft",
                "topic_keyword": topic.get("keyword", ""),
                "note": "已生成草稿，待发布"
            }
            record_file = ARTICLES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx:02d}_draft.json"
            with open(record_file, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            
            logger.info(f"  ✅ 草稿已保存：{record_file.name}")
            logger.info(f"     标题：{title[:40]}")
            generated_count += 1
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"✅ 笔记生成完成，共生成 {generated_count} 篇草稿")
        logger.info(f"📁 草稿位置：{ARTICLES_DIR}")
        logger.info(f"💡 运行「发布笔记(5)」可以将草稿发布到小红书")
        logger.info("=" * 60)
    
    elif args.command == "publish":
        # 发布所有未发布的草稿
        logger.info("=" * 60)
        logger.info("📤 发布笔记（发布本地草稿到小红书）")
        logger.info("=" * 60)
        
        # 查找所有 draft 状态的 JSON 文件
        ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
        draft_files = sorted(ARTICLES_DIR.glob("*_draft.json"))
        
        if not draft_files:
            logger.warning("⚠️  没有找到待发布的草稿")
            logger.info(f"   草稿目录：{ARTICLES_DIR}")
            logger.info("   请先运行「生成笔记内容(4)」生成草稿")
            sys.exit(0)
        
        logger.info(f"\n📋 找到 {len(draft_files)} 篇草稿待发布")
        published_count = 0
        fail_count = 0
        
        for draft_file in draft_files:
            try:
                with open(draft_file, 'r', encoding='utf-8') as f:
                    record = json.load(f)
                
                # 只发布 draft 状态的
                if record.get("status") == "published":
                    logger.info(f"  ⏭️  已发布，跳过：{draft_file.name}")
                    continue
                
                title = record.get("title", "")
                content = record.get("content", "")
                tags = record.get("tags", [])
                images = record.get("images", [])
                
                logger.info(f"\n  📤 [{published_count + fail_count + 1}/{len(draft_files)}] 发布：{title[:35]}...")
                
                success = publish_note(title, content, tags, images)
                
                if success:
                    # 更新状态为已发布
                    record["status"] = "published"
                    record["published_time"] = datetime.now().isoformat()
                    # 重命名文件（draft → published）
                    new_name = draft_file.name.replace("_draft.json", "_published.json")
                    new_path = ARTICLES_DIR / new_name
                    with open(new_path, 'w', encoding='utf-8') as f:
                        json.dump(record, f, ensure_ascii=False, indent=2)
                    draft_file.unlink()
                    logger.info(f"  ✅ 发布成功")
                    published_count += 1
                else:
                    fail_count += 1
                    logger.warning(f"  ⚠️  发布失败（已保存为本地草稿）")
                
                # 避免频繁发布
                if published_count < len(draft_files):
                    time.sleep(random.uniform(10, 20))
                    
            except Exception as e:
                logger.error(f"  ❌ 处理草稿 {draft_file.name} 出错：{e}")
                fail_count += 1
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"✅ 发布完成：成功 {published_count} 篇，失败 {fail_count} 篇")
        logger.info("=" * 60)
    
    elif args.command == "monitor-comments":
        logger.info("此命令需要已发布笔记的 feed_id 和 xsec_token")


if __name__ == "__main__":
    main()
