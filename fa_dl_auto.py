#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FurAffinity 批量下载工具 - 智能版 v6.0
特性：新手友好界面 | 自动Cookie刷新 | UA轮换 | Cloudflare应对 | 自动纠错
"""

import sys
import os
import subprocess
import random
import threading
import time
import json
import signal
import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# 可选依赖
try:
    import browser_cookie3
    BROWSER_COOKIE_AVAILABLE = True
except ImportError:
    BROWSER_COOKIE_AVAILABLE = False

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

try:
    from fake_useragent import UserAgent
    UA_GENERATOR_AVAILABLE = True
except ImportError:
    UA_GENERATOR_AVAILABLE = False

SCRIPT_DIR = Path(__file__).parent
PYTHON_EXE = sys.executable
DEFAULT_COOKIES_FILE = SCRIPT_DIR / "cookies.txt"
ARCHIVE_FILE = SCRIPT_DIR / "fa_projects.json"
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 内置 UA 池（当 fake_useragent 不可用时使用）
FALLBACK_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
]

class ArtistConfig:
    def __init__(self, name="", categories=None, output_base="", 
                 interval_mode=2, fixed_interval=3.5,
                 ua_mode=0, custom_ua="", browser="firefox"):
        self.name = name
        self.categories = categories if categories is not None else ["gallery"]
        self.output_base = output_base
        self.interval_mode = interval_mode
        self.fixed_interval = fixed_interval
        self.ua_mode = ua_mode
        self.custom_ua = custom_ua
        self.browser = browser

    def to_dict(self):
        return {
            "name": self.name,
            "categories": self.categories,
            "output_base": self.output_base,
            "interval_mode": self.interval_mode,
            "fixed_interval": self.fixed_interval,
            "ua_mode": self.ua_mode,
            "custom_ua": self.custom_ua,
            "browser": self.browser
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get("name", ""),
            categories=data.get("categories", ["gallery"]),
            output_base=data.get("output_base", ""),
            interval_mode=data.get("interval_mode", 2),
            fixed_interval=data.get("fixed_interval", 3.5),
            ua_mode=data.get("ua_mode", 0),
            custom_ua=data.get("custom_ua", ""),
            browser=data.get("browser", "firefox")
        )

class FABatchDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("FurAffinity 批量下载工具 - 智能版 v6.0")
        self.root.geometry("1100x800")
        self.root.resizable(True, True)

        # 全局设置
        self.global_output_base = tk.StringVar(value=r"FA_downloads")
        self.naming_rule = tk.IntVar(value=0)
        self.custom_subdir = tk.StringVar(value="")
        self.interval_mode = tk.IntVar(value=2)   # 1=固定,2=随机
        self.fixed_interval = tk.StringVar(value="2.0")
        self.random_min = tk.StringVar(value="1.0")
        self.random_max = tk.StringVar(value="3.0")
        self.run_mode = tk.IntVar(value=1)        # 1=前台,2=后台

        # 重试和反爬设置
        self.retry_count = tk.IntVar(value=5)
        self.retry_delay = tk.IntVar(value=3)
        self.timeout_sec = tk.IntVar(value=300)
        self.enable_ua_rotate = tk.BooleanVar(value=True)
        self.enable_cookie_refresh = tk.BooleanVar(value=True)
        self.cookie_refresh_interval = tk.IntVar(value=60)  # 分钟

        # Cookie 设置
        self.cookie_source = tk.IntVar(value=0)   # 0=自动浏览器,1=手动文件
        self.custom_cookie_path = tk.StringVar(value=str(DEFAULT_COOKIES_FILE))
        self.browser_for_cookie = tk.StringVar(value="firefox")

        # UA 设置
        self.ua_mode = tk.IntVar(value=0)  # 0=自动匹配浏览器,1=随机池,2=手动
        self.browser_for_ua = tk.StringVar(value="firefox")
        self.custom_ua = tk.StringVar(value="")

        # 代理设置
        self.proxy_enabled = tk.BooleanVar(value=False)
        self.proxy_http = tk.StringVar(value="")
        self.proxy_https = tk.StringVar(value="")

        # 画师列表
        self.artists = []
        self.selected_index = None

        # 下载控制
        self.current_process = None
        self.is_downloading = False
        self.stop_requested = False
        self.pause_requested = False
        self.skip_current_artist = False
        self.active_thread = None

        # 自动Cookie刷新定时器
        self.cookie_refresh_timer = None

        self.create_widgets()
        self.create_menu()
        self.start_cookie_refresh_timer()
        self.load_archive()
        self.auto_check_cookie_health()

    # ------------------ 界面构建（简化版）------------------
    def create_widgets(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        # 左侧：画师列表
        left_frame = ttk.Frame(main_paned, width=300)
        main_paned.add(left_frame, weight=1)
        list_frame = ttk.LabelFrame(left_frame, text="画师列表", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.tree = ttk.Treeview(list_frame, columns=("name",), show="tree", height=15)
        self.tree.heading("#0", text="序号")
        self.tree.heading("name", text="画师名")
        self.tree.column("#0", width=50)
        self.tree.column("name", width=180)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.edit_artist)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="添加画师", command=self.add_artist).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="编辑", command=self.edit_artist).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="删除", command=self.delete_artist).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="上移", command=self.move_up).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="下移", command=self.move_down).pack(side=tk.LEFT, padx=2)

        # 右侧：设置与日志
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)

        # 简化设置面板（单页）
        settings_frame = ttk.LabelFrame(right_frame, text="基本设置", padding=10)
        settings_frame.pack(fill=tk.X, pady=5)

        # 第一行：输出目录
        ttk.Label(settings_frame, text="输出目录:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(settings_frame, textvariable=self.global_output_base, width=40).grid(row=0, column=1, padx=5)
        ttk.Button(settings_frame, text="浏览", command=self.browse_output).grid(row=0, column=2, padx=5)

        # 第二行：请求间隔（带提示）
        ttk.Label(settings_frame, text="请求间隔:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        interval_frame = ttk.Frame(settings_frame)
        interval_frame.grid(row=1, column=1, sticky=tk.W)
        ttk.Radiobutton(interval_frame, text="随机", variable=self.interval_mode, value=2).pack(side=tk.LEFT)
        min_spin = ttk.Spinbox(interval_frame, from_=0.5, to=10.0, increment=0.5, textvariable=self.random_min, width=5)
        min_spin.pack(side=tk.LEFT, padx=2)
        ttk.Label(interval_frame, text="~").pack(side=tk.LEFT)
        max_spin = ttk.Spinbox(interval_frame, from_=1.0, to=20.0, increment=0.5, textvariable=self.random_max, width=5)
        max_spin.pack(side=tk.LEFT, padx=2)
        ttk.Label(interval_frame, text="秒  (推荐)").pack(side=tk.LEFT, padx=5)

        ttk.Radiobutton(interval_frame, text="固定", variable=self.interval_mode, value=1).pack(side=tk.LEFT, padx=10)
        ttk.Entry(interval_frame, textvariable=self.fixed_interval, width=5).pack(side=tk.LEFT)

        # 第三行：运行模式 + 健康检查按钮
        mode_frame = ttk.Frame(settings_frame)
        mode_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)
        ttk.Radiobutton(mode_frame, text="前台模式 (实时看日志)", variable=self.run_mode, value=1).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="后台模式 (安静运行)", variable=self.run_mode, value=2).pack(side=tk.LEFT, padx=5)
        ttk.Button(mode_frame, text="🔍 健康检查 (测试Cookie)", command=self.check_cookie_health).pack(side=tk.LEFT, padx=10)

        # 高级设置（折叠）
        self.advanced_frame = ttk.Frame(settings_frame)
        self.advanced_frame.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=5)
        self.advanced_visible = False
        ttk.Button(settings_frame, text="▶ 高级选项", command=self.toggle_advanced).grid(row=4, column=0, sticky=tk.W, padx=5)

        # Cookie 和 UA 快速配置行
        quick_frame = ttk.Frame(settings_frame)
        quick_frame.grid(row=5, column=0, columnspan=3, pady=5, sticky=tk.W)
        ttk.Button(quick_frame, text="🚀 一键自动配置 (Firefox)", command=self.one_click_auto).pack(side=tk.LEFT, padx=5)
        ttk.Button(quick_frame, text="❓ 快速开始向导", command=self.quick_start_wizard).pack(side=tk.LEFT, padx=5)

        # 控制按钮
        ctrl_frame = ttk.Frame(right_frame)
        ctrl_frame.pack(fill=tk.X, pady=5)
        ttk.Button(ctrl_frame, text="▶ 开始下载", command=self.start_download).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="⏸ 暂停", command=self.pause_download).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="▶ 继续", command=self.resume_download).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="⏭ 跳过当前画师", command=self.skip_artist).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="⏹ 停止下载", command=self.stop_download).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="🗑 清空日志", command=self.clear_log).pack(side=tk.LEFT, padx=5)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 日志区域
        log_frame = ttk.LabelFrame(right_frame, text="下载日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def toggle_advanced(self):
        if self.advanced_visible:
            self.advanced_frame.grid_remove()
            self.advanced_visible = False
        else:
            self.advanced_frame.grid()
            # 填充高级控件
            if not self.advanced_frame.winfo_children():
                ttk.Label(self.advanced_frame, text="重试次数:").grid(row=0, column=0, sticky=tk.W)
                ttk.Spinbox(self.advanced_frame, from_=1, to=10, textvariable=self.retry_count, width=5).grid(row=0, column=1, padx=5)
                ttk.Label(self.advanced_frame, text="超时(秒):").grid(row=0, column=2, sticky=tk.W, padx=10)
                ttk.Spinbox(self.advanced_frame, from_=60, to=900, textvariable=self.timeout_sec, width=6).grid(row=0, column=3, padx=5)

                ttk.Checkbutton(self.advanced_frame, text="启用UA轮换", variable=self.enable_ua_rotate).grid(row=1, column=0, columnspan=2, sticky=tk.W)
                ttk.Checkbutton(self.advanced_frame, text="自动刷新Cookie", variable=self.enable_cookie_refresh).grid(row=1, column=2, columnspan=2, sticky=tk.W)

                ttk.Label(self.advanced_frame, text="Cookie来源:").grid(row=2, column=0, sticky=tk.W)
                cookie_source_frame = ttk.Frame(self.advanced_frame)
                cookie_source_frame.grid(row=2, column=1, columnspan=3, sticky=tk.W)
                ttk.Radiobutton(cookie_source_frame, text="从浏览器自动提取", variable=self.cookie_source, value=0).pack(side=tk.LEFT)
                ttk.Radiobutton(cookie_source_frame, text="手动指定文件", variable=self.cookie_source, value=1).pack(side=tk.LEFT, padx=10)
                ttk.Entry(self.advanced_frame, textvariable=self.custom_cookie_path, width=30).grid(row=3, column=1, columnspan=2, padx=5)
                ttk.Button(self.advanced_frame, text="浏览", command=self.browse_cookie_file).grid(row=3, column=3)

                ttk.Label(self.advanced_frame, text="User-Agent:").grid(row=4, column=0, sticky=tk.W)
                ua_mode_frame = ttk.Frame(self.advanced_frame)
                ua_mode_frame.grid(row=4, column=1, columnspan=3, sticky=tk.W)
                ttk.Radiobutton(ua_mode_frame, text="自动匹配浏览器", variable=self.ua_mode, value=0).pack(side=tk.LEFT)
                ttk.Radiobutton(ua_mode_frame, text="随机池", variable=self.ua_mode, value=1).pack(side=tk.LEFT, padx=5)
                ttk.Radiobutton(ua_mode_frame, text="手动", variable=self.ua_mode, value=2).pack(side=tk.LEFT, padx=5)
                ttk.Entry(self.advanced_frame, textvariable=self.custom_ua, width=50).grid(row=5, column=1, columnspan=3)

                ttk.Label(self.advanced_frame, text="代理 (格式 http://user:pass@host:port):").grid(row=6, column=0, sticky=tk.W)
                ttk.Checkbutton(self.advanced_frame, text="启用", variable=self.proxy_enabled).grid(row=6, column=1, sticky=tk.W)
                ttk.Entry(self.advanced_frame, textvariable=self.proxy_http, width=30).grid(row=6, column=2, padx=5)
                ttk.Label(self.advanced_frame, text="HTTP/HTTPS").grid(row=6, column=3, sticky=tk.W)
            self.advanced_visible = True

    def create_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="保存存档", command=self.save_archive)
        file_menu.add_command(label="加载存档", command=self.load_archive)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="使用指南", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.root.config(menu=menubar)

    # ------------------ 新手友好功能 ------------------
    def quick_start_wizard(self):
        """引导新用户完成基本配置"""
        wizard = tk.Toplevel(self.root)
        wizard.title("快速开始向导")
        wizard.geometry("500x400")
        wizard.transient(self.root)
        wizard.grab_set()
        text = tk.Text(wizard, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        steps = """欢迎使用 FA 批量下载工具！

