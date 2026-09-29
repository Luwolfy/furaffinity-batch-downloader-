# FurAffinity 批量下载工具（fa-downloader）

> **FurAffinity batch downloader** — a GUI tool to batch-download galleries, scraps and favorites, with resume, auto cookie extraction, UA rotation and Cloudflare handling.

一个带图形界面的 FurAffinity 批量下载工具，用于批量下载画师的画廊（Gallery）、Scraps 与收藏（Favorites），支持图片、文本、Flash、音频等全部投稿类型，并自动保存标题、标签、评论等元数据。

> 本工具在开源项目 [furaffinity-dl](https://github.com/Xerbo/furaffinity-dl)（作者 Xerbo）的基础上二次开发，新增了图形界面、自动 Cookie 提取、UA 轮换、Cloudflare 应对、断点续传、自动纠错等特性，让新手也能轻松上手。

---

## ✨ 作者署名

| 角色 | 署名 |
| --- | --- |
| 作者 / 维护者 | **luwolfy** |
| 开发协作 | **DeepSeek** |
| 原始项目 | [Xerbo/furaffinity-dl](https://github.com/Xerbo/furaffinity-dl)（MIT License） |

---

## 🚀 功能特性

- 🖥️ **图形界面**（Tkinter），无需命令行，新手友好
- 🔑 **一键自动提取 Cookie**（Firefox / Chrome / Edge）
- 🎭 **User-Agent** 自动匹配浏览器 / 随机轮换
- ☁️ **Cloudflare** 验证应对（可选 `cloudscraper`）
- 🔄 **自动刷新 Cookie**、断点续传、文件完整性校验
- 📄 自动保存投稿元数据（标题、标签、评论等 JSON）
- ⏯️ 支持暂停 / 继续 / 跳过当前画师 / 停止

---

## 📁 目录结构

```
fa-downloader/
├── README.md                 # 本教程
├── LICENSE                   # MIT 许可证（来自原始项目 Xerbo）
├── requirements.txt          # 依赖清单
├── .gitignore                # Git 忽略规则（已排除 Cookie、个人配置、日志等）
├── furaffinity-dl.py         # 核心下载器（命令行，增强版 v3.0）
├── fa_dl_auto.py             # 图形界面（智能版 v6.0），启动它即可
├── fa_projects.example.json  # 配置示例（可复制为 fa_projects.json 使用）
└── cookies.example.txt       # Cookie 文件格式示例
```

---

## 🛠️ 环境要求

- Python 3.7+
- 操作系统：Windows / macOS / Linux 均可（图形界面在 Windows 上体验最佳）

---

## 📥 安装

### 1. 安装依赖

在项目目录下打开终端，执行：

```bash
pip install -r requirements.txt
```

`requirements.txt` 内容如下：

```text
beautifulsoup4
requests
tqdm

# 图形界面增强（可选，但强烈推荐安装）
browser-cookie3      # 一键自动提取浏览器 Cookie
cloudscraper         # 绕过 Cloudflare 验证
fake-useragent       # 随机 User-Agent 轮换
```

> 如果只是用命令行版，只装前三项即可；图形界面版建议全部安装。

### 2. 启动图形界面

```bash
python fa_dl_auto.py
```

> Windows 下若 `python` 无效，可尝试 `py fa_dl_auto.py`。

---

## 🎬 快速开始（图形界面，推荐新手）

1. **登录 FurAffinity**
   用浏览器（推荐 Firefox）登录你的 FA 账号，并勾选「记住我」。

2. **一键配置 Cookie 和 UA**
   点击主界面上的 **「🚀 一键自动配置 (Firefox)」** 按钮，程序会自动从浏览器提取 Cookie，并设置匹配的浏览器标识（User-Agent）。

   > 也可以先点 **「❓ 快速开始向导」**，按提示一步步操作。

3. **添加画师**
   点击左侧 **「添加画师」**，输入画师名字（例如 `chilllum`），
   勾选要下载的类别（Gallery / Scraps / Favorites），其余选项保持默认即可。

4. **开始下载**
   点击 **「▶ 开始下载」**，程序会按顺序下载所有画师的作品。
   下载过程中可随时 **暂停 / 继续 / 跳过当前画师 / 停止**。

5. **查看结果**
   下载内容默认保存到输出目录（首次启动默认 `FA_downloads`，可在「输出目录」里修改）。

💡 **提示**

- 建议保持默认的随机间隔（1~3 秒），避免请求过快被网站封禁。
- 如果遇到 Cloudflare 验证，请确保已安装 `cloudscraper`：`pip install cloudscraper`。
- 下载是断点续传的：已经下载完整、大小一致的文件会自动跳过。

---

## 🍪 获取 Cookie 的三种方法

批量下载（尤其是成人内容 / 私有内容）需要登录态 Cookie。

### 方法一：一键自动提取（最简单）

图形界面里点击 **「🚀 一键自动配置」**，程序通过 `browser-cookie3` 自动从浏览器读取 FA 的 Cookie 并保存为 `cookies.txt`。

### 方法二：浏览器扩展导出

用扩展把 Cookie 导出为 **Netscape 格式**的 `cookies.txt`：

- Firefox：[get-cookies-txt-locally](https://addons.mozilla.org/en-US/firefox/addon/get-cookies-txt-locally)
- Chrome / Edge：[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)

导出后，在图形界面的「高级选项」里把 Cookie 来源设为「手动指定文件」，指向该文件即可。

### 方法三：命令行传参

直接把 Cookie 文件路径传给命令行版（见下文）。

---

## ⌨️ 命令行用法（高级用户）

`furaffinity-dl.py` 也可单独在命令行使用：

```bash
python furaffinity-dl.py gallery 画师名
python furaffinity-dl.py -o 输出目录 gallery 画师名
python furaffinity-dl.py -c cookies.txt -u "你的User-Agent" gallery 画师名
python furaffinity-dl.py favorites 画师名
python furaffinity-dl.py scraps 画师名
```

完整参数说明：

```
positional arguments:
  category            下载类别：gallery / scraps / favorites
  username            画师用户名
  folder              文件夹完整路径（例如 123456/Folder-Name-Here）

optional arguments:
  -o, --output        输出目录（默认当前目录）
  -c, --cookies       Netscape 格式的 Cookie 文件路径
  -u, --ua            自定义 User-Agent
  -s, --start         从第几页开始
  -S, --stop          到第几页停止
  -d, --dont-redownload   跳过已下载且大小一致的文件（断点续传）
  -i, --interval      页间请求间隔（秒）
  -m, --metadir       元数据（JSON）保存目录
```

示例：登录后下载 `koul` 的画廊，间隔 3 秒：

```bash
python furaffinity-dl.py -c cookies.txt -i 3 gallery koul
```

---

## ⚙️ 配置说明（fa_projects.json）

图形界面会把你的设置自动保存为 `fa_projects.json`（**此文件已被 `.gitignore` 排除，不会上传到 GitHub**）。

- 输出目录、请求间隔、重试次数、Cookie 来源、UA 策略等全局设置
- 画师列表（每个画师的名字、类别、独立输出目录等）

如果你需要一份初始配置，可以把 `fa_projects.example.json` 复制为 `fa_projects.json` 后修改：

```bash
cp fa_projects.example.json fa_projects.json
```

---

## ❓ 常见问题（FAQ）

**Q：下载一直失败怎么办？**
A：点击「🔍 健康检查 (测试Cookie)」测试 Cookie 是否有效；若已失效，重新点击「一键自动配置」获取新的 Cookie。

**Q：遇到 Cloudflare 验证 / 403？**
A：运行 `pip install cloudscraper` 后重试，并把请求间隔调大一些（如 3~5 秒）。

**Q：如何跳过某个画师？**
A：下载过程中点击「⏭ 跳过当前画师」。

**Q：程序提示 `缺少 browser-cookie3 库`？**
A：执行 `pip install browser-cookie3`。若浏览器 Cookie 加密无法读取，改用「方法二：浏览器扩展导出」。

**Q：代理（Proxy）能用吗？**
A：图形界面的代理设置目前仅作为预留界面，核心下载器暂未实现 `--proxy` 参数，启用后会被忽略。

---

## ⚠️ 免责声明

本工具仅供个人备份、文化交流与资料保存之用途。请自行确认批量下载是否符合 FurAffinity 的服务条款并遵守相关规定，**因使用本工具产生的任何后果由使用者自行承担**。

请勿滥用本工具对网站造成过大压力，合理设置请求间隔，尊重内容创作者的权益。

---

## 🌐 GitHub 仓库设置（提高可搜索性）

发布到 GitHub 后，在仓库页补全「About 描述」和「Topics 标签」，用户搜索时更容易找到你：

**Description（粘贴到 About 栏的 Description 框）：**

```text
FurAffinity batch downloader with a Tkinter GUI — download galleries, scraps and favorites, with resume, auto-cookie extraction, UA rotation and Cloudflare handling.
```

**Topics（逐个添加到 About 栏下方的 Topics 标签）：**

```text
furaffinity  downloader  batch-downloader  scraper  python  tkinter  furry  gallery-downloader  crawler
```

---

## 📜 许可证

本项目核心下载器 `furaffinity-dl.py` 基于 [Xerbo/furaffinity-dl](https://github.com/Xerbo/furaffinity-dl)，遵循 MIT License，详见 [LICENSE](./LICENSE)。

图形界面 `fa_dl_auto.py` 由 **luwolfy** 与 **DeepSeek** 二次开发。
