# -*- coding: utf-8 -*-
from utils import file_to_list
from utils import scrape_site
from utils import make_paste
from config import settings
import configparser
import datetime
import json
import re
import os


def config_get(section, key, file=0):
    if file == 0:
        file = settings['settings']
    elif file == 1:
        file = settings['count_file']
    with open(file) as fp:
        config = configparser.RawConfigParser(allow_no_value=True)
        try:
            config.read_file(fp)
            return config.get(section, key)
        except configparser.NoSectionError:
            return False
        except configparser.NoOptionError:
            return False
        except configparser.DuplicateSectionError:
            return False


class WaifuRegisterClass:
    def __init__(self, user_id, username, name, gender):
        self.user_id = user_id
        self.username = username
        self.org_name = name
        self.name = self.clean_name(name)
        self.subscribe = False
        self.disable = False
        self.override = False
        self.multinames = False
        self.noimages = False
        self.TEMP_bug = False
        self.notenough = False
        self.offline = False
        self.soup = False
        if gender == 0:
            self.end_tags_main = "+solo"
            self.end_tags = "+-male+solo+-1boy+-genderswap"
            self.gender = "waifu"
            self.filename = "users_waifus.json"
            self.pic_limit = 30
        elif gender == 1:
            self.end_tags_main = "+solo+-1girl+-female"
            self.end_tags = "+solo+-1girl+-female+-genderswap"
            self.gender = "husbando"
            self.filename = "users_husbandos.json"
            self.pic_limit = 25

        blocked_waifus = file_to_list(
            os.path.join(settings['list_loc'],
                         'Blocked Waifus.txt'))
        self.disable = any([
            True for i in blocked_waifus if i in self.name])
        if self.disable:
            return None

        self.date = datetime.datetime.now().strftime("%Y-%m-%d")
        user_waifus_file = open(
            os.path.join(settings['list_loc'], self.filename), 'r',
            encoding='utf-8')
        self.user_waifus = json.load(user_waifus_file)
        user_waifus_file.close()
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
        for entry in self.user_waifus['users']:
            if self.name == entry['name']:
                self.override = True
                self.site_index = entry['web_index']
                break
        self.known = [["anarchy_stocking", "stocking_(psg)"],
                      ["hestia", "hestia_(danmachi!)"],
                      ["zelda", "princess_zelda"],
                      ["asuka", "asuka_langley"]]
        for [known, work] in self.known:
            if self.name == known or '_'.join(
                    reversed(self.name.split("_"))) == known:
                self.name = work
                self.override = True
                break
        if self.override:
            return None

    @staticmethod
    def clean_name(name):
        name = re.sub(
            '[<>"@#*:~\'$^%£]', '', name).strip()
        name = re.sub(' +', ' ', name).replace(" ", "_").lower()
        name = name.replace("kancolle", "kantai_collection")
        return name

    @staticmethod
    def reverse_name(name):
        name = name.split("_")
        name = '_'.join(reversed(name))
        return name

    def get_soup(self, site):
        if site == 0:
            cookie_file = settings['secret_key'] + "-sankakucomplex.txt"
            url_search = "https://chan.sankakucomplex.com/?tags="
        elif site == 2:
            cookie_file = settings['secret_key'] + "-safebooru.txt"
            a = "http://safebooru.org/"
            url_search = a + "index.php?page=post&s=list&tags="
        tags = self.name + self.end_tags
        if site == 0 or site > 2:
            tags += "+rating:safe"
        url = url_search + tags
        return scrape_site(url, cookie_file)

    def check_possible_names(self):
        possible_names = []
        if self.site == 0:
            names = self.soup.find_all('li',
                                       attrs={'class': 'tag-type-character'})
            for a in names:
                name = a.next.text
                name = name.title()
                if " " not in name:
                    name += " $"
                    possible_names.append(name)
        elif self.site == 2:
            names = self.soup.find_all('li',
                                       attrs={'class': 'tag-type-character'})
            for a in names:
                name = a.findNext('a').findNext('a').findNext('a').text
                name = name.title()
                if " " not in name:
                    name += " $"
                    possible_names.append(name)
        if not possible_names:
            return False
        if self.name.lower() + " $" in list(map(str.lower, possible_names)):
            return True
        help_eng = "%sRegister one of these names:" % self.gender.title()
        help_frn = "%sRegister un de ces noms:" % self.gender.title()
        help_spn = ""
        name_list_string = '\n'.join(possible_names)
        end_eng = """Don't see the name you are looking for here?
Read the help:
http://ace3df.github.io/AcePictureBot/commands/"""
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
        return m

    def is_name(self):
        # Make sure they're not registering a show
        # Check if they are trying to register a show name
        if self.soup.find('div', text="No matching posts"):
            return False
        html_tags = self.soup.find_all(
            'li', class_="tag-type-character")
        tags = []
        if self.site == 0:
            for tag in html_tags:
                tag = str(tag.text).split(" (?)")[0].replace(" ", "_")
                tags.append(tag)
        elif self.site == 2:
            for tag in html_tags:
                tag = tag.findNext('a').findNext('a').findNext('a').text
                tags.append(tag.replace(" ", "_"))

        if self.name in tags:
            return True
        return False

    def has_enough_imgs(self, site, reversed_search=False):
        if self.site == 0:
            try:
                post_count = self.soup.find(
                    'span', attrs={'class': 'tag-type-none'}).text
                post_count = int(post_count.replace(",", ""))
            except:
                post_count = int(len(
                    self.soup.find_all('img', attrs={'class': 'preview'})))
        elif self.site == 2:
            post_count = int(len(
                self.soup.find_all('span', attrs={'class': 'thumb'})))
        if post_count >= self.pic_limit:
            return post_count
        else:
            self.notenough = True
            return False

    def save_to_file(self):
        template = {"twitter_id": self.user_id,
                    "twitter_handle": self.username,
                    "name": self.name,
                    "subscribed": self.subscribe,
                    "tags": self.end_tags_main,
                    "web_index": self.site,
                    "date": self.date}
        self.user_waifus["users"].append(template)
        user_waifus_file = open(
            os.path.join(settings['list_loc'], self.filename), 'w',
            encoding='utf-8')
        json.dump(self.user_waifus, user_waifus_file, indent=2, sort_keys=True)
        user_waifus_file.close()

    def start(self):
        self.site = 0
        if config_get('Websites', 'sankakucomplex') == "False":
            self.site = 2
        self.soup = self.get_soup(self.site)
        if "error" in str(self.soup):
            self.TEMP_bug = True
            return self.TEMP_bug
        if not self.soup:
            self.offline = True
            return self.offline
        if "_" not in self.name and "$" not in self.org_name:
            self.multinames = self.check_possible_names()
            if isinstance(self.multinames, str):
                return self.multinames
            self.multinames = False
        if not self.is_name():
            if "(" in self.name:
                self.noimages = True
                return self.noimages
            self.name = self.reverse_name(self.name)
            self.soup = self.get_soup(0)
            if not self.soup:
                self.offline = True
                return self.offline
            if not self.is_name():
                self.noimages = True
                return self.noimages
        if not self.has_enough_imgs(0):
            return self.notenough
        self.save_to_file()
