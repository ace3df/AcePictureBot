from http.cookiejar import LWPCookieJar
from robobrowser import RoboBrowser
from urllib.parse import urlparse
from requests import Session
from config import website_logins
from config import extra_api_keys
from config import settings
from PIL import Image
import urllib.request
import configparser
import subprocess
import requests
import hashlib
import pathlib
import random
import ntpath
import json
import time
import sys
import re
import os
s = None


def printf(*objects, sep=' ', end='\n', file=sys.stdout):
    enc = file.encoding
    if enc == 'UTF-8':
        print(*objects, sep=sep, end=end, file=file)
    else:
        print(*map(
            lambda obj: str(obj).encode(
                enc, errors='backslashreplace').decode(
                enc), objects), sep=sep, end=end, file=file)


def path_leaf(path):
    head, tail = ntpath.split(str(path))
    return tail


def make_paste(text, title="", expire="10M"):
    post_url = "https://paste.ee/api"
    payload = {'key': extra_api_keys['pasteee'],
               'paste': text,
               'description': title}
    headers = {'content-type': 'application/json'}
    r = requests.post(post_url,
                      data=json.dumps(payload),
                      headers=headers)
    return r.json()['paste']['link']


def file_to_list(file):
    if "/" not in file:
        file = os.path.join(settings['list_loc'], file)
    lines = list(filter(None,
                 open(file, 'r', encoding='utf-8').read().splitlines()))
    if not lines:
        return []
    to_list = []
    split_by = False
    keep_s = -1
    if ":" in lines[0]:
        split_by = ":"
        keep_s = 0
        keep_e = 1
    elif "||" in lines[0]:
        split_by = "||"
        keep_s = 0
        keep_e = 2
        if (lines[3].count("||")) == 2:
            keep_e = 3
    for line in lines:
        # Comment line
        if line[0] == "#":
            continue
        if split_by:
            line = line.split(split_by)
            if keep_e < 2:
                line = line[keep_s:keep_e][0]
        to_list.append(line)
    return to_list


def scrape_site(url, cookie_file=""):
    global s
    s = Session()
    s.headers['User-Agent'] = 'Mozilla/5.0 (X11; Ubuntu; rv:39.0)'
    s.headers['Accept'] = 'text/html'
    s.headers['Connection'] = 'keep-alive'
    if cookie_file:
        s.cookies = LWPCookieJar(cookie_file)
        try:
            s.cookies.load()
            if not s.cookies._cookies:
                # Cookies have expired
                raise Exception
        except (FileNotFoundError, Exception):
            if os.path.exists(cookie_file):
                os.remove(cookie_file)
            browser = RoboBrowser(session=s,
                                  parser='html5lib',
                                  timeout=15)
            if "sankakucomplex.com" in url:
                url_login = "https://chan.sankakucomplex.com/user/login/"
                form_num = 0
                form_user = "user[name]"
                form_password = "user[password]"
                username = website_logins['sankakucomplex_username']
                password = website_logins['sankakucomplex_password']
                browser.open(url_login)
                form = browser.get_form(form_num)
                form[form_user].value = username
                form[form_password].value = password
                browser.submit_form(form)
                s.cookies.save()
    browser = RoboBrowser(session=s,
                          parser='html5lib',
                          timeout=15)
    try:
        browser.open(url)
        return browser
    except:
        # TODO: find what exceptions happens here
        printf("[WARNING] TIMEOUT WITH WEBSITE: {0}".format(url))
        return False


def image_hash(image, hash_size=8):
    if isinstance(image, str):
        image = Image.open(image)
    image = image.convert('L').resize(
        (hash_size + 1, hash_size),
        Image.ANTIALIAS,
    )

    difference = []
    for row in range(hash_size):
        for col in range(hash_size):
            pixel_left = image.getpixel((col, row))
            pixel_right = image.getpixel((col + 1, row))
            difference.append(pixel_left > pixel_right)
    decimal_value = 0
    hex_string = []
    for index, value in enumerate(difference):
        if value:
            decimal_value += 2**(index % 8)
        if (index % 8) == 7:
            hex_string.append(hex(decimal_value)[2:].rjust(2, '0'))
            decimal_value = 0

    return ''.join(hex_string)


