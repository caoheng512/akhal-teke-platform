#!/usr/bin/env python3
"""
页面自检程序
每次修改后运行，确保不引入明显问题
"""

import re
import sys
from pathlib import Path

HTML_FILE = Path(__file__).parent / "index.html"
ASSETS_DIR = Path(__file__).parent.parent.parent / "汗血马"  # ../../汗血马

ISSUES = []
WARNINGS = []


def check_file_exists(path: str, context: str):
    """检查引用的文件是否存在"""
    full = HTML_FILE.parent / path
    if not full.exists():
        ISSUES.append(f"[文件缺失] {context}: {path}")


def check_duplicate_ids(html: str):
    """检查重复的ID"""
    ids = re.findall(r'\bid=["\']([^"\']+)["\']', html)
    seen = set()
    for id in ids:
        if id in seen:
            ISSUES.append(f"[重复ID] id='{id}' 出现了多次")
        seen.add(id)


def check_video_in_card_areas(html: str):
    """检查首页卡片区域的video标签是否有controls属性（不应有）"""
    video_tags = re.finditer(r'<video([^>]*)>', html)
    for m in video_tags:
        attrs = m.group(1)
        pos = m.end()
        if 'horseData' not in html[:pos]:
            if 'controls' in attrs:
                ISSUES.append(f"[视频控制条] 首页video标签不应有controls属性: <video{attrs}>")
            if 'autoplay' in attrs:
                WARNINGS.append(f"[自动播放] 首页video标签有autoplay，可能干扰用户: <video{attrs}>")


def check_hero_video(html: str):
    """检查英雄区是否有问题视频"""
    hero_section = re.search(r'<section class="hero">.*?</section>', html, re.DOTALL)
    if hero_section:
        hero = hero_section.group(0)
        videos = re.findall(r'<video([^>]*)>', hero)
        for v in videos:
            if 'autoplay' in v:
                ISSUES.append(f"[英雄区视频] 英雄区不应有autoplay video: <video{v}>")


def check_modal_close_button(html: str):
    """检查弹窗关闭按钮"""
    if 'modal-overlay' in html:
        if 'modal-close' not in html:
            ISSUES.append("[关闭按钮] 弹窗overlay存在但没有关闭按钮(.modal-close)")
        if 'closeDetail' not in html:
            ISSUES.append("[关闭按钮] 弹窗没有closeDetail函数]")


def check_archive_video(html: str):
    """检查档案区视频"""
    archive_section = re.search(r'<section class="archive".*?</section>', html, re.DOTALL)
    if archive_section:
        videos = re.findall(r'<video([^>]*)>', archive_section.group(0))
        for v in videos:
            if 'autoplay' in v:
                WARNINGS.append(f"[档案区视频] 档案区video有autoplay: <video{v}>")
            if 'controls' not in v:
                WARNINGS.append(f"[档案区视频] 档案区video无controls，用户无法控制: <video{v}>")


def check_css_braces(html: str):
    """简单检查CSS大括号是否配对（不严谨但能抓到明显错误）"""
    style_blocks = re.findall(r'<style>(.*?)</style>', html, re.DOTALL)
    for block in style_blocks:
        opens = block.count('{')
        closes = block.count('}')
        if opens != closes:
            lines_before = html[:html.index(f'<style>{block}</style>')].count('\n')
            ISSUES.append(f"[CSS括号] 第{lines_before}行附近CSS括号不匹配: {{ {opens} vs }} {closes}")
            break


def check_no_orphan_video_without_error(html: str):
    """检查没有error处理的video（可能在文件不存在时崩溃）"""
    script_regions = list(re.finditer(r'<script[^>]*>.*?</script>', html, re.DOTALL))
    html_for_check = html
    for m in script_regions:
        html_for_check = html_for_check.replace(m.group(0), '')

    videos = re.finditer(r'<video([^>]*)src=["\']([^"\']+)["\']', html_for_check)
    for m in videos:
        attrs = m.group(1)
        src = m.group(2)
        if 'onerror' not in attrs and src.endswith('.mp4'):
            WARNINGS.append(f"[视频缺失] video src={src} 没有onerror处理，文件不存在时会显示空白")


def check_referenced_paths(html: str):
    """检查所有引用的路径是否存在（排除JS模板字符串区域）"""
    html_no_js = re.sub(r'\$\{[^}]+\}', '', html)

    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html_no_js)
    for src in imgs:
        check_file_exists(src, f"img src={src}")

    videos = re.findall(r'<video[^>]+src=["\']([^"\']+)["\']', html_no_js)
    for src in videos:
        check_file_exists(src, f"video src={src}")

    bgs = re.findall(r'background-image:\s*url\(["\']?([^"\')\s]+)', html)
    for bg in bgs:
        check_file_exists(bg, f"background-image={bg}")


def check_nav_links_horizontal(html: str):
    """检查导航链接是否横向排列"""
    nav_match = re.search(r'<nav id="navbar">(.*?)</nav>', html, re.DOTALL)
    if nav_match:
        nav = nav_match.group(1)
        if '.nav-links {' in html:
            style = re.search(r'\.nav-links\s*\{([^}]*)\}', html)
            if style:
                css = style.group(1)
                if 'display: flex' not in css and 'display:flex' not in css:
                    ISSUES.append("[导航] .nav-links 没有 display:flex，可能竖排")
                if 'display: none' in css or 'display:none' in css:
                    WARNINGS.append("[导航] .nav-links 包含 display:none，会导致导航消失")


