import sys
sys.path.append('..')
import time
import glob
import re
import os

from config import settings
from utils import get_image_online
from utils import printf as print  # To make sure debug printing won't brake
from utils import file_to_list

from slugify import slugify

IGNORE_TXTS = ["Allowed Users.txt", "patreon_users.txt",
               "Blocked Users.txt", "Blocked Waifus.txt", "Blocked Words.txt",
               "commands.txt", "Sp00k.txt", "spoilers.txt", "Warned Users.txt"]
DEFAULT_TAGS = "+rating:safe+-genderswap"
WAIFU_END_TAGS = "+solo"
HUSBANDO_END_TAGS = "+solo+-1girl+-female"
OTP_END_TAGS = "+2girls+yuri+-comic"
MAX_IN_FOLDER = 10
SLEEP_COUNT = 0

os.chdir(settings['list_loc'])
for file in glob.glob("*.txt"):
    if "otp" in file.lower():
        continue
    print("$ Running through file: {}".format(file))
    gender = "Waifu"
    is_list = True
    if file in IGNORE_TXTS:
        continue
    if "husbando" in file.lower() or "male" in file.lower():
        # TODO: Temp
        continue
        gender = "Husbando"
    file = os.path.join(settings['list_loc'], file)
    lines = file_to_list(file)
    if isinstance(lines[2], str):
        is_list = False
    for line in lines:
        did_web = False
        if is_list:
            name = line[0]
        elif "(x)" in line:
            gender = "OTP"
            names = line.split("(x)")
            names = [s.replace(" ", "_") for s in names]
            name = '+'.join(names)
        else:
            name = line
        if "#" in name:
            continue
        if "Set-Cookie" in name:
            continue
        print("$ Char: {}".format(name))
        if gender == "Waifu":
            dir_folder = "waifu"
            tags = name.replace(" ", "_") + WAIFU_END_TAGS + DEFAULT_TAGS
        elif gender == "Husbando":
            MAX_IN_FOLDER = 5
            dir_folder = "husbando"
            tags = name.replace(" ", "_") + HUSBANDO_END_TAGS + DEFAULT_TAGS
        elif gender == "OTP":
            MAX_IN_FOLDER = 3
            dir_folder = "otps"
            tags = name + OTP_END_TAGS + DEFAULT_TAGS

        path_name = slugify(name,
                            word_boundary=True,
                            separator="_")
        path_name = os.path.join(settings['image_loc'], dir_folder, path_name)
        if os.path.exists(path_name):
            img_count = len(os.listdir(path_name))
            if img_count > MAX_IN_FOLDER:
                # Too many images
                while img_count > MAX_IN_FOLDER:
                    files = os.listdir(path_name)
                    print("$ Deleting: {}".format(files[0]))
                    os.remove(os.path.join(path_name, files[0]))
                    img_count -= 1
        else:
            img_count = 0
            os.makedirs(path_name)
        false_count = 0
        dl_count =  MAX_IN_FOLDER - img_count
        while img_count < MAX_IN_FOLDER:
            did_web = True
            tweet_image = get_image_online(tags, 0, 0, "", path_name)
            if dl_count > MAX_IN_FOLDER:
                break
            if false_count == 2:
                print("$ No images for: {}".format(path_name))
                break
            print(tweet_image)
            if not tweet_image:
                false_count += 1
            else:
                dl_count += 1
            time.sleep(10)
        if did_web:
            SLEEP_COUNT += 1
            if SLEEP_COUNT == 5:
                SLEEP_COUNT = 0
                time.sleep(120)
            else:
                time.sleep(20)

input()
