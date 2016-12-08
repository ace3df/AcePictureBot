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
                       datadog_online_check, create_token,
                       slugify, yaml_to_list, download_file, get_global_level_cache,
                       calculate_level, return_command_usage, write_command_usage)

from discord.ext import commands
from bs4 import BeautifulSoup
from tabulate import tabulate
from PIL import Image
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
users_discord_command = []  # bit of a cheap way to get this to work


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


def make_context(message, command):
    attrs = {'bot': bot,
         'screen_name': message.author.name,
         'discord_id': message.author.id,
         'command': command,
         'message': message.content,
         'raw_data': message,
         'raw_bot': discord_bot
        }
    return UserContext(**attrs)


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


async def send_reply(reply_text, reply_media, ctx, server_settings={}):
    if not reply_text and not reply_media:
        # Silent return
        return False
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
    sent_message = False
    try:
        if server_settings.get('media', True) and reply_media:
            count = 0
            for media in reply_media:
                if os.path.isfile(media):
                    with open(media, 'rb') as file:
                        if count == 0:
                            sent_message = await discord_bot.send_file(message.channel, file, content=reply_text)
                        else:
                            sent_message = await discord_bot.send_file(message.channel, file)
                else:
                    if count == 0:
                        reply_text = reply_text + " " + media
                        sent_message = await discord_bot.send_message(message.channel, reply_text)
                    else:
                        sent_message = await discord_bot.send_message(message.channel, media)
                count += 1
        else:
            sent_message = await discord_bot.send_message(message.channel, reply_text)
    except discord.errors.Forbidden:
        return sent_message
    return sent_message


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
    await discord_bot.send_message(channel, welcome_message.format(server.owner.mention))


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
    if message.author.id in users_discord_command:
        users_discord_command.remove(message.author.id)
    await discord_bot.process_commands(message)
    if message.author.id in users_discord_command:
        return
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
    ctx = make_context(message, command)
    if not bot.check_rate_limit(ctx, or_seconds=40, or_per_user=4):
        return
    # TEMP
    if message.server:
        if message.server.id == "229372991648038913":
            ctx.is_patreon = True
    if command in ["mywaifu", "myhusbando"]:
        if not ctx.user_ids.get('twitter', False):
            # Don't have a Twitter account linked
            reply_text = create_token(message.author.name, message.author.id, bot.source.name)
            await discord_bot.send_message(message.author, reply_text)
            return
    elif command == "!level":
        await discord_bot.send_typing(message.channel)
    reply_text, reply_media = bot.on_command(ctx)
    # Handle MyWaifu command as we handle it a little differently on Discord.
    # TODO: make a better way to handle this based on ctx.bot.source.get_new_mywaifu
    if reply_text and command in ["mywaifu", "myhusbando"]:
        if "I don't know who" in reply_text:
            reply_text = reply_text.replace("Register or try tweeting",
                                            "Register on Twitter or try saying")
    bot.commands_used[ctx.command] += 1
    await send_reply(reply_text, reply_media, ctx, server_settings)

##############
# TODO:
# Queue the songs before the rounds start (so no down time between rounds)
# list them all in self.songs

class VoiceState:
    def __init__(self, bot):
        self.current = None
        self.voice = None
        self.bot = bot
        self.play_next_song = asyncio.Event()
        self.songs = asyncio.Queue()
        self.audio_player = self.bot.loop.create_task(self.audio_player_task())

    def is_playing(self):
        if self.voice is None or self.current is None:
            return False
        player = self.current.player
        return not player.is_done()

    @property
    def player(self):
        return self.current.player

    def skip(self):
        if self.is_playing():
            self.player.stop()

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    # Move this while True into the game part itself
    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            self.current = await self.songs.get()
            await self.bot.send_message(self.current.channel, 'Now playing ' + str(self.current))
            self.current.player.start()
            await self.play_next_song.wait()