def video_to_gif(video):
    """
    Return encoded gif path / compress gif size
    """
    try:
        save_to = os.path.dirname(video)
        SCRIPT_LOC = settings['webm_script']
        filename = os.path.join(
            save_to,
            hashlib.md5(
                open(video, 'rb').read()).hexdigest() + ".gif")
        command = [SCRIPT_LOC,
                   video,
                   filename]
        DEVNULL = open(os.devnull, 'w')
        pipe = subprocess.Popen(command, stdout=DEVNULL, bufsize=10**8)
        pipe.wait()
        if "gif" not in video:
            os.remove(video)
    except Exception as v:
        # Shouldn't happen but it's here to print in case
        printf(v)
        return False

    return filename


def download_image(url, path="", filename="", ignore_list=""):
    if ignore_list:
        try:
            ignore_imgs = open(
                os.path.join(
                    settings['ignore_loc'],
                    ignore_list), 'r').read().splitlines()
        except:
            ignore_imgs = []

    img_types = {"jpg": "image/jpeg",
                 "jpeg": "image/jpeg",
                 "png": "image/png",
                 "gif": "image/gif",
                 "webm": "video/webm"}
    file_path = urlparse(url).path
    ext = os.path.splitext(file_path)[1].lower()
    if not ext[ext.rfind(".") + 1:] in img_types:
        return False

    hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)',
           'Connection': 'keep-alive'}
    req = urllib.request.Request(url, headers=hdr)
    try:
        response = urllib.request.urlopen(req)
        data = response.read()
    except urllib.request.URLError:
        # Loss data / IncompleteRead
        return False
    if path:
        path = os.path.join(settings['image_loc'], "downloads")
    if filename == "":
        img_hash = hashlib.md5(data).hexdigest()
        filename = "%s%s" % (img_hash, ext)

    if not os.path.exists(path):
        os.makedirs(path)

    if not os.path.isfile(os.path.join(path, filename)):
        tweet_image = os.path.join(path, filename)
        with open(tweet_image, "wb") as code:
            code.write(data)
    else:
        tweet_image = os.path.join(path, str(filename))

    if "webm" in ext[ext.rfind(".") + 1:]:
        tweet_image = video_to_gif(tweet_image)
        if not tweet_image:
            return False
    # TODO: Debug around here to find out why the .gif gets lost
    if not os.path.exists(tweet_image):
        return False

    if (os.stat(tweet_image).st_size / 1000000) > 2.8:
        # File size too big, return False if normal image
        # TODO: Compress if it's a large image
        # Try to compress if a gif
        if "gif" in ext[ext.rfind(".")+1:]:
            tweet_image = video_to_gif(tweet_image)
            # Still too large
            if (os.stat(tweet_image).st_size / 1000000) > 2.8:
                os.remove(tweet_image)
                return False
        else:
            os.remove(tweet_image)
            return False

    pil_image = Image.open(tweet_image)
    if ignore_list:
        hex_data = image_hash(pil_image)
        if hex_data in ignore_imgs:
            return False
        ignore_imgs.append(hex_data)
        with open(os.path.join(
                settings['ignore_loc'], ignore_list), 'w') as file:
            file.write('\n'.join(ignore_imgs))
    pil_image.load()
    width, height = pil_image.size
    del pil_image
    if ext == ".gif":
        max_size = -160
        min_size = 610
    else:
        max_size = -610
        min_size = 610
    if (width - height) <= max_size or (width - height) >= min_size:
        os.remove(tweet_image)
        return False

    return tweet_image


