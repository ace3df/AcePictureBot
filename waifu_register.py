# -*- coding: utf-8 -*-
from utils import get_image_online
from utils import file_to_list
from utils import scrape_site
from utils import make_paste
from slugify import slugify
from config import settings
from string import capwords
import configparser
import json
import re
import os


class WaifuRegisterClass(object):
    """docstring for WaifuRegisterClass"""
    def __init__(self, user_id, username, name, gender):
        super(WaifuRegisterClass, self).__init__()
        self.user_id = user_id
        self.username = username
        self.original_name = name
        self.name = name.replace(" ", "_").lower()
        self.STOP = False

        if gender == 0:
            self.end_tags_main = "+solo"
            self.end_tags = "+-male+-1boy+-genderswap"
            self.gender = "waifu"
            self.filename = "users_waifus.json"
            self.pic_limit = 15
        elif gender == 1:
            self.end_tags_main = "+solo+-1girl+-female"
            self.end_tags = "+solo+-1girl+-female+-genderswap"
            self.gender = "husbando"
            self.filename = "users_husbandos.json"
            self.pic_limit = 10

        self.subscribe = False
        self.override = False
        self.single = False

        self.name = self.clean_name(name)

        # Only way to really do this
        if gender == 0:
            if "brando" in self.name:
                self.STOP = True

        if not self.STOP:
            blocked_waifus = file_to_list(
                            os.path.join(settings['list_loc'],
                                         'Blocked Waifus.txt'))
            self.STOP = any([
                True for i in blocked_waifus if i in self.name])

        user_waifus_file = open(
            os.path.join(settings['list_loc'], self.filename), 'r',
            encoding='utf-8')
        self.user_waifus = json.load(user_waifus_file)
        user_waifus_file.close()

        # Check if a name is already used and so we
        # can just pass all the checks to save time
        for entry in self.user_waifus['users']:
            if self.name == entry['name']:
                self.override = True
                self.site_index = entry['web_index']
                break

        # Quick name corrections
        self.known = [["anarchy_stocking", "stocking_(psg)"],
                      ["hestia", "hestia_(danmachi!)"],
                      ["zelda", "princess_zelda"]]

        for [known, work] in self.known:
            if self.name == known:
                self.original_name = work
                self.override = True
                break

        if "$" in self.original_name:
            self.single = True

        # End result of the website
        self.site_index = 0

        # Site HTML
        self.soup = ""

        # Image count of the name
        self.sankaku_count = 0
        self.safebooru_count = 0

        # Image count of the name reversed
        # Most of the time tag names are
        # Last Name - First Name
        self.sankaku_count_re = 0
        self.safebooru_count_re = 0

        # Note down that the name was reversed
        # TODO: Do I actually need this if count_re is higher?
        self.sankaku_re = False
        self.safebooru_re = False

    def blocked(self):
        if self.STOP:
            return True
        else:
            return False

    def clean_name(self, name):
        name = name.strip()
        name = re.sub(
            '[][<>"@#*:~\'$^%£]', '', name
            ).strip().replace(" ", "_").lower()
        return name

    def is_override(self):
        if self.override:
            return True
        else:
            return False

    def reverse_waifu(self, name):
        name = name.split("_")
        name = '_'.join(reversed(name))
        return name

    def check_possible_names(self):
        if "_" in self.name or self.single or self.override:
            return False, False

        waifu_site_name = self.name
        url = "https://chan.sankakucomplex.com/?tags=" + \
            waifu_site_name + self.end_tags
        soup = scrape_site(url)
        possible_names = []
        names = soup.find_all('li', attrs={'class': 'tag-type-character'})
        for a in names:
            name = a.next.text
            name = name.title()
            if " " not in name:
                name = name + " $"
            possible_names.append(name)
        if not possible_names:
            return False, False

        help_eng = "%sRegister one of these names:" % self.gender.title()
        help_frn = "%sRegister un de ces noms:" % self.gender.title()
        help_spn = ""

        name_list_string = '\n'.join(possible_names)

        end_eng = """If it's none of these (or the name can only be single),
simply add \"$\" on to the end of the name!
Remember to also check MyAnimeList.net for their FULL name!
Also make sure you look at the examples on the website!"""
        end_frn = "(Needs Translation)"
        end_spn = "(Needs Translation)"

        text = """English: {0}
French: {1}
Spanish: {2}

{3}

{4}
{5}
{6}
""".format(help_eng, help_frn, help_spn,
            name_list_string,
            end_eng, end_frn, end_spn)
        m = u"More than one name was found! Help: {0}".format(
            make_paste(text=text, title=self.name))
        return True, m

    def has_enough_images(self, soup, site, reversed_search=False):
        if site == 0:
            try:
                if soup.find('div', text="No matching posts"):
                    return False
                post_count = soup.find('span',
                                       attrs={'class': 'tag-type-none'}).text
                post_count = int(post_count.replace(",", ""))
            except:
                post_count = int(len(
                        soup.find_all('img', attrs={'class': 'preview'})))
            if reversed_search:
                self.sankaku_count_re = post_count
            else:
                self.sankaku_count = post_count
        elif site == 1:
            pass
        elif site == 2:
            try:
                if soup.find('h1', text="Nothing found, try google? "):
                    return False
            except:
                pass
            try:
                post_count = soup.find('a', attrs={'alt': 'last page'})['href']
                post_count = post_count.split("pid=")
                post_count = int(post_count[1])
            except:
                post_count = int(len(
                    soup.find_all('img', attrs={'class': 'preview'})))
            if reversed_search:
                self.safebooru_count_re = post_count
            else:
                self.safebooru_count = post_count
        if post_count >= self.pic_limit:
            return post_count
        else:
            # There isn't enough images
            # 10 isn't enough for how much people actually use MyWaifu
            return False

    def get_soup(self, site):
        if site == 0:
            cookie_file = "sankakucomplex.txt"
            url_search = "https://chan.sankakucomplex.com/?tags="
        elif site == 2:
            cookie_file = "safebooru.txt"
            a = "http://safebooru.org/"
            url_search = a + "index.php?page=post&s=list&tags="
        tags = self.name + self.end_tags
        if (site == 0 or site >= 2):
            tags += "+rating:safe"
        url = url_search + tags
        return scrape_site(url, cookie_file)

    def get_site_count(self, site):
        site_result = self.has_enough_images(self.soup, site)
        if not site_result or site_result < self.pic_limit:
            # Not enough/no images
            # Try reversing the name
            if "(" in self.name:
                return
            self.name = self.reverse_waifu(self.name)
            self.soup = self.get_soup(site)
            site_result = self.has_enough_images(self.soup, site, True)
        if site == 0:
            if self.sankaku_count_re > self.sankaku_count:
                self.sankaku_count = self.sankaku_count_re
                self.sankaku_re = True
        elif site == 2:
            if self.safebooru_count_re > self.safebooru_count:
                self.safebooru_count = self.safebooru_count_re
                self.safebooru_re = True

    def save_to_file(self):
        if self.site_index == 1:
            self.site_index = 2
        template = {"twitter_id": self.user_id,
                    "twitter_handle": self.username,
                    "name": self.name,
                    "subscribed": self.subscribe,
                    "tags": self.end_tags_main,
                    "web_index": self.site_index}
        self.user_waifus["users"].append(template)

        user_waifus_file = open(
            os.path.join(settings['list_loc'], self.filename), 'w',
            encoding='utf-8')
        json.dump(self.user_waifus, user_waifus_file, indent=2, sort_keys=True)
        user_waifus_file.close()

    def accept_tag(self):
        # Make sure they're not registering a show
        html_tags = self.soup.find_all(
            'li', class_="tag-type-copyright")
        tags = []
        for tag in html_tags:
            tags.append(str(tag.text).split(" (?)")[0].replace(" ", "_"))
        if self.name in tags:
            return False
        return True

    def start(self):
        # Check if they are already registered and remove them
        count = 0
        count = 0
        for a, datalist in self.user_waifus.items():
            for datadict in datalist:
                if str(datadict["twitter_id"]) == str(self.user_id):
                    try:
                        self.subscribe = bool(datadict['wednesday'])
                    except:
                        self.subscribe = False
                    datalist.pop(count)
                count += 1

        if not self.override:
            self.soup = self.get_soup(0)
            if not self.accept_tag():
                return False
            self.get_site_count(0)
        return True

    def four_images(self):
        path_name = slugify(self.name,
                            word_boundary=True, separator="_")
        path = os.path.join(settings['image_loc'],
                            self.gender.lower(), path_name)
        if not os.path.exists(path):
            os.makedirs(path)
        file_count = len(os.listdir(path))
        tags = self.name + self.end_tags_main
        if file_count < 3:
            needed_imgs = 3 - file_count
            for x in range(0, needed_imgs):
                get_image_online(tags, site=0, high_page=1, path=path)

    def finish(self):
        config = configparser.ConfigParser()
        config.read(settings['settings'])
        help_urls = (dict(config.items('Help URLs')))
        results = []
        if not self.override:
            results.append(self.sankaku_count)
            results.append(self.safebooru_count)
            if max(results) == 0:
                return "No images found for \"{0}\"! Help: {1}".format(
                    capwords(self.original_name), help_urls['no_imgs_found'])
            elif max(results) <= 15:
                return "Not enough images found for \"{0}\"! Help: {1}".format(
                    capwords(self.original_name), help_urls['not_enough_imgs'])
            self.site_index = results.index(max(results))
            if self.sankaku_re or self.safebooru_re:
                self.waifu_name = self.reverse_waifu(self.name)
        # Everything passed
        # Make sure 4 images are stored in the waifu/husbando
        # folder for that person
        self.four_images()
        self.save_to_file()
        self.user_waifus = ""
        return True
