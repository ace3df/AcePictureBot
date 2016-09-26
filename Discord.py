from collections import Counter, OrderedDict
from operator import itemgetter
from datetime import datetime
import traceback
import random
import copy
import time
import json
import sys
import os
import re

from config import settings, discord_settings
from functions import (BotProcess, Source, UserContext,
                       datadog_online_check, create_token, slugify)

from bs4 import BeautifulSoup
from tabulate import tabulate
from discord.ext import commands
import discord
import asyncio
import aiohttp


prefix = discord_settings.get('command_prefix', ["!apb "])
discord_bot = commands.Bot(command_prefix=prefix, pm_help=None)
if not discord.opus.is_loaded():
    discord.opus.load_opus('libopus-0.x86')
discord_bot.remove_command("help")
attrs = {'name': 'discord', 'character_limit': 1000, 'support_embedded': True, 'download_media': False, 'allow_new_mywaifu': False}
bot = BotProcess(Source(**attrs))
settings_edits = [["active", "The bot is now online for this server!", "The bot is now offline for this server!"],
                  ["media", "The bot will now post media (images) when it can!", "The bot will now not post any media!"],
                  ["mention", "Users must now @Mention the bot to use commands!", "Users don't need to @Mention to use commands!"],
                  ["music game", "This server can now use the music game!", "This server can not start the music game!"],
                  ["blacklist", "", ""], ["whitelist", "", ""], ["mods", "", ""]]

async def change_settings(server_settings, message):
    new_settings = copy.deepcopy(server_settings)
    prefix_used = [pre for pre in prefix if message.content.startswith(pre)]
    args = ' '.join(message.content.lower().split(prefix_used[0], 1)).split()
    if len(args) < 2:
        return
    to_edit = [edit for edit in settings_edits if edit[0] in args[0]]
    if not to_edit:
        return
    to_edit = to_edit[0]
    to_edit_name, help_on, help_off = to_edit
    on_or_off = ["active", "mention", "media", "music game"]
    if to_edit_name in on_or_off:
        if "on" in args[1]:
            new_settings[to_edit_name] = True
        elif "off" in args[1]:
            new_settings[to_edit_name] = False
        else:
            msg = "{} Invalid setting! Use either 'on' or 'off'!".format(message.author.mention)#
            try:
                await discord_bot.send_message(message.channel, msg)
            except discord.errors.Forbidden:
                pass
            return
        msg = help_on if new_settings[to_edit_name] else help_off
    else:
        if to_edit_name == "mods":
            current = new_settings['mods']
            changes_add = []
            changes_removed = []
            for user in message.mentions:
                if user.id == message.server.owner.id:
                    continue
                if user.id in current:
                    current.remove(user.id)
                    changes_removed.append(user.name)
                else:
                    current.append(user.id)
                    changes_add.append(user.name)
        elif to_edit_name == "blacklist" or to_edit_name == "whitelist":
            current = new_settings[to_edit_name]
            changes_add = []
            changes_removed = []
            for chan in message.channel_mentions:
                if chan.id in current:
                    current.remove(chan.id)
                    changes_removed.append(chan.name)
                else:
                    current.append(chan.id)
                    changes_add.append(chan.name)
        new_settings[to_edit_name] = current
        msg = "{} Change List:\n```diff\n".format(to_edit_name.title())
        if changes_add:
            msg += '\n+ ' + '\n+ '.join(changes_add)
        if changes_removed:
            msg += '\n- ' + '\n- '.join(changes_removed)
        msg += "```"
    if new_settings.items() == server_settings.items():
        msg = "No settings changed!"
    else:
        filename = os.path.join(bot.config_path, 'Discord Servers', "{0.id}.json".format(message.server))
        with open(filename, 'w') as f:
            json.dump(new_settings, f, sort_keys=True, indent=4)
    try:
        await discord_bot.send_message(message.channel, msg)
    except discord.errors.Forbidden:
        try:
            await discord_bot.send_message(message.author, msg)
        except discord.errors.Forbidden:
            pass
        pass
    return


