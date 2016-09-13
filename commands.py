from datetime import datetime, timedelta
import random
import json
import ast
import os
import re

try:
    from config import help_urls
except ImportError:
    help_urls = dict()
try:
    from config import settings
except ImportError:
    settings = dict()
from decorators import command
from functions import (yaml_to_list, slugify, get_media, get_media_online,
                       return_page_info, create_otp_image, make_paste,
                       write_user_ignore_list, handle_reply, append_json,
                       filter_per_series, connect_token, scrape_website,
                       append_warnings, patreon_reapeat_for)

from bs4 import BeautifulSoup


@command("waifu", aliases=["husbando"])
def waifu(ctx, gender=None, search_for=None, is_otp=False):
    if ctx.command == "waifu" or gender == "waifu":
        list_name = "Waifu"
        end_tag = ["1girl", "solo"]
    else:
        list_name = "Husbando"
        end_tag = ["-1girl", "-female", "1boy", "solo"]
    result = ()
    path = os.path.join(ctx.bot.config_path, '{} List.yaml'.format(list_name))
    char_list = yaml_to_list(path, list_name.lower())
    # This is used so they can't get aroun dbeing limited with x cmd
    # Plus to the odd series to make people actually use other cmds 😠.
    ignore = ["high-school-dxd", "love-live",
              "aoki-hagane-no-arpeggio", "kantai-collection",
              "aikatsu", "akb0048", "idolmaster",
              "idolmaster-cinderella-girls"]
    matched = []
    if search_for is None:
        search_for = ctx.args
    if len(search_for) >= 5 and slugify(search_for) not in ignore:
        result = filter_per_series(char_list, search_for, 4)
    if not result:
        result = random.choice(char_list)
    name = re.sub("[\(\[].*?[\)\]]", "", result[0]).strip()  # Remove () and []
    series = result[1].get('series', None)
    otp_image = result[1].get('otp image', None)
    if is_otp:
        return name, series, otp_image
    start_path = settings.get('image_location', os.path.join(os.path.realpath(__file__), 'images'))
    path_name = os.path.join(start_path, list_name, slugify(result[0]))
    end_tag.append(name.replace(" ", "_"))
    reply_text = "Your {} is {} ({})".format(list_name, name, series)
    media_args = {'tags': end_tag}
    reply_media = get_media(path=path_name, ctx=ctx, media_args=media_args)
    return reply_text, reply_media


@command("shipgirl",
    aliases=["idol", "touhou", "vocaloid", "sensei", "senpai",
             "kouhai", "imouto", "shota", "onii", "onee",
             "monstergirl", "tankgirl", "witchgirl", "granblue"],
    patreon_aliases=["yandere", "tsundere"])
