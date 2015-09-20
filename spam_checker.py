from datetime import timedelta
from datetime import datetime
from config import settings
import configparser
import os

FMT = '%Y-%m-%d %H:%M:%S.%f'


def config_get(section, key, file=0):
    with open(settings['settings']) as fp:
        config = configparser.ConfigParser(allow_no_value=True)
        config.readfp(fp)
        try:
            return config[section][key]
        except:
            return False


class SpamCheck(object):
    def __init__(self, twitter_id, twitter_handle, command):
        self._id = str(twitter_id)
        self._handle = twitter_handle
        self._command = command.lower()
        self._limit = str(config_get('Limit', self._command))
        self._limit_hours = str(config_get('Limit Hours', self._command))
        if not self._limit:
            self._limit = str(config_get('Limit', "default"))
            self._limit_hours = str(config_get('Limit Hours', "default"))
        self._now = datetime.now()
        try:
            self._userlist = open(
                os.path.join(
                    settings['ignore_loc'], 'User Limits.txt'), 'r').read(
            ).splitlines()
        except:
            self._userlist = "0||username||waifu||1||{0}||False".format(
                self._now).splitlines()

    def dump(self):
        with open(
                os.path.join(
                    settings['ignore_loc'], 'user limits.txt'), 'w') as file:
            file.write('\n'.join(self._userlist))
        return True

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

    def remove_one(self):
        edit_count = 0
        for a in self._userlist:
                line = a.split("||")
                id, handle, command, count, time, warning = line
                if not self._handle:
                    self._handle = handle
                if id == self._id and command == self._command:
                    # User is found with command
                    if int(count) <= 1:
                        # Just call remove_all
                        self.remove_all()
                        return True
                    self._userlist.pop(int(edit_count))
                    list_add = "{0}||{1}||{2}||{3}||{4}||False".format(
                                self._id, self._handle,
                                self._command, str(int(count) - 1),
                                time)
                    self._userlist += [list_add]
                    self.dump()
                    return True
                edit_count += 1
        self.dump()
        return True

    def remove_all(self):
        edit_count = 0
        for a in self._userlist:
                line = a.split("||")
                id, handle, command, count, time, warning = line
                if id == self._id and command == self._command:
                    self._userlist.pop(int(edit_count))
                    self.dump()
                    return True
                edit_count += 1
        self.dump()
        return True

    def command_limit(self):
        edit_count = 0
        for a in self._userlist:
                line = a.split("||")
                id, handle, command, count, time, warning = line
                if id == self._id and command == self._command:
                    # User is in list
                    if count >= self._limit:
                        # User has hit the limit
                        if (self._now - datetime.strptime(
                            time, FMT)) >= timedelta(
                             hours=int(self._limit_hours)):
                            # Limit is over, reset
                            self._userlist.pop(int(edit_count))
                            list_add = "{0}||{1}||{2}||{3}||{4}||True".format(
                                        self._id, self._handle,
                                        self._command, str(1),
                                        self._now)
                            self._userlist += [list_add]
                            self.dump()
                            return True
                        if warning == "False":
                            # Have no tweeted limit warning
                            self._userlist.pop(int(edit_count))
                            list_add = "{0}||{1}||{2}||{3}||{4}||True".format(
                                        self._id, self._handle,
                                        self._command, str(count),
                                        time)
                            self._userlist += [list_add]
                            self.dump()
                            return self.get_time(
                                datetime.strptime(time, FMT), False)
                        else:
                            # Still limited
                            return False
                    else:
                        # User is not limited; add
                        self._userlist.pop(int(edit_count))
                        list_add = "{0}||{1}||{2}||{3}||{4}||False".format(
                                    self._id, self._handle,
                                    self._command, str(int(count) + 1),
                                    time)
                        self._userlist += [list_add]
                        self.dump()
                        return True
                edit_count += 1

        # User not in list; add
        list_add = "{0}||{1}||{2}||1||{3}||False".format(
                    self._id, self._handle,
                    self._command, self._now)
        self._userlist.append(list_add)
        self.dump()
        return True


def remove_one_limit(twitter_id, command, twitter_handle=""):
    spam_object = SpamCheck(twitter_id, twitter_handle, command)
    spam_object.remove_one()


def remove_all_limit(twitter_id, command, twitter_handle=""):
    spam_object = SpamCheck(twitter_id, twitter_handle, command)
    spam_object.remove_all()


def user_spam_check(twitter_id, twitter_handle, command):
    spam_object = SpamCheck(twitter_id, twitter_handle, command)
    # Check if user is in the list already
    # If not, then add it there
    return spam_object.command_limit()
