from config import settings
import functions
import utils
import urllib.request
from threading import Thread
import xml.etree.ElementTree as etree
import time
import os
import re

__program__ = "AcePictureBot"
__version__ = "2.0.0"

BLOCKED_IDS = utils.file_to_list(
                os.path.join(settings['list_loc'],
                             "blocked_users.txt"))
LIMITED = False
HAD_ERROR = False
TWEETS_READ = []
RATE_LIMIT_DICT = {}
START_TIME = time.time()
HANG_TIME = time.time()

API = None
STATUS_API = None
SAPI = None


def read_notifications(api, reply, tweets_read):
    """ Read the bot's notification timeline to catch up
        on missed tweets from downtime.
        api -- The Twitter API object.
        reply -- If True will reply to each command.
        tweets_read -- List of already read Twitter IDs.
    """
    print("read_notifications")


def status_account(api):
    """ Read RSS feeds and post them on the status Twitter account."""
    def read_rss(url, name, pre_msg, find_xml):
        recent_id = open(os.path.join(settings['ignore_loc'],
                         name), 'r').read()
        rss = urllib.request.urlopen(url).read().decode("utf-8")
        xml = etree.fromstring(rss)
        entry = xml[find_xml['entries_in']]
        current_id = entry.findtext(
            find_xml['entry_id'])

        if current_id == recent_id:
            return False

        with open(os.path.join(settings['ignore_loc'], name), "w") as f:
            f.write(current_id)

        msg_url = entry.find(find_xml['link_id']).get('href')
        msg_msg = re.sub('<[^<]+?>', '', entry.findtext(find_xml['msg_id']))
        msg_msg = re.sub(' +', ' ', os.linesep.join(
                    [s for s in msg_msg.splitlines() if s])).lstrip()
        msg = "{0}{1}\n{3}".format(pre_msg,
                                   utils.short_str(msg_msg, 90),
                                   msg_url)
        print(msg)
        #functions.status_tweet(STATUS_API, msg)

    while True:
        url = "http://ace3df.github.io/AcePictureBot/feed.xml"
        name = "BlogHistory.txt"
        pre_msg = "[Blog Entry]]\n"
        find_xml = {"entries_in": 0,
                    "entry_id": "{http://www.w3.org/2005/Atom}id",
                    "link_id": "{http://www.w3.org/2005/Atom}link",
                    "msg_id": "title"}
        read_rss(url, name, pre_msg, find_xml)
        time.sleep(60)
        url = "https://github.com/ace3df/AcePictureBot/commits/master.atom"
        name = "GitCommit.txt"
        pre_msg = "[Git Commit]\n"
        find_xml = {"entries_in": 5,
                    "entry_id": "{http://www.w3.org/2005/Atom}id",
                    "link_id": "{http://www.w3.org/2005/Atom}link",
                    "msg_id": "{http://www.w3.org/2005/Atom}content"}
        read_rss(url, name, pre_msg, find_xml)
        time.sleep(60)



def start_stream(SAPI=None):
    if SAPI is None:
        SAPI = 2#functions.login(REST=False)
    print("START STREAM")
    pass


def handle_stream(SAPI):
    start_stream(SAPI)
    global HANG_TIME
    # Create a loop which makes sure that the stream
    # hasn't been haning at all.
    # If it has, it will try to reconnect.
    while True:
        time.sleep(5)
        elapsed = (time.time() - HANG_TIME)
        if elapsed > 600:
            print("[WARNING] STREAM HANING. RESTARTING...")
            try:
                # Tweet to the status bot that the stream was hanging.
                msg = settings['twitter_track'][0] + \
                 ":\nStream haning. Restarting..."
                print(msg)
                functions.status_tweet(STATUS_API, msg)
            except:
                pass
            try:
                # Try and disconnect the stream if it's not done already.
                SAPI.disconnect()
            except:
                pass
            time.sleep(1)
            # Restart the stream and catch up on late tweets.
            Thread(target=start_stream).start()
            Thread(target=read_notifications,
                   args=(API, True, TWEETS_READ)).start()
            # Restart HANG_TIME.
            HANG_TIME = time.time()

if __name__ == '__main__':
    # Load read IDs of already read tweets.
    TWEETS_READ = utils.file_to_list(
                os.path.join(settings['ignore_loc'],
                             "tweets_read.txt"))
    # Get the main bot's API and STREAM request.
    API, SAPI = 1, 2#functions.login(REST="Both")
    # Get the status account API.
    STATUS_API = 0#functions.login(status=True)
    # Start 3 _threads:
    # read_notifcations (for late start ups).
    # status_account (to check if there is a problem).
    # handle_stream (check if the stream has disconnected/haning).
    Thread(target=read_notifications, args=(API, True, TWEETS_READ)).start()
    Thread(target=status_account, args=(STATUS_API, )).start()
    Thread(target=handle_stream, args=(SAPI, )).start()
