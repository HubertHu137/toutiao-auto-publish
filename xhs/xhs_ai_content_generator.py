#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书 AI 内容生成模块
集成 OpenClaw 进行原创笔记生成和评论回复

功能：
1. 基于热门话题生成原创标题和正文
2. 自动生成相关标签
3. 为评论生成礼貌的 AI 回复
4. 避免内容重复和直接抄袭

使用：
    from xhs_ai_content_generator import AIContentGenerator
    
    generator = AIContentGenerator()
    content = generator.generate_article("OpenClaw", "学习OpenClaw的最佳方法")
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
import logging

# ============================================================
# 配置
# ============================================================
logger = logging.getLogger("XHS_AI_Generator")

OPENCLAW_CONFIG = {
    "model": "gpt-4",  # 或其他模型
    "temperature": 0.7,  # 创意度
    "max_tokens": 2000,
    "timeout": 30,
}


# ============================================================
# AI 内容生成器
# ============================================================
class AIContentGenerator:
    """基于 OpenClaw 的 AI 内容生成器"""
    
    def __init__(self):
        """初始化生成器"""
        self.cache_dir = Path.home() / ".openclaw/xhs_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("✅ AI 内容生成器初始化完成")
    
    def generate_article(
        self,
        keyword: str,
        reference_title: str,
        reference_content: Optional[str] = None,
        style: str = "专业"
    ) -> Dict[str, str]:
        """
        生成原创笔记
        
        参数：
            keyword: 主题关键词（如 "OpenClaw"）
            reference_title: 参考标题（用于理解方向，但不直接抄袭）
            reference_content: 参考内容摘要（可选）
            style: 写作风格（"专业", "轻松", "干货", "故事"）
        
        返回：
            {
                "title": "生成的标题",
                "content": "生成的正文",
                "tags": ["标签1", "标签2", ...],
                "summary": "简述"
            }
        """
        logger.info(f"📝 生成 {keyword} 的原创笔记 (风格: {style})...")
        
        # 构建 AI 提示词
        prompt = self._build_article_prompt(keyword, reference_title, reference_content, style)
        
        # 调用 AI 生成（这里使用模板，实际需要集成 OpenClaw）
        result = self._call_ai(prompt)
        
        logger.info(f"✅ 笔记生成完成")
        
        return result
    
    def generate_comment_reply(
        self,
        comment: str,
        article_title: str,
        tone: str = "友好"
    ) -> str:
        """
        为评论生成 AI 回复
        
        参数：
            comment: 评论内容
            article_title: 笔记标题（用于上下文）
            tone: 语气（"友好", "正式", "感谢", "解释"）
        
        返回：
            生成的回复文本
        """
        logger.info(f"💬 为评论生成回复 (语气: {tone})...")
        
        prompt = self._build_reply_prompt(comment, article_title, tone)
        reply = self._call_ai(prompt)
        
        logger.info(f"✅ 回复生成完成")
        
        return reply.get("reply", "感谢评论！")
    
    # ============================================================
    # 提示词构建
    # ============================================================
    
    def _build_article_prompt(
        self,
        keyword: str,
        reference_title: str,
        reference_content: Optional[str] = None,
        style: str = "专业"
    ) -> str:
        """构建文章生成的 AI 提示词 - 优化版（符合小红书爆款风格）"""
        
        style_guide = {
            "专业": "使用专业术语，逻辑清晰，适合行业人士。大量使用数字和对比",
            "轻松": "语气轻松有趣，使用比喻和例子，贴近生活。多用emoji和感叹号",
            "干货": "直截了当，提供可操作的建议和技巧。分点详细，易于操作",
            "故事": "通过故事叙述，融入个人经历和感悟。制造情感共鸣",
            "爆款": "模仿小红书顶流风格，大量emoji，数字对比，制造FOMO效应"
        }
        
        prompt = f"""
【任务】为小红书生成**爆款级别**的原创笔记

【主题关键词】{keyword}

【参考方向】
原笔记标题：{reference_title}
{f'原笔记内容摘要：{reference_content[:200]}...' if reference_content else ''}

【写作风格】{style}（爆款级别）
{style_guide.get(style, style_guide['爆款'])}

【小红书爆款必读要素】
✅ 包含数字对比（如"从2小时降到20分钟"）
✅ 大量emoji表情（每句话1-2个）
✅ 制造代入感和情感共鸣
✅ 多用"我"的角度讲述真实体验
✅ 包含具体的"干货"内容
✅ 制造FOMO（怕错过）的心理
✅ 多用感叹号和问号增加互动
✅ 避免生硬的格式列表，用自然语言表达

【要求】
1. **生成吸引眼球的标题**
   - 必须包含 emoji（1-3个）
   - 必须包含数字（如"3个月"、"5倍"、"99%"）
   - 长度 18-40 字
   - 使用"竟然"、"真的"、"没想到"等情感词
   - 例子：💡 坚持3个月，我的效率竟然翻了5倍！

2. **生成800-1200字的原创、完整正文**
   - 开头：用吸引力的陈述引入（制造代入感）❤️
   - 中间：具体的数字对比和真实体验 📊
   - 干货段：3-5个具体的技巧/功能，每个都要有详细解释 💪
   - 优缺点：既要讲优点，也要诚实说缺点（增加可信度） ⚠️
   - 建议：根据不同人群给出具体建议 ✅
   - 结尾：制造FOMO效应和行动号召 🎉
   
   - **必须要求**：
     * 每个段落都要有 emoji
     * 使用具体数字（不要说"很快"，要说"20分钟"）
     * 使用对比（之前 vs 现在）
     * 融入个人情感和真实经历
     * 包含行动建议（具体可做什么）

3. **生成 8-12 个相关标签**（多而精）
   - 必须包含热点词、品牌词、应用场景
   - 例如：["OpenClaw", "工作效率", "效率提升", "生产力工具", ...]
   - 不要 # 符号

4. **返回格式必须是有效的 JSON**：
{{
    "title": "💡 吸引眼球的标题（必含emoji和数字）",
    "content": "生成的正文（800-1200字，完整段落，大量emoji）",
    "tags": ["标签1", "标签2", ...],
    "summary": "一句话总结"
}}

【小红书爆款示例】
{{
    "title": "💡 坚持用 OpenClaw 3个月，我的工作效率竟然翻了 5 倍！",
    "content": "嘿各位！👋 我是一名工程师，最近三个月被 OpenClaw 这个工具「迷住」了...
    
✨ **为什么我会选择 OpenClaw？**
说实话，之前的工作效率真的让我头疼 😤 每天都在处理重复的工作...

📌 **工作时间直接砍半**
- 之前：2小时的任务
- 现在：只需20分钟 ⏱️
- 节省时间用来做更有价值的事情！

[更多详细内容...]
    ",
    "tags": ["OpenClaw", "工作效率", "生产力工具", "职场技能", ...],
    "summary": "分享 OpenClaw 如何让工作效率翻倍"
}}

【严格禁止】
- 直接复制原笔记内容
- 只改几个词的伪原创
- 生硬的列表格式（用自然段落替代）
- 内容不完整或"技巧1""技巧2"这样的占位符
- 长篇幅没有emoji的段落
- 缺少具体数字和对比
- 包含敏感词汇

【重要提示】
生成的内容必须：
✓ 完整（没有任何占位符或未完成的地方）
✓ 具体（包含数字、对比、真实案例）
✓ 有趣（emoji、对话体、情感表达）
✓ 可信（既说优点也说缺点）
✓ 可行（包含具体建议）
        """
        
        return prompt.strip()
    
    def _build_reply_prompt(
        self,
        comment: str,
        article_title: str,
        tone: str = "友好"
    ) -> str:
        """构建评论回复的 AI 提示词"""
        
        tone_guide = {
            "友好": "温暖亲切，表达感谢，可以用表情符号",
            "正式": "专业有礼，逻辑清晰",
            "感谢": "突出感谢，表达认可和赞赏",
            "解释": "耐心解释，提供有用的补充信息",
        }
        
        prompt = f"""
【任务】为小红书笔记的评论生成回复

【笔记标题】{article_title}

【评论内容】
{comment}

【回复语气】{tone}
{tone_guide.get(tone, '')}

【要求】
1. 回复要有礼貌、真诚
2. 长度 20-100 字
3. 可以使用 emoji，但不要过度
4. 针对评论内容给出回应
5. 如果是提问，尽量回答；如果是赞扬，表达感谢

【返回格式】
{{
    "reply": "生成的回复文本"
}}

【示例】
评论："太有用了，想问怎么快速上手？"
回复：
{{
    "reply": "感谢关注！😊 建议先从基础功能开始，一周内就能上手。我后续会分享详细教程，敬请期待！"
}}
        """
        
        return prompt.strip()
    
    # ============================================================
    # AI 调用
    # ============================================================
    
    def _call_ai(self, prompt: str) -> Dict:
        """
        调用 AI 生成内容
        
        注：这里需要集成实际的 AI 服务（OpenClaw、OpenAI 等）
        当前使用高质量模板示例，符合小红书风格
        """
        logger.debug(f"  调用 AI 生成内容 (提示词长度: {len(prompt)})")
        
        # TODO: 集成实际的 AI 服务
        # 选项1：OpenClaw HTTP API
        # 选项2：OpenAI API
        # 选项3：本地 LLM
        
        # 高质量响应 - 符合小红书爆款风格
        example_response = {
            "title": "💡 坚持用 OpenClaw 3个月，我的工作效率竟然翻了 5 倍！",
            "content": """
嘿各位！👋 我是一名工程师，最近三个月被 OpenClaw 这个工具「迷住」了，真的想和大家分享一下我的真实体验！

✨ **为什么我会选择 OpenClaw？**

说实话，之前的工作效率真的让我头疼 😤 每天都在处理重复的工作，感觉自己就像一台打卡机器。直到有天同事推荐了 OpenClaw，我抱着「试试看」的心态用了一下，结果一发不可收拾！

🎯 **使用 3 个月后的真实改变：**

📌 **工作时间直接砍半**
- 之前：2小时的任务
- 现在：只需20分钟 ⏱️
- 节省时间用来做更有价值的事情！

🎨 **准确度提升 99%**
- 再也不用担心人工操作出错
- 自动化处理减少了95%的低级失误
- 领导都在夸我工作质量提升了！

⚡ **上手难度？零！**
- 完全不用学习编程
- 内置教程超级详细 📚
- 三天就能掌握核心功能

💪 **我最常用的三个功能：**

1️⃣ **智能任务分配** - 一键分发任务，自动跟进进度，解放双手
2️⃣ **数据自动化处理** - 再也不用手动复制粘贴，一键生成报表
3️⃣ **流程优化建议** - 系统自动分析你的工作流程，给出优化方案

🎁 **额外惊喜：**
- 企业版还有团队协作功能，团队效率整体提升 30%！
- 客服响应速度快到不行，有问题秒解决 🚀
- 定期更新新功能，从不让你「过时」

⚠️ **诚实的缺点（我也要说）**
- 初期配置可能需要一点时间
- 功能太多了，有时候会有选择困难症 😅

💯 **我的真心建议：**

如果你也在做类似的工作，真的真的强烈推荐试试！特别是：
✅ 工作流程重复度高的人
✅ 经常加班处理数据的人  
✅ 想要提升工作效率的职场人士
✅ 团队协作需要优化的管理者

**总结：** OpenClaw 不仅改变了我的工作方式，还改变了我对「工作效率」的理解。从之前的「疲于奔命」到现在的「游刃有余」，这才是真正的生产力革命！🎉

如果你也有使用心得，欢迎在评论区分享～ 让我们一起打卡效率生活！💪

P.S. 这不是广告，这是我的真实体验，希望能帮助到同样在为效率烦恼的你们～ 🙏
            """,
            "tags": ["OpenClaw", "工作效率", "生产力工具", "职场技能", "提升效率", "工作方法", "效率提升"],
            "summary": "分享 OpenClaw 对工作效率的真实改善，从2小时降到20分钟，效率提升5倍！"
        }
        
        return example_response
    
    # ============================================================
    # 缓存管理
    # ============================================================
    
    def save_to_cache(self, key: str, content: Dict):
        """保存生成的内容到缓存"""
        cache_file = self.cache_dir / f"{key}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        logger.debug(f"  缓存已保存: {cache_file}")
    
    def load_from_cache(self, key: str) -> Optional[Dict]:
        """从缓存加载内容"""
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None


# ============================================================
# 示例使用
# ============================================================
def example():
    """示例使用"""
    generator = AIContentGenerator()
    
    # 生成文章
    article = generator.generate_article(
        keyword="OpenClaw",
        reference_title="火爆全网的 OpenClaw，如何使用？【保姆级】",
        style="干货"
    )
    
    print("\n生成的文章：")
    print(json.dumps(article, ensure_ascii=False, indent=2))
    
    # 生成评论回复
    comment = "太有用了！想问怎么快速上手？"
    reply = generator.generate_comment_reply(
        comment=comment,
        article_title=article["title"],
        tone="感谢"
    )
    
    print("\n生成的回复：")
    print(reply)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    example()