def random_list(ctx):
    # Male only lists.
    male_lists = ["shota", "onii"]
    # Both female and male can be under these.
    special_male_lists = ["idol", "sensei", "senpai", "kouhai", "yandere", "tsundere"]
    # Simple way to make sure to not load male list if one of these are used.
    possible_search = ["love", "idolmaster", "cinderella",
                       "akb0048", "wake", "aikatsu"] 
    # List of lists that don't need to show the series.
    ignore_series_lists = ["shipgirl", "touhou", "witchgirl", "tankgirl", "vocaloid"]
    list_name = "Waifu"
    end_tag = ["1girl", "solo"]
    if ctx.command in special_male_lists\
        and ("male" in ctx.args and not "female" in ctx.args)\
        or ctx.command in male_lists:
        list_name = "Husbando"
        end_tag = ["-1girl", "-female", "1boy"]
    elif ctx.command in special_male_lists\
        and not ("female" in ctx.args)\
        and not (any(show in ctx.args for show in possible_search)):
        random_gender = random.randint(0, 10)
        if random_gender > 7:
            list_name = "Husbando"
            end_tag = ["-1girl", "-female", "1boy"]
    result = ()
    search_for = ""
    show_series = False if ctx.command in ignore_series_lists else True
    support_otp = False
    # Special per list stuff
    if ctx.command == "shipgirl":
        # Default shipgirl to kantai collection only
        search_for = "Kantai Collection"
        support_otp = True
        if "all" in ctx.args.lower():
            search_for = ""
        elif "aoki" in ctx.args.lower():
            search_for = "Aoki Hagane no Arpeggio"
    elif ctx.command == "idol":
        args = ctx.message.lower().replace("!", "").replace("@", "a")
        if "love live sunshine" in args:
            search_for = "Love Live! Sunshine!!"
        elif "love live" in args:
            search_for = "Love Live!"
            support_otp = True
        elif "idolmaster" in args:
            search_for = "Idolmaster"
        elif "cinderella" in args:
            search_for = "Idolmaster Cinderella Girls"
        elif "akb0048" in args:
            search_for = "AKB0048"
        elif "wake up" in args:
            search_for = "Wake Up Girls!"
        elif "aikatsu" in args:
            search_for = "Aikatsu!"
    elif ctx.command == "onee" or ctx.command == "onii":
        ctx.command = ctx.command + "-chan"
    if support_otp and "otp" in ctx.message.lower():
        list_name = "otp"
    path = os.path.join(ctx.bot.config_path, '{} List.yaml'.format(list_name))
    char_list = yaml_to_list(path, ctx.command.lower())
    if search_for:
        result = filter_per_series(char_list, search_for, 4)
    if not result:
        result = random.choice(char_list)
    series = result[1].get('series', None)
    otp_image = result[1].get('otp image', None)
    start_path = settings.get('image_location', os.path.join(os.path.realpath(__file__), 'images'))
    if list_name == "otp":
        name_one, name_two = result[0].split("(x)")
        end_tag = ["2girls", "yuri", name_one.replace(" ", "_"), name_two.replace(" ", "_")]
        list_title = ctx.command.title() + " OTP"
        name = "{} x {}".format(re.sub("[\(\[].*?[\)\]]", "", name_one).strip(),
                                re.sub("[\(\[].*?[\)\]]", "", name_two).strip())
        path_name = os.path.join(start_path, list_name, slugify(name))
    else:
        list_title = ctx.command.title()
        name = re.sub("[\(\[].*?[\)\]]", "", result[0]).strip()  # Remove () and []
        end_tag.append(result[0].replace(" ", "_"))
        path_name = os.path.join(start_path, list_name, slugify(result[0]))
    if ctx.command == "granblue":
        reply_text = "{} has joined your party!".format(name)
    else:    
        reply_text = "Your {} is {}{}".format(
            list_title.replace("-C", "-c"),  # w/e
            name,
            "" if not show_series else " ({})".format(series))
    media_args = {'tags': end_tag}
    reply_media = get_media(path=path_name, ctx=ctx, media_args=media_args)
    return reply_text, reply_media


@command("otp", patreon_aliases=["harem"])
def otp(ctx):
    args = ctx.args.lower()
    max_harem = random.randint(3, 5)
    is_harem = True if ctx.command == "harem" else False
    otp_genders = []
    if "yuri" in args:
        args = args.replace("yuri", "")
        end_msg = "Yuri "
        otp_genders = list("waifu" for x in range(2))
        if is_harem:
            for person in range(0, max_harem):
                otp_genders.append("waifu")
    elif "yaoi" in args:
        args = args.replace("yaoi", "")
        end_msg = "Yaoi "
        otp_genders = list("husbando" for x in range(2))
        if is_harem:
            for person in range(0, max_harem):
                otp_genders.append("husbando")
    else:
        end_msg = ""
        if is_harem:
            for person in range(0, max_harem):
                otp_genders.append("waifu" if random.randint(0, 10) < 7 else "husbando")
        else:
            otp_genders.append("waifu")
            otp_genders.append("husbando")
    if is_harem:
        end_msg = "Harem " + end_msg
    search_for = [args.strip()]
    safe_loop = 0
    if "(x)" in args:
        search_for = [x.strip() for x in args.split("(x)")]
        if len(search_for) > len(otp_genders):
            search_for = search_for[0:len(otp_genders)]
    results = []
    loop_num = 0
    for gender in otp_genders:
        try:
            search = search_for[loop_num]
        except IndexError:
            search = random.choice(search_for)
        safe_loop = 0
        while True:
            if safe_loop == 10:
                break
            elif safe_loop == 5:
                search = ""
            name, series, image = waifu.callback(ctx, gender=gender, 
                                                search_for=search, is_otp=True)
            result = [name, series, image]
            safe_loop += 1
            if result not in results:
                break
        results.append(result)
        loop_num += 1
    end_msg_names = ""
    series_list = []
    for result in results:
        if result == results[-1]:
            msg_add = result[0]
        else:
            msg_add = result[0] + " and "
        end_msg_names += msg_add
        if result[1] not in series_list:
            series_list.append(result[1])
    # Werid way but this is good enough of not duping series name in text
    end_msg_series = "(" + ' / '.join(series_list) + ")"
    reply_text = "Your {}OTP is {} {}".format(end_msg, end_msg_names, end_msg_series)
    reply_media = create_otp_image(results)
    if len(reply_text) > ctx.bot.source.character_limit:
        reply_text = reply_text.split("(")[0].strip()
    return reply_text, reply_media


