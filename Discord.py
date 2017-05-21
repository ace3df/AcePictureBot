from collections import Counter, OrderedDict
from operator import itemgetter
from datetime import datetime
import traceback
import random
import types
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
                       calculate_level, return_command_usage, return_command_usage_date,
                       write_command_usage)

from discord.ext import commands
from bs4 import BeautifulSoup
from tabulate import tabulate
from PIL import Image
import discord
import asyncio
import aiohttp

prefix = discord_settings.get('command_prefix', ["!apb "])
# 0, 2 # 1, 2
discord_bot = commands.Bot(command_prefix=prefix, pm_help=None, shard_id=int(sys.argv[1].strip()), shard_count=int(sys.argv[2].strip()))
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
initial_extensions = [
    'cogs.meta',
    'cogs.admin',
    'cogs.repl',
    'cogs.tags',
    'cogs.rss',
    'cogs.alterakiba',
    'cogs.otakuuniverse',
]


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
        return False  # Silent return
    message = ctx.raw_data
    command = ctx.command
    reply_text = "{0.author.mention}{1} {2}".format(
        message,
        "'s" if command in ["mywaifu", "myhusbando"] or ctx.is_patreon_vip and command in ["myidol", "myotp"] else "",
        reply_text)
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
                    await discord_bot.change_presence(game=new_status)
                    await asyncio.sleep(8)
            else:
                new_status = discord.Game(name=status, idle=False)
                await discord_bot.change_presence(game=new_status)
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
    if message.author.bot:  # Ignore bots
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
    if message.content.startswith("!apb "):
        return
    if not command:
        return
    ctx = make_context(message, command)
    if not bot.check_rate_limit(ctx, or_seconds=40, or_per_user=4):
        return
    if command in ["mywaifu", "myhusbando"] and not ctx.user_ids.get('twitter', False):  # Don't have a Twitter account linked
        reply_text = create_token(message.author.id, bot.source.name)
        await discord_bot.send_message(message.author, reply_text)
        return
    reply_text, reply_media = bot.on_command(ctx)
    # Handle MyWaifu command as we handle it a little differently on Discord.
    # TODO: make a better way to handle this based on ctx.bot.source.get_new_mywaifu
    if reply_text and command in ["mywaifu", "myhusbando"]:
        if "I don't know who" in reply_text:
            reply_text = reply_text.replace("Register or try tweeting",
                                            "Register on Twitter or try saying")
    await send_reply(reply_text, reply_media, ctx, server_settings)


