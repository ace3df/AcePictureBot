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