@command("pictag", patreon_only=True)
def pictag(ctx):
    """ Search Safebooru or Gelbooru and return random results.
    Patreon supporter only command.
    """
    repeat_for = patreon_reapeat_for(ctx)
    args = ctx.args.replace("nsfw", "")
    if repeat_for > 1:
        to_replace = re.search(r'\d +', args[0:3]).group()
        args = args.replace(to_replace, "", 1)
    tags = [tag.strip() for tag in args.split(" ")]
    if len(tags) > 5:
        return (("Sorry, websites don't allow more than 5 tags to be searched!\n"
                 "Use _ to connect words!"), False)
    reply_media = []
    for x in range(0, repeat_for):
        media_args = {'tags': tags, 'random_page': True, 'return_url': ctx.bot.source.support_embedded}
        image = get_media_online(path=None, ctx=False, media_args=media_args)
        if not image:
            return ("Sorry, no images could be found! Try different tags!")
        reply_media.append(image)
    reply_text = "Result(s) for: {}".format(' '.join(tags))
    return reply_text, reply_media


@command("!airing")
def airing(ctx):
    if ctx.bot.source.name != "twitter" and not ctx.is_patreon:
        return ctx.bot.patreon_only_message()
    if len(ctx.args) <= 3:
        return False

    def find_show(url):
        soup = scrape_website(url)
        if not soup:
            return "Sorry can't connect to livechart.me !"
        show_list = soup.find_all('h3', class_="main-title")
        today = datetime.today() + timedelta(hours=-1)
        reply_text = False
        for show in show_list:
            if slugify(show.text) != slugify(ctx.args):
                continue
            episode_number = show.find_next('div', attrs={'class': "episode-countdown"})
            if show != episode_number.find_previous('h3'):
                return "{anime}\nNo air date set!".format(anime=show.text)
            episode_time = episode_number.find_next('time')['datetime'].replace("T", " ").replace("Z", "")
            next_ep_time = datetime.strptime(episode_time, '%Y-%m-%d %H:%M:%S') - today
            episode_number = re.findall(r'\d+', episode_number.text.split(":")[0])[0]
            hours, remainder = divmod(int(next_ep_time.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            days, hours = divmod(hours, 24)
            if days < 0:
                reply_text = ("{anime}\nEpisode {episode} has recently aired!".format(anime=show.text, episode=episode_number))
                return reply_text
            if days:
                fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
            else:
                fmt = '{h} hours, {m} minutes, and {s} seconds'        
            reply_text = ("{anime}\n"
                          "Episode {episode} airing in {fmt}".format(
                          anime=show.text, episode=episode_number,
                          fmt=fmt.format(d=days, h=hours, m=minutes, s=seconds)))
            return reply_text

    reply_text = find_show("https://www.livechart.me/schedule/tv")
    if not reply_text:
        reply_text = find_show("https://www.livechart.me/")
    if not reply_text:
        return "No match found for '{}'".format(ctx.args)
    return reply_text


@command("connect", only_allow=["twitter"])
def connect(ctx):
    if len(ctx.args) < 5:
        reply_text = "You haven't given a source to connect to! Example: 'connect discord token_here'"
        return reply_text
    result = ctx.args.split(" ", 2)
    if len(result) != 2:
        reply_text = "You haven't given either a source or your token! Example: 'connect discord token_here'"
        return reply_text
    to_source, token = result
    if ctx.bot.source.name in to_source or to_source not in settings.get('bot_sources', []):
        reply_text = "You have given an invalid source! Example: 'connect discord token_here'"
        return reply_text   
    reply_text = connect_token(ctx.user_id, token, ctx.bot.source.name, to_source)
    if not reply_text:
        reply_text = ("Invalid token!"
                      "\nSay MyWaifu on {} to get your token!".format(to_source.title()))
        return reply_text
    return reply_text

 
@command("!source", patreon_only=True)
def direct_source(ctx):
    # Easy, simple way to handle Patreon version
    image_url = None
    if ctx.bot.source.name == "discord":
        if ctx.raw_data.attachments:
            image_url = ctx.raw_data.attachments[0]['url']
        else:
            message = ctx.message
    if image_url is None:
        found_results = re.findall('(https?:/)?(/?[\w_\-&%?./]*?)\.(jpg|png|gif|jpeg)', message)
        if not found_results:
            return False
        # I dunno regex
        image_url = found_results[0][0] + found_results[0][1] + "." + found_results[0][2]
    return source.callback(ctx, image_url=image_url)


@command("source", only_allow=["twitter"])
def source(ctx, image_url=None):
    is_gif = False
    if image_url is None and ctx.raw_data.get('extended_entities', []):
        if ctx.raw_data['extended_entities'].get('media', []):
            image_url = ctx.raw_data['extended_entities']['media'][0].get('media_url_https', None)
    if image_url is None:
        status_id = ctx.raw_data.get('in_reply_to_status_id', False)
        if not status_id:
            return "Are you sure you're asking for source on an image?"
        try:
            tweet = ctx.bot.api.lookup_status(id=status_id)
        except:
            # Probably twython.exceptions.TwythonError
            return "Unable to search for source! Try using SauceNAO: http://saucenao.com/"
        tweet_media = tweet[0]['entities'].get('media', [])
        if 'tweet_video_thumb' in str(tweet):
            is_gif = True
        if not tweet_media:
            return "Are you sure you're asking for source on an image?"
        image_url = tweet_media[0]['media_url_https']
    sauce_nao_url = u"http://saucenao.com/search.php?urlify=1&url=" + image_url
    url = "http://iqdb.org/?url=" + image_url
    soup = scrape_website(url)
    if not soup or soup is None:
        return "Unable to search for source! Try using SauceNAO: " + sauce_nao_url
    best_match = soup.find('th', text="Best match")
    if best_match is None:
        return "No relevant source information found!\n" + sauce_nao_url
    bm_a = best_match.find_next('a')
    if bm_a is None:
        return "No relevant source information found!\n" + sauce_nao_url
    allow_hosts = ["sankaku", "danbooru"]
    if not any(host in bm_a['href'] for host in allow_hosts):
        # Try to find next best thing
        other_sources = soup.find_all('th', text="Additional match")
        for source in other_sources:
            if any(host in source.find_next('a')['href'] for host in allow_hosts):
                bm_a = source.find_next('a')
                break
    if bm_a is None:
        return "No relevant source information found!\n" + sauce_nao_url
    url = bm_a['href']
    if not url.startswith("http"):
        url = "https:" + url
    soup = scrape_website(url)
    if not soup:
        return "Unable to search for source! Try using SauceNAO: " + sauce_nao_url
    artist = None
    series = None
    characters = None
    if "sankakucomplex" in url:
        artist_html = soup.find_all('li', attrs={'class': 'tag-type-artist'})
        if artist_html:
            artist = ', '.join([tag.find_all('a', attrs={'itemprop': 'keywords'})[0].text.title() for tag in artist_html])
        series_html = soup.find_all('li', attrs={'class': 'tag-type-copyright'})
        if series_html:
            series = ', '.join([tag.find_all('a', attrs={'itemprop': 'keywords'})[0].text.title() for tag in series_html])
        characters_html = soup.find_all('li', attrs={'class': 'tag-type-character'})
        if characters_html:
            characters = ', '.join([tag.find_all('a', attrs={'itemprop': 'keywords'})[0].text.title() for tag in characters_html])
    elif "danbooru" in url:
        artist_html = soup.find('li', attrs={'class': 'category-1'})
        if artist_html:
            artist = ', '.join([tag.text.title() for tag in artist_html.find_all('a', attrs={'class': 'search-tag'})])
        series_html = soup.find('li', attrs={'class': 'category-3'})
        if series_html:
            series = ', '.join([tag.text.title() for tag in series_html.find_all('a', attrs={'class': 'search-tag'})])
        characters_html = soup.find('li', attrs={'class': 'category-4'})
        if characters_html:
            characters = ', '.join([tag.text.title() for tag in characters_html.find_all('a', attrs={'class': 'search-tag'})])
    else:
        return "Unable to search for source! Try using SauceNAO: " + sauce_nao_url
    if artist is None and series is None and characters is None:
        return "No relevant source information found!\n" + sauce_nao_url
    reply_list = []
    if artist:
        reply_list.append("By: {}".format(artist))
    if series:
        reply_list.append("From: {}".format(series))
    if characters:
        reply_list.append("Character(s): {}".format(characters))
    if is_gif:
        reply_list.append("*Source is a gif so this could be inaccurate.")
    reply_text = '\n'.join(reply_list)
    if (len(reply_text) + 23) > ctx.bot.source.character_limit:
        paste_link = make_paste(reply_text, url)
        reply_text = "Source infomation is too long: " + paste_link
    return reply_text + "\n" + sauce_nao_url


@command("mywaifu data", aliases=["myhusbando data"])  # Test to make sure this actually works
def mywaifudata(ctx):
    if "waifu" in ctx.command:
        list_name = "Waifu"
    else:
        list_name = "Husbando"
    if not ctx.user_ids.get('twitter', False):
        reply_text = "You don't have your account linked to Twitter!"
        return reply_text
    user_path = os.path.join(ctx.bot.config_path, 'Users', '{}Register'.format(list_name))
    if not os.path.exists(user_path):
        os.makedirs(user_path)
    user_file = os.path.join(user_path, ctx.user_ids['twitter'] + ".json")
    if not os.path.isfile(user_file):
        reply_text = "Have you used {}Register before?".format(list_name)
        return reply_text
    with open(user_file, 'r', encoding="utf-8") as f:
        user_data = json.load(f)
    clearn_name = re.sub("[\(\[].*?[\)\]]", "", user_data[0]['name'].replace("_", " ").title()).strip()
    m = "You first registered {} on {}!\n".format(clearn_name, user_data[0]['date'])
    m_append = []
    if len(user_data) > 1:
        for entry in user_data[1:]:
            clean_name = re.sub("[\(\[].*?[\)\]]", "", entry['name'].replace("_", " ").title()).strip()
            m_append.append("{} on {}".format(clean_name, entry['date']))
    reply_text = m + '\n'.join(m_append)
    if (len(reply_text) + 23) > ctx.bot.source.character_limit:
        paste_title = "{user} {gender} Data".format(user=ctx.user_ids['twitter'], gender=list_name)
        paste_link = make_paste(reply_text, paste_title)
        reply_text = "Your {}Register data: {}".format(list_name, paste_link)
    return reply_text


@command("mywaifu", aliases=["myhusbando"])
def mywaifu(ctx):
    if "waifu" in ctx.command:
        list_name = "Waifu"
    else:
        list_name = "Husbando"
    if not ctx.user_ids.get('twitter', False):
        # No twitter account connected.
        url_help = help_urls.get('mywaifu_connect_{}'.format(ctx.bot.source.name), False)
        reply_text = ("Couldn't find your {gender}, "
                      "register your {gender} on Twitter!"
                      "{url_help}".format(gender=list_name,
                                                    url_help="\nFollow: " + url_help if url_help else ""))
        return reply_text
    twitter_user_id = ctx.user_ids['twitter']
    if not ast.literal_eval(os.environ.get('gelbooru_online', 'True')) and\
       not ast.literal_eval(os.environ.get('safebooru_online', 'False')):
        if ctx and ctx.bot.source.name == "twitter":
            ctx.bot.check_rate_limit_per_cmd(ctx, remove=1)
        url_help = help_urls.get('waifuregister_websites_offline', False)
        reply_text = ("Websites are offline to get you your {}!\n"
                      "Try again later!{}".format(list_name,
            "\nHelp: " + url_help if url_help else ""))
        return reply_text
    repeat_for = patreon_reapeat_for(ctx)
    user_file = os.path.join(ctx.bot.config_path, "Users {}Register.json".format(list_name))
    if not os.path.isfile(user_file):
        reply_text = ("I don't know who your {gender} is!\n"
                      "Use {gender}Register or try tweeting '{gender}'!".format(gender=list_name))
        return reply_text
    else:
        with open(user_file, 'r', encoding="utf-8") as f:
            user_reigster_list = json.load(f)
    user_entry = [user for user in user_reigster_list if user['twitter_id'] == twitter_user_id]
    if not user_entry:
        # No waifu registered
        reply_text = ("I don't know who your {gender} is!\n"
                      "Use {gender}Register or try tweeting '{gender}'!".format(gender=list_name))
        return reply_text
    user_entry = user_entry[0]
    skip_already_used = False
    if "my{}+".format(list_name.lower()) in ctx.message.lower():
        skip_already_used = True
    elif "my{}-".format(list_name.lower()) in ctx.message.lower():
        write_user_ignore_list(ctx.user_id, ctx.bot.source.name, clear=True)
    start_path = settings.get('image_location', os.path.join(os.path.realpath(__file__), 'images'))
    path_name = os.path.join(start_path, list_name, slugify(user_entry['name'].replace("_", " ")))
    tags = [user_entry['name']] + user_entry['tags'].split("+")
    clean_name = re.sub("[\(\[].*?[\)\]]", "", user_entry['name'].replace("_", " ").title()).strip()
    reply_text = ""
    if ctx.bot.source.name == "twitter":
        if datetime.now().isoweekday() == 3:
            reply_text = "#{0}Wednesday".format(list_name)
    else:
        reply_text = "{gender} is {name}".format(gender=list_name, name=clean_name)
    reply_media = []
    for x in range(0, repeat_for):
        media_args = {'ignore_used': skip_already_used}
        if ctx.bot.source.allow_new_mywaifu:
            media_args = {'tags': tags, 'random_page': True, 'return_url': ctx.bot.source.support_embedded,
                          'ignore_used': skip_already_used}
        image = get_media(path=path_name, ctx=ctx, media_args=media_args)
        if image:
            reply_media.append(image)
        if not reply_media:
            if ctx.bot.source.allow_new_mywaifu:
                if ctx and  ctx.bot.source.name == "twitter":
                    ctx.bot.check_rate_limit_per_cmd(ctx, remove=1)
                url_help = help_urls.get('mywaifu_no_image', False)
                reply_text = ("Failed to grab a new image!\n"
                              "The image websites could be offline.\n"
                              "Try again later!{}".format(
                    "\nHelp: " + url_help if url_help else ""))
            else:
                reply_text = ("Failed to grab a new image!\n"
                              "Use the command on Twitter to help the bot store more images!\n"
                              "You can also use My{gender}+ to skip checking for an already used image"
                              " or My{gender}- to start from fresh!".format(gender=list_name))
            if len(reply_media) < 1:
                return reply_text
            break
    return reply_text, reply_media


@command("waifuregister", aliases=["husbandoregister"], only_allow=["twitter"])
def waifuregister(ctx):
    if "waifu" in ctx.command:
        list_name = "Waifu"
        end_tag = ["solo", "-1boy"]
        min_imgs = 30
    else:
        list_name = "Husbando"
        end_tag = ["-1girl", "-female", "1boy", "solo"]
        min_imgs = 25
    if not ast.literal_eval(os.environ.get('gelbooru_online', 'True')) and\
       not ast.literal_eval(os.environ.get('safebooru_online', 'False')):
        # Both websites are offline.
        ctx.bot.check_rate_limit_per_cmd(ctx, remove=1)
        url_help = help_urls.get('waifuregister_websites_offline', False)
        reply_text = ("Websites are offline to register your waifu!\n"
                      "Try again later!{}".format(
            "\nHelp: " + url_help if url_help else ""))
        return reply_text
    if ctx.args == "" or len(ctx.args) < 3:
        url_help = help_urls.get('waifuregister_no_name', False)
        reply_text = ("You forgot to include a name!{}".format(
            "\nHelp: " + url_help if url_help else ""))
        return reply_text
    if len(ctx.args) >= 40:
        return False
    # Clean the name and ready it for searching.
    name = ctx.args.lower().replace("+", "").replace("( ", "(").replace(" )", ")")
    name = re.sub('[<>"@#*~\'$%£]', '', name).strip()
    name = re.sub(' +', ' ', name).replace(" ", "_")
    # Help mass replace common differances.
    # TODO: move to file? this could get pretty big
    replace_help = {
        "kancolle": "kantai_collection",
        "hestia": "hestia_(danmachi!)",
        "zelda": "princess_zelda",
        "asuna": "asuna_(sao)",
        "rem": "rem_(re:zero)"
    }
    for i, j in replace_help.items():
        if name.lower() == i.lower():
            name = name.replace(i, j)
    # First see if they included a meme, if so ignore.
    config_path = settings.get('config_path', os.path.join(os.path.realpath(__file__), 'Configs'))
    blocked_waifus_file = os.path.join(config_path, 'Blocked Waifus.txt')
    with open(blocked_waifus_file, 'r', encoding="utf-8") as f:
        blocked_waifus = f.read().splitlines()
    if any(True for waifu in blocked_waifus if waifu in name):
        # They included banned name, silent warn and ignore.
        append_warnings(ctx.user_ids['twitter'], "twitter", "{}Register {}".format(list_name, name))
        return False
    # Everything is fine so far.
    new_entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "name": name,
        "subscribed": False,
        "tags": "+" + '+'.join(end_tag),
        "twitter_handle": ctx.screen_name,
        "twitter_id": ctx.user_ids['twitter'],
        "web_index": 0
    }
    # web_index will not be used now. 0 = gelbooru, 1 = safebooru, etc
    is_subbed = False
    user_reigster_list = []
    path = os.path.join(ctx.bot.config_path, "Users {}Register.json".format(list_name))
    if not os.path.isfile(path):
        user_reigster_list = []
    else:
        with open(path, 'r', encoding="utf-8") as f:
            user_reigster_list = json.load(f)
    # See if they're already registered, if true, remove.
    count = 0
    for entry in user_reigster_list:
        if str(entry['twitter_id']) == ctx.user_ids['twitter']:
            """if entry['name'] == name:
                                                    # Reregistering, cheat them to use "-MyWafiu"
                                                    ctx.args = "-"
                                                    args = mywaifu.callback(ctx)
                                                    return handle_reply(args)"""
            if entry['subscribed']:
                is_subbed = True
            user_reigster_list.pop(count)
            break
        count += 1
    # See if the name has already been registered before - 
    # so we can save on searching.
    entry = None
    override = False
    # TEMP OFF WHILE FIX NAMES
    """for entry in user_reigster_list:
                    if name == entry['name']:
                        override = True
                        break
                    elif '_'.join(reversed(name.split("_"))) == entry['name']:
                        new_entry['name'] = '_'.join(reversed(name.split("_")))
                        override = True
                        break"""
    if not override:
        # Check name to make sure it's not a series name, etc.
        search_url = "http://gelbooru.com/index.php?page=post&s=list&tags=rating:safe+"
        if not ast.literal_eval(os.environ.get('gelbooru_online', 'True')):
            search_url = "http://safebooru.org/index.php?page=post&s=list&tags="
        count_before_flip = 0
        is_flipped = False
        while True:
            tags = end_tag + [name]
            info = return_page_info(search_url + '+'.join(tags), True)
            if not info:
                # Low chance of happening while in the middle, but it can.
                ctx.bot.check_rate_limit_per_cmd(ctx, remove=1)
                url_help = help_urls.get('waifuregister_websites_offline', False)
                reply_text = ("Websites are offline to register your waifu!\n"
                              "Try again later!{}".format(
                    "\nHelp: " + url_help if url_help else ""))
                return reply_text
            series_lower = [text.strip().lower().replace(" ", "_") for text in info.get('series', [])]
            artists_lower = [text.strip().lower().replace(" ", "_") for text in info.get('artists', [])]
            characters_lower = [text.strip().lower().replace(" ", "_") for text in info.get('characters', [])]
            if any(text == name for text in series_lower) \
            or any(text == name for text in artists_lower):
                # Uses a name that is a series
                url_help = help_urls.get('waifuregister_no_images', False)
                reply_text = ("No images found for '{}'!{}".format(
                              ctx.args, "\nHelp: " + url_help if url_help else ""))
                return reply_text
            if "_" not in name:
                if not any(text == name for text in characters_lower):
                    # Found multi single names, return help
                    found = [text.replace("_", " ").title() for text in characters_lower if name in text]
                    if len(found) > 1:
                        url_help = help_urls.get('waifuregister_no_images', False)
                        help_string = """English: {gender}Reigster one of these names!
    French: {gender}Register un de ces noms!
    Spanish: {gender}Register!

    {found_names}
    {help_url}
    """.format(
        gender=list_name,
        found_names='\n'.join(found),
        help_url="" if not url_help else "\nDon't see the name you are looking for here?\nHelp: " + url_help)
                        paste_link = make_paste(help_string, name)
                        reply_text = "More than one name was found: " + paste_link
                        return reply_text
            # Check if there are any images
            img_count = int(info.get('image_count', 0))
            if not is_flipped:
                # Store how many before flip
                count_before_flip = img_count
            if not any(text == name for text in characters_lower):
                img_count = 0
            if img_count < min_imgs:
                # No images at all.
                if not is_flipped:
                    # Flip the name and see if we can find images this way
                    is_flipped = True
                    name = '_'.join(reversed(name.split("_")))
                    continue
                # No images even when flipped.
                if count_before_flip > img_count:
                    # Before flip had images == pass not enough images found
                    img_count = count_before_flip
                if img_count == 0:
                    url_help = help_urls.get('waifuregister_no_images', False)
                    reply_text = ("No images found for '{}'!{}".format(
                                  ctx.args, "\nHelp: " + url_help if url_help else ""))
                else:
                    url_help = help_urls.get('waifuregister_no_images', False)
                    reply_text = ("Not enough images found for '{}'!{}".format(
                                  ctx.args, "\nHelp: " + url_help if url_help else ""))
                return reply_text
            if is_flipped:
                # Everything passed, flipped name is working.
                new_entry['name'] = name
            break
    # Everything passed!
    # First write to own stored history of registered people.
    user_path = os.path.join(ctx.bot.config_path, 'Users', '{}Register'.format(list_name))
    if not os.path.exists(user_path):
        os.makedirs(user_path)
    user_file = os.path.join(user_path, ctx.user_ids['twitter'] + ".json")
    append_json(user_file, new_entry)
    # Write to main file.
    user_reigster_list.append(new_entry)
    with open(path, 'w', encoding="utf-8") as f:
        json.dump(user_reigster_list, f, indent=2, sort_keys=True)
    args = mywaifu.callback(ctx)
    reply_text, reply_media = handle_reply(args)
    if not reply_media:
        reply_text = ("Your {gender} registerted but we couldn't get you a image right now\n"
                      "Try My{gender} later!".format(gender=list_name))
    return reply_text, reply_media