class Games:
    def __init__(self, bot):
        self.bot = bot
        # Guess Game
        self.guess_current_games = []

        # Music Game
        self.MUSIC_MAX_PLAYERS = 2
        self.music_voice_states = {}  # Can use as current_games
        self.music_break_leave = []
        self.music_queued_games = OrderedDict()
        # TODO: change this and support 2 players
        self.music_current_games = []
        self.player = None
        self.current_game = None
        self.bot.loop.create_task(self.read_music_game_queue())

        # All

    def get_voice_state(self, server):
        state = self.music_voice_states.get(server.id)
        if state is None:
            state = VoiceState(self.bot)
            self.music_voice_states[server.id] = state
        return state

    async def create_voice_client(self, channel):
        voice = await self.bot.join_voice_channel(channel)
        state = self.get_voice_state(channel.server)
        state.voice = voice

    async def stop_voice(self, ctx):
        server = ctx.message.server
        state = self.get_voice_state(server)
        if state.is_playing():
            player = state.player
            player.stop()
        try:
            state.audio_player.cancel()
            del self.music_voice_states[server.id]
            await state.voice.disconnect()
        except:
            pass

    def __unload(self):
        for state in self.music_voice_states.values():
            try:
                state.audio_player.cancle()
                if state.voice:
                    self.bot.loop.create_task(state.voice.disconnect())
            except:
                pass

    async def read_music_game_queue(self):
        """Loop queued_games and join next game when ready."""
        while not self.bot.is_closed:
            if self.music_queued_games:
                while len(self.music_voice_states) >= self.MUSIC_MAX_PLAYERS:
                    # Wait until a voice channel has left
                    await asyncio.sleep(5)
                new_game = self.music_queued_games.popitem(last=False)
                self.bot.loop.create_task(self.start_music_game(new_game))
                await asyncio.sleep(3)
            await asyncio.sleep(1)

    def check_answer(correct, guess):
        if correct.server.channel != guess.server.channel:
            return False
        if guess.message.content:
            pass

    def return_settings(self, message, options):

        def fix_setting(var, settings):
            if var is None:
                return settings[2]
            num_min, num_max = settings[0:2]
            if var.isdigit():
                var = int(var)
                if var > num_max:
                    var = num_max
                elif var < num_min:
                    var = num_min
                return var
            else:
                return settings[2]
        
        def fix_year(year, not_range=False):
            if year == "max":
                return datetime.now().year
            if not year.isdigit():
                if not_range:
                    return range(2010, datetime.now().year)
                year = 2010
            year = int(year)
            if year > datetime.now().year + 1 or year < 1970:
                year = 2010
            return year

        user_arguments = dict(message[i:i+2] for i in range(0, len(message), 2))
        settings = {}
        settings['rounds'] = fix_settings(user_arguments.get('rounds'), options.get('rounds', [1, 5, 3]))
        settings['gametype'] = fix_settings(user_arguments.get('gametype'), options.get('gametype', [1, 3, 1]))
        settings['difficulty'] = fix_settings(user_arguments.get('difficulty'), options.get('difficulty', [1, 5, 3]))
        settings['hints'] = options.get('hints', True)
        if user_arguments.get('hints'):
            if user_arguments['hints'].lower() in ["false", "off", "no"]:
                settings['hints'] = False
        year = range(2010, datetime.now().year)
        if user_arguments.get('year') and options.get('year'):
            if "-" in user_arguments['year']:
                # Year is a range
                year_split = user_arguments['year'].split("-")
                year = range(fix_year(year_split[0]), fix_year(year_split[1]))
            else:
                year = fix_year(user_arguments['year'], not_range=True)
                year = range(year, year)
        settings['year'] = year
        return settings

    async def start_music_game(self, new_game):
        # Join voice
        try:
            ctx = new_game[1]['ctx']
            state = self.get_voice_state(ctx.message.server)
            state.voice = await self.bot.join_voice_channel(new_game[1]['voice_channel'])
            music_game_help = discord_settings.get('music_game_help')
            help_text = ("\nYou can use any of the game settings here: " + music_game_help) if music_game_help else ""
            reply_text = ("{0.author.mention} The bot is now ready to play!"
                          "\nStart by saying '**start game**' in the channel you want to play in!"
                          "{1}\n*(You have 80 seconds before the bot auto-disconnects)*".format(
                            ctx.message, help_text))
            await self.bot.send_message(ctx.message.channel, reply_text)
            has_started = await self.bot.wait_for_message(
                author=ctx.message.author, timeout=80,
                check=lambda msg: msg.content.startswith('start game'))
            if has_started is None:
                # Timeout they took too long, leave.
                reply_text = ("Sorry you took too long!"
                              "\nYou were holding other games up :(")
                await self.bot.send_message(ctx.message.channel, reply_text)
                return False
            game_options = {'_comment': ["min", "max", "default"],
                            'rounds': [1, 5, 3], 'gametype': [1, 3, 1], 'difficulty': [1, 5, 1],
                            'hints': True, 'year': [1970, "max"]}
            game_settings = await self.return_settings(ctx.message.content, options=game_options)
            print(game_settings)
            with open(os.path.join(bot.config_path, 'Music Game.json'), 'r') as f:
                anime_songs = json.load(f)
        except:
            # print error
            pass
        finally:
            await self.stop_voice(ctx)


    @commands.command(pass_context=True)
    async def summon(self, ctx):
        """Summons the bot to join your voice channel."""
        summoned_channel = ctx.message.author.voice_channel
        server = ctx.message.server
        if summoned_channel is None:
            await self.bot.say('You are not in a voice channel.')
            return False
        # Check current games to make sure not in more than 2 servers at a time.
        if (len(self.music_voice_states) >= self.MUSIC_MAX_PLAYERS and self.music_voice_states.get(server.id) is None):
            # 2 games running, add to queue
            if self.music_queued_games.get(server.id):
                # Already in queue, return current pos
                q_pos = list(self.music_queued_games).index(server.id) + 1
            else:
                q_pos = len(list(self.music_queued_games)) + 1
            reply_text = ("Games are already running, please wait!"
                          "\nYour queue position is **{}**"
                          "\nYour estimated wait time is **{} minutes**".format(
                            q_pos, q_pos * 4))
            await self.bot.say(reply_text)
        elif self.music_voice_states.get(server.id):
            # Server already has a game running, use this to move channel
            state = self.get_voice_state(ctx.message.server)
            if state.voice is not None:
                await state.voice.move_to(summoned_channel)
            return True
        self.music_queued_games[server.id] = {'ctx': ctx, 'voice_channel': summoned_channel}
        return True