def get_server_settings(server):
    # Takes server discord object
    server_settings = {'active': True,
                       'music game': True,
                       'media': True,
                       'mention': False,
                       'blacklist': [],
                       'whitelist': [],
                       'mods': []}
    if server is None:
        server_settings['music game'] = False
        return server_settings
    path = os.path.join(bot.config_path, 'Discord Servers')
    if not os.path.exists(path):
        os.makedirs(path)
    filename = os.path.join(path, "{0.id}.json".format(server))
    if not os.path.isfile(filename):
        with open(filename, 'w') as f:
            json.dump(server_settings, f, sort_keys=True, indent=4)
    else:
        with open(filename, 'r') as f:
            server_settings = json.load(f)
    return server_settings


async def send_reply(reply_text, reply_media, ctx, server_settings):
    if not reply_text and not reply_media:
        # Silent return
        return
    message = ctx.raw_data
    command = ctx.command
    if command in ["mywaifu", "myhusbando"] or ctx.is_patreon_vip and command in ["myidol", "myotp"]:
        reply_text = "{0.author.mention}'s {1}".format(message, reply_text)
    else:
        reply_text = "{0} {1.author.mention} ".format(reply_text, message)
    destination = None
    if message.channel.is_private:
        destination = "Private Message"
    else:
        destination = "#{0.channel.name} ({0.server.name})".format(message)
    log_str = "{0.timestamp}: {0.author.name} in {1} [{2}]: {0.content}".format(message, destination, command)
    bot.log.info(log_str)
    try:
        if server_settings.get('media', True) and reply_media:
            count = 0
            for media in reply_media:
                if os.path.isfile(media):
                    with open(media, 'rb') as file:
                        if count == 0:
                            await discord_bot.send_file(message.channel, file, content=reply_text)
                        else:
                            await discord_bot.send_file(message.channel, file)
                else:
                    if count == 0:
                        reply_text = reply_text + " " + media
                        await discord_bot.send_message(message.channel, reply_text)
                    else:
                        await discord_bot.send_message(message.channel, media)
                count += 1
        else:
            await discord_bot.send_message(message.channel, reply_text)
    except discord.errors.Forbidden:
        return
    return


async def change_status():
    """Change the account's current game to text that will show tips and tricks."""
    custom_tips = bot.settings.get('custom_tips', [])
    cmd_tips = ["Try: " + a for a in bot.commands if not bot.commands[a].patreon_only or\
           a not in bot.commands[a].patreon_aliases or\
           a not in bot.commands[a].mod_only]
    complete_tips = custom_tips + cmd_tips
    await discord_bot.wait_until_ready()
    while not discord_bot.is_closed:
        for status in complete_tips:
            if isinstance(status, list):
                for a in status:
                    new_status = discord.Game(name=a, idle=False)
                    await discord_bot.change_status(game=new_status)
                    await asyncio.sleep(8)
            else:
                new_status = discord.Game(name=status, idle=False)
                await discord_bot.change_status(game=new_status)
            await asyncio.sleep(120)


@discord_bot.event
async def on_server_join(server):
    welcome_message = discord_settings.get('welcome_message', False)
    if not welcome_message:
        return
    channel = None
    for chan in server.channels:
        if chan.is_default:
            if chan.is_private:
                return
            channel = chan
            break
    if channel is None:
        return
    await client.send_message(channel, welcome_message.format(server.owner.mention))


@discord_bot.event
async def on_command_error(error, ctx):
    if isinstance(error, commands.NoPrivateMessage):
        await discord_bot.send_message(ctx.message.author, 'This command cannot be used in private messages.')
    elif isinstance(error, commands.DisabledCommand):
        await discord_bot.send_message(ctx.message.author, 'Sorry. This command is disabled and cannot be used.')
    elif isinstance(error, commands.CommandInvokeError):
        bot.log.info('In {0.command.qualified_name}:'.format(ctx))
        traceback.print_tb(error.original.__traceback__)
        bot.log.info('{0.__class__.__name__}: {0}'.format(error.original))


@discord_bot.event
async def on_command(command, ctx):
    message = ctx.message
    destination = None
    if message.channel.is_private:
        destination = 'Private Message'
    else:
        destination = '#{0.channel.name} ({0.server.name})'.format(message)
    bot.log.info('{0.timestamp}: {0.author.name} in {1}: {0.content}'.format(message, destination))