def check_pointer_events_on_clickable(html: str):
    """检查有onclick的元素是否被pointer-events:none阻挡"""
    # 提取所有CSS块
    style_blocks = re.findall(r'<style>(.*?)</style>', html, re.DOTALL)
    all_css = '\n'.join(style_blocks)

    # 找出所有pointer-events: none的CSS选择器
    pointer_none_selectors = set()
    for match in re.finditer(r'([^{]+)\{[^}]*pointer-events\s*:\s*none[^}]*\}', all_css):
        selectors = match.group(1).split(',')
        for sel in selectors:
            pointer_none_selectors.add(sel.strip())

    # 找出所有有onclick的元素
    onclick_elements = re.finditer(r'<(\w+)[^>]*onclick=["\']([^"\']+)["\'][^>]*>', html)

    for match in onclick_elements:
        tag = match.group(1)
        attr_content = match.group(2)
        onclick_name = re.search(r'(\w+)\(', attr_content)
        if onclick_name:
            func_name = onclick_name.group(1)
            elem_start = match.start()
            elem_end = match.end()

            # 检查这个元素的所有祖先元素
            # 简化：检查到前1000个字符范围内有没有pointer-events: none的祖先
            search_range = html[max(0, elem_start-2000):elem_end]
            for selector in pointer_none_selectors:
                selector_clean = selector.strip()
                if selector_clean.startswith('.'):
                    class_name = selector_clean[1:]
                    if f'class="[^"]*{class_name}' in search_range or f"class='[^']*{class_name}" in search_range:
                        WARNINGS.append(f"[交互问题] onclick=\"{func_name}(...)\"的元素可能被 pointer-events:none 阻挡 (选择器: {selector_clean})")
                        break


def check_onclick_elements_cursor(html: str):
    """检查有onclick但没有cursor:pointer的元素"""
    style_blocks = re.findall(r'<style>(.*?)</style>', html, re.DOTALL)
    all_css = '\n'.join(style_blocks)

    # 找出所有cursor: pointer的CSS选择器
    cursor_pointer_selectors = set()
    for match in re.finditer(r'([^{]+)\{[^}]*cursor\s*:\s*pointer[^}]*\}', all_css):
        selectors = match.group(1).split(',')
        for sel in selectors:
            cursor_pointer_selectors.add(sel.strip())

    # 找出所有有onclick但可能没有cursor的元素
    onclick_elements = re.finditer(r'<(\w+)[^>]*onclick=["\']([^"\']+)["\'][^>]*>', html)
    checked_classes = set()

    for match in onclick_elements:
        elem_start = match.start()
        search_range = html[max(0, elem_start-500):match.end()]

        # 提取元素的所有class
        class_match = re.search(r'class=["\']([^"\']+)["\']', search_range)
        if class_match:
            classes = class_match.group(1).split()
            for cls in classes:
                cls_selector = '.' + cls
                if cls_selector not in cursor_pointer_selectors and cls not in checked_classes:
                    checked_classes.add(cls)
                    # 检查这个class的CSS定义里有没有cursor
                    cls_css_match = re.search(rf'\.{cls}\s*\{{([^}}]*)\}}', all_css)
                    if cls_css_match and 'cursor' not in cls_css_match.group(1):
                        # 检查是不是可点击的标签
                        if match.group(1) not in ['link', 'a', 'button']:
                            WARNINGS.append(f"[交互问题] {match.group(1)}.{cls} 有onclick但CSS没有设置cursor:pointer")


def check_video_playback_function(html: str):
    """检查视频播放函数是否正确实现"""
    # 查找toggleVideo函数
    if 'toggleVideo' in html and 'function toggleVideo' not in html:
        ISSUES.append("[函数缺失] toggleVideo函数被引用但未定义")

    # 检查播放按钮overlay是否有正确的onclick
    play_btn_match = re.search(r'<div[^>]+class="play-btn-overlay"[^>]*>', html)
    if play_btn_match:
        if 'onclick' not in play_btn_match.group(0):
            ISSUES.append("[播放按钮] .play-btn-overlay 缺少 onclick 属性")


def run():
    if not HTML_FILE.exists():
        print(f"错误：找不到 {HTML_FILE}")
        sys.exit(1)

    html = HTML_FILE.read_text(encoding='utf-8')

    print("=" * 50)
    print("页面自检开始")
    print("=" * 50)

    check_duplicate_ids(html)
    check_video_in_card_areas(html)
    check_hero_video(html)
    check_modal_close_button(html)
    check_archive_video(html)
    check_css_braces(html)
    check_no_orphan_video_without_error(html)
    check_referenced_paths(html)
    check_nav_links_horizontal(html)
    check_pointer_events_on_clickable(html)
    check_onclick_elements_cursor(html)
    check_video_playback_function(html)

    print()
    if ISSUES:
        print(f"❌ 发现 {len(ISSUES)} 个问题：")
        for issue in ISSUES:
            print(f"  {issue}")
    else:
        print("✅ 无问题")

    if WARNINGS:
        print(f"\n⚠️  发现 {len(WARNINGS)} 个警告：")
        for w in WARNINGS:
            print(f"  {w}")

    print()
    print(f"检查文件：{HTML_FILE}")
    print(f"检查完成")

    return len(ISSUES) == 0


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