@discord_bot.command(pass_context=True)
async def info(ctx, member : discord.Member = None):
    if not member:
        now = datetime.utcnow()
        delta = now - bot.uptime
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        if days > 1:
            fmt = '{d} days\n{h} hours\n{m} minutes\n{s} seconds'
        elif days:
            fmt = '{d} day\n{h} hours\n{m} minutes\n{s} seconds'
        else:
            fmt = '{h} hours\n{m} minutes\n{s} seconds'

        embed = discord.Embed(description="Bot Infomation:")
        embed.title = "Click here for a full list of commands!"
        embed.url = "http://ace3df.github.io/AcePictureBot/commands/"
        embed.color = 0x1f8b4c
        total_members = sum(len(s.members) for s in discord_bot.servers)
        total_online  = sum(1 for m in discord_bot.get_all_members() if m.status != discord.Status.offline)
        unique_members = set(discord_bot.get_all_members())
        channel_types = Counter(c.type for c in discord_bot.get_all_channels())
        voice = channel_types[discord.ChannelType.voice]
        text = channel_types[discord.ChannelType.text]

        members = '%s total\n%s online\n%s unique' % (total_members, total_online, len(unique_members),)
        embed.add_field(name='Members', value=members)
        embed.add_field(name='Channels', value='{} total\n{} text\n{} voice'.format(text + voice, text, voice))
        embed.add_field(name='Uptime', value=fmt.format(d=days, h=hours, m=minutes, s=seconds))
        embed.timestamp = bot.uptime
        embed.add_field(name='Servers',
                        value='{} (In Shard: {})\n{} Total'.format(
                            len(discord_bot.servers),
                            sys.argv[1].strip(), "xd"))
        embed.add_field(name='Commands Run', value=sum(bot.commands_used.values()))
        most_used = ["{}: {}".format(a.title(), b) for a, b in bot.commands_used.most_common(3)]
        if most_used:
            embed.add_field(name='Most Used Commands', value='\n'.join(most_used))
        debug_info = ("Current Server ID: {0.server.id}"
                      "\nCurrent Channel ID: {0.channel.id}"
                      "\nYour ID: {0.author.id}".format(ctx.message))
        embed.add_field(name='Debug Info', value=debug_info)
        embed.set_footer(text="Follow @AcePictureBot on Twitter!",
                        icon_url='https://cdn2.iconfinder.com/data/icons/minimalism/512/twitter.png')
    else:
        embed = discord.Embed(description="Discord Information only")
        embed.title = "Infomation for Member: {}".format(member)
        embed.color = 0x1f8b4c
        attrs = {'bot': bot,
             'screen_name': member.name,
             'discord_id': member.id,
             'command': "waifu",
             'message': ctx.message.content,
             'raw_data': ctx.message,
             'raw_bot': discord_bot
            }
        user_ctx = UserContext(**attrs)
        cmd_usage = return_command_usage(user_ctx)
        most_used = ["{}: {}".format(a.title(), b) for a, b in cmd_usage.most_common(5)]
        least_used = ["{}: {}".format(a.title(), b) for a, b in list(reversed(cmd_usage.most_common()[-5:]))]
        if most_used:
            embed.add_field(name='Most Used Commands', value='\n'.join(most_used))
        if least_used:
            embed.add_field(name='Least Used Commands', value='\n'.join(least_used))
        embed.set_thumbnail(url=member.avatar_url)
        first_used = return_command_usage_date(user_ctx)
        embed.add_field(name='Commands Run', value=sum(cmd_usage.values()))
        embed.add_field(name='First recorded use', value=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(first_used)))
        embed.add_field(name='Connected Accounts', value=', '.join(["{}".format(a.title()) for a, b in user_ctx.user_ids.items() if b]))
    await discord_bot.say(embed=embed)


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
    before = ctx.message.timestamp
    user_ctx = make_context(ctx.message, command)
    user_ctx.args = user_ctx.args.lower().replace("!apb benchmark", "").strip()
    reply_text, reply_media = bot.on_command(user_ctx)
    after = datetime.utcnow()
    post_message = "```Command: {}\nArgs: {}\nTime: {}\n{} (Media: {})```".format(
        command, user_ctx.args, after - before, reply_text, bool(reply_media))
    before_post = datetime.utcnow()
    sent_message = await send_reply(post_message, reply_media, user_ctx)
    post_message = "```Command: {}\nArgs: {}\nTime: {}\n{} (Media: {})\nPost Time: {}```".format(
        command, user_ctx.args, after - before, reply_text, bool(reply_media), sent_message.timestamp - before_post)
    await discord_bot.edit_message(sent_message, post_message)


@discord_bot.command(name="airing", pass_context=True)
async def airing(ctx):
    from commands import airing
    await discord_bot.send_typing(ctx.message.channel)
    message = ctx.message
    user_ctx = make_context(message, "!airing")
    user_ctx.args = user_ctx.args.lower().replace("!apb airing ", "")
    reply_text = airing.callback(user_ctx)
    await discord_bot.say(reply_text)


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
    discord_bot.send_report = types.MethodType(send_report, discord_bot)
    #await discord_bot.send_report("test message")   


async def send_report(self, message):
    debug_channel_id = bot.settings.get('report_channel')
    if debug_channel_id:
        debug_channel = self.get_channel(debug_channel_id)
        await self.send_message(debug_channel, message)


if __name__ == '__main__':
    if not bot.settings.get('token', False):
        raise Exception("Missing Discord Bot Token from Discord Settings.json in /Configs/")
    discord_bot.client_id = bot.settings.get('client_id', '')
    discord_bot.owner_id = bot.settings.get('owner_id', '')
    discord_bot.shard_id = int(sys.argv[1].strip())
    discord_bot.loop.create_task(change_status())
    if bot.settings.get('datadog', False):
        discord_bot.loop.create_task(datadog_data())
    for extension in initial_extensions:
        try:
            discord_bot.load_extension(extension)
        except Exception as e:
            print('Failed to load extension {}\n{}: {}'.format(extension, type(e).__name__, e))
    discord_bot.run(bot.settings['token'])