def get_image_online(tags, site=0, high_page=10, ignore_list="", path=""):
    if ":" not in path:
        path = os.path.join(settings['image_loc'], path)
    config = configparser.RawConfigParser(allow_no_value=True)
    config.read(settings['settings'])
    websites = (dict(config.items('Websites')))
    blacklisted_tags = (config.get('Settings', 'blacklisted_tags')).split(', ')
    if websites['sankakucomplex'] == "False" and site == 0:
        site = 1
    if websites['danbooru'] == "False" and site == 1:
        site = 0
    if ignore_list:
        try:
            ignore_urls = open(
                os.path.join(
                    settings['ignore_loc'],
                    ignore_list), 'r').read().splitlines()
        except FileNotFoundError:
            ignore_urls = []

    tried_pages = [high_page + 1]
    last_tries = 0
    try_count = 0
    low_page = 0
    found_image = False
    found_page = False
    good_image = False
    browser = False
    if site == 0:
        cookie_file = settings['secret_key'] + "-sankakucomplex.txt"
        url_start = "https://chan.sankakucomplex.com"
        url_search = "https://chan.sankakucomplex.com/?tags="
        url_login = "https://chan.sankakucomplex.com/user/login/"
        pid = False
        login = True
    elif site == 1:
        cookie_file = settings['secret_key'] + "-danbooru.txt"
        url_start = "https://danbooru.donmai.us"
        url_search = "https://danbooru.donmai.us/posts?tags="
        pid = False
        login = False
    elif site == 2:
        cookie_file = settings['secret_key'] + "-safebooru.txt"
        url_start = "http://safebooru.org"
        url_search = "http://safebooru.org/index.php?page=post&s=list&tags="
        pid = True
        login = False
    elif site == 3:
        cookie_file = settings['secret_key'] + "-yande.txt"
        url_start = "https://yande.re"
        url_search = "https://yande.re/post?tags="
        pid = False
        login = False
    elif site == 4:
        cookie_file = settings['secret_key'] + "-konachan.txt"
        url_start = "http://konachan.com"
        url_search = "http://konachan.com/post?tags="
        pid = False
        login = False
    else:
        return False
    if isinstance(tags, list):
        tag_count = len(tags)
        tags = '+'.join(tags)
    else:
        tag_count = len(tags.split("+"))
    if site == 0:
        if "rating:safe" not in tags:
            tags += "+rating:safe"
        if "order:popular" not in tags:
            if tag_count < 7:
                tags += "+order:popular"
    if pid:
        rand = 40
        tried_pages = [high_page * rand]
    else:
        rand = 1
    x = min(tried_pages)
    while not good_image:
        while not found_image:
            while not found_page:
                no_images = False
                try_count += 1
                if try_count == 15:
                    return False
                page = str(int(random.randint(low_page, high_page) * rand))
                while int(page) in tried_pages or int(page) > int(x):
                    if int(page) == 0:
                        break
                    page = str(int(random.randint(low_page, high_page) * rand))
                    if int(page) < int(x):
                        break
                if not pid:
                    page_url = "&page=" + str(page)
                elif pid:
                    page_url = "&pid=" + str(page)
                url = "%s%s%s" % (url_search, tags, page_url)
                tried_pages.append(int(page))
                tried_pages = [int(i) for i in tried_pages]
                x = min(tried_pages)
                browser = scrape_site(url, cookie_file)
                printf("Searching:\n" + str(browser))
                if not browser:
                    # Time'd out
                    return False
                if site == 0:
                    if browser.find('div', text="No matching posts"):
                        no_images = True
                elif site == 1:
                    if browser.find('p', text="Nobody here but us chickens!"):
                        no_images = True
                elif site == 2:
                    if browser.find('h1', text="Nothing found, try google? "):
                        no_images = True
                    elif len(browser.find_all('span',
                             attrs={'class': "thumb"})) < 2:
                        no_images = True
                elif site == 3 or site == 4:
                    if browser.find('p', text="Nobody here but us chickens!"):
                        no_images = True
                time.sleep(1)
                if not no_images:
                    break
                elif no_images and int(page) == 0:
                    return False
            good_image_links = []
            image_links = browser.find_all('a')
            for link in image_links:
                try:
                    link['href']
                except:
                    continue
                if site == 0:
                    if "/post/show/" not in link['href']:
                        continue
                elif site == 1:
                    if "/posts/searches" in link['href']:
                        continue
                    if "events" in link['href']:
                        continue
                    if "random" in link['href']:
                        continue
                    if "/posts/" not in link['href']:
                        continue
                elif site == 2:
                    if "&id=" not in link['href']:
                        continue
                elif site == 3:
                    if "/post/show/" not in link['href']:
                        continue
                elif site == 4:
                    if "/post/show/" not in link['href']:
                        continue
                good_image_links.append(link['href'])
            if not good_image_links:
                return False
            random.shuffle(good_image_links)
            if site == 0:
                url = "%s%s" % (url_start, random.choice(good_image_links))
            else:
                url = "%s/%s" % (url_start, random.choice(good_image_links))
            try_count = 0
            if ignore_list:
                while url in ignore_urls:
                    url = "%s/%s" % (url_start,
                                     random.choice(good_image_links))
                    try_count += 1
                    if try_count == 20:
                        break
                ignore_urls.append(url)
            try:
                browser.open(url)
            except:
                # TODO: find what exception happens here
                browser = False
            if not browser:
                return False
            if ignore_list:
                with open(os.path.join(
                        settings['ignore_loc'], ignore_list), 'w') as file:
                        file.write('\n'.join(ignore_urls))
            image_tags = []
            if site == 0:
                site_tag = browser.find('ul', id="tag-sidebar")
                if not site_tag:
                    # No tags? Normal post got passed?
                    return False
                site_tag = site_tag.find_all('li')
                for tag in site_tag:
                    text = tag.text
                    text = text.split("(?)")
                    text = text[0]
                    text = text.replace("&#39;", "\'")
                    image_tags.append(text)
            elif site == 1:
                site_tag = browser.find('section', id="tag-list")
                site_tag = site_tag.find_all('li')
                for tag in site_tag:
                    text = tag.find_all('a')
                    text = text[1]
                    text = text.text
                    text = text.replace("&#39;", "\'")
                    image_tags.append(text)
            elif site == 2:
                site_tag = browser.find('ul', id="tag-sidebar")
                site_tag = site_tag.find_all('li')
                for tag in site_tag:
                    tag = tag.find('a')
                    text = tag.text
                    text = text.replace("&#39;", "\'")
                    image_tags.append(text)
            elif site == 3:
                site_tag = browser.find('ul', id="tag-sidebar")
                site_tag = site_tag.find_all('li')
                for tag in site_tag:
                    text = tag.find_all('a')
                    text = text[1]
                    text = text.text
                    text = text.replace("&#39;", "\'")
                    image_tags.append(text)
            elif site == 4:
                site_tag = browser.find('ul', id="tag-sidebar")
                site_tag = site_tag.find_all('li')
                for tag in site_tag:
                    text = tag.find_all('a')
                    text = text[1]
                    text = text.text
                    text = text.replace("&#39;", "\'")
                    image_tags.append(text)
            image_tags = list(map(str.strip, image_tags))
            if any([item.lower()in blacklisted_tags
                    for item in image_tags]):
                continue
            if any("(cosplay)" in s for s in image_tags):
                continue
            break

        image_url = browser.find('img', attrs={'id': 'image'})
        if not image_url:
            image_url = browser.find('video', attrs={'id': 'image'})
        if site == 0:
            try:
                url = "https:%s" % (image_url['src'])
            except:
                return False
        elif site == 1:
            try:
                url = url_start + image_url['src']
            except:
                return False
        elif site == 2:
            url = image_url['src']
        tweet_image = download_image(url=url, path=path,
                                     ignore_list=ignore_list)
        last_tries += 1
        if last_tries == 5:
            # Just return last found
            return tweet_image
        if tweet_image:
            return tweet_image


