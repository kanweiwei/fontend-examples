#!/usr/bin/env python

from math import floor
import urllib3
import urllib.parse
import urllib.request
import sys
import os
from threading import Thread
from bs4 import BeautifulSoup
import argparse
import re

'''
用于下载视频
./fetch_m3u8.py --url [第一集的网页url] --name [视频名称，诸如：危机边缘]
'''

file_index = 0


def list_split(items, n):
    return [items[i:i+n] for i in range(0, len(items), n)]


def download_ts(http, files, total, path):
    global file_index
    for file in files:
        print("Downloading " + file,
              str(file_index)+'/'+str(total))
        filename = os.path.basename(file)
        if not os.path.exists(os.path.join(path, filename)):
            f = http.request('GET', file, preload_content=False)
            r = f.data
            with open(os.path.join(path, filename), 'wb') as out:
                out.write(r)

        file_index += 1


def download_m3u8_ts(url, name, audioName):
    mp4 = os.path.join(os.getcwd(), audioName, name + ".mp4")
    if os.path.exists(mp4):
        return
    global file_index
    file_index = 0
    target_dir = os.path.abspath(os.getcwd())
    result = urllib.parse.urlparse(url)
    threadCount = 8
    http = urllib3.PoolManager(num_pools=threadCount+1)
    r = http.request('GET', url)
    data = bytes.decode(r.data, "utf-8")
    if data.find(".m3u8") != -1:
        target_m3u8 = None
        for l in r.data.splitlines():
            if bytes.decode(l).endswith(".m3u8"):
                target_m3u8 = bytes.decode(l)
        if target_m3u8 is None:
            sys.exit('No m3u8 file found')
        return download_m3u8_ts(result.scheme + '://' + result.netloc + target_m3u8, name, audioName)
    if data.find('.ts'):
        ts_files = []
        for l in r.data.splitlines():
            if bytes.decode(l, 'utf-8').endswith(".ts"):
                ts_files.append(result.scheme + '://' +
                                result.netloc + bytes.decode(l, 'utf-8'))
        if len(ts_files) == 0:
            sys.exit('No ts file found')
        if name is None or name == "":
            sys.exit("No name specified")
        ts_files_path = os.path.join(
            target_dir, audioName, ("ts_files_%s" % name))
        if not os.path.exists(ts_files_path):
            os.makedirs(ts_files_path)

        total = len(ts_files)

        count = floor(total / threadCount)

        new_ts_files = [ts_files[i:i+count]
                        for i in range(0, len(ts_files), count)]
        if len(new_ts_files) <= threadCount:
            download_ts(http, ts_files, len(ts_files), ts_files_path)

        else:
            threads = []
            for files in new_ts_files:
                t = Thread(target=download_ts, args=(
                    http, files, len(ts_files), ts_files_path))
                threads.append(t)

            for t in threads:
                t.start()
            for t in threads:
                t.join()

        with open(os.path.join(target_dir, audioName, name + '.mp4'), 'wb+') as out:
            for item in range(len(ts_files)):
                with open(os.path.join(ts_files_path, os.path.basename(ts_files[item])), 'rb') as f:
                    out.write(f.read())


def get_target_script(soup):
    scripts = soup.find_all("script")
    for script in scripts:
       # ...code 省略...
       return None
    return None


def get_m3u8(url):
    url_parse = urllib.parse.urlparse(url)
    opener = urllib.request.build_opener()
    opener.addheaders = [
        ('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.61 Safari/537.36')]
    urllib.request.install_opener(opener)
    data = urllib.request.urlopen(url, data=None, timeout=120)
    data = bytes.decode(data.read(), "utf-8")
    soup = BeautifulSoup(data, 'lxml')
    script = get_target_script(soup)
    if script is None:
        sys.exit("No script found")
    search_Result = re.search(r'(http.*?\.m3u8)', script.string)
    next_url = re.search(r'\"next\":\"([^\"]*?)\"', script.string)
    next = None
    if next_url is not None:
        next = next_url.group(1)
    if next is None or next == "":
        print("最后一集")
    else:
        next = url_parse.scheme + '://' + url_parse.netloc + next
        next = next.replace("\\", "")

    if search_Result is None:
        sys.exit("No m3u8 found")
    m3u8 = search_Result.group(1).replace("\\", "")
    name = os.path.basename(url).split('.')[0]
    return m3u8, name, next


def get_current_url(audioName):
    current_download = os.path.join(os.path.abspath(audioName), "current")
    if os.path.exists(current_download):
        with open(current_download, 'r') as f:
            return f.read()


def update_current_url(audioName, url):
    current_download = os.path.join(os.path.abspath(audioName), "current")
    with open(current_download, 'w+') as f:
        f.write(url)


def download_mp4(html_url, audioName):
    current_url = get_current_url(audioName)
    if current_url == "":
        sys.exit("No url specified")
    elif current_url is not None and current_url.find("http") != -1:
        html_url = current_url

    (url, name, next) = get_m3u8(html_url)
    update_current_url(audioName, html_url)
    download_m3u8_ts(url, name, audioName)
    if next is not None or next != "":
        update_current_url(audioName, next)
        download_mp4(next, audioName)
    else:
        update_current_url(audioName, "")
        print("All videos download finished")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch m3u8 file from html')
    parser.add_argument('--url', dest="url",
                        help='url of the html page', required=True)
    parser.add_argument('--name', dest="name",
                        help="video name", required=True)
    args = parser.parse_args()
    print(args)
    download_mp4(args.url, args.name)
