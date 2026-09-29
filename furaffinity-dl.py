#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
FurAffinity 下载器 - 增强版 v3.0（完整性校验 + 详细日志）
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
from tqdm import tqdm
from argparse import RawTextHelpFormatter
import json
from bs4 import BeautifulSoup
import requests
import http.cookiejar as cookielib
import re
import os
from time import sleep

# ------------------ 参数解析 ------------------
parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description='Downloads the entire gallery/scraps/favorites of a furaffinity user')
parser.add_argument('category', metavar='category', type=str, nargs='?', default='gallery')
parser.add_argument('username', metavar='username', type=str, nargs='?')
parser.add_argument('folder', metavar='folder', type=str, nargs='?')
parser.add_argument('--output', '-o', dest='output', type=str, default='.')
parser.add_argument('--cookies', '-c', dest='cookies', type=str, default='')
parser.add_argument('--ua', '-u', dest='ua', type=str, default='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:68.7) Gecko/20100101 Firefox/68.7')
parser.add_argument('--start', '-s', dest='start', type=str, default=1)
parser.add_argument('--stop', '-S', dest='stop', type=str, default='')
parser.add_argument('--dont-redownload', '-d', dest='dont_redownload', action='store_true', help="Skip already downloaded files (with size check)")
parser.add_argument('--interval', '-i', dest='interval', type=float, default=0)
parser.add_argument('--metadir', '-m', dest='metadir', type=str, default=None)

args = parser.parse_args()
if args.username is None:
    parser.print_help()
    exit()

# 创建目录
if args.output != '.':
    os.makedirs(args.output, exist_ok=True)
if args.metadir is None:
    args.metadir = args.output
else:
    os.makedirs(args.metadir, exist_ok=True)

# 校验类别和用户名
valid_categories = ['gallery', 'favorites', 'scraps']
if args.category not in valid_categories:
    raise Exception('Category is not valid', args.category)
if bool(re.compile(r'[^a-zA-Z0-9\-~._]').search(args.username)):
    raise Exception('Username contains non-valid characters', args.username)

# 会话与 Cookie
session = requests.session()
session.headers.update({'User-Agent': args.ua})
if args.cookies != '':
    cookies = cookielib.MozillaCookieJar(args.cookies)
    cookies.load()
    session.cookies = cookies

base_url = 'https://www.furaffinity.net'
gallery_url = f'{base_url}/{args.category}/{args.username}'
if args.folder is not None:
    gallery_url += f"/folder/{args.folder}"
page_num = args.start

# ------------------ 核心函数 ------------------
def download_file(url, fname, expected_size, desc):
    """下载文件，带完整性校验和重试"""
    # 检查是否已存在且完整
    if args.dont_redownload and os.path.isfile(fname):
        local_size = os.path.getsize(fname)
        if local_size == expected_size and local_size > 0:
            print(f'✓ 已存在且完整: "{desc[:40]}" ({local_size} bytes) → 跳过')
            return True
        elif local_size == 0:
            print(f'⚠ 发现空文件: {fname}，删除后重新下载')
            os.remove(fname)
        else:
            print(f'⚠ 文件大小不匹配: 本地 {local_size} vs 服务器 {expected_size}，重新下载')
            os.remove(fname)

    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            r = session.get(url, stream=True, timeout=(10, 60))
            if r.status_code != 200:
                print(f"HTTP {r.status_code} 错误，下载 {fname} 失败")
                return False

            total = int(r.headers.get('Content-Length', 0))
            with open(fname, 'wb') as file, tqdm(
                desc=desc.ljust(40)[:40],
                total=total,
                miniters=100,
                unit='b',
                unit_scale=True,
                unit_divisor=1024
            ) as bar:
                for data in r.iter_content(chunk_size=1024):
                    file.write(data)
                    bar.update(len(data))
            # 下载后校验大小
            downloaded_size = os.path.getsize(fname)
            if downloaded_size == total and total > 0:
                return True
            else:
                raise Exception(f"下载后大小异常: {downloaded_size} / {total}")
        except Exception as e:
            print(f"下载失败 ({attempt+1}/{max_retries+1}): {e}")
            if attempt < max_retries:
                delay = 3 * (2 ** attempt)
                print(f"等待 {delay} 秒后重试...")
                sleep(delay)
            else:
                print(f"放弃下载: {fname}")
                return False
    return False


