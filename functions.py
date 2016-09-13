from collections import OrderedDict, Counter
from inspect import getmembers, isfunction
from datetime import datetime, timedelta
from http.cookiejar import LWPCookieJar
import xml.etree.ElementTree as ET
import subprocess
import mimetypes
import difflib
import pathlib
import hashlib
import random
import json
import time
import ast
import sys
import os
import re
import logging
from logging.handlers import TimedRotatingFileHandler

from config import settings, update, api_keys
from decorators import CommandGroup, Command

from PIL import Image
from yaml import load as yaml_load, dump as yaml_dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from bs4 import BeautifulSoup
import requests


class Source:
    def __init__(self, **attrs):
        self.name = attrs.get('name', '')
        if not self.name:
            raise Exception("No Source name set!")
        self.character_limit = attrs.get('character_limit', 140)
        self.allow_nsfw = attrs.get('allow_nsfw', False)
        self.support_embedded = attrs.get('support_embedded', False)
        self.download_media = attrs.get('download_media', False)
        self.allow_new_mywaifu = attrs.get('allow_new_mywaifu', False)
        self.max_filesize = attrs.get('max_filesize', 3145728)  # Bytes

    def __str__(self):
        return self.name


class BotProcess(CommandGroup):

    def __init__(self, source):
        if not isinstance(source, Source):
            raise Exception("Bot Source isn't Source class!")
        self.source = source
        self.uptime = datetime.utcnow()
        self.commands_used = Counter()
        self.commands = OrderedDict()
        self.config_path = settings.get('config_path', os.path.join(os.path.realpath(__file__), 'Configs'))
        try:
            with open(os.path.join(self.config_path, 'Global Settings.json'), 'r', encoding="utf-8") as f:
                global_settings = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("Global Settings.json was not found in /configs/")
        try:
            with open(os.path.join(self.config_path, '{} Settings.json'.format(source.name.title())), 'r', encoding="utf-8") as f:
                source_settings = json.load(f)
        except FileNotFoundError:
            source_settings = {}
        self.settings = global_settings
        for item in source_settings.items():
            if not self.settings.get(item[0], False):
                self.settings[item[0]] = item[1]
            else:
                self.settings[item[0]] = {**self.settings[item[0]], **item[1]}
        self.mod_list = self.settings.get('mod_ids', [])
        self.patreon_list = self.settings.get('patreon_ids', [])
        if self.settings.get('datadog', False):
            import datadog
            options = {
                'api_key': self.settings['datadog']['api_key'],
                'app_key': self.settings['datadog']['app_key'],
                'statsd_host': self.settings['datadog']["statsd_host"],
                'statsd_port': self.settings['datadog']["statsd_port"]
            }
            datadog.initialize(**options)
            self.datadog = datadog

        import commands
        members = getmembers(commands)
        for name, member in members:
            if isinstance(member, Command):
                if member.parent is None:
                    if member.only_allow:
                        if self.source.name not in member.only_allow:
                            continue
                    self.add_command(member)
                continue

        default_rate_limits = self.settings.get('rate_limits', {})
        rates = default_rate_limits.get(self.source.name.lower(), {})
        if not rates:
            rates = default_rate_limits.get(
                'default',
                {"rate_seconds": 10800, "rate_per_user": 10})
        self.rate_limit = {'rates': OrderedDict(), **rates}
        self.log = self.get_logging()

    def get_logging(self):
        log_path = os.path.join(self.config_path, "Logs", self.source.name.title())
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        log = logging.getLogger(self.source.name)
        log.setLevel(logging.INFO)
        handler = TimedRotatingFileHandler(
            filename=os.path.join(log_path, '{}.log'.format(self.source.name.title())),
            encoding='utf-8', when='midnight')
        log.addHandler(handler)
        handler = logging.StreamHandler(sys.stdout)
        log.addHandler(handler)
        return log

    def patreon_only_message(self):
        reply_text = False
        if self.settings.get('use_patreon', False):
            p_url = self.settings.get('patreon_url', False)
            reply_text = ("This is a Patreon only command!"
                          "{}".format("\nFeel free to support us at: " + p_url if p_url else ""))
        return reply_text, False

    def on_command(self, ctx):
        if not ctx.command:
            return False, False
        command = ctx.command
        reply_text = None
        reply_media = None
        if self.commands[command].mod_only and not ctx.is_mod:
            # Mod only command, return nothing
            return False, False
        if (self.commands[command].patreon_only and not ctx.is_patreon)\
        or (command in self.commands[command].patreon_aliases and not ctx.is_patreon):
                return self.patreon_only_message()
        if update.get('auto_update', False):
            os.environ[update['is_busy_environ'] + self.source.name] = 'True'
        try:
            reply_text, reply_media = handle_reply(self.commands[command].callback(ctx))
        except Exception as e:
            # This is like this and messy for now as it shouldn't really happen
            # this way I can work on catching every problem for now
            import sys
            import traceback
            print(command)
            print(traceback.print_tb(e.__traceback__))
            quit()
            # The function broke somehow
            # TODO: record this
            pass
        self.commands_used[command] += 1
        if update.get('auto_update', False):
            os.environ[update['is_busy_environ'] + self.source.name] = 'False'
        return reply_text, reply_media

    def uses_command(self, text):
        """Check to see if text contains a command."""
        text = text.replace("🚢👧", "shipgirl").lower()
        command_list = list(self.commands.keys())
        command = [cmd for cmd in command_list if cmd in text]
        if command:
            # Only return last from list (as waifuregister conflict can happen with waifu)
            command = difflib.get_close_matches(text, command, n=1, cutoff=0.1)
            if command:
                command = command[0]
        if not command:
            return False
        return command

    def check_rate_limit(self, user_id, or_seconds=False, or_per_user=False):
        """Check to see if the user is under basic ratelimit."""
        current_time = datetime.now()
        if or_seconds:
            rate_seconds = or_seconds
        else:
            rate_seconds = self.rate_limit.get('rate_seconds', 10800)
        if or_per_user:
            rate_per_user = or_per_user
        else:
            # TODO: Move back to 15
            rate_per_user = self.rate_limit.get('rate_per_user', 10)
        user_rates = self.rate_limit['rates']

        if user_id in user_rates:
            # User is now limited.
            if ((current_time - user_rates[user_id][0])
                    .total_seconds() < rate_seconds)\
                and (user_rates[user_id][1] >= rate_per_user):
                return False
            # User limit is over.
            elif ((current_time - user_rates[user_id][0])
                    .total_seconds() >= rate_seconds):
                del user_rates[user_id]
            else:
                user_rates[user_id][1] += 1
        else:
            # User not found, add them and quickly go over removing old users.
            for person in list(user_rates):
                if ((current_time - user_rates[person][0])
                    .total_seconds() > rate_seconds):
                    del user_rates[person]
            user_rates[user_id] = [current_time, 1]
        self.rate_limit['rates'] = user_rates
        return True

    def check_rate_limit_per_cmd(self, ctx, remove=False):
        path = os.path.join(ctx.bot.config_path,
                            '{} User Ratelimits.txt'.format(ctx.bot.source.name))
        if not os.path.isfile(path):
            with open(path, 'w') as f:
                f.write('')
        while True:
            # Wait until file is not busy
            try:
                with open(path, 'r', encoding="utf-8") as f:
                    current_user_limits = f.read().splitlines()
                break
            except (IOError):
                # File is busy
                time.sleep(0.1)
        list_add = False
        file_changed = False
        tweet_warning = False
        template = "{0}||{1}||{2}||{3}||{4}||{5}"
        current_time = datetime.now().replace(microsecond=0)
        used_command = ctx.command.replace("waifu", "{GENDER}").replace("husbando", "{GENDER}")
        command_limit, command_time = ctx.bot.settings[
            'rate_limits']['commands'].get(used_command, [False, False])
        if not command_limit:
            command_limit, command_time = ctx.bot.settings[
            'rate_limits']['commands'].get('general', [6, 9])
        current_loop = 0
        for user in current_user_limits:
            user_data = user.split("||")
            user_id, handle, command, count, first_time, warning = user_data
            if user_id == ctx.user_id and command == ctx.command:
                if remove:
                    # Remove 1 or more usage from cmd
                    new_count = int(count) - remove
                    if new_count < 0:
                        new_count = 0
                    current_user_limits.pop(current_loop)
                    list_add = template.format(
                        user_id, handle,
                        command, str(new_count),
                        current_time, "False")
                    current_user_limits += [list_add]
                    file_changed = True
                    break
                if int(count) >= command_limit:
                    # User has hit the limit.
                    if (current_time - datetime.strptime(
                         first_time, '%Y-%m-%d %H:%M:%S'))\
                        >= timedelta(hours=int(command_time)):
                        # Limit is over, reset.
                        current_user_limits.pop(current_loop)
                        list_add = template.format(
                            user_id, handle,
                            command, "1",
                            current_time, "False")
                        current_user_limits += [list_add]
                        file_changed = True
                        break
                    if warning == "False":
                        # User is limited, tweet them a about it
                        current_user_limits.pop(current_loop)
                        list_add = template.format(
                            user_id, handle,
                            command, count,
                            current_time, "True")
                        current_user_limits += [list_add]
                        file_changed = True
                        tweet_warning = True
                        break
                    else:
                        # Still limited, return False.
                        return False
                else:
                    # User is not limited but in file.
                    current_user_limits.pop(current_loop)
                    list_add = template.format(
                            user_id, handle,
                            command, str(int(count) + 1),
                            first_time, "False")
                    current_user_limits += [list_add]
                    file_changed = True
                    break
            current_loop += 1
        if not list_add:
            # User is not in file.
            list_add = template.format(
                ctx.user_id, ctx.screen_name,
                ctx.command, "1",
                current_time, "False")
            current_user_limits += [list_add]
            file_changed = True

        if file_changed:
            # save to file
            while True:
                try:
                    with open(path, 'w', encoding="utf-8") as f:
                        f.write('\n'.join(current_user_limits))
                    break
                except (IOError):
                    # File is busy
                    time.sleep(1)
        if tweet_warning:
            elapsed = current_time - datetime.strptime(
                first_time, '%Y-%m-%d %H:%M:%S')
            tleft = timedelta(hours=int(command_time)) - elapsed
            hours, remainder = divmod(int(tleft.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            days, hours = divmod(hours, 24)
            if days:
                fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
            elif not days and hours:
                fmt = '{h} hours, {m} minutes, and {s} seconds'
            elif not days and not hours and minutes:
                fmt = '{m} minutes, and {s} seconds'
            else:
                fmt = '{s} seconds'
            msg = "You can not use {} for another {}"
            return msg.format(command, fmt.format(d=days, h=hours, m=minutes, s=seconds))
        return True

    def get_uptime(self):
        now = datetime.utcnow()
        delta = now - self.uptime
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        if days:
            fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
        else:
            fmt = '{h} hours, {m} minutes, and {s} seconds'
        return fmt.format(d=days, h=hours, m=minutes, s=seconds)


class UserContext:
    def __init__(self, **attrs):
        self.bot = attrs.pop('bot')
        self.screen_name = attrs.pop('screen_name')
        self.user_ids = {'twitter': attrs.pop('twitter_id', False),
                         'discord': attrs.pop('discord_id', False),
                         'twitch': attrs.pop('twitch_id', False),
                         'reddit': attrs.pop('reddit_id', False),
                         'facebook': attrs.pop('facebook_id', False)}
        self.user_id = list(filter(None, self.user_ids.values()))[0]
        self.command = attrs.pop('command')
        self.message = attrs.pop('message')
        self.args = self.clean_message(self.message)
        self.raw_data = attrs.pop('raw_data')
        self.is_mod = self.get_is_mod()
        # TODO: This is temp Until Monday
        self.is_patreon =  True  # self.get_is_patreon()
        self.get_other_ids()

    def clean_message(self, message):
        ignore_cmd_case = re.compile(re.escape(self.command), re.IGNORECASE)
        message = ignore_cmd_case.sub("", message)
        message = re.sub('(@[A-Za-z0-9_.+-]+)', ' ', message)
        message = re.sub('[<>"@#*~\'$%£]', '', message)
        return re.sub(' +', ' ', message).strip()

    def get_is_mod(self):
        if not self.bot.settings.get('mod_ids', {}):
            return False
        mod_ids = self.bot.settings['mod_ids'].get(self.bot.source.name, [])
        return self.user_ids.get(self.bot.source.name) in mod_ids

    def get_is_patreon(self):
        if not self.bot.settings.get('patreon_ids', {}):
            return False
        patreon_ids = self.bot.settings['patreon_ids'].get(self.bot.source.name, [])
        return self.user_ids.get(self.bot.source.name) in patreon_ids

    def get_other_ids(self):
        accounts = {}
        try:
            with open(os.path.join(self.bot.config_path, 'Connected Accounts.json'), 'r') as f:
                accounts = json.load(f)
        except FileNotFoundError:
            with open(os.path.join(self.bot.config_path, 'Connected Accounts.json'), 'w') as f:
                json.dump(accounts, f, sort_keys=True, indent=4)
        for account in accounts:
            if account.get(self.bot.source.name, False) and account[self.bot.source.name] == self.user_id:
                for source in account.items():
                    self.user_ids[source[0]] = source[1]
                return


def connect_token(user_id, token, from_source, to_source):
    tokens = {}
    config_path = settings.get('config_path', os.path.join(os.path.realpath(__file__), 'Configs'))
    with open(os.path.join(config_path, "Connect Tokens.json"), 'r') as f:
        tokens = json.load(f)
    if not tokens.get(token, False):  # Invalid token
        return False
    connected_user_id = tokens.pop(token)
    try:
        with open(os.path.join(config_path, 'Connected Accounts.json'), 'r') as f:
            accounts = json.load(f)
    except FileNotFoundError:
            accounts = {}
    # TODO: Support muilti conencts
    """
    @a connect discord token
    {
        "discord": "ABC1TWOTHREE"
    }
    """
    accounts.append({from_source: user_id,
                     to_source: connected_user_id})
    with open(os.path.join(config_path, 'Connected Accounts.json'), 'w') as f:
        json.dump(accounts, f, sort_keys=True, indent=4)
    with open(os.path.join(config_path, "Connect Tokens.json"), 'w') as f:
        json.dump(tokens, f, sort_keys=True, indent=4)
    return "You can now use MyWaifu / MyHusbando on {}!".format(to_source.title())


def create_token(screen_name, user_id, from_source, to_source):    
    config_path = settings.get('config_path', os.path.join(os.path.realpath(__file__), 'Configs'))
    try:
        with open(os.path.join(config_path, 'Connected Accounts.json'), 'r') as f:
            accounts = json.load(f)
    except FileNotFoundError:
            accounts = {}
    is_in_accounts = False
    count = 0
    for account in accounts:
        if account.get(from_source, False) and account[from_source] == user_id:
            is_in_accounts = True
            break
        count += 1
    if is_in_accounts:
        # TODO: Suggest disconnect discord, etc
        return "You already have an account linked!"
    #accounts.append({from_source: user_id})
    try:
        with open(os.path.join(config_path, 'Connect Tokens.json'), 'r') as f:
            tokens = json.load(f)
    except FileNotFoundError:
            tokens = {}
    new_token = None
    for token in tokens.items():
        if token[1] == user_id:
            new_token = token[0]
            break
    if new_token is None:
        new_token = ''.join(random.choice(list(slugify(screen_name)) +\
                                    list(from_source) +\
                                    list(map(str, range(0, 10)))) for _ in range(15)).lower().replace(" ", "")
        tokens[new_token] = user_id
    with open(os.path.join(config_path, "Connect Tokens.json"), 'w') as f:
        json.dump(tokens, f, sort_keys=True, indent=4)
    """with open(os.path.join(config_path, 'Connected Accounts.json'), 'w') as f:
                    json.dump(accounts, f, sort_keys=True, indent=4)"""
    msg = ("Link your account by tweeting to {twitter_account_url}"
           "\n@{twitter_account_handle} connect {source_name} {token}".format(
            twitter_account_url=settings.get('twitter_account_url', 'https://twitter.com/AcePictureBot'),
            twitter_account_handle=settings.get('twitter_account_url', 'AcePictureBot'),
            source_name=from_source, token=new_token))
    return msg


def filter_per_series(entry_list, search_for, needed_match=None):
    matched = []
    search_for = slugify(search_for).lower().strip()
    for entry in entry_list:
        slug_series = slugify(entry[1].get('series', '').lower().strip())
        if search_for == slug_series:
            matched.append(entry)
    if not matched:
        # No matches.
        return False
    if needed_match is not None:
        if len(matched) <= needed_match:
            # Not enough results.
            return False
    return random.choice(matched)


def file_to_list(file):
    """This is an updated version of parsing old lists.
        Not used now but keeping it just in case."""
    with open(file, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()
    lines = list(filter(None, lines))
    # Remove Commented lines
    lines = [line for line in lines if not line.startswith(
            "#") or line.startswith("\ufeff")]
    if not lines:
        # Empty file
        return []
    split_with = lines[0].count("||")
    if split_with == 0:
        return lines
    return [line.split("||") for line in lines]


def slugify(text):
    text = re.sub(r'\W+', '-', text.lower())
    return re.sub('\-$', '', text)


def yaml_to_list(file_path, filter_section):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            yaml_file = yaml_load(f.read(), Loader=Loader)
    except FileNotFoundError:
        raise FileNotFoundError("yaml file '{}' was not found!".format(file))
    if yaml_file is None:
        raise Exception("yaml file '{}' was empty!".format(file))
    # Only get the people if they're in filter_section
    return [char for char in list(
            yaml_file.items()) if filter_section in char[1].get('lists', [])]


def get_user_ignore_list(user_id, source="twitter"):
    config_path = settings.get('config_path', os.path.join(os.path.realpath(__file__), 'Configs'))
    ignore_file = os.path.join(config_path, 'Users', 'Ignore', source)
    if not os.path.exists(ignore_file):
        os.makedirs(ignore_file)
    ignore_file = os.path.join(ignore_file, user_id + ".txt")
    if not os.path.isfile(ignore_file):
        with open(ignore_file, 'w') as f:
            f.write('')
        ignore_list = []
    else:
        with open(ignore_file, 'r') as f:
            ignore_list = f.read().splitlines()
    return ignore_list


def write_user_ignore_list(user_id, source="twitter", ignore_list=[], clear=False):
    """ Write the new ignore_list to file
    clear can be used if the user wants to reset their own ignore_list."""
    config_path = settings.get('config_path', os.path.join(os.path.realpath(__file__), 'Configs'))
    ignore_file = os.path.join(config_path, 'Users', 'Ignore', source)
    if not os.path.exists(ignore_file):
        os.makedirs(ignore_file)
    ignore_file = os.path.join(ignore_file, user_id + ".txt")
    with open(ignore_file, 'w') as f:
        if clear:
            f.write('')
        elif ignore_list:
            f.write('\n'.join(ignore_list))
    return


def append_json(json_file, new_entry):
    data = []
    if os.path.isfile(json_file):
        with open(json_file, 'r', encoding="utf-8") as f:
            data = json.load(f)
    data.append(new_entry)
    with open(json_file, 'w', encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    return


def append_blocked(user_id, source, reason=""):
    """Used to completely ignore a user."""
    config_path = settings.get('config_path', os.path.join(os.path.realpath(__file__), 'Configs'))
    path = os.path.join(config_path, 'Blocked {} Users.txt'.format(source))
    if not os.path.isfile(path):
        with open(path, 'w') as f:
            f.write('')
    with open(path, 'r') as f:
        blocked_users = f.read().splitlines()
    line = "{0}:{1}".format(user_id, reason)
    blocked_users.append(line)
    with open(path, 'w') as f:
        f.write('\n'.join(blocked_users))
    return


def append_warnings(user_id, source, reason=""):
    # A simple warning for using a joke register or not following.
    # User will be added to the block list after 3 faults
    config_path = settings.get('config_path', os.path.join(os.path.realpath(__file__), 'Configs'))
    path = os.path.join(config_path, 'Warned {} Users.txt'.format(source))
    if not os.path.isfile(path):
        with open(path, 'w') as f:
            f.write('')
    with open(path, 'r', encoding="utf-8") as f:
        warned_users = f.read().splitlines()
    count = 0
    warning_count = 0
    to_pop = []
    blocked = False
    for warning in warned_users:
        line = warning.split(":")
        if str(line[0]) == str(user_id):
            to_pop.append(count)
            warning_count += 1
        if warning_count == 3:
            count = 0
            for pop in to_pop:
                warned_users.pop(pop - count)
                count += 1
            append_blocked(user_id, source=source, reason=reason)
            blocked = True
            break
        count += 1
    if not blocked:
        line = "{0}:{1}".format(user_id, reason)
        warned_users.append(line)
    with open(path, 'w', encoding="utf-8") as f:
        f.write('\n'.join(warned_users))
    return


def download_file(url, path=None, filename=None):
    if path is None:
        path = settings.get('default_dl_locaction', os.path.realpath(__file__))
    if filename is None:
        filename = url.split('/')[-1]
    local_filename = os.path.join(path, filename)
    try:
        r =  requests.get(url, stream=True, timeout=5)
    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
        return False
    if r.status_code != 200:
        return False
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024): 
            if chunk:
                f.write(chunk)
    return local_filename


def login_website(website, sess=None):
    if not sess:
        sess = requests.Session()
    user_data = {}
    form_data = {}
    if "gelbooru" in website:
        user_data['username'] = api_keys.get('gelbooru_username', '')
        user_data['password'] = api_keys.get('gelbooru_password', '')
        form_data['username'] = "user"
        form_data['password'] = "pass"
        cookie_file = "gelbooru_cookie.cookies"
        login_url = "http://gelbooru.com/index.php?page=account&s=login&code=00"
    sess.cookies = LWPCookieJar(cookie_file)
    try:
        sess.cookies.load()
        if not sess.cookies:
            raise Exception  # No valid cookies
    except (FileNotFoundError, Exception):
        payload = {
            form_data['username']: user_data['username'],
            form_data['password']: user_data['password'],
            'submit': form_data['Log+in']
        }
        sess.post(login_url, data=payload)
        sess.cookies.save()
    return sess


def scrape_website(url, sess=False, content_only=False):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'
    }
    try:
        if sess:
            r = sess.get(url, timeout=5, headers=headers)
        else:
            r = requests.get(url, timeout=5,  headers=headers)
    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
        return False
    if r.status_code != 200:
        # bad status_code
        return False
    if r.content == "":
        # Empty site
        return False
    if not content_only:
        return BeautifulSoup(r.content, 'html5lib')
    else:
        return r.content


def get_media_online(path=None, ctx=None, media_args={}, ignore_used=False):
    if path is not None and not os.path.exists(path):
        os.makedirs(path)
    ignore_list = []
    if ctx and not ignore_used:
        ignore_list = get_user_ignore_list(ctx.user_id, ctx.bot.source.name)
    tags = ""
    if isinstance(len(media_args.get('tags', [])), list) >= 8:
        # Too many tags. Safe way to not get rejected from websites.
        media_args['tags'] = media_args.get('tags', [])[0:6]
    if media_args.get('tags', []):
        tags = '%20'.join([tag.replace(" ", "_") for tag in media_args.get('tags', []) if tag is not ""])
    tags += r"%20rating:safe"
    username = ""
    password = ""
    user_data = ()
    form_data = ()
    website = None
    if ast.literal_eval(os.environ.get('gelbooru_online', 'True')):
        add_page = 1
        start_page = 0  # Sometimes page 0 and 1 are the same, can cause 2 requests.
        max_page = 10  # Don't go past this page.
        search_url = "http://gelbooru.com/index.php?tags={search}%20sort:score&pid={page}&page=dapi&s=post&q=index"
        page_id_url = "http://gelbooru.com/index.php?page=post&s=view&id={}"
        website = "gelbooru"
    elif ast.literal_eval(os.environ.get('safebooru_online', 'False')):
        add_page = 1
        start_page = 0
        max_page = 10
        search_url = "http://safebooru.org/index.php?tags={search}%20sort:score&pid={page}&page=dapi&s=post&q=index"
        page_id_url = "http://safebooru.org/index.php?page=post&s=view&id={}"
        website = "safebooru"
    with requests.Session() as sess:
        if user_data:
            sess = login_website(website, sess)
        soft_kill = 0
        post_media = None
        current_page = start_page
        if media_args.get('random_page', False):
            current_page = random.randint(start_page, max_page) * add_page  # Random page.
        while True:
            if soft_kill == 6:
                return False
            soft_kill += 1
            url = search_url.format(search=tags, page=current_page)
            soup = scrape_website(url, sess, True)
            if not soup:
                time.sleep(0.5)
                continue
            xml_parse = ET.fromstring(soup)
            entries = [post for post in xml_parse if post.tag == "post"]
            random.shuffle(entries)
            if media_args.get('return_count', False):
                if xml_parse.get('count', False):
                    return int(xml_parse.get('count'))
                return False
            if not entries:
                # No XML entries under "post"
                if xml_parse.get('count', False):
                    max_page = int(int(xml_parse.get('count')) / 100)
                if current_page == start_page:
                    return False
                elif current_page > start_page:
                    current_page -= add_page
                if soft_kill == 5:
                    current_page = start_page
                continue
            post = None
            safe_break = 0
            for post in entries:
                safe_break += 1
                if safe_break == 10:
                    # Don't want to go through too many entries
                    break
                post_media = post.attrib.get('file_url', False)
                media_hash = post_media.split('/')[-1].split('.')[0]
                post_id = post.attrib.get('id', False)
                post_tags = post.attrib.get('tags', '').strip().split(" ")
                if not post_media:
                    continue
                if not post_id:
                    continue
                if any(tag.lower() in settings.get('blacklist_tags', []) for tag in post_tags):
                    continue
                if media_hash in ignore_list:
                    continue
                else:
                    if any(tag in ["solo", "1girl", "1boy"] for tag in post_tags):
                        # This sucks but it's the only way.
                        # This will make sure only 1 charater is in the image-
                        # when the tag "solo"/"1girl"/"1boy" is used.
                        url = page_id_url.format(post_id)
                        a_break = 0
                        while True:
                            a_break += 1
                            if a_break == 3:
                                return False
                            soup = scrape_website(url, sess)
                            if not soup:
                                continue
                            break
                        if len(soup.find_all('li', attrs={'class': 'tag-type-character'})) > 2:
                            # Ignore images with more than 2 chars in it.
                            # I would like this to be 1 but there are a lot of
                            # chars that go under 2 names both being tagged in the image
                            time.sleep(0.25)
                            continue
                    break
            if not media_args.get('return_url', False):
                downloaded_media = download_file(post_media, path=path)
                if not downloaded_media:
                    continue
                media = compress_media(downloaded_media)
                if os.path.isfile(media) and ctx and os.path.getsize(media) > ctx.bot.source.max_filesize:
                    os.remove(media)
                    continue
            else:
                media = post_media
            if not media:
                continue   
            break  # Perfectly fine image, break to continue on.
    if post_media is not None and ignore_used is False:
        if post_media not in ignore_list and ctx:
            ignore_list.append(media_hash)
            if os.path.isfile(media):
                md5_hash = md5_file(media)
                ignore_list.append(md5_hash)
            write_user_ignore_list(ctx.user_id, ctx.bot.source.name, ignore_list)
    return media


def get_media_local(path, ctx=None, media_args={}):
    ignore_used = media_args.get('ignore_used', False)
    if not os.path.exists(path):
        os.makedirs(path)
        return False
    ignore_list = []
    if ctx and not ignore_used:
        ignore_list = get_user_ignore_list(ctx.user_id, ctx.bot.source.name)
    files = [p.as_posix() for p in pathlib.Path(path).iterdir() if p.is_file()]
    random.shuffle(files)
    media = None
    for file in files:
        md5_hash = md5_file(file)
        if md5_hash not in ignore_list:
            media = file
            break
    if media is not None and ignore_used is False:
        if media not in ignore_list and ctx:
            if os.path.isfile(media):
                md5_hash = md5_file(media)
                ignore_list.append(md5_hash)
            write_user_ignore_list(ctx.user_id, ctx.bot.source.name, ignore_list)
    return media


def get_media(path=None, ctx=False, media_args={}):
    """Uses get_media_local and if False, use get_media_online."""
    media = False
    if path is not None:
        media = get_media_local(path=path, ctx=ctx, media_args=media_args)
    if ctx and not ctx.bot.source.download_media:
        return media
    if not media and media_args:
        media = get_media_online(path=path, media_args=media_args, ctx=ctx, ignore_used=False)
    if not os.path.isfile(media):
        return False
    if os.path.isfile(media) and ctx and os.path.getsize(media) > ctx.bot.source.max_filesize:
        return False
    return media


def get_media_info(media):
    process = subprocess.Popen(
        ['ffmpeg',  '-i', media],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    stdout, stderr = process.communicate()
    return str(stdout)


def return_page_info(url, get_extra_info=False):
    # TODO: Add more info to return, no point now
    # doesn't support per post details yet
    info = {}
    login_with = None
    if "gelbooru" in url:
        login_with = "gelbooru"
    elif "safebooru" in url:
        login_with = "safebooru"
    with requests.Session() as sess:
        if login_with is None:
            sess = login_website(login_with, sess)
        soup = scrape_website(url, sess)
        if not soup:
            return False
        artists, characters, series, tags = [], [], [], []
        if "gelbooru" in url and "page=dapi" not in url:
            index_value = 3
            search_url = ("http://gelbooru.com/index.php?tags="
                          "{}%20rating:safe&pid=0&page=dapi"
                          "&s=post&q=index")
        elif "safebooru" in url and "page=dapi" not in url:
            index_value = 2
            search_url = ("http://safebooru.org/index.php?tags="
                          "{}%20rating:safe&pid=0&page=dapi"
                          "&s=post&q=index")
        if "gelbooru" in url or "safebooru" in url:
            artist_html = soup.find_all('li', attrs={'class': 'tag-type-artist'})
            if artist_html:
                artists = [tag.find_all('a')[index_value].text.title() for tag in artist_html]
            character_html = soup.find_all('li', attrs={'class': 'tag-type-character'})
            if character_html:
                characters = [tag.find_all('a')[index_value].text.title() for tag in character_html]
            series_html = soup.find_all('li', attrs={'class': 'tag-type-copyright'})
            if series_html:
                series = [tag.find_all('a')[index_value].text.title() for tag in series_html]
            if "s=list" in url and get_extra_info:
                tags = url.split("&tags=")[1]
                safe_break = 0
                while True:
                    safe_break += 1
                    if safe_break == 3:
                        return False
                    search_url = search_url.format(tags)
                    soup = scrape_website(search_url, sess, content_only=True)
                    if not soup:
                        time.sleep(0.5)
                        continue
                    xml_parse = ET.fromstring(soup)
                    break
                info['image_count'] = xml_parse.get('count')
        info['artists'] = artists
        info['characters'] = characters
        info['series'] = series
    return info

# TODO: Test this more
# Commonly get file not found convert_to .gif
def convert_media(media, convert_to):
    filename, file_extension = os.path.splitext(media)
    new_media = media.replace(file_extension, "_converted" + convert_to)
    if convert_to == ".gif":
        # Generate palette.png
        # TEMP
        return media
        cmd = ("ffmpeg -v warning -i {input} -vf "
               "fps=15,scale=320:-1:flags=lanczos,palettegen "
               "palette.png".format(input=media))
        process = subprocess.call(cmd)
        # Convert to gif
        cmd = ("ffmpeg -i {input} -i palette.png -filter_complex "
               "\"fps=10,scale=320:-1:flags=lanczos[x];[x][1:v]paletteuse\""
               " {output}".format(input=media, output=new_media))
        process = subprocess.call(cmd)
        os.remove("palette.png")
    elif convert_to == ".mp4":
        vf = "scale=720:trunc(ow/a/2)*2"
        cmd = "ffmpeg -y -i {} -vf \"{}\" {} ".format(media, vf, new_media)
        pipe = subprocess.call(cmd)
    elif convert_to == ".jpeg" or convert_to == ".png":
        with open(media, 'rb') as file:
            img = Image.open(file)
            ImageFile.MAXBLOCK = img.size[0] * img.size[1]
            img.save(new_media, quality=90, optimize=True)
    if media != new_media:
        # delete old media (keeping new_media)
        os.remove(media)
    return new_media


def compress_media(media):
    file_size = os.path.getsize(media) / 1000000  # bytes to MB
    if file_size > 50:
        # File size is way too big, compressing wont do much
        return False
    max_video_length = 60  # Seconds
    min_video_length = 8  # If less than, turn into gif (if no audio)
    convert_to = False
    has_audio = False

    if media.endswith(".webm"):
        # mimetypes doesn't support webm so just do it this way
        convert_to = ".mp4"
        stdout = get_media_info(media)
        if "Audio" in str(stdout):
            has_audio = True
        matches = re.search(r"Duration:\s{1}(?P<hours>\d+?):(?P<minutes>\d+?):(?P<seconds>\d+\.\d+?),", str(stdout), re.DOTALL).groupdict()
        if int(matches.get('hours', 0)) >= 1:
            return False
        video_seconds = (60 * int(matches.get('minutes', 0))) + int(float(matches.get('seconds', 0)))
        if video_seconds > max_video_length:
            return False
        elif video_seconds < min_video_length:
            if not has_audio:
                # No audio, convert to gif
                convert_to = ".gif"
    else:
        file_type = mimetypes.guess_type(media)[0]
        if file_type is None:
            # Can't guess file type, don't do anything
            return media
        imgs = ["image/png", "image/jpg", "image/jpeg"]
        if file_type in imgs:
            # Stop super long images from getting past
            with Image.open(media) as pil_image:
                width, height = pil_image.size
                max_size = -610
                min_size = 610
            if (width - height) <= max_size or (width - height) >= min_size:
                os.remove(media)
                return False
        if file_type == "image/gif":
            convert_to = ".gif"
        if file_type == 'video/mp4':
            # Get video length
            stdout = get_media_info(media)
            if "audio" in stdout:
                has_audio = True
            matches = re.search(r"Duration:\s{1}(?P<hours>\d+?):(?P<minutes>\d+?):(?P<seconds>\d+\.\d+?),", stdout, re.DOTALL).groupdict()
            if matches.get('hours', 0) >= 1:
                return False
            video_seconds = (60 * matches.get('minutes', 0)) + matches.get('seconds', 0)
            if video_seconds > max_video_length:
                return False
            elif video_seconds < min_video_length:
                # Check if file has audio
                if not has_audio:
                    # No audio, convert go gif
                    convert_to = ".gif"
    if not convert_to:
        # Media is fine, don't need to convert
        return media
    return convert_media(media, convert_to)


def create_otp_image(otp_results=[]):
    overlay = False
    if settings.get('otp_overlay_location', False):
        overlay = get_media_local(path=os.path.join(settings['otp_overlay_location']))
    path = settings.get('default_dl_locaction', os.path.realpath(__file__))
    filename = os.path.join(path, str(random.randint(0, 999)) + ".jpg")
    img_size = (225 * len(otp_results), 350)
    with Image.new("RGB", img_size) as otp_image:
        used_files = []  # To delete later.
        for result in otp_results:
            # check if file is in download folder first
            # split download link to get just the id then check
            temp_dl = download_file(result[2])
            if not temp_dl:
                return False
            used_files.append(temp_dl)
            with Image.open(temp_dl) as temp_img:
                otp_image.paste(temp_img, (225 * otp_results.index(result), 0))
        if overlay:
            with Image.open(overlay) as ol:
                overlay_open = ol.resize((img_size), Image.ANTIALIAS)
            otp_image.paste(overlay_open, (0, 0), mask=overlay_open)
        otp_image.save(filename)
    [os.remove(file) for file in used_files]
    return filename


def make_paste(text, title=""):
    post_url = "https://paste.ee/api"
    payload = {'key': api_keys['pasteee'],
               'paste': text,
               'description': title}
    headers = {'content-type': 'application/json'}
    r = requests.post(post_url,
                      data=json.dumps(payload),
                      headers=headers)
    return r.json()['paste']['link']


def handle_reply(args):
    """Handle the mess I've made."""
    reply_text = ""
    reply_media = []
    if isinstance(args, tuple):
        if len(args) == 1:
            reply_media = args[0]
        elif len(args) == 2:
            reply_text, reply_media = args
    else:
        reply_text = args
    if not isinstance(reply_media, list):
        reply_media = [reply_media]
    if reply_media:
        if not reply_media[0]:
            reply_media = False
    return reply_text, reply_media


def datadog_online_check(datadog_obj, check, host_name, response='Response: 200 OK'):
    while True:
        datadog_obj.api.ServiceCheck.check(
            check=check, host_name=host_name,
            status= datadog_obj.api.constants.CheckStatus.OK,
            message=response)
        time.sleep(5 * 60)


def patreon_reapeat_for(ctx):
    """Try to guess how many images they want (1 - 4) (Patreon only)."""
    if not ctx.is_patreon:
        return 1
    if len(ctx.args) == 1:
        a = r'\d+'
    else:
        # This is used mostly for pictag when it comes to "pictag 2 1girl"
        a = r'\d +'
    try:
        repeat_for = int(re.search(a, ctx.args[0:3]).group())
    except AttributeError:
        return 1
    # TODO: This is limited to 2 for now
    if repeat_for > 2:
        repeat_for = 2
    return repeat_for


def md5_file(file):
    hash_md5 = hashlib.md5()
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()