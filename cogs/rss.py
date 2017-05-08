from .utils import config, checks
from .utils.paginator import Pages
from .utils.scrape import scrape_website

from discord.ext import commands
import discord
import feedparser

import datetime
import logging
import asyncio
import json
import re

log = logging.getLogger(__name__)
MAX_RSS_PER_SERVER = 5
# TODO:
# Finish all of this
# clean it up
# add sync posting
class RSSInfo:
    __slots__ = ('url', 'owner_id', 'most_recent_ids', 'blacklist_tags', 'post_count', 'channel_id', 'created_at')
    def __init__(self, url, owner_id, **kwargs):
        self.url = url
        self.owner_id = owner_id
        self.most_recent_ids = kwargs.pop('most_recent_ids', [])
        self.blacklist_tags = kwargs.pop('blacklist_tags', [])
        self.post_count = kwargs.pop('post_count', 0)
        self.channel_id = kwargs.pop('channel_id')
        self.created_at = kwargs.pop('created_at', 0.0)

    def __str__(self):
        return "RSS Feed <{}> - Created at {} by {}".format(self.url, self.created_at, self.owner_id)
    
    async def embed(self, ctx):
        e = discord.Embed(title=self.url)
        e.add_field(name='Owner', value='<@!%s>' % self.owner_id)
        e.add_field(name='Usage', value=self.post_count)
        if self.most_recent_ids:
            e.add_field(name='Recent Post IDs', value=', '.join(self.most_recent_ids[0:3]))

        if self.created_at:
            e.timestamp = datetime.datetime.fromtimestamp(self.created_at)

        owner = discord.utils.find(lambda m: m.id == self.owner_id, ctx.bot.get_all_members())
        if owner is None:
            owner = await ctx.bot.get_user_info(self.owner_id)

        e.set_author(name=str(owner), icon_url=owner.avatar_url or owner.default_avatar_url)
        return e


class RSSEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, RSSInfo):
            payload = {
                attr: getattr(obj, attr)
                for attr in RSSInfo.__slots__
            }
            payload['__rss__'] = True
            return payload
        return json.JSONEncoder.default(self, obj)


def rss_decoder(obj):
    if '__rss__' in obj:
        return RSSInfo(**obj)
    return obj


