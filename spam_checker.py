from functions import config_get
from config import settings
from datetime import datetime, timedelta
import pickle
import os

FMT = '%Y-%m-%d %H:%M:%S'


class SpamCheck(object):
    def __init__(self, twitter_id, twitter_handle, command):
        self._id = int(twitter_id)
        self._handle = twitter_handle
        self._command = command.lower()

        self._limit = int(config_get('Limit', self._command))
        self._limit_hours = int(config_get('Limit Hours', self._command))
        if not self._limit:
            self._limit = int(config_get('Limit', "default"))
            self._limit_hours = int(config_get('Limit Hours', "default"))

        self._now = datetime.now()

        try:
            self._userlist = pickle.load(open(
                os.path.join(settings['ignore_loc'], 'userlimit.pkl'), 'rb'))
        except:
            self._userlist = [[0, "username", "command", 1, self._now, False]]

    def dump(self):
        pickle.dump(self._userlist, open(
            os.path.join(settings['ignore_loc'], 'userlimit.pkl'), 'wb'))

    def get_time(self, lst_time, is_max):
        elapsed = self._now - (lst_time)
        if is_max:
            tleft = timedelta(hours=int(self._max_limit_hours)) - elapsed
        else:
            tleft = timedelta(hours=int(self._limit_hours)) - elapsed
        tleft = str(tleft).split(".")
        tleft = tleft[0]
        part_two = None
        if "day" in str(tleft):
            tleft = tleft.split(", ")
            part_one = tleft[0]
            part_two = tleft[1].split(":")
            msg = part_one + " and " + part_two[0]
        else:
            part_two = tleft.split(":")
            time_left = part_two[0]
            msg = time_left
        if int(part_two[0]) == 0:
            msg = part_two[1] + " minutes"
        elif int(part_two[0]) > 1:
            msg += " hours"
        else:
            msg += " hour"
        if is_max:
            msg = "You can not use any command for another %s!" % (msg)
        else:
            msg = "You can not use %s for another %s!" % (
                self._command, msg)
        return msg

    def command_limit(self):
        print(self._limit)
        for i, [lst_id, lst_handle, lst_command, lst_count,
                lst_time, lst_warning] in enumerate(self._userlist):
            if lst_id == self._id and lst_command == self._command:
                # User is in list
                if lst_count >= self._limit:
                    # User has hit the limit
                    if ((self._now - lst_time) >= timedelta(
                         hours=int(self._limit_hours))):
                        # Limit over, rest
                        self._userlist[i] = [self._id, self._handle,
                                             self._command, 1,
                                             self._now, False]
                        self.dump()
                        return True
                    if not lst_warning:
                        # Have not tweeted warning, so tweet it
                        self._userlist[i] = [self._id, self._handle,
                                             self._command, lst_count,
                                             lst_time, True]
                        self.dump()
                        return self.get_time(lst_time, False)
                    else:
                        # Still limited
                        return False
                else:
                    # User is not limited; add
                    self._userlist[i] = [self._id, self._handle,
                                         self._command, lst_count + 1,
                                         lst_time, False]
                    self.dump()
                    return True
        # Add to list
        list_add = [self._id, self._handle, self._command, 1, self._now, False]
        self._userlist.append(list_add)
        self.dump()
        return True


def user_spam_check(twitter_id, twitter_handle, command):
    spam_object = SpamCheck(twitter_id, twitter_handle, command)
    # Check if user is in the list already
    # If not, then add it there
    return spam_object.command_limit()
