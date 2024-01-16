# basic split-processing for multiple api keys
import os
import glob
import subprocess
import sys
import datetime
from typing import List
# repeat
from itertools import repeat
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
def execute_command(command, event):
    """
    Execute command, set event to True when finished.
    """
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip().decode("utf-8"))
        if event.is_set():
            process.kill()
            break
    rc = process.poll()
    if rc != 0:
        print(f"Error: {rc}")

def split_and_execute(folder_path:str, proxy_file:str, proxy_auth:str, num:int, sleep_time:int, repeat_count:int, max_retries:int, policy:str, max_threads:int=10) -> None:
    """
    Split the folder_path into num parts, execute query-gemini-v2.py for each part.
    """
    num = len(api_keys)
    temp_paths = split_into_temp_paths(folder_path, num)
    proxies = load_proxies(proxy_file)
    if proxies:
        proxies_iter = repeat(proxies)
    else:
        proxies_iter = repeat(None)
    # execute query-gemini-4.py for each temp_path
    threads = []
    event = threading.Event()
    for i, proxy_addr in zip(range(num), proxies_iter):
        temp_path = temp_paths[i]
        api_key = api_keys[i]
        print(f"temp_path: {temp_path}")
        print(f"api_key: {api_key}")
        args_default = ["python3", "query-gemini-v2.py", "--api_key", api_key, "--path", temp_path, "--threaded", "--sleep_time", str(sleep_time), "--repeat_count", str(repeat_count), "--max_retries", str(max_retries), "--policy", policy, "--max_threads", str(max_threads)]
        if proxy_addr:
            args_default.extend([ "--proxy", proxy_addr, "--proxy_auth", proxy_auth])
        t = threading.Thread(target=execute_command, args=(args_default, event))
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
        sys.exit(1)

def load_proxies(proxy_file:str) -> List[str]:
    """
    Load proxies from proxy_file
    """
    if not os.path.exists(proxy_file):
        return []
    with open(proxy_file, 'r', encoding="utf-8") as f:
        proxies = f.readlines()
    proxies = [proxy.strip() for proxy in proxies]
    return proxies

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder_path', type=str, required=True, help='Path to the folder to split and execute.')
    parser.add_argument('--api_file', type=str, default="api_keys.txt", help='Path to the api_file.')
    parser.add_argument('--proxy_file', type=str, default="proxy.txt", help='Path to the proxy_file.')
    parser.add_argument('--proxy_auth', type=str, default="user:pass", help='Proxy authentication.')
    # max_threads, sleep_time, repeat_count, max_retries
    parser.add_argument('--max_threads', type=int, default=10, help='Max threads.')
    parser.add_argument('--sleep_time', type=int, default=1.1, help='Sleep time.')
    parser.add_argument('--repeat_count', type=int, default=3, help='Repeat count.')
    parser.add_argument('--max_retries', type=int, default=0, help='Max retries.')
    parser.add_argument('--policy', type=str, default="default", help='Policy for skipping, skip_exist, default')
    parser.add_argument('--api_keys_count', type=int, default=1, help='Number of api keys to use.')
    args = parser.parse_args()
    # check folder_path exists
    api_file = args.api_file
    if not os.path.exists(api_file):
        print(f"api_file: {api_file} does not exist")
        sys.exit(1)
    with open(api_file, 'r', encoding="utf-8") as f:
        api_keys = f.readlines()
    api_keys = [api_key.strip() for api_key in api_keys]
    api_keys = api_keys[:args.api_keys_count]
    assert len(api_keys) > 0, "No api keys"
    print(f"Loaded {len(api_keys)} api keys")
    if not os.path.exists(args.folder_path):
        print(f"folder_path: {args.folder_path} does not exist")
        sys.exit(1)
    split_and_execute(args.folder_path, args.proxy_file, args.proxy_auth, len(api_keys),  args.sleep_time, args.repeat_count, args.max_retries, args.policy, args.max_threads)