def download(path):
    page_url = base_url + path
    response = session.get(page_url)
    s = BeautifulSoup(response.text, 'html.parser')

    # 系统消息
    if s.find(class_='notice-message') is not None:
        msg = s.find(class_='notice-message').find('div').find(class_="link-override").text.strip()
        raise Exception('System Message', msg)

    image = s.find('a', string='Download').attrs.get('href')
    title = s.find('div', class_='submission-title').find('h2').text.strip()
    filename = image.split("/")[-1]
    # 获取服务器文件大小（通过 HEAD 请求或从响应头中获取）
    head = session.head('https:' + image)
    expected_size = int(head.headers.get('Content-Length', 0))

    stats_container = s.find(class_='submission-content-stats')
    stat_keys = stats_container.find_all('span', recursive=False)[0].find_all('span')
    stat_values = stats_container.find_all('span', recursive=False)[1].find_all('span')
    stats = {key.text.strip(): value.text.strip() for key, value in zip(stat_keys, stat_values)}

    data = {
        'id': int(path.split('/')[-2]),
        'filename': filename,
        'author': s.find(class_='c-usernameBlockSimple__displayName').attrs.get('title').strip(),
        'date': s.find(class_='popup_date').attrs.get('title'),
        'title': title,
        'description': s.find(class_='submission-description').text.strip().replace('\r\n', '\n').strip(),
        "description_html": s.find(class_='submission-description').prettify(),
        "tags": [],
        'category': stats.get("Category", ""),
        'type': stats.get("Theme", ""),
        'species': stats.get("Species", ""),
        'views': int(s.find(title='Views').find_all('div')[0].text) if s.find(title='Views') else 0,
        'favorites': int(s.find(title='Favorites').find_all('div')[0].text) if s.find(title='Favorites') else 0,
        'rating': s.find(class_=re.compile('c-contentRating--[a-z]*')).text.strip() if s.find(class_=re.compile('c-contentRating--[a-z]*')) else "",
        'comments': []
    }

    # 提取 tags
    tag_section = s.find(class_='submission-tags')
    if tag_section:
        for tag in tag_section.find_all(class_='tags'):
            a = tag.find('a', href=re.compile('/search/.*'))
            if a:
                data['tags'].append(a.text)

    # 提取评论（简化）
    for comment in s.find_all(class_='comment_container'):
        if comment.find(class_='comment-link') is None:
            continue
        data['comments'].append({
            'cid': int(comment.find(class_='comment-link').attrs.get('href')[5:]),
            'parent_cid': None,
            'content': comment.find(class_='user-submitted-links').text.strip().replace('\r\n', '\n'),
            'username': comment.find(class_='c-usernameBlock__userName').attrs.get('href')[5:],
            'date': comment.find(class_='popup_date').attrs.get('title')
        })

    url = 'https:' + image
    output_path = os.path.join(args.output, filename)

    if not download_file(url, output_path, expected_size, data["title"]):
        return False

    # 保存元数据
    with open(os.path.join(args.metadir, f'{filename}.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return True


# ------------------ 主循环 ------------------
while True:
    if args.stop and str(args.stop) == str(page_num):
        print(f"到达停止页 {args.stop}，结束")
        break

    page_url = f'{gallery_url}/{page_num}'
    for attempt in range(3):
        try:
            response = session.get(page_url, timeout=30)
            break
        except Exception as e:
            print(f"获取页面失败 ({attempt+1}/3): {e}")
            if attempt == 2:
                raise Exception(f"无法获取页面 {page_url}")
            sleep(5)

    s = BeautifulSoup(response.text, 'html.parser')

    if page_num == '1' or page_num == 1:
        avatar = s.find(class_='loggedin_user_avatar')
        if avatar:
            print('已登录为', avatar.attrs.get('alt'))
        else:
            print('未登录，无法访问成人内容')

    # 系统消息或结束
    if s.find(class_='notice-message'):
        msg = s.find(class_='notice-message').find('div').find(class_="link-override").text.strip()
        raise Exception('System Message', msg)
    if s.find(id='no-images'):
        print('已到末尾')
        break

    # 下载本页所有图片
    for img in s.find_all('figure'):
        link = img.find('a')
        if link and link.get('href'):
            if not download(link.get('href')):
                print("某图片下载失败，继续...")
        if args.interval > 0:
            sleep(args.interval)

    # 下一页
    next_btn = s.find('button', class_='button standard', string="Next")
    if not next_btn or not next_btn.parent:
        print('找不到下一页按钮')
        break

    if args.category != "favorites":
        page_num = next_btn.parent.attrs['action'].split('/')[-2]
        print(f'转到第 {page_num} 页')
    else:
        next_link = next_btn.parent.attrs['action']
        match = re.search(r'/\d+', next_link)
        if not match:
            print('无法解析 favorites 下一页链接')
            break
        page_num = match.group(0) + "/next"
        print(f'转到 {page_num}')

print('全部下载完成')