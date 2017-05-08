import subprocess
import time
import os
import re

def call_process(process_line):
    ps = subprocess.Popen(process_line, shell=True, stdout=subprocess.PIPE)
    output = ps.stdout.read()
    ps.stdout.close()
    ps.wait()
    return output

def find_process(process_name):
    return call_process("ps -ef | grep '{}' | grep -v grep".format(process_name))

def is_running(process_name):
    output = find_process(process_name)
    if re.search(process_name, str(output)) is None:
        return False
    else:
        return True

# TODO: After checking if they're running, check last activity to see if they might be hanging (should all have global VAR)
process_check_list = ["Twitch.py", "Twitter.py", "Discord.py 1 2", "Discord.py 0 2"]
while True:
    print("Checking at: {}".format(time.strftime("%Y-%m-%d %H:%M")))
    for process in process_check_list:
        if not is_running("python3 " + process):
          # Start process
          print("Process: {} was not running ({})".format(process, time.strftime("%Y-%m-%d %H:%M")))
          print_name = process.split(".py")[0].lower()
          to_call = "nohup python3 {0} >{1}.out &".format(process, print_name)
          print("Running:")
          print(to_call)
          call_process(to_call)
        time.sleep(3)
    time.sleep(120)