@discord_bot.event
async def on_message(message):
    if bot.settings.get('datadog', False) and bot.settings['datadog'].get('statsd_messages', False):
        bot.datadog.statsd.increment(bot.settings['datadog']['statsd_messages'])

    if message.author.id == discord_bot.user.id:
        destination = None
        if message.channel.is_private:
            destination = "Private Message"
        else:
            destination = "#{0.channel.name} ({0.server.name})".format(message)
        log_str = "{0.timestamp}: {0.author.name} in {1}: {0.content}".format(message, destination)
        bot.log.info(log_str)
        return
    if message.author.bot:
        # Ignore bots
        return
    # Process !apb type commands
    await discord_bot.process_commands(message)
    # Get server settings.
    server_settings = get_server_settings(message.server)
    if message.server is not None and \
        message.content.startswith(tuple(prefix)) and \
        any(cmd[0] in message.content for cmd in settings_edits):
        if message.author == message.server.owner or\
           message.author.id in server_settings['mods'] or\
           message.author.id in bot.settings['mod_ids'].get('discord', []):
            await change_settings(server_settings, message)
            return
    if not server_settings['active']:
        return
    if server_settings['whitelist']:
        if message.channel.id not in server_settings['whitelist']:
            return
    if message.channel.id in server_settings['blacklist']:
        return
    if server_settings['mention']:
        is_mentioned = False
        for mention in message.mentions:
            if mention.id == discord_bot.user.id:
                is_mentioned = True
                break
        if not is_mentioned:
            return
    command = bot.uses_command(message.content)
    if not command:
        return

    attrs = {'bot': bot,
             'screen_name': message.author.name,
             'discord_id': message.author.id,
             'command': command,
             'message': message.content,
             'raw_data': message
            }
    ctx = UserContext(**attrs)
    if not bot.check_rate_limit(ctx.user_id, or_seconds=120, or_per_user=10):
        return
    if command in ["mywaifu", "myhusbando"]:
        if not ctx.user_ids.get('twitter', False):
            # Don't have a Twitter account linked
            reply_text = create_token(message.author.name, message.author.id, bot.source.name)
            await discord_bot.send_message(message.author, reply_text)
            return
    reply_text, reply_media = bot.on_command(ctx)
    # Handle MyWaifu command as we handle it a little differently on Discord.
    # TODO: make a better way to handle this based on ctx.bot.source.get_new_mywaifu
    if reply_text and command in ["mywaifu", "myhusbando"]:
        if "I don't know who" in reply_text:
            reply_text = reply_text.replace("Register or try tweeting",
                                            "Register on Twitter or try saying")
    bot.commands_used[ctx.command] += 1
    await send_reply(reply_text, reply_media, ctx, server_settings)