##############

class newGames:

    def __init__(self, bot):
        self.bot = bot

        # Character guess game
        self.char_current_games = []
        self.char_break_leave = {'server_id': None}

        # Music guess game
        self.music_current_games = []
        self.music_queued_games = OrderedDict()
        self.music_break_leave = {'server_id': None}
        # TODO: change this and support 2 players
        self.player = None
        self.current_game = None

        self.bot.loop.create_task(self.read_music_game_queue())

    async def read_music_game_queue(self):
        """Loop music_queued_games and join next game when ready."""
        await self.bot.wait_for_ready()
        while not self.bot.is_closed:
            if self.music_queued_games:
                if self.player is None:
                    try:
                        self.current_game = self.music_queued_games.popitem(last=False)
                        await self.music_game_start(self.current_game[1])
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
                    del self.music_break_leave[self.current_game[1].server.id]
                    self.player = None
            await asyncio.sleep(1)   

class aGames:
    # TODO:
    # Rewrite all of this to support multi games without using same code all the time
    def __init__(self, bot):
        self.bot = bot
        self.char_current_games = []
        self.char_last_used = []

        self.music_current_games = []
        self.music_last_used = []
        self.music_queued_games = OrderedDict()
        # These two will be changed when supporting up to 2 players at once
        self.player = None
        self.break_leave = None
        self.current_game = None

        self.bot.loop.create_task(self.read_music_game_queue())

    async def read_music_game_queue(self):
        """Loop queued_games and join next game when ready."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed:
            if self.music_queued_games:
                if self.player is None:
                    try:
                        self.current_game = self.music_queued_games.popitem(last=False)
                        await self.music_game_start(self.current_game[1])
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

    async def check_queue(self, ctx, channel, server_id):
        if self.player is not None:
            if self.current_game is not None and self.current_game[0] == ctx.message.server.id:
                reply_text = "A game is already running in this server!"
                await self.bot.say(reply_text)
                return
            else:
                q_pos = len(list(self.music_queued_games.keys())) + 1
                if self.music_queued_games.get(server_id, False):
                    q_pos = list(self.music_queued_games.keys()).index(server_id) + 1
                reply_text = ("A game is already running!"
                              "\nYour queue position is **{}**"
                              "\nYour estimated wait time is **{} minutes**".format(
                                q_pos, q_pos * 5))
            await self.bot.say(reply_text)
        if self.music_queued_games.get(server_id, False):
            return
        self.music_queued_games[ctx.message.server.id] = {'ctx': ctx, 'voice_channel': channel}

    async def add_score_to_global(self, ctx, gametype, leaderboard):
        path = os.path.join(bot.config_path,
                            'Global {} Game Leaderboard.json'.format(gametype))
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

    async def return_settings(self, message, options={}):

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

        game_settings = {}
        msg_args = {}
        msg_args = message.content.lower().replace("game start", "").replace("=", " ").split()
        msg_args = dict(msg_args[i:i+2] for i in range(0, len(msg_args), 2))
        # How many rounds. Max: 5, Min: 1
        game_settings['rounds'] = fix_setting(msg_args.get('rounds', 3), num_max=5, num_min=1)
        if not game_settings['rounds']:
            game_settings['rounds'] = 3
        # Gametype. 1 = Openings and Endings, 2 = Openings only, 3 = Endings only.
        game_settings['gametype'] = fix_setting(
            msg_args.get('gametype', 1),
            num_max=options.get('gametype_max', 3), num_min=1)
        if not game_settings['gametype']:
            game_settings['gametype'] = 1
        # Difficulty. 1 = Guess if OP/ED, 2 = Guess if OP/ED + Number, 3 = Guess Anime name and OP/ED
        #             4 = Guess Anime name and OP/ED + Number, 5 = Guess Song name
        game_settings['difficulty'] = fix_setting(
                msg_args.get('difficulty', options.get('difficulty_default', 3)),
                num_max=options.get('difficulty_max', 5), num_min=1)
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
        return game_settings

    async def return_end_scoreboard(self, ctx, gametype, player_leaderboard):
        if not player_leaderboard:
            return("No one got any right. Damn.")
        # Order by points
        game_leaderboard = list(reversed(sorted(player_leaderboard.items(), key=itemgetter(1))))
        await self.add_score_to_global(ctx, gametype, game_leaderboard)
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
        return(''.join(score_string))

    @commands.group(name="guess", pass_context=True)
    async def guess_game(self, ctx):

        def guess_check(msg):
            if game_settings['difficulty'] == 2:
                # only need to guess one part of this text_guessmd
                if slugify(msg) in slugify(text_guess):
                    return True
                return slugify(msg) in '-'.join(reversed(slugify(text_guess).split("-")))
            else:
                if slugify(text_guess) in slugify(msg):
                    return True
                return '-'.join(reversed(slugify(text_guess).split("-"))) in slugify(msg)

        if ctx.message.channel.id in self.char_current_games:
            return  # Channel currently has a game running.
        self.char_current_games.append(ctx.message.channel.id)
        otp_path = settings.get('image_location', os.path.realpath(__file__))
        otp_images_path = os.path.join(otp_path, 'OTP')
        game_settings = await self.return_settings(ctx.message, {'difficulty_default': 2, 'difficulty_max': 3})
        include_series = True
        # cheap cuns
        if game_settings['difficulty'] == 1:
            diff_msg = "what series the character is from"
            first_top_right = 30
            first_top_left = 60
            first_bottom_right = random.randint(40, 50)
            first_bottom_left = random.randint(50, 60)
            second_top_right = 40
            second_top_left = 80
            second_bottom_right = random.randint(40, 90)
            second_bottom_left = random.randint(60, 100)
        elif game_settings['difficulty'] == 2:
            diff_msg = "one part of the character's name (the order of the name does not matter)"
            first_top_right = 10
            first_top_left = 40
            first_bottom_right = random.randint(20, 50)
            first_bottom_left = random.randint(50, 60)
            second_top_right = 40
            second_top_left = 60
            second_bottom_right = random.randint(40, 70)
            second_bottom_left = random.randint(60, 80)
        elif game_settings['difficulty'] == 3:
            diff_msg = "the character's full name (the order of the name does not matter)"
            first_top_right = 10
            first_top_left = 20
            first_bottom_right = random.randint(10, 70)
            first_bottom_left = random.randint(20, 70)
            second_top_right = 20
            second_top_left = 30
            second_bottom_right = random.randint(20, 50)
            second_bottom_left = random.randint(30, 70)
            include_series = False
        help_msg = ("**How to play:**"
                    "\nYou will have to guess {0}!"
                    "\nRounds last for 60 seconds!"
                    "\nThe quicker you answer the more points you earn!"
                    "\nAfter **{1} round(s)** the game will end!".format(
                        diff_msg, game_settings['rounds']))
        try:
            await self.bot.send_message(ctx.message.channel, help_msg)
        except discord.errors.Forbidden:
            return
        player_leaderboard = {}
        current_round = 1
        while True:
            if game_settings['gametype'] == 1:
                gender_random = 11
            elif game_settings['gametype'] == 2:
                gender_random = 7
            elif game_settings['gametype'] == 3:
                gender_random = 0
            list_name = "Waifu"
            random_gender = random.randint(0, 10)
            if random_gender > gender_random:
                list_name = "Husbando"
            config_path = settings.get('config_path', os.path.join(os.path.realpath(__file__), 'Configs'))
            path = os.path.join(config_path, '{} List.yaml'.format(list_name))
            guess_list = yaml_to_list(path)
            while True:
                players_corrent_round = []
                # Loop until either entry has OTP image or local images
                entry = random.choice(guess_list)
                if not entry[1].get('otp image', False):
                    continue
                otp_filename = entry[1]['otp image'].split("/")[-1]
                otp_image_file = os.path.join(otp_images_path, otp_filename)
                if not os.path.isfile(otp_image_file):
                    otp_image_file = download_file(entry[1]['otp image'], path=otp_images_path)
                    if not otp_image_file:
                        continue
                if otp_image_file:
                    break
            img = Image.open(otp_image_file)
            w, h = img.size
            w, h = w / 2, h / 2
            # Cut the image up
            hint_1 = img.crop((w - random.randint(first_top_right, int(w / 2)),
                               h - random.randint(first_top_left, int(h / 2)),
                               w + first_bottom_right,
                               h + first_bottom_left))
            hint_2 = img.crop((w - random.randint(second_top_right, int(w)),
                               h - random.randint(second_top_left, int(h)),
                               (w + 40) + second_bottom_right,
                               (h + 40) + second_bottom_left))
            hint_1.save('otp_{}_1.png'.format(ctx.message.channel.id))
            hint_2.save('otp_{}_2.png'.format(ctx.message.channel.id))
            cleaned_name = re.sub("[\(\[].*?[\)\]]", "", entry[0]).strip()
            if game_settings['difficulty'] == 1:
                text_guess = entry[1]['series']
                hint_msg = ""
            elif game_settings['difficulty'] == 2:
                # TODO: only need to guess one part of the slugify that would happen here
                text_guess = cleaned_name
                hint_msg = ": They are from {}".format(entry[1]['series'])
            elif game_settings['difficulty'] == 3:
                text_guess = cleaned_name
                hint_msg = ": They are from {}".format(entry[1]['series'])
            print(text_guess)
            first_correct = None
            timer = time.time()
            max_help_count = 3
            current_help_count = 1
            points_to_add = 1
            if game_settings['hints']:
                showed_hint = False
            else:
                showed_hint = True
            await asyncio.sleep(1)
            reply_text = "**Round: {} - Start!**".format(current_round)
            with open('otp_{}_1.png'.format(ctx.message.channel.id), 'rb') as file:
                await self.bot.send_file(ctx.message.channel, file, content=reply_text)
            while True:
                guess = await self.bot.wait_for_message(channel=ctx.message.channel, timeout=0)
                if guess is not None:
                    if guess_check(guess.content):
                        if guess.author not in players_corrent_round:
                            if not players_corrent_round:
                                first_correct = guess
                            players_corrent_round.append(guess.author)
                            if not player_leaderboard.get(guess.author, False):
                                player_leaderboard[guess.author] = points_to_add
                            else:
                                player_leaderboard[guess.author] += points_to_add
                            break
                if time.time() - timer > 45 and not showed_hint:
                    # Show second image.
                    showed_hint = True
                    reply_text = ":exclamation: **Hint{}**".format(
                        "" if not include_series else hint_msg)
                    with open('otp_{}_2.png'.format(ctx.message.channel.id), 'rb') as file:
                        await self.bot.send_file(ctx.message.channel, file, content=reply_text)  
                elif time.time() - timer > 60:
                    break  # Round over
            # Rounds finished
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
                              "**{}**").format(cleaned_name + " ({})".format(entry[1]['series']))
            try:
                with open(otp_image_file, 'rb') as file:
                    await self.bot.send_file(ctx.message.channel, file, content=round_end_msg)
            except discord.errors.Forbidden:
                return
            # Song has finished playing.
            current_round += 1
            if current_round > game_settings['rounds']:
                # End of the game
                break
        game_end_msg = await self.return_end_scoreboard(ctx, "Character", player_leaderboard)
        try:
            await self.bot.send_message(ctx.message.channel, game_end_msg)
        except discord.errors.Forbidden:
            return
        os.remove('otp_{}_1.png'.format(ctx.message.channel.id))
        os.remove('otp_{}_2.png'.format(ctx.message.channel.id))
        self.char_current_games.remove(ctx.message.channel.id)

    async def music_game_start(self, ctx):
        voice_channel = ctx['voice_channel']
        ctx = ctx['ctx']
        try:
            self.player = await self.bot.join_voice_channel(voice_channel)
        except (discord.errors.Forbidden, discord.errors.InvalidArgument):
            return
        music_game_help = discord_settings.get('music_game_help', False)
        help_text = ("\nYou can use any of the game settings here: " + music_game_help) if music_game_help else ""
        reply_text = ("{0.author.mention} The bot is now ready to play!"
                      "\nStart by saying '**start game**' in the channel you want to play in!"
                      "{1}\n*(You have 80 seconds before the bot auto-disconnects)*".format(
                        ctx.message, help_text))
        try:
            await self.bot.send_message(ctx.message.channel, reply_text)
        except discord.errors.Forbidden:
            return

        def check(msg):
            if not msg.server == ctx.message.server:
                return False
            return msg.content.startswith('start game')

        timeout = time.time()
        while True:
            new_msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=0, check=check)
            if new_msg:
                log_str = "{0.timestamp}: {0.author.name} in {0.server.name} [{1}]: {0.content}".format(new_msg, "Music Game")
                bot.log.info(log_str)
                break
            if time.time() - timeout > 80:
                reply_text = ("Sorry you took too long!"
                              "\nYou were holding other games up :(")
                try:
                    await self.bot.send_message(ctx.message.channel, reply_text)
                except discord.errors.Forbidden:
                    return
                return
        game_channel = new_msg.channel
        game_settings = await self.return_settings(ctx.message)
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
            await self.bot.send_message(new_msg.channel, help_msg)
        except discord.errors.Forbidden:
            return
        if len(finished) < 6:
            message = "**No entries found with them settings! Using default settings!**"
            try:
                await self.bot.send_message(new_msg.channel, message)
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
            while entry in self.music_last_used:
                safe_break += 1
                if safe_break == 5:
                    break
                entry = random.choice(finished)
            bot.log.info("Music Game Entry: " + str(entry))
            self.music_last_used.append(entry)
            if len(self.music_last_used) > 30:
                self.music_last_used = self.music_last_used[-10:]
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
                await self.bot.send_message(new_msg.channel, "**Round: {} - Start!**".format(current_round))
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
                guess = await self.bot.wait_for_message(channel=new_msg.channel, timeout=0)
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
                            await self.bot.send_message(game_channel, end_string)
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
                await self.bot.send_message(new_msg.channel, round_end_msg)
            except discord.errors.Forbidden:
                return
            # Song has finished playing.
            current_round += 1
            if current_round > game_settings['rounds']:
                # End of the game
                break
        game_end_msg = await self.return_end_scoreboard(ctx, "Music", player_leaderboard)
        try:
            await self.bot.send_message(new_msg.channel, game_end_msg)
        except discord.errors.Forbidden:
            return

    @commands.command(pass_context=True)
    async def summon(self, ctx):
        """Music Game:
        Summons the bot to join your voice channel."""
        summoned_channel = ctx.message.author.voice_channel
        server_id = ctx.message.server.id
        if summoned_channel is None:
            await self.bot.say('You are not in a voice channel.')
            return
        await self.check_queue(ctx, summoned_channel, server_id)

    # @commands.group(pass_context=True)
    async def leaderboard(self, ctx, *, gametype):
        this_server_only = False
        if "server" in gametype.lower():
            this_server_only = True
        if "music" in gametype.lower():
            filename = 'Global Music Game Leaderboard.json'
        elif "guess" in gametype.lower():
            filename = 'Global Character Game Leaderboard.json'
        else:
            await self.bot.say('Invalid gametype: "music" or "guess"')
            return
        try:
            with open(os.path.join(bot.config_path, filename), 'r') as f:
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
            member = discord.utils.get(self.bot.get_all_members(), id=user[0])
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
        await self.bot.say(reply_text)


@discord_bot.command(pass_context=True)
async def help(ctx, command : str = None):
    users_discord_command.append(ctx.message.author.id)
    message = False
    if command:
        command = bot.uses_command(ctx.message.content)
        if command:
            message = "```" + bot.commands[command].description.replace("{OPTION}", command.title()) + "```"
    if not message:
        message = discord_settings.get('help_message', False)
        public_cmds = [cmd for cmd in bot.commands.keys() \
                       if not bot.commands[cmd].patreon_only \
                       and not cmd in bot.commands[cmd].patreon_aliases \
                       and not bot.commands[cmd].patreon_vip_only \
                       and not cmd in bot.commands[cmd].patreon_vip_aliases]
        patreon_cmds = [cmd for cmd in bot.commands.keys() \
                       if bot.commands[cmd].patreon_only \
                       or cmd in bot.commands[cmd].patreon_aliases \
                       or bot.commands[cmd].patreon_vip_only \
                       or cmd in bot.commands[cmd].patreon_vip_aliases]
        message += "\n**Full list of commands: **{}".format(', '.join(public_cmds))
        message += "\n**Full list of Patreon only commands: **{}".format(', '.join(patreon_cmds))
        message += "\n**For a description or help for a command use \"!apb help <command>\"**"
        if not message:
            return
    await discord_bot.say(message)


@discord_bot.command(pass_context=True)
async def benchmark(ctx, command : str):
    """Benchmark a given command.
    Example: !apb benchmark waifu"""
    users_discord_command.append(ctx.message.author.id)
    command = bot.uses_command(ctx.message.content)
    if not command:
        await discord_bot.say("No command given. Example:\n`!apb time waifu`")
        return
    before = time.time()
    user_ctx = make_context(ctx.message, command)
    user_ctx.args = user_ctx.args.lower().replace("!apb benchmark", "").strip()
    reply_text, reply_media = bot.on_command(user_ctx)
    after = time.time()
    post_message = "```Command: {}\nArgs: {}\nTime: {}\n{} (Media: {})```".format(
        command, user_ctx.args, after - before, reply_text, bool(reply_media))
    before_post = time.time()
    sent_message = await send_reply(post_message, reply_media, user_ctx)
    after_post = time.time()
    post_message = "```Command: {}\nArgs: {}\nTime: {}\n{} (Media: {})\nPost Time: {}```".format(
        command, user_ctx.args, after - before, reply_text, bool(reply_media), after_post - before_post)
    await discord_bot.edit_message(sent_message, post_message)


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


async def is_owner(ctx):
    app_info = await discord_bot.application_info()
    return ctx.message.author.id == getattr(app_info, 'owner').id


@discord_bot.command()
@commands.check(is_owner)
async def reload():
    bot.reload_commands()
    await discord_bot.say(":ok_hand:")


@discord_bot.command(pass_context=True)
async def debug(ctx):
    msg = ("Current Server ID: {0.server.id}"
           "\nCurrent Channel ID: {0.channel.id}"
           "\nYour ID: {0.author.id}".format(ctx.message))
    await discord_bot.send_message(ctx.message.channel, msg)

##########################################
# TODO:
# can easily make all this into one function
# ugly for now
# very ugly
# more ugly
@discord_bot.group(pass_context=True)
async def buy(ctx):
    reply_text = """{}
