# basic split-processing for multiple api keys
import os
import glob
import subprocess
import sys
import datetime
from typing import List
import threading
import argparse

api_keys = []

def split_into_temp_paths(folder_path, num:int) -> List[str]:
    """
    Glob the folder_path, write to temporary paths, return the temporary paths.
    """
    all_files = glob.glob(os.path.join(folder_path, "*"))
    # exclude the text files.
    all_files = [file for file in all_files if file.split('.')[-1] != 'txt']
    # split into num parts
    num_files_per_part = len(all_files) // num
    print(f"num_files_per_part: {num_files_per_part}")
    parts_len = [num_files_per_part] * num
    # add remainder to last part
    parts_len[-1] += len(all_files) % num
    print(f"parts_len: {parts_len}")
    # save to process_date_{i}.txt
    temp_paths = []
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    for i in range(num):
        temp_path = f"process_{date}_{i}.txt"
        temp_paths.append(temp_path)
        with open(temp_path, 'w') as f:
            for j in range(parts_len[i]):
                f.write(all_files.pop() + "\n")
    return temp_paths
def execute_command(command):
    """
    Execute command, set event to True when finished.
    """
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    print(f"stdout: {stdout}")
    print(f"stderr: {stderr}")

def split_and_execute(folder_path):
    num = len(api_keys)
    temp_paths = split_into_temp_paths(folder_path, num)
    # execute query-gemini-4.py for each temp_path
    threads = []
    event = threading.Event()
    for i in range(num):
        temp_path = temp_paths[i]
        api_key = api_keys[i]
        print(f"temp_path: {temp_path}")
        print(f"api_key: {api_key}")
        t = threading.Thread(target=execute_command, args = (["python3", "query-gemini-v2.py", "--api_key", api_key, "--path", temp_path, "--threaded"], event))
        t.start()
        threads.append(t)
    # wait for all threads to finish, if keyboard interrupt, then exit
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("KeyboardInterrupt")
        # kill all threads
        event.set()
        for t in threads:
            t.kill()
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder_path', type=str, required=True, help='Path to the folder to split and execute.')
    args = parser.parse_args()
    # check folder_path exists
    api_file = "api_keys.txt"
    api_keys = []
    if not os.path.exists(api_file):
        print(f"api_file: {api_file} does not exist")
        sys.exit(1)
    with open(api_file, 'r', encoding="utf-8") as f:
        api_keys = f.readlines()
    api_keys = [api_key.strip() for api_key in api_keys]
    print(f"Loaded {len(api_keys)} api keys")
    if not os.path.exists(args.folder_path):
        print(f"folder_path: {args.folder_path} does not exist")
        sys.exit(1)
    split_and_execute(args.folder_path)