class RSS:
    """The RSS related commands."""

    def __init__(self, bot):
        self.bot = bot
        self.config = config.Config('rss.json', encoder=RSSEncoder, object_hook=rss_decoder,
                                                loop=bot.loop)
        self.get_thread = bot.loop.create_task(self.get_rss_task())
        # await self.bot.send_message(channel, )

    def verify_lookup(self, lookup):
        if '@everyone' in lookup or '@here' in lookup:
            raise RuntimeError('That url includes blocked words.')

        if not lookup:
            raise RuntimeError('You need to actually pass in a url.')

        urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', lookup)
        if not urls:
            raise RuntimeError('This is not a valid URL.')
        soup = feedparser.parse(urls[0])
        if not soup:
            raise RuntimeError('Failed to load RSS feed. Try again later?')
        if not soup.entries:
            raise RuntimeError('No RSS Entries were found, is this a valid RSS feed?')

    def get_rss(self, db, channel_id, lookup):
        entry = [entry for entry in db if entry.url == lookup and entry.channel_id == channel_id]
        if len(entry) >= 1:
            entry = entry[0]
        return entry

    def clean_html(self, raw_html):
        cleanr = re.compile('<.*?>')
        clean_text = re.sub(cleanr, '', raw_html)
        clean_readmore = re.sub('Read.*?Siliconera!', '', clean_text, flags=re.DOTALL)
        return clean_readmore.replace("&#32;", "").strip()

    def embed_feed(self, entry):
        description = self.clean_html(entry.get('summary', ''))
        description = (description[:275] + '..') if len(description) > 275 else description
        e = discord.Embed(description=description)
        soup = scrape_website(entry['link'])
        image_url = soup.find('meta', attrs={'property':'og:image'})
        if image_url:
            e.set_image(url=image_url['content'])
        e.title = "{}".format(entry['title'])
        e.url = entry['link']
        e.color = 0x1f8b4c
        e.timestamp = datetime.datetime.utcnow()
        return e

    async def post_feed(self, channel, feed):
        soup = feedparser.parse(feed.url)
        if not soup:
            # Failed to load/read rss
            report_message  ="Failed to load RSS Feed: {}\nFor Channel: {} ({})".format(
                feed.url, channel)
            await self.bot.send_report(report_message)
        for item in soup.entries[:2]:
            if item['id'] in feed.most_recent_ids:
                continue
            if item.get('category') and str(item['category']).replace(" ", "").lower().strip() in feed.blacklist_tags:
                continue
            feed.post_count += 1
            feed.most_recent_ids.append(item['id'])
            feed.most_recent_ids = feed.most_recent_ids[-5:]
            await self.bot.send_message(channel, embed=self.embed_feed(item))
            await asyncio.sleep(3)
        return feed

    @commands.group(pass_context=True, invoke_without_command=True, no_pm=True)
    async def rss(self, ctx):
        server = ctx.message.server
        db = self.config.get(server.id, [])
        results = []
        if db:
            past_channels = {}
            past_members = {}
            for feed in [u for u in db if isinstance(u, RSSInfo)]:
                if not past_channels.get(feed.channel_id):
                    past_channels[feed.channel_id] = self.bot.get_channel(feed.channel_id)
                if not past_members.get(feed.owner_id):
                    past_members[feed.owner_id] = server.get_member(feed.owner_id)
                fmt = "**#{}** - {}\nAdded by: {}\nCreated at: {}".format(
                    past_channels[feed.channel_id],
                    feed.url, past_members[feed.owner_id],
                    datetime.datetime.fromtimestamp(feed.created_at))
                results.append(fmt)
        if results:
            try:    
                p = Pages(self.bot, message=ctx.message, entries=results)
                p.embed.colour = 0x738bd7 # blurple
                p.embed.set_author(name=ctx.message.author.display_name,
                                   icon_url=ctx.message.author.avatar_url or ctx.message.author.default_avatar_url)
                await p.paginate()
            except Exception as e:
                await self.bot.say(e)
        else:
            await self.bot.say("This server has no RSS feeds.")

    @rss.command(pass_context=True, aliases=['add'])
    async def create(self, ctx, url : str, *, channel : discord.Channel = None):
        server = ctx.message.server
        if channel is None:
            channel = ctx.message.channel
        lookup = url.lower().strip()
        try:
            self.verify_lookup(lookup)
        except RuntimeError as e:
            return await self.bot.say(e)
        db = self.config.get(server.id, [])
        # TODO: Add patreon owner/server check here
        if len(db) >= MAX_RSS_PER_SERVER:
            # Set a max num of RSS feeds in server to not allow them to go crazy.
            await self.bot.say('You have hit the max number of feeds you can set!')
            return
        if db and lookup in [u.url for u in db if isinstance(u, RSSInfo)]:
            await self.bot.say('This feed is already in this channel!')
            return

        soup = feedparser.parse(lookup)
        possible_tags = []
        most_recent_ids = []
        for post in soup.entries:
            most_recent_ids.append(post['id'])
            if post.get('category') and str(post['category']).replace(" ", "").lower().strip() not in possible_tags:
                possible_tags.append(str(post['category']).replace(" ", "").lower().strip())
        blacklist_tags = []
        if len(possible_tags) > 1:
            msg = ("Multiple post tags were found. Say which ones you want to **ignore** (example: {})"
                   "\nSay 'None' to keep all tags!\n`{}`".format(
                    ', '.join(possible_tags[0:2]) if len(possible_tags) > 3 else "gaming, manga",
                    ', '.join(possible_tags)))
            await self.bot.say(msg)
            input_tags = await self.bot.wait_for_message(author=ctx.message.author, channel=ctx.message.channel, timeout=60.0)
            if input_tags is None:
                await self.bot.say('You took too long. Ignoring no tags.')
            else:
                user_tags = input_tags.content.replace(" ", "").split(",")
                for tag in user_tags:
                    if tag.lower().strip() in possible_tags:
                        blacklist_tags.append(tag)

        db.append(RSSInfo(lookup, ctx.message.author.id,
                             channel_id=channel.id,
                             blacklist_tags=blacklist_tags,
                             most_recent_ids=most_recent_ids[:-2],
                             created_at=datetime.datetime.utcnow().timestamp()))

        await self.config.put(server.id, db)
        await self.bot.say(":ok_hand: RSS Feed added. It will check for new posts every 6 minutes.")

    @rss.command(pass_context=True, aliases=['delete'])
    async def remove(self, ctx, url : str, *, channel : discord.Channel = None):
        if channel is None:
            channel = ctx.message.channel
        lookup = url.lower()
        server = ctx.message.server

        db = self.config.get(server.id, [])
        feed = self.get_rss(db, channel.id, lookup)
        if not feed:
            await self.bot.say('That feed is currently not in this channel.')
            return

        can_delete = checks.is_owner_check(ctx.message) or feed.owner_id == ctx.message.author.id
        if not can_delete:
            await self.bot.say('You do not have permissions to delete this feed.')
            return

        db.remove(feed)
        await self.config.put(server.id, db)
        await self.bot.say("The feed has been removed.")

    @rss.command(pass_context=True, aliases=['owner'])
    async def info(self, ctx, url : str, *, channel : discord.Channel = None):
        server = ctx.message.server
        if channel is None:
            channel = ctx.message.channel
        lookup = url.lower().strip()
        db = self.config.get(server.id, [])
        feed = self.get_rss(db, channel.id, lookup)
        if not feed:
            await self.bot.say('That feed is currently not in this channel.')
            return

        embed = await feed.embed(ctx)
        await self.bot.say(embed=embed)

    @rss.command(pass_context=True)
    @checks.is_owner()
    async def test(self, ctx):
        a = {'title': 'Disgaea 5 Complete Introduces Killia, Seraphina, And More Of Its Colorful Cast', 'slash_comments': '0', 'link': 'http://www.siliconera.com/2017/04/12/disgaea-5-complete-introduces-killia-seraphina-colorful-cast/', 'wfw_commentrss': 'http://www.siliconera.com/2017/04/12/disgaea-5-complete-introduces-killia-seraphina-colorful-cast/feed/', 'author': 'Casey', 'summary': '<p>A new trailer for the upcoming strategy JRPG introduces two of the game\'s main charcters: Killia and Seraphina.</p>\n<p>Read <a href="http://www.siliconera.com/2017/04/12/disgaea-5-complete-introduces-killia-seraphina-colorful-cast/" rel="nofollow">Disgaea 5 Complete Introduces Killia, Seraphina, And More Of Its Colorful Cast</a> on <a href="http://www.siliconera.com" rel="nofollow">Siliconera</a>!</p>', 'comments': 'http://www.siliconera.com/2017/04/12/disgaea-5-complete-introduces-killia-seraphina-colorful-cast/#respond', 'title_detail': {'language': None, 'value': 'Disgaea 5 Complete Introduces Killia, Seraphina, And More Of Its Colorful Cast', 'base': 'http://www.siliconera.com/feed/', 'type': 'text/plain'}, 'summary_detail': {'language': None, 'value': '<p>A new trailer for the upcoming strategy JRPG introduces two of the game\'s main charcters: Killia and Seraphina.</p>\n<p>Read <a href="http://www.siliconera.com/2017/04/12/disgaea-5-complete-introduces-killia-seraphina-colorful-cast/" rel="nofollow">Disgaea 5 Complete Introduces Killia, Seraphina, And More Of Its Colorful Cast</a> on <a href="http://www.siliconera.com" rel="nofollow">Siliconera</a>!</p>', 'base': 'http://www.siliconera.com/feed/', 'type': 'text/html'}, 'guidislink': False, 'author_detail': {'name': 'Casey'}, 'links': [{'href': 'http://www.siliconera.com/2017/04/12/disgaea-5-complete-introduces-killia-seraphina-colorful-cast/', 'rel': 'alternate', 'type': 'text/html'}], 'id': 'http://www.siliconera.com/?p=626583', 'authors': [{'name': 'Casey'}], 'tags': [{'label': None, 'term': 'Uncategorized', 'scheme': None}, {'label': None, 'term': 'Disgaea 5: Alliance of Vengeance', 'scheme': None}, {'label': None, 'term': 'Nintendo Switch', 'scheme': None}, {'label': None, 'term': 'PlayStation 4', 'scheme': None}], 'published': 'Wed, 12 Apr 2017 15:00:47 +0000'}
        e = self.embed_feed(a)
        await self.bot.say(embed=e)

    @rss.command()
    @checks.is_owner()
    async def run(self):
        if self.get_thread:
            self.get_thread.cancel()
        self.get_thread = self.bot.loop.create_task(self.get_rss_task())

    async def run_rss_feed(self):
        past_servers = {}
        past_channels = {}
        past_members = {}
        database = self.config.all()
        for server_id, server_feeds in database.items():
            if not past_servers.get(server_id):
                past_servers[server_id] = self.bot.get_server(server_id)
                if not past_servers[server_id]:
                    # TODO: remove from file
                    log.warning("[SERVER DEAD] {}".format(past_servers[server_id]))
                    continue
            for feed in server_feeds:
                if not past_channels.get(feed.channel_id):
                    past_channels[feed.channel_id] = self.bot.get_channel(feed.channel_id)
                if not past_members.get(feed.owner_id):
                    past_members[feed.owner_id] = past_servers[server_id].get_member(feed.owner_id)
                updated_feed = await self.post_feed(past_channels[feed.channel_id], feed)
                db = database.get(server_id, [])
                db.remove(feed)
                db.append(updated_feed)
                await self.config.put(server_id, db)

    async def get_rss_task(self):
        await self.bot.wait_until_ready()
        log.info("[RSS Thread] Starting GET RSS Task.")
        while not self.bot.is_closed:
            try:
                await self.run_rss_feed()
            except Exception as e:
                log.warning(e)
            await asyncio.sleep(360)  # 6 mins

def setup(bot):
    bot.add_cog(RSS(bot))