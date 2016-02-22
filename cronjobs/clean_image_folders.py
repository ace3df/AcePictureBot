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

IGNORE_TXTS = ["Blocked Users.txt", "Blocked Waifus.txt", "Blocked Words.txt",
               "commands.txt", "Sp00k.txt", "spoilers.txt", "Warned Users.txt"]
DEFAULT_TAGS = "+rating:safe+-genderswap"
WAIFU_END_TAGS = "+1girl+solo"
HUSBANDO_END_TAGS = "+solo+-1girl+-female"
OTP_END_TAGS = "+2girls+yuri+-comic"
MAX_IN_FOLDER = 5
SLEEP_COUNT = 0

os.chdir(settings['list_loc'])
for file in glob.glob("*.txt"):
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
        img_count = MAX_IN_FOLDER
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
        if gender == "Waifu":
            dir_folder = "waifu"
            tags = name.replace(" ", "_") + WAIFU_END_TAGS + DEFAULT_TAGS
        elif gender == "Husbando":
            MAX_IN_FOLDER = 3
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
            img_count -= len(os.listdir(path_name))
            if img_count <= 0:
                # Has enough images
                if img_count < -3:
                    # Too many images
                    while img_count < 0:
                        files = os.listdir(path_name)
                        os.remove(os.path.join(path_name, files[0]))
                        img_count += 1
                continue
        else:
            os.makedirs(path_name)

        false_count = 0
        print(path_name)
        for x in range(0, img_count):
            tweet_image = get_image_online(tags, 0, 0, "", path_name)
            if false_count == 2:
                break
            if not tweet_image:
                false_count += 1
                print("$ Possible no images for:")
                print(path_name)
                print("$")
                continue
            else:
                img_count -= 1
        SLEEP_COUNT += 1
        if SLEEP_COUNT == 5:
            SLEEP_COUNT = 0
            time.sleep(120)
        else:
            time.sleep(10)
