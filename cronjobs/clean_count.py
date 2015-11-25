""" Cleans the count.ini to remove users that have only used x amount of commands.
Keeping them in there and letting the count.ini line count add up is not good.
"""
from configparser import RawConfigParser
import time
import sys
import os

count_file = r"../count.ini"
busy_file = r"../is_busy.txt"
needed_count = 6
to_delete = []
config = RawConfigParser(allow_no_value=True)
config.read_file(open(count_file))
for each_section in config.sections():
    if each_section == "global" or each_section == "failed":
        continue
    if each_section == "waifu" or each_section == "husbando":
        continue
    count = 0
    for (each_key, each_val) in config.items(each_section):
        if each_val is None:
            if each_section not in to_delete:
                to_delete.append(each_section)
        else:
            count += int(each_val)
    if count <= needed_count:
        to_delete.append(each_section)

for sec in to_delete:
    config.remove_section(sec)

while True:
    if not os.path.exists(busy_file):
        with open(count_file, 'w') as configfile:
            config.write(configfile)
        sys.exit(0)
    time.sleep(1)