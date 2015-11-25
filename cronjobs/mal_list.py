from http.cookiejar import LWPCookieJar
from robobrowser import RoboBrowser
from bs4 import BeautifulSoup
from requests import Session
from config import settings
from splinter import Browser
import datetime
import time
import sys
import os
import re


def printf(*objects, sep=' ', end='\n', file=sys.stdout):
    enc = file.encoding
    if enc == 'UTF-8':
        print(*objects, sep=sep, end=end, file=file)
    else:
        print(*map(
            lambda obj: str(obj).encode(
                enc, errors='backslashreplace').decode(
                enc), objects), sep=sep, end=end, file=file)


def scrape_site(url, cookie_file=""):
    global s
    s = Session()
    if cookie_file:
        s.cookies = LWPCookieJar(cookie_file)
        try:
            s.cookies.load(ignore_discard=True)
        except:
            # Cookies don't exist yet
            pass
    s.headers['User-Agent'] = 'Mozilla/5.0 (X11; Ubuntu; rv:39.0)'
    s.headers['Accept'] = 'text/html'
    s.headers['Connection'] = 'keep-alive'
    browser = RoboBrowser(session=s,
                          parser='html5lib',
                          timeout=15)
    try:
        browser.open(url)
        return browser
    except:
        print("[WARNING] TIMEOUT WITH WEBSITE: {0}".format(url))
        return False


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


def find_images(name):
    name = name.replace(" ", "_")
    flipped = False
    while True:
        while True:
            soup = scrape_site("https://chan.sankakucomplex.com/?tags=rating%3Asafe+solo+" + name,
                               r"..\sankakucomplex.txt")
            if soup:
                break
            time.sleep(10)
        if soup.find('div', text="No matching posts"):
            # Flip name
            if not flipped:
                flipped = True
                name = '_'.join(reversed(name.split("_")))
                continue
            else:
                # No images
                return False
        post_count = int(len(soup.find_all('img', attrs={'class': 'preview'})))
        if post_count < 3:
            # Flip name
            if flipped:
                flipped = False
                name = '_'.join(reversed(name.split("_")))
                continue
            else:
                # Not enough images
                return False

        # Has images
        # Download 4 (waifu / 3 husbando) images
        return name.replace("_", " ")


def start(url):
    complete_list = []
    not_any_list = []

    waifu_list = open(os.path.join(settings['list_loc'],
                                   "Waifu" + " List.txt"), 'r').readlines()

    husbando_list = open(os.path.join(settings['list_loc'],
                                      "Husbando" + " List.txt"), 'r').readlines()

    with Browser() as browser:
        # Visit URL
        browser.visit(url)
        printf(url)
        soup = BeautifulSoup(browser.html, 'html5lib')
        class_airing = "seasonal-anime-list js-seasonal-anime-list" \
                       " js-seasonal-anime-list-key-1 clearfix"
        airing_div = soup.find('div', class_=class_airing)
        for b in airing_div.find_all('a', class_="link-title"):
            browser.visit(b['href'])
            time.sleep(0.5)
            soup = BeautifulSoup(browser.html, 'html5lib')
            member_count = soup.find('span', text="Members:")
            member_count = member_count.next.next.string
            if int(member_count.replace(",", "")) < 30000:
                continue
            #if soup.find('td', text="Prequel:"):
            #    continue
            show_name = soup.find('span', attrs={'itemprop': "name"}).string
            browser.visit(b['href'] + "/characters")
            time.sleep(0.5)
            soup = BeautifulSoup(browser.html, 'html5lib')
            for a in soup.find_all('a'):
                try:
                    a['href']
                except:
                    continue
                if ".php?from=" in str(a['href']):
                    continue
                if not a.find('img'):
                    continue
                if "character" in str(a['href']):
                    if "questionmark" in str(a.find('img')):
                        # A nobody with no image
                        continue
                    # Check if they are already in the list
                    # (manually been added)
                    browser.visit("http://myanimelist.net" + a['href'])
                    time.sleep(1.5)
                    soup = BeautifulSoup(browser.html, 'html5lib')
                    image = str(soup.find_all('img')[1].get('src')).replace("t.jpg", ".jpg")
                    name = a['href'].split('/')[-1].replace("_", " ")
                    if " " not in name:
                        # Single name put in own list file
                        continue
                    guess_string = "{0}||{1}||{2}\n".format(name, show_name, image)
                    if guess_string in waifu_list or guess_string in husbando_list:
                        continue
                    # Flip name in case that was the case
                    name = ' '.join(reversed(name.split(" ")))
                    guess_string = "{0}||{1}||{2}\n".format(name, show_name, image)
                    if guess_string in waifu_list or guess_string in husbando_list:
                        continue
                    mem_fav = soup.find_all(text=re.compile("Member Favorites: "))
                    mem_fav = int(mem_fav[0].replace("Member Favorites: ", "").strip())
                    if mem_fav < 60:
                        # Not popular enough
                        continue
                    # Check if Girl here full of IF's and such
                    # if "She is" "she wants"
                    # time.sleep(10)  # Slow down so MAL wont get mad
                    has_imgs_name = find_images(name)
                    if not has_imgs_name:
                        # Not enough images/None
                        # Append to list to make sure later
                        not_any_list.append("{0}||{1}||{2}".format(name, show_name, image))
                        continue
                    guess_string = "{0}||{1}||{2}".format(has_imgs_name, show_name, image)
                    complete_list.append(guess_string)
                    for a in complete_list:
                        printf(a)
                    print("================")
                    for a in not_any_list:
                        printf(a)
                    print("=============================================")
            # Split series
            try:
                if complete_list[-1] != "":
                    complete_list.append("")
            except:
                # No entries yet
                pass


if __name__ == "__main__":
    """ This script will automatically run 6 weeks into the current anime season and target last season's anime.
    It will script the MyAnimeList season page, check if the anime is popular (30,000 "members").
    If it passes it will then go through each character filtering
    out people without an image and ones without more than 20 fans.
    The last check is to see if the person has any images.
    If the name doesn't have images it will put it into a side list for manual check up later.
    """
    current_date = datetime.datetime.now()
    # Uncomment this to manually do a year/season.
    current_date = current_date.replace(year=2013, month=4)
    if current_date.month in range(1, 3):
        # Winter
        #current_date = current_date.replace(year=current_date.year - 1)
        season = "fall"
    elif current_date.month in range(4, 6):
        # Spring
        season = "winter"
    elif current_date.month in range(7, 9):
        # Summer
        #
        season = "spring"
    else:
        # Fall
        season = "summer"
    # http://myanimelist.net/anime/season/2015/summer
    url = "http://myanimelist.net/anime/season/{year}/{season}".format(
        year=current_date.year, season=season)
    start(url)