class Music:
    def __init__(self, discord_bot):
        self.music_bot = discord_bot
        self.last_played_global = []
        self.queued_games = OrderedDict()
        self.player = None
        self.break_leave = None
        self.current_game = None
        discord_bot.loop.create_task(self.read_music_game_queue())

    async def add_score_to_global(self, ctx, leaderboard):
        path = os.path.join(bot.config_path, 'Global Music Game Leaderboard.json')
        try:
            with open(path, 'r') as f:
                current_leaderboard = json.load(f)
        except FileNotFoundError:
            current_leaderboard = {}
        server_id = ctx.message.server.id
        if not current_leaderboard.get(server_id, False):
            current_leaderboard[server_id] = {}
        for player in leaderboard:
            if not current_leaderboard[server_id].get(player[0].id, False):
                current_leaderboard[server_id][player[0].id] = player[1]
            else:
                current_leaderboard[server_id][player[0].id] += player[1]
        with open(path, 'w') as f:
            json.dump(current_leaderboard, f, sort_keys=True, indent=4)

    async def check_if_audio_chanel(self, ctx, channel):
        check = lambda c: c.name == channel.name and \
            c.type == discord.ChannelType.voice
        return discord.utils.find(check, ctx.message.server.channels)

    async def read_music_game_queue(self):
        """Loop queued_games and join next game when ready."""
        # TODO:
        # Still a lot of problems with this
        # Current ones:
        # Fails to download song (connection to site problem)
        # int has no .name 
        await discord_bot.wait_until_ready()
        while not discord_bot.is_closed:
            if self.queued_games:
                if self.player is None:
                    try:
                        self.current_game = self.queued_games.popitem(last=False)
                        await self.game_ready(self.current_game[1])
                        if self.player is not None:
                            await self.player.disconnect()
                    except Exception as e:
                        # TEMP, need to find the cause of this
                        traceback.print_tb(e.__traceback__)
                        bot.log.info('{0.__class__.__name__}: {0}'.format(e))
                        bot.log.warning("MUSIC GAME CLOSED {}".format(self.current_game))
                    try:
                        await self.player.disconnect()
                    except Exception as e:
                        traceback.print_tb(e.__traceback__)
                        bot.log.info('{0.__class__.__name__}: {0}'.format(e))
                        bot.log.warning("MUSIC GAME COULDNT LEAVE VOICE {}".format(self.current_game))
                    self.current_game = None
                    self.break_leave = None
                    self.player = None
            await asyncio.sleep(1)

    async def game_ready(self, ctx):
        voice_channel = ctx['voice_channel']
        ctx = ctx['ctx']
        is_channel = await self.check_if_audio_chanel(ctx, voice_channel)
        if not is_channel:
            reply_text = ("Could not find a Voice Channel by that name!")
            try:
                await discord_bot.say(ctx.message.server, reply_text)
            except discord.errors.Forbidden:
                return
            return
        try:
            self.player = await discord_bot.join_voice_channel(voice_channel)
        except (discord.errors.Forbidden, discord.errors.InvalidArgument):
            return
        music_game_help = discord_settings.get('music_game_help', False)
        help_text = ("\nYou can use any of the game settings here: " + music_game_help) if music_game_help else ""
        reply_text = ("{0.author.mention} The bot is now ready to play!"
                      "\nStart by saying '**start game**' in the channel you want to play in!"
                      "{1}\n*(You have 80 seconds before the bot auto-disconnects)*".format(
                        ctx.message, help_text))
        try:
            await discord_bot.send_message(ctx.message.channel, reply_text)
        except discord.errors.Forbidden:
            return

        def check(msg):
            if not msg.server == ctx.message.server:
                return False
            return msg.content.startswith('start game')

        def fix_setting(var, num_max=3, num_min=1):
            if isinstance(var, int):
                var = str(var)
            if var.isdigit():
                var = int(var)
                if var > num_max:
                    var = num_max
                elif var < num_min:
                    var = num_min
            else:
                return False
            return int(var)

        timeout = time.time()
        while True:
            new_msg = await discord_bot.wait_for_message(author=ctx.message.author, timeout=0, check=check)
            if new_msg:
                log_str = "{0.timestamp}: {0.author.name} in {0.server.name} [{1}]: {0.content}".format(new_msg, "Music Game")
                bot.log.info(log_str)
                break
            if time.time() - timeout > 80:
                reply_text = ("Sorry you took too long!"
                              "\nYou were holding other games up :(")
                try:
                    await discord_bot.send_message(ctx.message.channel, reply_text)
                except discord.errors.Forbidden:
                    return
                return
        game_channel = new_msg.channel
        game_settings = {}
        msg_args = {}
        msg_args = new_msg.content.lower().replace("game start", "").replace("=", " ").split()
        msg_args = dict(msg_args[i:i+2] for i in range(0, len(msg_args), 2))
        # How many rounds. Max: 5, Min: 1
        game_settings['rounds'] = fix_setting(msg_args.get('rounds', 3), num_max=5, num_min=1)
        if not game_settings['rounds']:
            game_settings['rounds'] = 3
        # Gametype. 1 = Openings and Endings, 2 = Openings only, 3 = Endings only.
        game_settings['gametype'] = fix_setting(msg_args.get('gametype', 1), num_max=3, num_min=1)
        if not game_settings['gametype']:
            game_settings['gametype'] = 1
        # Difficulty. 1 = Guess if OP/ED, 2 = Guess if OP/ED + Number, 3 = Guess Anime name and OP/ED
        #             4 = Guess Anime name and OP/ED + Number, 5 = Guess Song name
        game_settings['difficulty'] = fix_setting(msg_args.get('difficulty', 3), num_max=5, num_min=1)
        if game_settings['gametype'] != 1 and game_settings['difficulty'] == 1:
            # Stop them from getting very easy points
            game_settings['difficulty'] = 2
        game_settings['hints'] = msg_args.get('hints', True)
        if isinstance(game_settings['hints'], str):
            if game_settings['hints'].lower() == "off" or game_settings['hints'].lower() == "false":
                game_settings['hints'] = False
            else:
                game_settings['hints'] = True

        def limit_year(year):
            if not year.isdigit():
                year = 2010
            year = int(year)
            if year > datetime.now().year + 1 or year < 1970:
                year = 2010
            return year

        game_settings['year'] = msg_args.get('year', range(2008, datetime.now().year))
        if game_settings['year']:
            if "-" in game_settings['year']:
                start_year, end_year = game_settings['year'].split("-")
                game_settings['year'] = range(limit_year(start_year), limit_year(end_year))
            elif isinstance(game_settings['year'], str):
                if not game_settings['year'].isdigit():
                    game_settings['year'] = range(2006, datetime.now().year)
                else:
                    game_settings['year'] = limit_year(game_settings['year'])
        with open(os.path.join(bot.config_path, 'Music Game.json'), 'r') as f:
            anime_songs = json.load(f)
        anime_songs = list(anime_songs.items())
        random.shuffle(anime_songs)
        finished = []
        complete_pack = []
        for name, data in anime_songs:
            for entry in data.items():
                complete_pack.append({**{'series': name, 'type': entry[0]}, **entry[1]})
                if game_settings['year']:
                    if entry[1].get('year', False):
                        year_str = entry[1]['year']
                        if year_str == "70s":
                            year_int = 1979
                        elif year_str == "80s":
                            year_int = 1989
                        elif year_str == "90s":
                            year_int = 1999
                        elif year_str == "00s":
                            year_int = 2009
                        else:
                            year_int = int(year_str)
                        if isinstance(game_settings['year'], range):
                            if year_int not in game_settings['year']:
                                continue
                        elif year_int != game_settings['year']:
                            continue
                if game_settings['gametype'] == 2 and entry[0].startswith('ED'):
                    continue
                elif game_settings['gametype'] == 3 and entry[0].startswith('OP'):
                    continue
                if game_settings['difficulty'] == 5:
                    if not entry[1].get('song_title', False):
                        continue
                finished.append({**{'series': name, 'type': entry[0]}, **entry[1]})
        if game_settings['difficulty'] == 1:
            diff_msg = "if it's the **Opening** or **Ending**"
        elif game_settings['difficulty'] == 2:
            diff_msg = "if it's the **Opening** or **Ending** *and* the OP/ED **number**"
        elif game_settings['difficulty'] == 3:
            diff_msg = "the **Anime Series** and if it's the **Opening** or **Ending**"
        elif game_settings['difficulty'] == 4:
            diff_msg = "the **Anime Series** and if it's the **Opening** or **Ending** *and* the OP/ED **number**"
        elif game_settings['difficulty'] == 5:
            diff_msg = "the **Song Name**"
        help_msg = ("**How to play:**"
                    "\nYou will have to guess {0} until the song has finished playing!"
                    "\nThe quicker you answer the more points you earn!"
                    "\nAfter **{1} round(s)** the game will end!".format(
                        diff_msg, game_settings['rounds']))
        try:
            await discord_bot.send_message(new_msg.channel, help_msg)
        except discord.errors.Forbidden:
            return
        if len(finished) < 6:
            message = "**No entries found with them settings! Using default settings!**"
            try:
                await discord_bot.send_message(new_msg.channel, message)
            except discord.errors.Forbidden:
                return
            finished = complete_pack
        player_leaderboard = {}
        current_round = 1
        while True:
            # Game start.
            players_corrent_round = []
            yt_player = None
            if self.break_leave:
                return
            random.shuffle(finished)
            entry = random.choice(finished)
            safe_break = 0
            while entry in self.last_played_global:
                safe_break += 1
                if safe_break == 5:
                    break
                entry = random.choice(finished)
            bot.log.info("Music Game Entry: " + str(entry))
            self.last_played_global.append(entry)
            if len(self.last_played_global) > 30:
                self.last_played_global = self.last_played_global[-10:]
            op_ed_text = entry['type'].replace("ED", "Ending").replace("OP", "Opening")
            full_string = entry['series']
            if game_settings['difficulty'] == 1:
                text_guess = ''.join([i for i in op_ed_text if not i.isdigit()])
            elif game_settings['difficulty'] == 2:
                text_guess = entry['type'].replace("ED", "Ending ").replace("OP", "Opening ")
            elif game_settings['difficulty'] == 3:
                a = ''.join([i for i in op_ed_text if not i.isdigit()])
                text_guess = entry['series'] + " " + a
            elif game_settings['difficulty'] == 4:
                a = ''.join([i for i in op_ed_text if not i.isdigit()])
                b = ''.join([i for i in op_ed_text if i.isdigit()])
                text_guess = entry['series'] + " "+ a + " " + b
            elif game_settings['difficulty'] == 5:
                text_guess = entry['song_title']
                full_string = entry['song_title']
            opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
                'quiet': True
            }
            yt_player = await self.player.create_ytdl_player(entry['dl'], ytdl_options=opts)
            await asyncio.sleep(3)
            yt_player.start()
            try:
                await discord_bot.send_message(new_msg.channel, "**Round: {} - Start!**".format(current_round))
            except discord.errors.Forbidden:
                return

            def guess_check(msg):
                return slugify(text_guess) in slugify(msg)

            # Incase of glitch
            safe_timer = time.time()
            first_correct = None
            points_to_add = 3 # First then -1 till it's 1
            # Hints
            timer = time.time()
            hint_cooldown = 40
            max_help_count = 3
            current_help_count = 1
            full_lst = list(range(len(full_string)))
            hint_str = list("_" * len(full_string))
            while yt_player.is_playing():
                if self.break_leave:
                    return
                if safe_timer - time.time() > 250:
                    break
                guess = await discord_bot.wait_for_message(channel=new_msg.channel, timeout=0)
                if guess is not None:
                    if guess_check(guess.content):
                        # Correct!
                        if guess.author not in players_corrent_round:
                            if not players_corrent_round:
                                first_correct = guess
                            players_corrent_round.append(guess.author)
                            if not player_leaderboard.get(guess.author, False):
                                player_leaderboard[guess.author] = points_to_add
                            else:
                                player_leaderboard[guess.author] += points_to_add
                            points_to_add -= 1
                            if points_to_add < 1:
                                points_to_add = 1
                if game_settings['hints']:
                    if time.time() - timer > hint_cooldown and current_help_count < max_help_count:
                        clock = ":clock{}:".format(current_help_count)
                        to_dev = 2
                        show_max = int(len(full_string) / to_dev / current_help_count)
                        for x in range(0, show_max):
                            i = random.choice(full_lst)
                            full_lst.remove(i)
                            hint_str[i] = list(full_string)[i]
                        end_string = "{}:exclamation: **Hint {}: {}**".format(
                            clock, current_help_count, ''.join(hint_str).replace("_", " \_ "))
                        try:
                            await discord_bot.send_message(game_channel, end_string)
                        except discord.errors.Forbidden:
                            return
                        current_help_count += 1
                        if len(full_string) < 8:
                            # Short string, don't give more hints.
                            current_help_count = max_help_count
                        hint_cooldown = 20
                        timer = time.time()
            # Round finished
            if first_correct is None:
                round_end_msg = "**No one got the answer right!**"
            else:
                second = "" if len(players_corrent_round) < 2 else "\nSecond: **" + players_corrent_round[1].name + "**"
                thrid = "" if len(players_corrent_round) < 3 else "\nThird: **" + players_corrent_round[2].name + "**"
                others = ""
                if len(players_corrent_round) > 3:
                    others = [a.name for a in players_corrent_round[3:]]
                    others = "\nFollowed by: {}".format(', '.join(others))
                round_end_msg = ("**{first}** got it right first!"
                                 "{second}{thrid}{others}".format(
                                    first=players_corrent_round[0].name,
                                    second=second, thrid=thrid, others=others))
            round_end_msg += ("\nThe correct answer was: "
                              "**{series} - {opening}**{artist}".format(
                                series=entry['series'],
                                opening=entry['type'].replace("OP", "Opening ").replace("ED", "Ending "),
                                artist="" if not entry.get('song_title', False) else "\n**Song Name: **" + entry['song_title']))
            try:
                await discord_bot.send_message(new_msg.channel, round_end_msg)
            except discord.errors.Forbidden:
                return
            # Song has finished playing.
            current_round += 1
            if current_round > game_settings['rounds']:
                # End of the game
                break
        # Final Score
        if not player_leaderboard:
            game_end_msg = "No one got any right. Damn."
        else:
            # Order by points
            game_leaderboard = list(reversed(sorted(player_leaderboard.items(), key=itemgetter(1))))
            await self.add_score_to_global(ctx, game_leaderboard)
            player_pos = 1
            past_player_score = 1337
            score_string = ["**Leaderboard:**\n"]
            past_player_score = None
            for player in game_leaderboard:
                is_tie = False
                score = player[1]
                if score == past_player_score:
                    is_tie = True
                if is_tie:
                    s = score_string[player_pos - 1].split("|", 1)
                    score_string[player_pos - 1] = s[0] + ", " + player[1].name + " | " + s[1]
                else:
                    if player_pos == 1:
                        s = "**First: **" + player[0].name + " | " + str(player[1])
                    elif player_pos == 2:
                        s = "\n**Second: **" + player[0].name + " | " + str(player[1])
                    elif player_pos == 3:
                        s = "\n**Thrid: **" + player[0].name + " | " + str(player[1])
                    elif player_pos == 4:
                        s = "\n**Others: **" + player[0].name + " | " + str(player[1])
                    elif player_pos >= 5:
                        s = "\n" + player[0].name + " | " + str(player[1])
                    score_string.append(s)
                past_player_score = score
                player_pos += 1
            score_string.append("\nThanks for playing!")
            game_end_msg = ''.join(score_string)
        try:
            await discord_bot.send_message(new_msg.channel, game_end_msg)
        except discord.errors.Forbidden:
            return

    async def check_queue(self, ctx, channel, server_id):
        if self.player is not None:
            if self.current_game is not None and self.current_game[0] == ctx.message.server.id:
                reply_text = "A game is already running in this server!"
                await discord_bot.say(reply_text)
                return
            else:
                q_pos = len(list(self.queued_games.keys())) + 1
                if self.queued_games.get(server_id, False):
                    q_pos = list(self.queued_games.keys()).index(server_id) + 1
                reply_text = ("A game is already running!"
                              "\nYour queue position is **{}**"
                              "\nYour estimated wait time is **{} minutes**".format(
                                q_pos, q_pos * 5))
            await discord_bot.say(reply_text)
        if self.queued_games.get(server_id, False):
            return
        self.queued_games[ctx.message.server.id] = {'ctx': ctx, 'voice_channel': channel}

    @commands.command(pass_context=True)
    async def summon(self, ctx):
        """Summons the bot to join your voice channel."""
        summoned_channel = ctx.message.author.voice_channel
        server_id = ctx.message.server.id
        if summoned_channel is None:
            await discord_bot.say('You are not in a voice channel.')
            return False
        await self.check_queue(ctx, summoned_channel, server_id)

    @commands.command(pass_context=True)
    async def join(self, ctx, *, channel : discord.Channel):
        """Joins a voice channel."""
        server_id = ctx.message.server.id
        is_channel = await self.check_if_audio_chanel(ctx, channel)
        if not is_channel:
            reply_text = ("Could not find a Voice Channel by that name!")
            await discord_bot.send_message(ctx.message.server, reply_text)
            return
        await self.check_queue(ctx, channel, server_id)

    @commands.command(pass_context=True)
    async def leaderboard(self, ctx, *, get_server_lb : str=None):
        this_server_only = False
        if get_server_lb and get_server_lb.lower() == "server":
            this_server_only = True
        try:
            with open(os.path.join(bot.config_path, 'Global Music Game Leaderboard.json'), 'r') as f:
                current_leaderboard = json.load(f)
        except FileNotFoundError:
            current_leaderboard = {}
        server_id = ctx.message.server.id
        if not current_leaderboard.get(server_id, False):
            current_leaderboard[server_id] = {}
        display_leaderboard = {}
        user_rank = 0
        for lb_server in current_leaderboard.items():
            if this_server_only:
                if lb_server[0] != ctx.message.server.id:
                    continue
            for user in lb_server[1].items():
                if user[0] == ctx.message.author.id:
                    user_rank += user[1]
                if not display_leaderboard.get(user[0], False):
                    display_leaderboard[user[0]] = user[1]
                else:
                    display_leaderboard[user[0]] += user[1]
        ordered_leaderboard = list(reversed(sorted(display_leaderboard.items(), key=itemgetter(1))))
        user_in_ranks = (ctx.message.author.id, user_rank)
        append_later = False
        if user_in_ranks not in ordered_leaderboard[:10]:
            # User not in top 10
            append_later = True
        end_string = []
        rank = 1
        # Get top 10 only
        for user in ordered_leaderboard[:10]:
            member = discord.utils.get(discord_bot.get_all_members(), id=user[0])
            name = user[0] + " [USER ID]"
            if member:
                name = member.name
            end_string.append([rank, name, user[1]])
            rank += 1
        if not end_string:
            reply_text = "No games have been played yet!"
        else:
            reply_text = tabulate(end_string,
                                  ["Rank", "Name",
                                   "{is_global}Score".format(is_global="Global " if not this_server_only else "")])
            if append_later:
                reply_text += "\nYou: {} | Score: {}".format(ctx.message.author.name, user_rank)
            first_msg = "**Top 10 Global**\n" if not this_server_only else "**Top 10 This Server**\n"
            reply_text = first_msg + "```\n" + reply_text + "```"
        await discord_bot.say(reply_text)