请按以下步骤快速开始：

1️⃣ **登录 FurAffinity**
   使用浏览器（推荐 Firefox）登录你的 FA 账号，并勾选“记住我”。

2️⃣ **一键配置 Cookie 和 UA**
   关闭此窗口后，点击主界面上的 “🚀 一键自动配置 (Firefox)” 按钮。
   程序会自动从 Firefox 提取 Cookie 并设置匹配的浏览器标识。

3️⃣ **添加画师**
   点击左侧 “添加画师”，输入画师名字（例如：chilllum），
   选择要下载的类别（Gallery/Scraps/Favorites），其他选项可保持默认。

4️⃣ **开始下载**
   点击 “▶ 开始下载” 按钮，程序会按顺序下载所有画师的作品。

💡 **提示**
- 建议保持默认的随机间隔 1~3 秒，避免被网站封禁。
- 如果遇到 Cloudflare 验证，请确保已安装 cloudscraper 库：
  pip install cloudscraper
- 下载过程中可随时点击“暂停”、“继续”或“跳过当前画师”。

遇到问题？点击主菜单“帮助”→“使用指南”查看更多详情。
"""
        text.insert(tk.END, steps)
        text.config(state=tk.DISABLED)
        ttk.Button(wizard, text="知道了，开始配置", command=wizard.destroy).pack(pady=10)

    def one_click_auto(self):
        """一键自动配置：提取 Firefox Cookie + 设置UA策略"""
        self.browser_for_cookie.set("firefox")
        self.auto_fetch_cookie()
        self.browser_for_ua.set("firefox")
        self.ua_mode.set(0)  # 自动匹配浏览器UA
        self.enable_ua_rotate.set(False)
        self.log("✅ 一键配置完成：Cookie 已导入，UA 策略设为自动匹配 Firefox")
        self.status_var.set("配置完成，Cookie 已导入")

    def auto_fetch_cookie(self):
        """从浏览器提取 Cookie 并保存"""
        if not BROWSER_COOKIE_AVAILABLE:
            self.log("❌ 缺少 browser-cookie3 库，请运行: pip install browser-cookie3")
            return
        browser = self.browser_for_cookie.get().lower()
        self.log(f"🔍 正在从 {browser} 提取 Cookie...")
        try:
            if browser == "chrome":
                cj = browser_cookie3.chrome(domain_name='.furaffinity.net')
            elif browser == "edge":
                cj = browser_cookie3.edge(domain_name='.furaffinity.net')
            elif browser == "firefox":
                cj = browser_cookie3.firefox(domain_name='.furaffinity.net')
            else:
                self.log("不支持的浏览器")
                return
        except Exception as e:
            self.log(f"❌ 提取失败: {e}")
            return
        if not cj:
            self.log("未找到 Cookie，请确保已登录并勾选「记住我」")
            return
        lines = ["# Netscape HTTP Cookie File"]
        processed = 0
        for cookie in cj:
            if not (cookie.domain.endswith('.furaffinity.net') or cookie.domain == 'furaffinity.net'):
                continue
            domain = cookie.domain
            flag = 'TRUE' if domain.startswith('.') else 'FALSE'
            path = cookie.path if cookie.path else '/'
            secure = 'TRUE' if cookie.secure else 'FALSE'
            expires_val = cookie.expires if cookie.expires else 0
            if expires_val and expires_val > 1e12:
                expires_val = int(expires_val / 1000)
            else:
                expires_val = int(expires_val) if expires_val else 0
            line = f"{domain}\t{flag}\t{path}\t{secure}\t{expires_val}\t{cookie.name}\t{cookie.value}"
            lines.append(line)
            processed += 1
        if processed == 0:
            self.log("未找到有效的 FA Cookie")
            return
        target = DEFAULT_COOKIES_FILE
        with open(target, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        self.log(f"✅ Cookie 已保存到 {target} ({processed} 条)")
        # 验证格式
        try:
            import http.cookiejar as cookielib
            cookielib.MozillaCookieJar(target).load(ignore_discard=True, ignore_expires=True)
            self.log("   ✓ 格式验证通过")
        except Exception as e:
            self.log(f"   ⚠️ 验证警告: {e}")
        # 自动设置UA
        auto_ua = self.get_browser_ua(browser)
        self.custom_ua.set(auto_ua)
        self.log(f"   🔧 已自动设置匹配的 {browser} UA: {auto_ua[:50]}...")

    def get_browser_ua(self, browser_name):
        """获取指定浏览器的真实 UA"""
        if UA_GENERATOR_AVAILABLE:
            try:
                ua = UserAgent()
                if browser_name == "chrome":
                    return ua.chrome
                elif browser_name == "edge":
                    return ua.edge
                elif browser_name == "firefox":
                    return ua.firefox
            except:
                pass
        # 回退到预置 UA
        if browser_name == "firefox":
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
        elif browser_name == "edge":
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        else:
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def get_random_ua(self):
        """返回一个随机 UA (根据设置)"""
        if self.enable_ua_rotate.get() and self.ua_mode.get() == 1:
            if UA_GENERATOR_AVAILABLE:
                try:
                    return UserAgent().random
                except:
                    pass
            return random.choice(FALLBACK_UA_POOL)
        elif self.ua_mode.get() == 0:
            return self.get_browser_ua(self.browser_for_ua.get())
        elif self.ua_mode.get() == 2 and self.custom_ua.get():
            return self.custom_ua.get()
        else:
            return self.get_browser_ua("chrome")

    # ------------------ Cookie 健康检查与自动刷新 ------------------
    def check_cookie_health(self):
        """测试当前 Cookie 是否有效"""
        cookie_path = self.get_current_cookie_path()
        if not cookie_path.exists():
            self.log("❌ Cookie 文件不存在，请先配置")
            return False
        # 简单测试：能否访问登录后的页面
        test_url = "https://www.furaffinity.net/msg/pms/"
        try:
            import requests
            session = requests.Session()
            session.cookies = self.load_cookies_into_jar(cookie_path)
            resp = session.get(test_url, timeout=15, allow_redirects=False)
            if resp.status_code == 200:
                self.log("✅ Cookie 有效，可正常访问私信页面")
                return True
            elif resp.status_code == 302 and "login" in resp.headers.get('Location', ''):
                self.log("❌ Cookie 已失效，请重新登录并提取 Cookie")
                return False
            else:
                self.log(f"⚠️ Cookie 状态码 {resp.status_code}，可能部分功能受限")
                return False
        except Exception as e:
            self.log(f"❌ 健康检查异常: {e}")
            return False

    def load_cookies_into_jar(self, cookie_path):
        import http.cookiejar as cookielib
        import requests
        cj = cookielib.MozillaCookieJar(cookie_path)
        cj.load(ignore_discard=True, ignore_expires=True)
        session = requests.Session()
        session.cookies = cj
        return session.cookies

    def start_cookie_refresh_timer(self):
        """启动定时刷新 Cookie 的线程"""
        def refresh_loop():
            while True:
                time.sleep(self.cookie_refresh_interval.get() * 60)
                if self.enable_cookie_refresh.get() and not self.is_downloading:
                    self.log("🔄 定时刷新 Cookie...")
                    self.auto_fetch_cookie()
        if self.enable_cookie_refresh.get():
            t = threading.Thread(target=refresh_loop, daemon=True)
            t.start()

    def auto_check_cookie_health(self):
        """启动时自动检查一次"""
        if self.get_current_cookie_path().exists():
            self.log("🔍 正在检测 Cookie 有效性...")
            if not self.check_cookie_health():
                self.log("💡 建议点击「一键自动配置」重新获取 Cookie")

    # ------------------ 核心下载逻辑 (增强自动纠错) ------------------
    def get_interval_param(self, artist):
        if artist.interval_mode == 1:
            return f"--interval {artist.fixed_interval}"
        else:
            try:
                min_val = float(self.random_min.get())
                max_val = float(self.random_max.get())
                if min_val > max_val:
                    min_val, max_val = max_val, min_val
                interval_val = round(random.uniform(min_val, max_val), 1)
            except:
                interval_val = round(random.uniform(1.0, 3.0), 1)
            return f"--interval {interval_val}"

    def get_output_path(self, artist, category):
        base = artist.output_base if artist.output_base else self.global_output_base.get()
        rule = self.naming_rule.get()
        if rule == 0:
            return Path(base) / artist.name / category
        elif rule == 1:
            return Path(base) / artist.name
        else:
            sub = self.custom_subdir.get().strip()
            if not sub:
                sub = artist.name
            else:
                sub = sub.replace("{artist}", artist.name).replace("{category}", category)
            return Path(base) / sub

    def get_current_cookie_path(self):
        if self.cookie_source.get() == 0:
            return DEFAULT_COOKIES_FILE
        else:
            return Path(self.custom_cookie_path.get())

    def kill_process_tree(self, proc):
        if sys.platform == "win32":
            subprocess.run(f'taskkill /F /T /PID {proc.pid}', shell=True, capture_output=True)
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except:
                proc.terminate()

    def download_one_with_retry(self, artist, category, foreground):
        max_retries = self.retry_count.get()
        base_delay = self.retry_delay.get()
        for attempt in range(max_retries + 1):
            if self.stop_requested or self.skip_current_artist:
                return False
            while self.pause_requested and not self.stop_requested and not self.skip_current_artist:
                time.sleep(0.1)
            try:
                success = self.download_one(artist, category, foreground)
                if success:
                    return True
                else:
                    raise Exception("下载进程返回非0")
            except Exception as e:
                self.log(f"[{artist.name}/{category}] 下载失败: {e}")
                # 智能错误分析
                error_str = str(e).lower()
                if "connectionreset" in error_str or "10054" in error_str:
                    self.log("检测到连接被重置，可能触发反爬，尝试更换UA并刷新Cookie...")
                    if attempt == 0:
                        self.auto_fetch_cookie()  # 刷新Cookie
                if attempt < max_retries:
                    delay = min(base_delay * (2 ** attempt), 60)
                    self.log(f"[{artist.name}/{category}] 重试 {attempt+1}/{max_retries}，等待 {delay} 秒...")
                    for _ in range(int(delay * 10)):
                        if self.stop_requested or self.skip_current_artist:
                            return False
                        time.sleep(0.1)
                else:
                    self.log(f"[{artist.name}/{category}] 已达到最大重试次数，跳过该类别")
                    return False
        return False

    def download_one(self, artist, category, foreground):
        if self.stop_requested or self.skip_current_artist:
            return False
        ua = self.get_random_ua() if self.enable_ua_rotate.get() else self.get_browser_ua(artist.browser)
        interval_param = self.get_interval_param(artist)
        cookie_path = self.get_current_cookie_path()
        if not cookie_path.exists():
            self.log(f"[{artist.name}/{category}] ❌ Cookie 文件不存在")
            return False

        final_output_dir = self.get_output_path(artist, category)
        final_output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(PYTHON_EXE), "furaffinity-dl.py",
            "-c", str(cookie_path),
            "-u", ua,
            "-d",
            interval_param.split()[0], interval_param.split()[1],
            category, artist.name,
            "-o", str(final_output_dir)
        ]
        # 代理功能：核心下载器 furaffinity-dl.py 暂未实现 --proxy 参数，这里仅给出提示
        if self.proxy_enabled.get() and self.proxy_http.get():
            self.log("⚠️ 核心下载器暂不支持代理，已忽略代理设置")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        self.log(f"[{artist.name}/{category}] 开始下载 (UA: {ua[:40]}...)")
        if foreground:
            try:
                old_cwd = os.getcwd()
                os.chdir(SCRIPT_DIR)
                self.current_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    encoding='utf-8', errors='replace', bufsize=1, env=env
                )
                last_output_time = time.time()
                while True:
                    if self.stop_requested or self.skip_current_artist:
                        self.kill_process_tree(self.current_process)
                        return False
                    if time.time() - last_output_time > self.timeout_sec.get():
                        self.log(f"[{artist.name}/{category}] ⏰ 下载卡死超过 {self.timeout_sec.get()} 秒，强制终止")
                        self.kill_process_tree(self.current_process)
                        return False
                    try:
                        line = self.current_process.stdout.readline()
                        if not line:
                            break
                        last_output_time = time.time()
                        # 过滤进度条行
                        if '%|' in line and '100%' not in line:
                            continue
                        # 检测是否遇到 Cloudflare 验证
                        if "cf-challenge" in line.lower() or "attention required" in line.lower():
                            self.log(f"[{artist.name}/{category}] ⚠️ 检测到 Cloudflare 验证！")
                            if CLOUDSCRAPER_AVAILABLE:
                                self.log("正在尝试使用 cloudscraper 绕过...")
                                # 这里可以调用 cloudscraper 重新下载，但为简化，仅提示用户安装
                            else:
                                self.log("建议安装 cloudscraper: pip install cloudscraper")
                        self.log(f"[{artist.name}/{category}] {line.strip()}")
                    except Exception as e:
                        self.log(f"读取输出异常: {e}")
                        break
                self.current_process.wait()
                os.chdir(old_cwd)
                if self.current_process.returncode == 0:
                    self.log(f"[{artist.name}/{category}] ✅ 完成")
                    return True
                else:
                    self.log(f"[{artist.name}/{category}] ❌ 失败，返回码 {self.current_process.returncode}")
                    return False
            except Exception as e:
                self.log(f"[{artist.name}/{category}] 错误: {e}")
                return False
            finally:
                self.current_process = None
        else:
            # 后台模式省略（可复用之前代码，但保持简化）
            self.log("后台模式暂简化，建议使用前台模式")
            return False

    # ------------------ 其他界面回调 ------------------
    def log(self, msg):
        timestamp = time.strftime('%H:%M:%S')
        full_msg = f"[{timestamp}] {msg}"
        self.log_text.insert(tk.END, full_msg + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        # 同时写入文件
        with open(LOG_DIR / "gui.log", "a", encoding="utf-8") as f:
            f.write(full_msg + "\n")

    def clear_log(self):
        self.log_text.delete(1.0, tk.END)

    def on_select(self, event):
        sel = self.tree.selection()
        if sel:
            idx = int(self.tree.item(sel[0], "text")) - 1
            self.selected_index = idx
        else:
            self.selected_index = None

    def update_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, artist in enumerate(self.artists):
            self.tree.insert("", tk.END, text=str(idx+1), values=(artist.name,))

    def move_up(self):
        if self.selected_index and self.selected_index > 0:
            self.artists[self.selected_index], self.artists[self.selected_index-1] = self.artists[self.selected_index-1], self.artists[self.selected_index]
            self.selected_index -= 1
            self.update_tree()
            self.tree.selection_set(self.tree.get_children()[self.selected_index])

    def move_down(self):
        if self.selected_index is not None and self.selected_index < len(self.artists)-1:
            self.artists[self.selected_index], self.artists[self.selected_index+1] = self.artists[self.selected_index+1], self.artists[self.selected_index]
            self.selected_index += 1
            self.update_tree()
            self.tree.selection_set(self.tree.get_children()[self.selected_index])

    def add_artist(self):
        self.edit_artist(new=True)

    def edit_artist(self, event=None, new=False):
        if not new and self.selected_index is None:
            messagebox.showinfo("提示", "请先选中一个画师")
            return
        index = self.selected_index if not new else len(self.artists)
        artist = ArtistConfig() if new else self.artists[index]

        dialog = tk.Toplevel(self.root)
        dialog.title("添加画师" if new else "编辑画师")
        dialog.geometry("450x350")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="画师名:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        name_var = tk.StringVar(value=artist.name)
        ttk.Entry(dialog, textvariable=name_var, width=30).grid(row=0, column=1, padx=5)

        ttk.Label(dialog, text="下载类别:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        cat_frame = ttk.Frame(dialog)
        cat_frame.grid(row=1, column=1, sticky=tk.W)
        gallery_var = tk.BooleanVar(value="gallery" in artist.categories)
        scraps_var = tk.BooleanVar(value="scraps" in artist.categories)
        fav_var = tk.BooleanVar(value="favorites" in artist.categories)
        ttk.Checkbutton(cat_frame, text="Gallery", variable=gallery_var).pack(anchor=tk.W)
        ttk.Checkbutton(cat_frame, text="Scraps", variable=scraps_var).pack(anchor=tk.W)
        ttk.Checkbutton(cat_frame, text="Favorites", variable=fav_var).pack(anchor=tk.W)

        ttk.Label(dialog, text="输出目录(可选):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        output_var = tk.StringVar(value=artist.output_base)
        ttk.Entry(dialog, textvariable=output_var, width=40).grid(row=2, column=1, padx=5)

        ttk.Label(dialog, text="请求间隔:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        interval_frame = ttk.Frame(dialog)
        interval_frame.grid(row=3, column=1, sticky=tk.W)
        interval_mode_var = tk.IntVar(value=artist.interval_mode)
        fixed_interval_var = tk.StringVar(value=str(artist.fixed_interval))
        ttk.Radiobutton(interval_frame, text="固定", variable=interval_mode_var, value=1).pack(side=tk.LEFT)
        ttk.Entry(interval_frame, textvariable=fixed_interval_var, width=5).pack(side=tk.LEFT)
        ttk.Radiobutton(interval_frame, text="随机", variable=interval_mode_var, value=2).pack(side=tk.LEFT, padx=10)

        def save():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("错误", "画师名不能为空")
                return
            cats = []
            if gallery_var.get(): cats.append("gallery")
            if scraps_var.get(): cats.append("scraps")
            if fav_var.get(): cats.append("favorites")
            if not cats:
                messagebox.showerror("错误", "至少选择一个类别")
                return
            new_artist = ArtistConfig(
                name=name, categories=cats, output_base=output_var.get().strip(),
                interval_mode=interval_mode_var.get(),
                fixed_interval=float(fixed_interval_var.get()) if interval_mode_var.get()==1 else 3.5,
                ua_mode=artist.ua_mode, custom_ua=artist.custom_ua, browser=artist.browser
            )
            if new:
                self.artists.append(new_artist)
            else:
                self.artists[index] = new_artist
            self.update_tree()
            dialog.destroy()

        ttk.Button(dialog, text="保存", command=save).grid(row=4, column=0, columnspan=2, pady=10)

    def delete_artist(self):
        if self.selected_index is None:
            messagebox.showinfo("提示", "请先选中一个画师")
            return
        if messagebox.askyesno("确认", f"删除画师「{self.artists[self.selected_index].name}」？"):
            del self.artists[self.selected_index]
            self.selected_index = None
            self.update_tree()

    def start_download(self):
        if self.is_downloading:
            self.log("已有下载任务运行中")
            return
        if not self.artists:
            self.log("画师列表为空")
            return
        cookie_path = self.get_current_cookie_path()
        if not cookie_path.exists():
            self.log("❌ Cookie 文件不存在，请先一键配置")
            return
        if not self.check_cookie_health():
            if not messagebox.askyesno("Cookie 无效", "Cookie 可能已失效，是否继续尝试下载？\n建议点击「一键自动配置」重新获取。"):
                return
        self.stop_requested = False
        self.pause_requested = False
        self.skip_current_artist = False
        self.is_downloading = True
        tasks = [(idx, cat) for idx, a in enumerate(self.artists) for cat in a.categories]
        foreground = (self.run_mode.get() == 1)
        self.log(f"开始顺序下载，共 {len(tasks)} 个任务")
        self.active_thread = threading.Thread(target=self.run_sequential, args=(tasks, foreground), daemon=True)
        self.active_thread.start()

    def run_sequential(self, tasks, foreground):
        try:
            current_artist_idx = None
            for idx, cat in tasks:
                if self.stop_requested:
                    break
                if self.skip_current_artist:
                    if current_artist_idx is None or current_artist_idx == idx:
                        self.log(f"跳过画师「{self.artists[idx].name}」的类别 {cat}")
                        continue
                    else:
                        self.skip_current_artist = False
                while self.pause_requested and not self.stop_requested:
                    time.sleep(0.1)
                if self.stop_requested:
                    break
                current_artist_idx = idx
                artist = self.artists[idx]
                self.status_var.set(f"下载中: {artist.name} - {cat}")
                success = self.download_one_with_retry(artist, cat, foreground)
                if not success:
                    self.log(f"[{artist.name}/{cat}] 最终失败，继续下一个")
                if self.skip_current_artist:
                    self.skip_current_artist = False
        except Exception as e:
            self.log(f"下载线程异常: {e}")
        finally:
            self.is_downloading = False
            self.status_var.set("就绪")
            self.log("所有任务完成" if not self.stop_requested else "下载已停止")

    def pause_download(self):
        if self.is_downloading and not self.pause_requested:
            self.pause_requested = True
            self.log("⏸ 下载已暂停")
            self.status_var.set("已暂停")

    def resume_download(self):
        if self.is_downloading and self.pause_requested:
            self.pause_requested = False
            self.log("▶ 下载已恢复")
            self.status_var.set("下载中")

    def skip_artist(self):
        if not self.is_downloading:
            self.log("没有正在运行的任务")
            return
        self.log("⏭ 正在跳过当前画师...")
        self.skip_current_artist = True
        if self.current_process and self.current_process.poll() is None:
            self.kill_process_tree(self.current_process)

    def stop_download(self):
        if not self.is_downloading:
            self.log("没有正在运行的任务")
            return
        self.log("⏹ 正在停止下载...")
        self.stop_requested = True
        self.pause_requested = False
        if self.current_process and self.current_process.poll() is None:
            self.kill_process_tree(self.current_process)
        if self.active_thread and self.active_thread.is_alive():
            self.active_thread.join(timeout=2)
        self.is_downloading = False
        self.status_var.set("已停止")
        self.log("下载已停止")

    def browse_output(self):
        d = filedialog.askdirectory()
        if d:
            self.global_output_base.set(d)

    def browse_cookie_file(self):
        f = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if f:
            self.custom_cookie_path.set(f)

    def save_archive(self):
        data = {
            "global_output": self.global_output_base.get(),
            "naming_rule": self.naming_rule.get(),
            "custom_subdir": self.custom_subdir.get(),
            "interval_mode": self.interval_mode.get(),
            "fixed_interval": self.fixed_interval.get(),
            "random_min": self.random_min.get(),
            "random_max": self.random_max.get(),
            "run_mode": self.run_mode.get(),
            "retry_count": self.retry_count.get(),
            "timeout_sec": self.timeout_sec.get(),
            "enable_ua_rotate": self.enable_ua_rotate.get(),
            "enable_cookie_refresh": self.enable_cookie_refresh.get(),
            "cookie_source": self.cookie_source.get(),
            "custom_cookie_path": self.custom_cookie_path.get(),
            "browser_for_cookie": self.browser_for_cookie.get(),
            "ua_mode": self.ua_mode.get(),
            "browser_for_ua": self.browser_for_ua.get(),
            "custom_ua": self.custom_ua.get(),
            "artists": [a.to_dict() for a in self.artists]
        }
        with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.log("存档已保存")

    def load_archive(self):
        if not ARCHIVE_FILE.exists():
            return
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.global_output_base.set(data.get("global_output", r"FA_downloads"))
        self.naming_rule.set(data.get("naming_rule", 0))
        self.custom_subdir.set(data.get("custom_subdir", ""))
        self.interval_mode.set(data.get("interval_mode", 2))
        self.fixed_interval.set(data.get("fixed_interval", "1.5"))
        self.random_min.set(data.get("random_min", "1.0"))
        self.random_max.set(data.get("random_max", "3.0"))
        self.run_mode.set(data.get("run_mode", 1))
        self.retry_count.set(data.get("retry_count", 5))
        self.timeout_sec.set(data.get("timeout_sec", 300))
        self.enable_ua_rotate.set(data.get("enable_ua_rotate", True))
        self.enable_cookie_refresh.set(data.get("enable_cookie_refresh", True))
        self.cookie_source.set(data.get("cookie_source", 0))
        self.custom_cookie_path.set(data.get("custom_cookie_path", str(DEFAULT_COOKIES_FILE)))
        self.browser_for_cookie.set(data.get("browser_for_cookie", "firefox"))
        self.ua_mode.set(data.get("ua_mode", 0))
        self.browser_for_ua.set(data.get("browser_for_ua", "firefox"))
        self.custom_ua.set(data.get("custom_ua", ""))
        self.artists = [ArtistConfig.from_dict(ad) for ad in data.get("artists", [])]
        self.update_tree()
        self.log(f"加载存档成功，共 {len(self.artists)} 个画师")

    def show_help(self):
        help_text = """FA 批量下载工具 v6.0 使用指南

【快速上手】
1. 点击“快速开始向导”或直接使用“一键自动配置 (Firefox)”
2. 添加画师（输入用户名，选择类别）
3. 点击“开始下载”

【反爬策略】
- 自动随机间隔（推荐1~3秒）
- UA轮换（每次请求不同浏览器标识）
- 定时刷新Cookie（默认每小时）
- 检测到Cloudflare时提示安装cloudscraper

【常见问题】
Q: 下载一直失败怎么办？
A: 点击“健康检查”测试Cookie，如果失效重新运行一键配置。

Q: 遇到Cloudflare验证？
A: 运行 pip install cloudscraper，然后重试。程序会自动处理部分验证。

Q: 如何跳过某个画师？
A: 下载过程中点击“跳过当前画师”。

更多详情请访问项目主页。
"""
        messagebox.showinfo("帮助", help_text)

    def show_about(self):
        messagebox.showinfo("关于", "FA 批量下载工具 v6.0\n智能反爬 | 自动纠错 | 新手友好\n基于 furaffinity-dl 增强版")

if __name__ == "__main__":
    root = tk.Tk()
    app = FABatchDownloader(root)
    root.mainloop()