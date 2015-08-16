from config import settings
import os


def file_to_list(file):
    lines = list(filter(None,
                 open(file, 'r', encoding='utf-8').read().splitlines()))
    to_list = []
    split_by = False
    keep = -1
    if ":" in lines[0]:
        split_by = ":"
        keep = 0
    elif "||" in lines[0]:
        split_by = "||"

    for line in lines:
        # Comment line
        if line[0] == "#":
            continue
        if split_by:
            line = line.split(split_by)
            if keep >= 0:
                line = line[keep]
        to_list.append(line)
    return to_list


def short_str(string, cap=30):
    if not string:
        return string
    try:
        count = 0
        if string[cap + 5]:
            for char in string:
                count += 1
                if count >= cap or not char:
                    break
            string = string[:count].strip()
            return string + "[...]"
    except:
        return string.strip()


def get_command(string):
    string = string.lower()
    string = string.replace("waifu", "{GENDER}")
    string = string.replace("husbando", "{GENDER}")
    triggers = file_to_list(
                    os.path.join(settings['list_loc'],
                                 "commands.txt"))
    command = [s for s in triggers if str(s).lower() in string.lower()]
    if not command:
        return False
    else:
        command = command[0]
        if type(command) is bool:
            return False
    return command