@discord_bot.command()
async def help():
    message = discord_settings.get('help_message', False)
    if not message:
        return
    await discord_bot.say(message)


@discord_bot.command()
async def patreon():
    if not bot.settings.get('use_patreon', False):
        return
    message = discord_settings.get('patreon_msg', False)
    if not message:
        return
    await discord_bot.say(message)


@discord_bot.command()
async def invite():
    perms = discord.Permissions.none()
    perms.read_messages = True
    perms.send_messages = True
    perms.embed_links = True
    perms.attach_files = True
    msg = "Use this URL to invite the bot: "
    await discord_bot.say(msg + discord.utils.oauth_url(discord_bot.client_id, perms))


@discord_bot.command(pass_context=True)
async def debug(ctx):
    msg = ("Current Server ID: {0.server.id}"
           "\nCurrent Channel ID: {0.channel.id}"
           "\nYour ID: {0.author.id}".format(ctx.message))
    await discord_bot.send_message(ctx.message.channel, msg)


@discord_bot.command(pass_context=True)
async def info(ctx):
    now = datetime.utcnow()
    delta = now - bot.uptime
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    if days > 1:
        fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
    elif days:
        fmt = '{d} day, {h} hours, {m} minutes, and {s} seconds'
    else:
        fmt = '{h} hours, {m} minutes, and {s} seconds'
    msg = ("Currently in {0} total servers!"
           "\nServing a total of {1} Users!"
           "\nUptime: {2}"
           "\nSince uptime a total of {3} commands have been used!"
           "\nMost common being '{4}' used {5} times!"
           "{6}"
           .format(len(discord_bot.servers),
                   len(list(discord_bot.get_all_members())),
                   fmt.format(d=days, h=hours, m=minutes, s=seconds),
                   sum(bot.commands_used.values()),
                   bot.commands_used.most_common(1)[0][0],
                   bot.commands_used.most_common(1)[0][1],
                   "\nCheck out more stats here: {}".format(
                    bot.settings['datadog']['share_url']) if bot.settings.get('datadog', False) and\
                    bot.settings['datadog'].get('share_url', False) else ""))
    await discord_bot.send_message(ctx.message.channel, msg)


