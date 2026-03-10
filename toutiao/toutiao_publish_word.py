#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
今日头条 - Word文档导入发布
使用头条编辑器的Word导入功能上传文章
"""

import sys
import os
import asyncio
import json
from playwright.async_api import async_playwright

COOKIE_FILE = os.path.expanduser("~/.openclaw/toutiao_cookies.json")

def load_cookies():
    """加载Cookie"""
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r") as f:
            return json.load(f)
    return []

async def publish_word_doc(word_path, save_draft_only=False):
    """使用Word导入功能发布文章"""
    
    if not os.path.exists(word_path):
        print(f"❌ Word文件不存在: {word_path}")
        return False
    
    print(f"📄 Word文档: {os.path.basename(word_path)}")
    print(f"⚙️  模式: {'仅保存草稿' if save_draft_only else '直接发布'}")
    
    cookies = load_cookies()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,   # 云端服务器无图形界面，必须使用无头模式
            args=[
                "--window-size=1640,1080",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        context = await browser.new_context()
        
        # 注入Cookie
        if cookies:
            await context.add_cookies(cookies)
        
        page = await context.new_page()
        
        try:
            # 1. 打开发文页
            print("🌐 打开头条号发文页...")
            await page.goto("https://mp.toutiao.com/profile_v4/graphic/publish", timeout=30000)
            await page.wait_for_timeout(3000)
            
            # 检查是否需要登录
            page_url = page.url
            if 'login' in page_url or 'sso' in page_url:
                print("⚠️  需要登录头条号，请在浏览器中完成登录...")
                print(f"   当前URL: {page_url}")
                await page.screenshot(path="/tmp/toutiao_login.png")
                print("   截图已保存到: /tmp/toutiao_login.png")
                await page.wait_for_timeout(30000)  # 等待30秒登录
            
            # 关闭右侧的"头条创作助手"面板（如果存在）
            print("🔍 检查并关闭右侧侧边栏...")
            try:
                # 根据用户截图，右上角有个关闭按钮，坐标大约在 (1325, 36)
                # 先检测侧边栏是否存在
                sidebar_exists = await page.evaluate("""() => {
                    const text = document.body.innerText;
                    return text.includes('头条创作助手') || text.includes('创作热点推荐');
                }""")
                
                if sidebar_exists:
                    print("  检测到侧边栏，正在关闭...")
                    # 点击右上角关闭按钮
                    await page.mouse.click(1325, 36)
                    await page.wait_for_timeout(1500)  # 等待更长时间让页面重新布局
                    print("  ✅ 已关闭侧边栏，页面已重新布局")
                else:
                    print("  未检测到侧边栏（或已关闭）")
            except Exception as e:
                print(f"  侧边栏处理失败（继续）: {str(e)[:50]}")
            
            # 保存页面截图供调试（关闭侧边栏后）
            await page.screenshot(path="/tmp/toutiao_editor.png")
            print(f"📸 页面截图: /tmp/toutiao_editor.png")
            
            # 调试：输出页面所有按钮信息（此时侧边栏已关闭，按钮完全可见）
            print("🔍 分析页面按钮（侧边栏已关闭）...")
            buttons_info = await page.evaluate("""() => {
                // 查找所有可点击元素（包括button、a、div等）
                const allElements = Array.from(document.querySelectorAll('button, [role="button"], a, div[class*="btn"], span[class*="btn"]'));
                // 查找工具栏区域：y在50-180之间（扩大范围），x在500以上（向右查找）
                const toolbarElements = allElements.filter(el => {
                    const rect = el.getBoundingClientRect();
                    const visible = rect.width > 10 && rect.height > 10;  // 确保元素可见
                    return rect.y > 50 && rect.y < 180 && rect.x > 500 && visible;
                });
                // 按x坐标排序（从右到左，最右边的排最前面）
                toolbarElements.sort((a, b) => b.getBoundingClientRect().x - a.getBoundingClientRect().x);
                return toolbarElements.slice(0, 35).map((el, index) => ({  // 增加到35个
                    index: index,
                    tag: el.tagName,
                    text: el.innerText?.substring(0, 30) || '',
                    title: el.title || '',
                    ariaLabel: el.getAttribute('aria-label') || '',
                    class: el.className?.substring(0, 80) || '',
                    html: el.innerHTML?.substring(0, 100) || '',
                    x: el.getBoundingClientRect().x,
                    y: el.getBoundingClientRect().y,
                    width: el.getBoundingClientRect().width
                }));
            }""")
            
            print(f"  发现右上角 {len(buttons_info)} 个按钮")
            for info in buttons_info:
                print(f"  [{info['index']}] {info['tag']} | text:{info['text'][:10]} | title:{info['title'][:15]} | ({info['x']:.0f},{info['y']:.0f})")
                print(f"      html: {info['html'][:60]}...")
            
            # 2. 自动查找并点击Word导入按钮
            print("\n🔍 查找Word导入按钮...")
            
            # 尝试多种方式查找导入按钮
            import_btn_clicked = False
            
            # 方式1: 点击doc-import按钮，等待对话框，然后点击"选择文档"按钮
            try:
                print("方式1: 点击doc-import按钮...")
                # 使用JavaScript点击按钮
                await page.evaluate("""() => {
                    const button = document.querySelector('.syl-toolbar-tool.doc-import button');
                    if (button) button.click();
                }""")
                
                print("  等待'文档导入'对话框出现...")
                await page.wait_for_timeout(1500)
                
                # 检查对话框是否出现
                dialog_visible = await page.evaluate("""() => {
                    const text = document.body.innerText;
                    return text.includes('文档导入') || text.includes('选择文档');
                }""")
                
                if dialog_visible:
                    print("  ✅ 对话框已出现")
                    await page.screenshot(path="/tmp/toutiao_import_dialog.png")
                    print("  📸 对话框截图: /tmp/toutiao_import_dialog.png")
                    
                    # 查找对话框中的 input[type="file"] 元素（显示为"选择文档"按钮）
                    print("  查找文件输入元素...")
                    
                    # 等待一下确保对话框完全加载
                    await page.wait_for_timeout(800)
                    
                    # 查找对话框中的 input[type="file"]
                    file_inputs = await page.query_selector_all('input[type="file"]')
                    print(f"  找到 {len(file_inputs)} 个file input元素")
                    
                    if len(file_inputs) > 0:
                        # 找到最后一个（最新出现的）file input，应该就是对话框中的
                        file_input = file_inputs[-1]
                        print("  ✅ 找到文件输入元素，直接设置文件...")
                        
                        try:
                            await file_input.set_input_files(word_path)
                            print("✅ 文件已选择成功")
                            import_btn_clicked = True
                        except Exception as set_err:
                            print(f"  ❌ 设置文件失败: {str(set_err)[:60]}")
                    else:
                        print("  ❌ 未找到file input元素")
                else:
                    print("  ❌ 对话框未出现")
            except Exception as e:
                print(f"  方式1失败: {str(e)[:80]}")
                pass
            
            # 方式2: 通过role和icon查找
            if not import_btn_clicked:
                try:
                    # 查找所有按钮，寻找包含导入相关icon的
                    buttons = await page.query_selector_all('button, [role="button"]')
                    for btn in buttons:
                        btn_html = await btn.inner_html()
                        btn_title = await btn.get_attribute('title') or ''
                        btn_aria = await btn.get_attribute('aria-label') or ''
                        
                        # 检查是否包含导入相关关键词
                        if any(keyword in (btn_html + btn_title + btn_aria) for keyword in ['导入', 'import', 'word', 'Word', '文档']):
                            print(f"✅ 找到导入按钮（方式2: 属性匹配）- {btn_title or btn_aria}")
                            async with page.expect_file_chooser() as fc_info:
                                await btn.click()
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(word_path)
                            print("✅ 文件已选择")
                            import_btn_clicked = True
                            break
                except Exception as e:
                    print(f"  方式2失败: {e}")
            
            # 方式3: 遍历工具栏按钮，找到能触发文件选择器的那个
            if not import_btn_clicked:
                try:
                    print("  尝试方式3: 遍历工具栏按钮查找文档导入...")
                    
                    # 从buttons_info中获取所有按钮坐标
                    toolbar_buttons = [(info['x'], info['y'], info['index']) for info in buttons_info if info['tag'] == 'BUTTON']
                    
                    # 遍历每个按钮，尝试触发文件选择器
                    for x, y, idx in toolbar_buttons:
                        try:
                            print(f"  测试按钮#{idx} ({x:.0f}, {y:.0f})...")
                            # 尝试触发文件选择器（超时时间短，快速失败）
                            async with page.expect_file_chooser(timeout=800) as fc_info:
                                await page.mouse.click(x + 12, y + 12)
                            
                            # 如果成功触发文件选择器
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(word_path)
                            print(f"🎉 成功！按钮#{idx} 是文档导入按钮")
                            import_btn_clicked = True
                            break
                        except:
                            # 这个按钮没有触发文件选择器，等待一下避免对话框残留
                            await page.wait_for_timeout(300)
                            # 按ESC关闭可能的对话框
                            await page.keyboard.press('Escape')
                            await page.wait_for_timeout(200)
                            continue
                    
                    if import_btn_clicked:
                        pass  # 成功，跳过后续代码
                    else:
                        # 如果遍历完都没找到，尝试点击"更多"按钮查找菜单
                        print("  遍历未找到，尝试点击'更多'按钮...")
                        # 三个点按钮通常在工具栏最右侧，坐标约 (978, 104)
                        await page.mouse.click(978, 104)
                        await page.wait_for_timeout(1000)
                        
                        # 查找菜单中的"导入"选项
                        menu_items = await page.evaluate("""() => {
                            const items = Array.from(document.querySelectorAll('[role="menuitem"], [role="option"], li'));
                            return items.map((item, i) => ({
                                index: i,
                                text: item.innerText?.trim() || '',
                                html: item.innerHTML?.substring(0, 80) || ''
                            }));
                        }""")
                        
                        if len(menu_items) > 0:
                            print(f"  找到菜单，有 {len(menu_items)} 个选项:")
                            for item in menu_items[:8]:
                                print(f"    [{item['index']}] {item['text'][:40]}")
                            
                            # 查找"导入"选项并点击
                            try:
                                import_item = page.locator('text="导入"').or_(page.locator('text="文档导入"')).first
                                if await import_item.is_visible(timeout=2000):
                                    print("  ✅ 找到'导入'菜单项")
                                    await import_item.click()
                                    await page.wait_for_timeout(1000)
                                else:
                                    print("  未找到'导入'菜单项")
                            except:
                                print("  未找到'导入'菜单项")
                        
                        # 如果还是没成功，尝试原来的固定坐标
                        if not import_btn_clicked:
                            print("  尝试点击固定坐标...")
                            await page.mouse.click(825, 102)
                    print("  已点击按钮，等待对话框...")
                    await page.wait_for_timeout(1000)
                    
                    # 检测对话框是否出现
                    dialog_appeared = await page.evaluate("""() => {
                        const dialogs = document.querySelectorAll('[role="dialog"], .modal, [class*="dialog"], [class*="modal"]');
                        return dialogs.length > 0;
                    }""")
                    
                    if dialog_appeared:
                        print("  ✅ 检测到对话框")
                        await page.wait_for_timeout(500)
                        await page.screenshot(path="/tmp/toutiao_dialog.png")
                        print("  📸 对话框截图: /tmp/toutiao_dialog.png")
                        
                        # 在对话框中查找"选择文档"按钮
                        # 根据用户截图，这是一个红色按钮，文字为"选择文档"
                        select_btn_found = False
                        
                        # 获取对话框内所有按钮
                        dialog_buttons = await page.evaluate("""() => {
                            const dialog = document.querySelector('[role="dialog"], .modal, [class*="dialog"]');
                            if (!dialog) return [];
                            const buttons = Array.from(dialog.querySelectorAll('button'));
                            return buttons.map((btn, i) => ({
                                index: i,
                                text: btn.innerText?.trim() || '',
                                class: btn.className || '',
                                html: btn.innerHTML?.substring(0, 80) || ''
                            }));
                        }""")
                        
                        print(f"  对话框中有 {len(dialog_buttons)} 个按钮:")
                        for db in dialog_buttons[:5]:
                            print(f"    [{db['index']}] text: {db['text'][:30]}")
                        
                        # 尝试多种选择器
                        selectors = [
                            'button:has-text("选择文档")',
                            'button:has-text("选择")',
                            '[role="dialog"] button',
                            '.modal button'
                        ]
                        
                        for selector in selectors:
                            try:
                                # 获取所有匹配的按钮
                                buttons = await page.locator(selector).all()
                                for btn in buttons:
                                    btn_text = await btn.inner_text()
                                    if '选择' in btn_text:
                                        print(f"  ✅ 找到按钮: {btn_text[:20]}")
                                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                                            await btn.click()
                                        file_chooser = await fc_info.value
                                        await file_chooser.set_files(word_path)
                                        print("✅ 文件已选择")
                                        import_btn_clicked = True
                                        select_btn_found = True
                                        break
                                if select_btn_found:
                                    break
                            except Exception as e2:
                                continue
                        
                        if not select_btn_found:
                            print("  ❌ 未找到'选择文档'按钮")
                            dialog_text = await page.evaluate("""() => {
                                const dialog = document.querySelector('[role="dialog"], .modal, [class*="dialog"]');
                                return dialog ? dialog.innerText : '';
                            }""")
                            print(f"  对话框内容: {dialog_text[:300]}")
                    else:
                        print("  ❌ 未检测到对话框")
                        await page.screenshot(path="/tmp/toutiao_no_dialog.png")
                        print("  📸 点击后截图: /tmp/toutiao_no_dialog.png")
                        
                except Exception as e:
                    print(f"  方式3失败: {str(e)[:100]}")
            
            if not import_btn_clicked:
                print("❌ 所有方式都未能找到Word导入按钮")
                await page.screenshot(path="/tmp/toutiao_failed.png")
                print("📸 失败截图: /tmp/toutiao_failed.png")
                return False
            
            # 4. 等待上传和解析
            print("⏳ 等待Word文档上传和解析...")
            await page.wait_for_timeout(5000)
            
            # 检查是否有错误提示
            page_text = await page.evaluate("() => document.body.innerText")
            if '上传失败' in page_text or '解析失败' in page_text or '格式不支持' in page_text:
                print("⚠️  Word导入失败，可能格式不支持")
                await page.screenshot(path="/tmp/word_import_error.png")
                return False
            
            # 5. 检查内容是否已导入
            content_check = await page.evaluate("""() => {
                const editor = document.querySelector('.ProseMirror, [contenteditable="true"]');
                if (editor && editor.innerText.trim().length > 10) {
                    return {
                        success: true,
                        length: editor.innerText.trim().length
                    };
                }
                return { success: false };
            }""")
            
            if content_check.get('success'):
                print(f"✅ 内容已导入: {content_check['length']} 字符")
            else:
                print("⚠️  未检测到导入内容")
            
            await page.wait_for_timeout(2000)
            
            # 6. 点击"预览并发布"
            if not save_draft_only:
                # 先关闭可能遮挡的AI assistant drawer
                print("🔍 检查并关闭AI助手面板...")
                try:
                    ai_drawer_closed = await page.evaluate("""() => {
                        const drawer = document.querySelector('.ai-assistant-drawer');
                        if (drawer && drawer.offsetParent) {
                            // 查找关闭按钮
                            const closeBtn = drawer.querySelector('[aria-label*="关闭"], [aria-label*="close"], .close-btn, button[class*="close"]');
                            if (closeBtn) {
                                closeBtn.click();
                                return true;
                            }
                        }
                        return false;
                    }""")
                    if ai_drawer_closed:
                        print("  ✅ 已关闭AI助手面板")
                        await page.wait_for_timeout(800)
                    else:
                        print("  未检测到AI助手面板（或已关闭）")
                except Exception as e:
                    print(f"  AI助手面板处理失败（继续）: {str(e)[:50]}")
                
                print("🚀 查找「预览并发布」按钮...")
                
                # 先查看页面上所有包含"发布"的按钮
                all_publish_buttons = await page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    return btns
                        .filter(btn => btn.innerText && btn.innerText.includes('发布'))
                        .map((btn, i) => ({
                            index: i,
                            text: btn.innerText.trim(),
                            visible: btn.offsetParent !== null,
                            className: btn.className
                        }));
                }""")
                
                print(f"  找到 {len(all_publish_buttons)} 个包含'发布'的按钮:")
                for pb in all_publish_buttons[:5]:
                    print(f"    [{pb['index']}] {pb['text']} (visible: {pb['visible']})")
                
                # 尝试点击"预览并发布"按钮
                print("  尝试点击「预览并发布」按钮...")
                click_result = await page.evaluate("""() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    for (const btn of buttons) {
                        if (btn.innerText.includes('预览并发布') && btn.offsetParent) {
                            btn.click();
                            return { clicked: true, text: btn.innerText.trim() };
                        }
                    }
                    return { clicked: false };
                }""")
                
                if click_result.get('clicked'):
                    print(f"  ✅ 成功点击: {click_result.get('text')}")
                else:
                    print("  ❌ 未找到可点击的「预览并发布」按钮")
                
                await page.wait_for_timeout(2000)
                
                # 等待封面面板
                print("⏳ 等待封面设置...")
                await page.wait_for_timeout(3000)
                
                # 检测文章中是否有图片
                has_images = await page.evaluate("""() => {
                    const editor = document.querySelector('.ProseMirror, [contenteditable="true"]');
                    if (editor) {
                        const images = editor.querySelectorAll('img');
                        return images.length > 0;
                    }
                    return false;
                }""")
                
                print(f"  文章中{'有' if has_images else '没有'}图片")
                
                # 如果文章中没有图片，必须主动点击"无封面"单选框
                # 否则平台会根据图片数量自动选择封面选项
                if not has_images:
                    print("  📌 文章无图片，需要主动选择「无封面」")
                    
                    # 先截图看看封面面板的状态
                    await page.screenshot(path="/tmp/toutiao_cover_panel.png")
                    print("  📸 封面面板截图: /tmp/toutiao_cover_panel.png")
                    
                    # 查找所有可能的"无封面"选项元素
                    cover_options = await page.evaluate("""() => {
                        const allElements = Array.from(document.querySelectorAll('*'));
                        const noCoverElements = [];
                        
                        for (const elem of allElements) {
                            const text = elem.textContent || elem.getAttribute('aria-label') || '';
                            if (text.includes('无封面')) {
                                const rect = elem.getBoundingClientRect();
                                noCoverElements.push({
                                    tag: elem.tagName,
                                    text: text.substring(0, 30),
                                    class: elem.className?.substring(0, 60) || '',
                                    visible: elem.offsetParent !== null,
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height,
                                    type: elem.type || '',
                                    id: elem.id || ''
                                });
                            }
                        }
                        return noCoverElements;
                    }""")
                    
                    print(f"  找到 {len(cover_options)} 个包含'无封面'的元素:")
                    for i, opt in enumerate(cover_options[:5]):
                        print(f"    [{i}] {opt['tag']} | text:{opt['text'][:15]} | visible:{opt['visible']} | pos:({opt['x']:.0f},{opt['y']:.0f}) size:{opt['width']:.0f}x{opt['height']:.0f}")
                        print(f"        class:{opt['class'][:40]} type:{opt['type']}")
                    
                    # 尝试多种方式点击
                    no_cover_clicked = False
                    
                    # 方式1: 参考morning_brief_to_toutiao.py的_switch_to_no_cover实现
                    # 关键：找value='1'的radio或文本为"无封面"的元素，设置checked，点击label，返回坐标用于鼠标点击
                    if not no_cover_clicked:
                        try:
                            print("  尝试方式1: 参考晨报脚本实现...")
                            pos = await page.evaluate("""() => {
                                // 方法1: 找 value='1' 的 radio（头条无封面对应value=1）并设置选中
                                const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                                for (const r of radios) {
                                    const lbl = r.closest('label') || r.parentElement;
                                    const lblText = (lbl ? lbl.textContent : '').trim();
                                    if (!lblText.includes('无封面') && r.value !== '1') continue;
                                    if (!r.offsetParent) continue;
                                    // JS 设置选中
                                    r.checked = true;
                                    r.dispatchEvent(new Event('change', { bubbles: true }));
                                    r.dispatchEvent(new Event('input', { bubbles: true }));
                                    r.click();
                                    if (lbl) lbl.click();
                                    // 返回 label 坐标用于鼠标点击
                                    const target = lbl || r;
                                    const rect = target.getBoundingClientRect();
                                    if (rect.width > 0 && rect.height > 0) {
                                        return { found: true, x: rect.x + rect.width/2, y: rect.y + rect.height/2, method: 'radio-value' };
                                    }
                                    return { found: true, x: 0, y: 0, method: 'radio-js-only' };
                                }
                                // 方法2: 找文字为「无封面」的可见元素
                                const candidates = Array.from(document.querySelectorAll(
                                    '.byte-radio-inner-text, span, label, div'
                                ));
                                for (const el of candidates) {
                                    if (el.textContent.trim() !== '无封面') continue;
                                    if (!el.offsetParent) continue;
                                    const r = el.getBoundingClientRect();
                                    if (r.width > 0 && r.height > 0) {
                                        return { found: true, x: r.x + r.width/2, y: r.y + r.height/2, method: 'text' };
                                    }
                                }
                                return { found: false };
                            }""")
                            
                            if pos.get('found'):
                                method = pos.get('method', '')
                                mx, my = pos.get('x', 0), pos.get('y', 0)
                                print(f"    方式1找到目标: method={method} 坐标=({mx:.0f},{my:.0f})")
                                # 鼠标物理点击（如果坐标有效）
                                if mx > 0 and my > 0:
                                    await page.mouse.click(mx, my)
                                    await page.wait_for_timeout(800)
                                    
                                    # 验证是否选中
                                    is_checked = await page.evaluate("""() => {
                                        const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                                        for (const r of radios) {
                                            if (r.checked) {
                                                const lbl = r.closest('label') || r.parentElement;
                                                const lblText = (lbl ? lbl.textContent : '').trim();
                                                if (lblText.includes('无封面') || r.value === '1') {
                                                    return true;
                                                }
                                            }
                                        }
                                        return false;
                                    }""")
                                    
                                    if is_checked:
                                        print(f"    ✅ 方式1成功: 验证「无封面」已被选中")
                                        no_cover_clicked = True
                                    else:
                                        print(f"    ⚠️  方式1: 点击了但未能验证选中状态")
                                else:
                                    print("    ⚠️  方式1: JS点击but但没有有效坐标")
                            else:
                                print("    方式1未找到匹配元素")
                        except Exception as e:
                            print(f"    方式1失败: {str(e)[:50]}")
                    
                    # 方式2: 使用Playwright直接点击radio元素
                    if not no_cover_clicked:
                        try:
                            print("  尝试方式2: 使用Playwright点击radio...")
                            # 查找"无封面"对应的radio元素
                            # 先找到所有radio，然后找到关联"无封面"文本的那个
                            radios = await page.locator('input[type="radio"]').all()
                            print(f"    找到 {len(radios)} 个radio元素")
                            
                            for i, radio in enumerate(radios):
                                # 获取radio的父元素，检查是否包含"无封面"文本
                                parent_text = await page.evaluate("""(radio) => {
                                    let container = radio.parentElement;
                                    for (let i = 0; i < 5; i++) {
                                        if (!container) break;
                                        const text = container.textContent?.trim() || '';
                                        if (text) return text;
                                        container = container.parentElement;
                                    }
                                    return '';
                                }""", radio)
                                
                                if parent_text == '无封面':
                                    print(f"    找到'无封面'对应的radio (#{i})")
                                    
                                    # 先滚动到可见位置
                                    await radio.scroll_into_view_if_needed()
                                    await page.wait_for_timeout(300)
                                    
                                    # 尝试多种点击方式，直到验证成功
                                    click_methods = [
                                        ('Playwright force click', lambda: radio.click(force=True)),
                                        ('点击label', lambda: page.evaluate("""(r) => {
                                            const label = r.parentElement?.querySelector('label') || 
                                                         document.querySelector(`label[for="${r.id}"]`) ||
                                                         r.parentElement;
                                            if (label) label.click();
                                        }""", radio)),
                                        ('移除遮挡后点击', lambda: page.evaluate("""(r) => {
                                            // 临时移除pointer-events阻挡
                                            const parent = r.parentElement;
                                            if (parent) {
                                                parent.style.pointerEvents = 'auto';
                                                parent.style.zIndex = '9999';
                                            }
                                            r.style.pointerEvents = 'auto';
                                            r.click();
                                        }""", radio)),
                                    ]
                                    
                                    for method_name, click_func in click_methods:
                                        try:
                                            print(f"      尝试: {method_name}")
                                            await click_func()
                                            await page.wait_for_timeout(800)
                                            
                                            # 验证是否真的被选中了
                                            is_checked = await page.evaluate("""(r) => r.checked""", radio)
                                            print(f"      验证结果: checked = {is_checked}")
                                            
                                            if is_checked:
                                                print(f"    ✅ 方式2成功: {method_name} 已选中'无封面'")
                                                no_cover_clicked = True
                                                await page.wait_for_timeout(1000)
                                                break
                                        except Exception as click_err:
                                            print(f"      {method_name} 失败: {str(click_err)[:40]}")
                                            continue
                                    
                                    if no_cover_clicked:
                                        break
                            
                            if not no_cover_clicked:
                                print("    方式2未找到匹配的radio")
                        except Exception as e:
                            print(f"    方式2失败: {str(e)[:50]}")
                    
                    # 方式3: 通过坐标点击最大的"无封面"元素
                    if not no_cover_clicked and len(cover_options) > 0:
                        try:
                            print("  尝试方式3: 通过坐标点击...")
                            # 找到最大的可见元素（通常是可点击区域）
                            visible_options = [opt for opt in cover_options if opt['visible'] and opt['width'] > 10]
                            if visible_options:
                                # 按面积排序，选择最大的
                                visible_options.sort(key=lambda x: x['width'] * x['height'], reverse=True)
                                target = visible_options[0]
                                
                                click_x = target['x'] + target['width'] / 2
                                click_y = target['y'] + target['height'] / 2
                                
                                print(f"    点击坐标: ({click_x:.0f}, {click_y:.0f})")
                                await page.mouse.click(click_x, click_y)
                                await page.wait_for_timeout(1000)
                                
                                # 验证是否选中了"无封面"
                                verify_result = await page.evaluate("""() => {
                                    const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                                    for (const radio of radios) {
                                        if (radio.checked) {
                                            // 查找这个radio关联的文本
                                            let container = radio.parentElement;
                                            for (let i = 0; i < 5; i++) {
                                                if (!container) break;
                                                const text = container.textContent?.trim() || '';
                                                if (text === '无封面') {
                                                    return { success: true, text: '无封面' };
                                                }
                                                container = container.parentElement;
                                            }
                                        }
                                    }
                                    return { success: false };
                                }""")
                                
                                if verify_result.get('success'):
                                    print(f"    ✅ 方式3成功: 验证「{verify_result.get('text')}」已被选中")
                                    no_cover_clicked = True
                                else:
                                    print("    ❌ 方式3: 点击了但未能选中'无封面'")
                        except Exception as e:
                            print(f"    方式3失败: {str(e)[:50]}")
                    
                    # 只有成功选中"无封面"后才继续
                    if no_cover_clicked:
                        print("  ✅ 「无封面」已成功选中")
                        print("  🚀 选中「无封面」后，需要再次点击「预览并发布」按钮...")
                        await page.wait_for_timeout(1000)
                        
                        # 再次点击"预览并发布"按钮
                        publish_again_result = await page.evaluate("""() => {
                            const buttons = Array.from(document.querySelectorAll('button'));
                            for (const btn of buttons) {
                                const text = btn.innerText.trim();
                                if (text.includes('预览并发布') && btn.offsetParent) {
                                    const rect = btn.getBoundingClientRect();
                                    btn.click();
                                    return { clicked: true, text: text, x: rect.x, y: rect.y };
                                }
                            }
                            return { clicked: false };
                        }""")
                        
                        if publish_again_result.get('clicked'):
                            print(f"  ✅ 已再次点击「{publish_again_result.get('text')}」按钮")
                            print(f"     坐标: ({publish_again_result.get('x'):.0f}, {publish_again_result.get('y'):.0f})")
                            print("  ⏳ 等待按钮变成「确认发布」（最多10秒）...")
                            
                            # 等待按钮文本从"预览并发布"变成"确认发布"
                            for wait_i in range(10):
                                await page.wait_for_timeout(1000)
                                btn_check = await page.evaluate("""() => {
                                    const btns = Array.from(document.querySelectorAll('button'));
                                    const confirmBtn = btns.find(b => 
                                        (b.innerText.trim().includes('确认发布') || b.innerText.trim() === '发布') 
                                        && b.offsetParent
                                    );
                                    if (confirmBtn) {
                                        return { found: true, text: confirmBtn.innerText.trim() };
                                    }
                                    return { found: false };
                                }""")
                                
                                if btn_check.get('found'):
                                    print(f"  ✅ 按钮已变成「{btn_check.get('text')}」！(等待{wait_i+1}秒)")
                                    break
                                elif wait_i % 2 == 1:
                                    print(f"  ⏳ [{wait_i+1}/10] 仍在等待按钮变化...")
                        else:
                            print("  ⚠️  未找到「预览并发布」按钮，尝试直接查找「确认发布」")
                    else:
                        print("  ❌ 所有方式都未能选中「无封面」选项，无法继续发布")
                        print("  💡 提示：请手动选择「无封面」后再点击「确认发布」")
                        await page.screenshot(path="/tmp/toutiao_no_cover_failed.png")
                        print("  📸 失败截图: /tmp/toutiao_no_cover_failed.png")
                        # 不继续后续流程，让用户手动操作
                        print("  ⏸️  脚本暂停120秒，等待手动选择...")
                        await page.wait_for_timeout(120000)
                else:
                    print("  📷 文章有图片，使用平台默认封面设置")
                    await page.wait_for_timeout(2000)
                
                # 点击确认发布
                print("📝 查找「确认发布」按钮...")
                
                # 先截图看看当前状态
                await page.screenshot(path="/tmp/toutiao_before_confirm.png")
                print("  📸 截图: /tmp/toutiao_before_confirm.png")
                
                # 查看所有包含"发布"的按钮
                all_buttons_before_confirm = await page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    return btns
                        .filter(btn => btn.innerText && btn.innerText.includes('发布'))
                        .map((btn, i) => ({
                            index: i,
                            text: btn.innerText.trim(),
                            visible: btn.offsetParent !== null
                        }));
                }""")
                
                print(f"  找到 {len(all_buttons_before_confirm)} 个包含'发布'的按钮:")
                for btn_info in all_buttons_before_confirm:
                    print(f"    [{btn_info['index']}] {btn_info['text']} (visible: {btn_info['visible']})")
                
                # 尝试点击"确认发布"按钮
                confirm_result = await page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    for (const btn of btns) {
                        const text = btn.innerText.trim();
                        if ((text.includes('确认发布') || text === '发布') && btn.offsetParent) {
                            btn.click();
                            return { clicked: true, text: text };
                        }
                    }
                    return { clicked: false };
                }""")
                
                if confirm_result.get('clicked'):
                    print(f"✅ 已点击「{confirm_result.get('text')}」按钮")
                    await page.wait_for_timeout(5000)
                    print("✅ 发布成功！")
                else:
                    print("⚠️  未找到「确认发布」按钮，尝试其他方式...")
                    await page.screenshot(path="/tmp/toutiao_no_confirm_btn.png")
                    print("  📸 截图: /tmp/toutiao_no_confirm_btn.png")
                    
                    # 尝试方案1：点击页面空白区域，触发blur让封面设置生效
                    print("  尝试点击页面空白区域...")
                    await page.mouse.click(640, 400)  # 点击页面中间偏上的位置
                    await page.wait_for_timeout(2000)
                    
                    # 再次查找"确认发布"按钮
                    confirm_result2 = await page.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll('button'));
                        for (const btn of btns) {
                            const text = btn.innerText.trim();
                            if ((text.includes('确认发布') || text === '发布') && btn.offsetParent) {
                                btn.click();
                                return { clicked: true, text: text };
                            }
                        }
                        return { clicked: false };
                    }""")
                    
                    if confirm_result2.get('clicked'):
                        print(f"  ✅ 方案1成功！已点击「{confirm_result2.get('text')}」按钮")
                        await page.wait_for_timeout(5000)
                        print("✅ 发布成功！")
                    else:
                        # 方案2：直接再次点击"预览并发布"按钮（可能选择封面后需要点击两次）
                        print("  尝试再次点击「预览并发布」按钮...")
                        publish_again_result = await page.evaluate("""() => {
                            const buttons = Array.from(document.querySelectorAll('button'));
                            for (const btn of buttons) {
                                if (btn.innerText.includes('预览并发布') && btn.offsetParent) {
                                    btn.click();
                                    return { clicked: true };
                                }
                            }
                            return { clicked: false };
                        }""")
                        
                        if publish_again_result.get('clicked'):
                            print("  ✅ 已再次点击「预览并发布」")
                            await page.wait_for_timeout(3000)
                            
                            # 最后一次尝试查找"确认发布"或"发布"按钮
                            # 注意：必须排除"定时发布"、"预览并发布"等按钮
                            final_result = await page.evaluate("""() => {
                                const btns = Array.from(document.querySelectorAll('button'));
                                for (const btn of btns) {
                                    const text = btn.innerText.trim();
                                    // 精确匹配"确认发布"或单独的"发布"，排除"定时发布"、"预览并发布"
                                    if ((text === '确认发布' || text === '发布') && btn.offsetParent) {
                                        btn.click();
                                        return { clicked: true, text: text };
                                    }
                                }
                                return { clicked: false };
                            }""")
                            
                            if final_result.get('clicked'):
                                print(f"  ✅ 方案2成功！已点击「{final_result.get('text')}」按钮")
                                await page.wait_for_timeout(5000)
                                print("✅ 发布成功！")
                            else:
                                # 如果还是找不到，说明可能按钮文本不是"发布"，尝试再次点击任何发布相关按钮
                                print("  尝试最后方案: 查找任何发布相关按钮...")
                                any_publish_btn = await page.evaluate("""() => {
                                    const btns = Array.from(document.querySelectorAll('button'));
                                    for (const btn of btns) {
                                        const text = btn.innerText.trim();
                                        // 包含"发布"但不是"定时发布"的按钮
                                        if (text.includes('发布') && !text.includes('定时') && btn.offsetParent) {
                                            btn.click();
                                            return { clicked: true, text: text };
                                        }
                                    }
                                    return { clicked: false };
                                }""")
                                
                                if any_publish_btn.get('clicked'):
                                    print(f"  ✅ 最后方案成功！点击了「{any_publish_btn.get('text')}」")
                                    await page.wait_for_timeout(5000)
                                    print("✅ 发布成功！")
                                else:
                                    print("  ❌ 所有方案都失败了")
                                    await page.screenshot(path="/tmp/toutiao_final_failed.png")
                                    print("  📸 最终失败截图: /tmp/toutiao_final_failed.png")
                        else:
                            print("  ❌ 未找到「预览并发布」按钮")
            else:
                print("📝 草稿模式：保存为草稿")
                await page.wait_for_timeout(3000)
            
            # 保存Cookie
            new_cookies = await context.cookies()
            with open(COOKIE_FILE, "w") as f:
                json.dump(new_cookies, f, ensure_ascii=False, indent=2)
            print(f"💾 Cookie 已保存")
            
            print("✅ 完成！")
            return True
            
        except Exception as e:
            print(f"❌ 发生错误: {e}")
            await page.screenshot(path="/tmp/word_publish_error.png")
            return False
        finally:
            await page.wait_for_timeout(2000)
            await browser.close()

def main():
    if len(sys.argv) < 2:
        print("用法: python3 toutiao_publish_word.py <word文件路径> [--save-draft]")
        sys.exit(1)
    
    word_path = sys.argv[1]
    save_draft = "--save-draft" in sys.argv
    
    success = asyncio.run(publish_word_doc(word_path, save_draft))
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
