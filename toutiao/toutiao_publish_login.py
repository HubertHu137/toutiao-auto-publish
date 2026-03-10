#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
头条号登录工具 - 保存登录态到 Cookie 文件
运行一次即可，之后发布脚本复用 Cookie

支持两种模式：
  - 本地模式（默认）：打开有头浏览器，用户手动扫码
  - 无头模式（云端）：截取二维码图片，通过 openclaw/飞书推送给用户扫码
    python3 toutiao_publish_login.py --headless
"""

import json
import os
import sys
import time
import subprocess
import base64
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

COOKIE_FILE = os.path.expanduser("~/.openclaw/toutiao_cookies.json")
QR_IMG_PATH = "/tmp/toutiao_login_qr.png"

# 通知渠道配置（通过环境变量控制）
FEISHU_CHAT_ID = os.environ.get("FEISHU_CHAT_ID", "")


def send_notification(message: str, image_path: str = None):
    """
    通过 openclaw 推送消息/图片
    支持：OpenClaw Web 回复 + 飞书消息
    """
    # 1. 尝试通过 openclaw 命令推送
    if _command_exists("openclaw"):
        try:
            # 发送文字消息
            subprocess.run(
                ["openclaw", "message", "send", "--message", message],
                check=True, capture_output=True, timeout=10
            )
            # 发送图片（如果有）
            if image_path and os.path.exists(image_path):
                subprocess.run(
                    ["openclaw", "message", "send", "--image", image_path],
                    check=True, capture_output=True, timeout=10
                )
            print(f"  ✅ 已通过 OpenClaw 推送通知")
        except Exception as e:
            print(f"  ⚠️  openclaw 推送失败: {e}")

    # 2. 尝试通过飞书推送
    if FEISHU_CHAT_ID and _command_exists("openclaw"):
        try:
            subprocess.run(
                ["openclaw", "message", "send",
                 "--channel", "feishu",
                 "--target", FEISHU_CHAT_ID,
                 "--message", message],
                check=True, capture_output=True, timeout=10
            )
            if image_path and os.path.exists(image_path):
                subprocess.run(
                    ["openclaw", "message", "send",
                     "--channel", "feishu",
                     "--target", FEISHU_CHAT_ID,
                     "--image", image_path],
                    check=True, capture_output=True, timeout=10
                )
            print(f"  ✅ 已通过飞书推送通知")
        except Exception as e:
            print(f"  ⚠️  飞书推送失败: {e}")


def _command_exists(cmd: str) -> bool:
    """检查命令是否存在"""
    try:
        subprocess.run(["which", cmd], check=True, capture_output=True)
        return True
    except Exception:
        return False


def crop_qr_from_screenshot(page, output_path: str) -> bool:
    """
    从页面截图中裁剪出二维码区域并保存
    返回 True 表示成功找到并裁剪二维码
    """
    try:
        # 先尝试直接定位二维码元素截图
        qr_selectors = [
            "canvas[data-v]",           # 头条常见 canvas 二维码
            ".qrcode-img",
            ".login-qrcode img",
            ".qrcode img",
            "[class*='qrcode'] img",
            "[class*='qr-code'] img",
            "[class*='scan'] canvas",
            "img[src*='qrcode']",
            "img[src*='qr']",
        ]

        for selector in qr_selectors:
            try:
                el = page.query_selector(selector)
                if el:
                    el.screenshot(path=output_path)
                    size = os.path.getsize(output_path)
                    if size > 500:
                        print(f"  ✅ 找到二维码元素（{selector}），截图已保存")
                        return True
            except Exception:
                continue

        # 回退：全页截图（让用户自己找二维码）
        page.screenshot(path=output_path, full_page=False)
        print(f"  ⚠️  未精准定位二维码，已保存全页截图")
        return True

    except Exception as e:
        print(f"  ❌ 截图失败: {e}")
        return False


def wait_for_login_headless(page, timeout_seconds: int = 180) -> bool:
    """
    无头模式下轮询等待登录完成
    每隔5秒检测一次，超时返回 False
    """
    print(f"  ⏳ 等待扫码登录（最长 {timeout_seconds} 秒）...")
    start = time.time()
    notified_qr_refresh = False

    while time.time() - start < timeout_seconds:
        elapsed = int(time.time() - start)

        # 检测是否已登录：URL 不含 login/sso，且含 mp.toutiao.com
        current_url = page.url
        if "mp.toutiao.com" in current_url and \
           "login" not in current_url and \
           "sso" not in current_url:
            print(f"  ✅ 检测到登录成功！（耗时 {elapsed} 秒）")
            return True

        # 检测二维码是否过期（页面出现"刷新"字样）
        try:
            page_text = page.evaluate("() => document.body.innerText")
            if ("二维码已过期" in page_text or "刷新二维码" in page_text) \
               and not notified_qr_refresh:
                print("  ⚠️  二维码已过期，正在刷新并重新推送...")

                # 点击刷新按钮
                refresh_selectors = [
                    "text=刷新二维码",
                    "text=点击刷新",
                    "[class*='refresh']",
                ]
                for sel in refresh_selectors:
                    try:
                        page.click(sel, timeout=2000)
                        break
                    except Exception:
                        continue

                time.sleep(2)

                # 重新截图并推送
                if crop_qr_from_screenshot(page, QR_IMG_PATH):
                    send_notification(
                        "🔄 头条号二维码已刷新，请重新扫码登录：",
                        QR_IMG_PATH
                    )
                notified_qr_refresh = True
        except Exception:
            pass

        # 每5秒检测一次
        time.sleep(5)

    print(f"  ❌ 等待超时（{timeout_seconds} 秒），未检测到登录")
    return False


def save_login_headless():
    """无头模式：适用于云端服务器，截图二维码并推送通知"""
    print("=" * 50)
    print("🔑 头条号登录工具（无头云端模式）")
    print("=" * 50)
    print("流程：启动无头浏览器 → 截取二维码 → 推送到 OpenClaw/飞书 → 等待扫码 → 保存 Cookie")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        )

        page = context.new_page()

        print("📂 正在打开头条号登录页...")
        page.goto("https://mp.toutiao.com/profile_v4/index", timeout=30000)
        page.wait_for_timeout(3000)

        current_url = page.url
        print(f"  当前页面: {current_url}")

        # 已登录（Cookie 有效）
        if "mp.toutiao.com" in current_url and \
           "login" not in current_url and \
           "sso" not in current_url:
            print("✅ 当前 Cookie 仍有效，无需重新登录")
            browser.close()
            return True

        # 需要登录：截取二维码并推送
        print("📸 正在截取登录二维码...")
        page.wait_for_timeout(2000)

        qr_ok = crop_qr_from_screenshot(page, QR_IMG_PATH)

        notify_msg = (
            "🔑 头条号需要重新登录\n\n"
            "📱 请用手机扫描二维码完成登录\n"
            f"⏱  有效期约 3 分钟，过期会自动推送新码"
        )

        if qr_ok:
            send_notification(notify_msg, QR_IMG_PATH)
        else:
            send_notification(notify_msg + "\n\n⚠️  二维码截图失败，请检查服务器日志")

        # 轮询等待登录
        logged_in = wait_for_login_headless(page, timeout_seconds=180)

        if not logged_in:
            send_notification("❌ 头条号登录超时，请重新运行登录脚本")
            browser.close()
            sys.exit(1)

        # 保存 Cookie
        cookies = context.cookies()
        Path(COOKIE_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"✅ Cookie 已保存至：{COOKIE_FILE}")
        print(f"   共保存 {len(cookies)} 条 Cookie")

        # 验证：访问发布页
        try:
            page.goto(
                "https://mp.toutiao.com/profile_v4/graphic/publish-article",
                timeout=15000
            )
            page.wait_for_timeout(2000)
            final_url = page.url
            if "mp.toutiao.com" in final_url and "login" not in final_url:
                msg = "✅ 头条号登录成功！Cookie 已保存，发布脚本可正常使用。"
                print(msg)
                send_notification(msg)
            else:
                msg = f"⚠️  验证异常，当前页面：{final_url}"
                print(msg)
                send_notification(msg)
        except Exception as e:
            print(f"⚠️  验证时出错：{e}")

        browser.close()

    print("\n🎉 登录态已保存，现在可以运行发布脚本了")
    return True


def save_login_local():
    """本地模式：打开有头浏览器，用户手动扫码（原始方式，本机调试用）"""
    print("=" * 50)
    print("🔑 头条号登录工具（本地模式）")
    print("=" * 50)
    print("说明：将打开浏览器，请手动完成头条号登录")
    print("      登录成功后按 Enter 键保存登录状态")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        )

        page = context.new_page()

        print("📂 正在打开头条号创作者中心...")
        page.goto("https://mp.toutiao.com/profile_v4/index", timeout=30000)

        print("\n⏳ 请在浏览器中完成登录（扫码或账号密码）")
        print("   登录成功后，确认已进入创作者中心首页")
        input("   ✅ 登录完成后，按 Enter 键保存登录状态...\n")

        # 保存 Cookie
        cookies = context.cookies()
        Path(COOKIE_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"✅ Cookie 已保存至：{COOKIE_FILE}")
        print(f"   共保存 {len(cookies)} 条 Cookie")

        # 验证登录状态
        try:
            page.goto(
                "https://mp.toutiao.com/profile_v4/graphic/publish-article",
                timeout=15000
            )
            page.wait_for_timeout(2000)
            current_url = page.url
            if "mp.toutiao.com" in current_url and "login" not in current_url:
                print("✅ 验证成功：可以访问发布页面")
            else:
                print(f"⚠️  当前页面：{current_url}，可能需要重新登录")
        except Exception as e:
            print(f"⚠️  验证时出错：{e}")

        browser.close()

    print("\n🎉 登录态已保存，现在可以运行发布脚本了")


if __name__ == "__main__":
    headless_mode = "--headless" in sys.argv

    if headless_mode:
        save_login_headless()
    else:
        # 自动检测：没有显示器时强制使用无头模式
        display = os.environ.get("DISPLAY", "")
        if not display and sys.platform != "darwin":
            print("⚠️  未检测到图形界面（DISPLAY 未设置），自动切换到无头云端模式")
            print("   提示：手动指定模式可使用 --headless 参数")
            print()
            save_login_headless()
        else:
            save_login_local()