**List of options you can use:**
!apb buy background <Background ID>
!apb buy tint <HTML HEX colour/off>
!apb buy theme <white/black/red/blue/pink>
Full list of backgrounds you can buy, theme examples and help can be found here:
<https://gist.github.com/ace3df/3d35fc77bde1ba0fbd3a54c370e9cfa6>
""".format(ctx.message.author.mention)
    if ctx.invoked_subcommand is None:
        await discord_bot.say(reply_text)


@buy.command(name="background", pass_context=True)
async def buy_background(ctx, bg : int = 0):
    if not bg:
        reply_text = ("{} See the full list of backgrounds and pirces here: "
                      "<https://gist.github.com/ace3df/3d35fc77bde1ba0fbd3a54c370e9cfa6#apb-buy-background-background-id>".format(
                        ctx.message.author.mention))
        await discord_bot.say(reply_text)
        return
    user_ctx = make_context(ctx.message, "!level")
    user_level_dict = return_command_usage(ctx=user_ctx)
    exp_data = calculate_level(user_level_dict)
    exp_data['cash'] -= user_level_dict['level_card']['cash_spent']
    path = settings.get('image_location', os.path.realpath(__file__))
    background_path = os.path.join(path, 'Level Images', 'Level Backgrounds')
    bg_list = [f for f in os.listdir(background_path) if os.path.isfile(os.path.join(background_path, f))]
    new_bg = [f for f in bg_list if f.split("_")[1] == str(bg)]
    if not new_bg:
        # Invalid background number
        await discord_bot.say('{} Invalid background number!\n'
                              'See all the options and prices here: {}'.format(
                                ctx.message.author.mention,
                                "<https://gist.github.com/ace3df/3d35fc77bde1ba0fbd3a54c370e9cfa6>"))
        return

    cost = int(new_bg[0].split("_")[2].replace(".png", "")) * 100
    if str(bg) in user_level_dict['level_card']['owned_bg']:
        await discord_bot.say("{} You already own this background! Applying it now!".format(ctx.message.author.mention))
    elif cost > exp_data['cash'] and not user_ctx.is_patreon:
        # Not enough cash
        await discord_bot.say("{} You don't have enough cash! "
                              "Use more commands to level up and gain more!"
                              "\nYou currently have: {}"
                              "\nThis background costs: {}".format(ctx.message.author.mention,
                                exp_data['cash'], cost))
        return
    else:
        # Buy it here
        if not user_ctx.is_patreon:
            exp_data['cash'] -= cost
            user_level_dict['level_card']['cash_spent'] += cost
        user_level_dict['level_card']['owned_bg'].append(str(bg))
        await discord_bot.say("{} Background {} bought and applied!\nYou now have {} cash left!".format(
            ctx.message.author.mention, bg, exp_data['cash']))
    user_level_dict['level_card']['background_number'] = bg
    write_command_usage("Discord", ctx.message.author.id, user_level_dict)
    return True


@discord_bot.command(name="leaderboard", pass_context=True)
async def leaderboard(ctx, game_type : str = "", is_local : str = ""):
    options = ["Level", "Music", "Guess"]
    to_search = [a for a in options if a.lower() in game_type.lower()]
    if not to_search:
        await discord_bot.say("Invalid option! Use one of these: {}\n"
                              "You can also use add 'global' on the end for the global leaderboard!".format(', '.join(options)))
    await discord_bot.send_typing(ctx.message.channel)
    to_search = to_search[0]
    rank = 1
    user_score = 0
    end_string = []
    _leaderboard = {}
    local_only = True
    user_not_top = True
    if any(is_global in is_local.lower() for is_global in ["global", "all"]):
        local_only = False
    user_ctx = make_context(ctx.message, "!level")
    if to_search == "Level":
        if ctx.message.server is not None and local_only:
            for member in ctx.message.server.members:
                if member.bot:
                    continue
                attrs = {'bot': user_ctx.bot,
                         'screen_name': '',
                         'discord_id': member.id,
                         'command': "!level",
                         'message': '',
                         'raw_data': '',
                         'raw_bot': ''
                        }
                member_ctx = UserContext(**attrs)
                member_usage = return_command_usage(member_ctx)
                if not member_usage:
                    continue
                member_data = calculate_level(member_usage)
                if ctx.message.author.id == member.id:
                    user_score = member_data['total_exp']
                _leaderboard[member.id] = member_data['total_exp']
        else:
            userlevels = get_global_level_cache(user_ctx)
            for entry in userlevels:
                if ctx.message.author.id == entry['user_id']:
                    user_score = entry['total_exp']
                _leaderboard[entry['user_id']] = entry['total_exp']
    elif to_search in ["Music", "Guess"]:
        filename = os.path.join(bot.config_path, "Leaderboard {} Game.json".format(to_search))
        if os.path.isfile(filename):
            with open(filename, 'r') as f:
                _leaderboard = json.load(f)
        if ctx.message.server is not None and local_only:
            # Filter out users that are not in server
            _leaderboard = _leaderboard.get(ctx.message.server.id)
            if _leaderboard is None:
                if to_search in ["Music", "Guess"]:
                    reply_text = "No games have been played yet!"
                else:
                    reply_text = "No entries found!"
                await discord_bot.say(reply_text)
                return
            for user_id, score in _leaderboard.items():
                if user_id != ctx.message.author.id:
                    continue
                user_score += score
        else:
            new_leaderboard = {}
            # Combine user scores from differnt servers
            for server, users in _leaderboard.items():
                for user_id, score in users.items():
                    if user_id == ctx.message.author.id:
                        user_score += score
                    if not new_leaderboard.get(user_id):
                        new_leaderboard[user_id] = score
                    else:
                        new_leaderboard[user_id] += score
            _leaderboard = new_leaderboard.copy()
    ordered_leaderboard = list(reversed(sorted(_leaderboard.items(), key=itemgetter(1))))
    if not user_not_top and (ctx.message.author.id, user_score) not in ordered_leaderboard[:10]:
        # User not in top 10
        user_not_top = False
    for user_id, score in ordered_leaderboard[:10]:
        member = discord.utils.get(discord_bot.get_all_members(), id=user_id)
        name = user_id + " [USER ID]"
        if member:
            name = member.name
        end_string.append([rank, name, score])
        rank += 1
    if not end_string:
        if to_search in ["Music", "Guess"]:
            reply_text = "No games have been played yet!"
        else:
            reply_text = "No entries found!"
    else:
        reply_text = tabulate(end_string, ["Rank", "Name", "Score" if not to_search == "Level" else "EXP"])
        if not user_not_top:
            reply_text += "\nYou: {} | Score: {}".format(ctx.message.author.name, user_score)
        first_msg = "**Top 10 {} ".format(to_search)
        first_msg += "Global**" if not local_only else "Server**"
        reply_text = first_msg + "```\n" + reply_text + "```"
    await discord_bot.say(reply_text)


@discord_bot.command(name="level", pass_context=True)
async def level(ctx):
    from commands import user_level
    users_discord_command.append(ctx.message.author.id)
    await discord_bot.send_typing(ctx.message.channel)
    user_ctx = make_context(ctx.message, "!level")
    reply_text, reply_media = user_level.callback(user_ctx)
    await discord_bot.send_file(ctx.message.channel, reply_media,
                                content=ctx.message.author.mention + " " + reply_text)


@discord_bot.command(name="airing", pass_context=True)
async def airing(ctx):
    from commands import airing
    await discord_bot.send_typing(ctx.message.channel)
    user_ctx = make_context(ctx.message, "!airing")
    reply_text, reply_media = airing.callback(user_ctx)
    await discord_bot.send_file(ctx.message.channel, reply_media,
                                content=ctx.message.author.mention + " " + reply_text)


@buy.command(name="theme", pass_context=True)
async def buy_theme(ctx, *, theme: str):
    user_ctx = make_context(ctx.message, "!level")
    user_level_dict = return_command_usage(ctx=user_ctx)
    exp_data = calculate_level(user_level_dict)
    exp_data['cash'] -= user_level_dict['level_card']['cash_spent']
    cost = 30
    POSSIBLE_THEMES = ["default", "dark", "red"]
    if not theme or theme.strip() not in POSSIBLE_THEMES:
        await discord_bot.say('{} Invalid theme!\n'
                              "You can use: default, dark or red.".format(ctx.message.author.mention))
        return
    user_ctx = make_context(ctx.message, "!level")
    user_level_dict = return_command_usage(ctx=user_ctx)
    exp_data = calculate_level(user_level_dict)
    exp_data['cash'] -= user_level_dict['level_card']['cash_spent']
    cost = 30
    if cost > exp_data['cash'] and not user_ctx.is_patreon:
        # Not enough cash
        await discord_bot.say("{} You don't have enough cash! "
                              "Use more commands to level up and gain more!"
                              "\nYou currently have: {}"
                              "\nThemes cost: {}".format(
                                ctx.message.author.mention, exp_data['cash'], cost))
        return
    else:
        # Buy it here
        if not user_ctx.is_patreon:
            exp_data['cash'] -= cost
            user_level_dict['level_card']['cash_spent'] += cost
        await discord_bot.say("{} Enjoy your new background tint!\nYou now have {} cash left!".format(
            ctx.message.author.mention, exp_data['cash']))
    user_level_dict['level_card']['theme'] = theme.strip().lower()
    write_command_usage("Discord", ctx.message.author.id, user_level_dict)
    return True


@buy.command(name="tint", pass_context=True)
async def buy_tint(ctx, *, tint: str):
    if not tint:
        await discord_bot.say('{} You forgot to include a HTML HEX colour for a tint!\n'
                              "You can also use 'background tint off' to remove it!".format(ctx.message.author.mention))
        return
    else:
        tint = tint.replace("#", "")
        if not tint.lower() == "off":
            match = re.search(r'^(?:[0-9a-fA-F]{3}){1,2}$', tint)
            if not match:
                await discord_bot.say('{} Invalid HTML HEX colour for a tint!\n'
                                      "You can also use 'background tint off' to remove it!".format(ctx.message.author.mention))
                return
    user_ctx = make_context(ctx.message, "!level")
    user_level_dict = return_command_usage(ctx=user_ctx)
    exp_data = calculate_level(user_level_dict)
    exp_data['cash'] -= user_level_dict['level_card']['cash_spent']
    cost = int(user_level_dict['level_card']['bg_tint_count'] * 1.25 + 60)
    if cost > exp_data['cash'] and not user_ctx.is_patreon:
        # Not enough cash
        await discord_bot.say("{} You don't have enough cash! "
                              "Use more commands to level up and gain more!"
                              "\nYou currently have: {}"
                              "\nThis tint costs: {}".format(
                                ctx.message.author.mention, exp_data['cash'], cost))
        return
    else:
        # Buy it here
        if not user_ctx.is_patreon:
            exp_data['cash'] -= cost
            user_level_dict['level_card']['cash_spent'] += cost
        await discord_bot.say("{} Enjoy your new background tint!\nYou now have {} cash left!".format(
            ctx.message.author.mention, exp_data['cash']))
    user_level_dict['level_card']['bg_tint_count'] += 1
    user_level_dict['level_card']['background_tint'] = tint.lower()
    write_command_usage("Discord", ctx.message.author.id, user_level_dict)
    return True
#########################

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
    #discord_bot.add_cog(aGames(discord_bot))
    discord_bot.run(bot.settings['token'])