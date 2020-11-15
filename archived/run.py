#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
@author: glin
"""


import os
import sys
import platform
import getopt
import datetime
import re
import threading
import requests
import functools

DEBUG = False
SITES = [
    'http://www.proxyserverlist24.top/',
    'http://www.live-socks.net/'
]
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Win64; x64; Trident/6.0)'
}
TIMEOUT = 8
SPIDER_PROXIES = None
# SHOWMYIP = 'https://www.showmyip.com/'
# IP138 = 'https://ip138.com/'
ICANHAZIP = 'http://icanhazip.com/'
LOCK = threading.Lock()


def echo(color, *args):
    colors = {
        'error': '\033[91m',
        'success': '\033[94m',
        'info': '\033[93m'
    }
    if color not in colors or platform.system() == 'Windows':
        print(' '.join(args))
    print(colors[color], ' '.join(args), '\033[0m')


def debug(func):
    @functools.wraps(func)
    def _debug(*args, **kwargs):
        output = func(*args, **kwargs)
        if DEBUG:
            # echo('info', '%s(%r, %r): %r' % (func.__name__, args, kwargs, output))
            echo('info', '%s(%r, %r) is called.' % (func.__name__, args, kwargs))
        return output
    return _debug


@debug
def get_content(url, proxies=None) -> str:
    """ get content based on url and proxy """
    try:
        r = requests.get(url, headers=HEADERS, proxies=proxies, timeout=TIMEOUT)
        if r.status_code == requests.codes.ok:
            return r.text
        echo('error', 'Request failed', str(r.status_code), url)
    except Exception as e:
        echo('error', 'Exception occurred', url, str(e))
    return ''


def get_proxies_thread(site, proxies):
    """ get proxies from a site """
    content = get_content(site, SPIDER_PROXIES)
    pages = re.findall(r'<h3[\s\S]*?<a.*?(http.*?\.html).*</a>', content)
    for page in pages:
        content = get_content(page, SPIDER_PROXIES)
        LOCK.acquire()
        proxies += re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}', content)
        LOCK.release()


def get_proxies_set() -> list:
    """ get proxies from all sites and remove duplicates """
    spider_pool, proxies = [], []
    for site in SITES:
        t = threading.Thread(
            target=get_proxies_thread,
            args=(site, proxies)
        )
        spider_pool.append(t)
        t.start()
    for t in spider_pool:
        t.join()
    return list(set(proxies))


def check_proxies_thread(checker_url, proxies, usable_proxies):
    """ check if the proxies are usable """
    for proxy in proxies:
        proxy = proxy.strip()
        # proxy = proxy if proxy.startswith('http://') else ''.join(['http://', proxy])
        content = get_content(checker_url, proxies={'http': proxy})
        if content:
            if checker_url == ICANHAZIP:
                ip = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', content)
                if not (ip and ip.group() in proxy):
                    continue
            LOCK.acquire()
            usable_proxies.append(proxy)
            LOCK.release()


def check_and_save_proxies(checker_url, proxies, output_file):
    """ check and save usable proxies """
    checker_pool = []
    usable_proxies = []
    for i in range(0, len(proxies), 20):
        t = threading.Thread(
            target=check_proxies_thread,
            args=(checker_url, proxies[i:i+20], usable_proxies)
        )
        checker_pool.append(t)
        t.start()
    for t in checker_pool:
        t.join()
    with open(output_file, 'w') as of:
        of.writelines('\n'.join(usable_proxies))
    return len(usable_proxies)


if __name__ == '__main__':
    input_file, output_file, checker_url = '', 'proxies.txt', ICANHAZIP
    try:
        opts, _ = getopt.getopt(sys.argv[1:], 'u:f:o:')
    except getopt.GetoptError as e:
        echo('error', str(e))
        sys.exit(2)
    for o, a in opts:
        if o == '-f':
            input_file = os.path.abspath(a)
        elif o == '-u':
            checker_url = a
        elif o == '-o':
            output_file = os.path.abspath(a)
        else:
            assert False, 'Unhandled Option'
    start = datetime.datetime.now()
    proxies = open(input_file, 'r').readlines() if input_file else get_proxies_set()
    num_of_usable_proxies = check_and_save_proxies(checker_url, proxies, output_file)
    stop = datetime.datetime.now()
    note = '\nProxy total:%s\nUsable proxies:%s\nResult file:%s\nTime elapsed:%s\n' % \
           (len(proxies), num_of_usable_proxies, output_file, stop - start)
    echo('success', note)