def get_image(path, ignore_list=False):
    if ":" not in path:
        path = os.path.join(settings['image_loc'], path)
    if not ignore_list:
        try:
            files = [p for p in pathlib.Path(path).iterdir() if p.is_file()]
            img = path_leaf(random.choice(files))
            return os.path.join(path, img)
        except (FileNotFoundError, IndexError):
            return False
    else:
        try:
            ignore_imgs = open(
                os.path.join(
                    settings['ignore_loc'],
                    ignore_list), 'r').read().splitlines()
        except FileNotFoundError:
            ignore_imgs = []
        try:
            files = [p for p in pathlib.Path(path).iterdir() if p.is_file()]
            img = path_leaf(random.choice(files))
        except (FileNotFoundError, IndexError):
            return False
        hex_data = image_hash(os.path.join(path, img))
        safe_break = 0
        while hex_data in ignore_imgs:
            safe_break += 1
            if safe_break == 10:
                return False
            img = path_leaf(random.choice(files))
            hex_data = image_hash(os.path.join(path, img))
            if hex_data in ignore_imgs:
                continue
        ignore_imgs.append(hex_data)
        with open(os.path.join(
                settings['ignore_loc'], ignore_list), 'w') as file:
            file.write('\n'.join(ignore_imgs))
        return os.path.join(path, img)


def get_command(string):
    string = string.lower()
    gender = ""
    if "waifu" in string:
        gender = "Waifu"
    elif "husbando" in string:
        gender = "Husbando"
    rep = {"waifu": "{GENDER}", "husbando": "{GENDER}",
           "anime?": "source", "anime ?": "source",
           "is this from": "source", "sauce": "source"}
    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    string = pattern.sub(lambda m: rep[re.escape(m.group(0))], string)
    triggers = file_to_list(
        os.path.join(settings['list_loc'],
                     "commands.txt"))
    command = [s for s in triggers if str(s).lower() in string.lower()]
    if not command:
        return False
    else:
        command = command[0]
        if type(command) is bool:
            return False
    command = command.replace("{GENDER}", gender)
    return command


def short_string(string, limit=40):
    if string == "":
        return string
    elif len(string) <= limit:
        return string
    count = 0
    for a in string:
        count += 1
        if count >= limit and a == " ":
            break
    string = string[:count].strip()
    return string + "[..]"


def gender(string):
    string = string.lower()
    if "waifu" in string:
        return 0
    elif "husbando" in string:
        return 1
    return False