async def datadog_data():
    await discord_bot.wait_until_ready()
    await asyncio.sleep(5)
    while not discord_bot.is_closed:
        await asyncio.sleep(5)
        if bot.settings['datadog'].get('statsd_servers', False):
            datadog_server_count = len(discord_bot.servers)
            bot.datadog.statsd.gauge(bot.settings['datadog']['statsd_servers'], datadog_server_count)
        if bot.settings['datadog'].get('statsd_members', False):
            datadog_server_count = len(list(discord_bot.get_all_members()))
            bot.datadog.statsd.gauge(bot.settings['datadog']['statsd_members'], datadog_server_count)                


@discord_bot.event
async def on_ready():
    print('Logged in as:')
    print('Username: ' + discord_bot.user.name)
    print('ID: ' + discord_bot.user.id)
    print('------')


if __name__ == '__main__':
    if not bot.settings.get('token', False):
        raise Exception("Missing Discord Bot Token from Discord Settings.json in /Configs/")
    discord_bot.client_id = bot.settings.get('client_id', '')
    discord_bot.owner_id = bot.settings.get('owner_id', '')
    discord_bot.loop.create_task(change_status())
    if bot.settings.get('datadog', False):
        discord_bot.loop.create_task(datadog_data())
    discord_bot.add_cog(Music(discord_bot))
    discord_bot.run(bot.settings['token'])