import pathlib
import os
import sys
import json
import glob
import argparse
from typing import List, Optional, Union
import time
from functools import cache
from PIL import Image
import tqdm
from concurrent.futures import ThreadPoolExecutor
from converter import generate_request, analyze_model_response

POLICY = 'default' # default, skip_existing

def load_secret(api_key=None):
    """
    If api_key is not given,
    Load the secret.json file from the current directory.
    Else, use the given api_key.
    """
    if not api_key:
        with open('secret.json', 'r',encoding='utf-8') as f:
            secrets = json.load(f)
            api_key = secrets.get('GOOGLE_API_KEY', None)
    if not api_key:
        raise ValueError("API Key is not given!")
    return api_key

def format_missing_tags(previous_response, sanity_check_result):
    """
    Format the missing tags.
    """
    return f"""
    PREVIOUS_RESPONSE: {previous_response}
    MISSING_TAGS: {sanity_check_result}
    These were the tags which were not included in the PREVIOUS_RESPONSE, you MUST include these MISSING_TAGS in the REFINED RESPONSE.

    REFINED RESPONSE:
    """

def image_inference(image_path=None):
    """
    Load image from the given image.
    """
    if image_path is None:
        image_path = "assets/5841101.jpg"
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return
    image = Image.open(image_path)
    image = image.convert("RGB")
    # resize if bigger than 768*768
    if image.size[0] > 768 and image.size[1] > 768:
        # resize to shorter side 768
        if image.size[0] > image.size[1]:
            image = image.resize((768, int(768 * image.size[1] / image.size[0])))
        else:
            image = image.resize((int(768 * image.size[0] / image.size[1]), 768))
    return image

@cache
def tags_formatted(image_path):
    """
    Loads .txt file from the given image path.
    """
    extension = pathlib.Path(image_path).suffix
    if not os.path.exists(image_path.replace(extension, '.txt')):
        print(f"Tags not found for {image_path}!")
        raise FileNotFoundError(f"Tags not found for {image_path}!")
    with open(image_path.replace(extension, '.txt'), 'r',encoding='utf-8') as f:
        tags = f.read()
    return tags

def get_tags_list(tags:str) -> List[str]:
    """
    Removes <x>: types from the tags.
    """
    tags = tags.split()
    return tags


def read_result(image_path):
    """
    Reads Generated or Annotated text from the given image path.
    """
    extension = pathlib.Path(image_path).suffix
    if os.path.exists(image_path.replace(extension, '_gemini.txt')):
        with open(image_path.replace(extension, '_gemini.txt'), 'r',encoding='utf-8') as f:
            result = f.read()
    elif os.path.exists(image_path.replace(extension, '_annotated.txt')):
        with open(image_path.replace(extension, '_annotated.txt'), 'r',encoding='utf-8') as f:
            result = f.read()
    else:
        result = None
    return result

def sanity_check(tags, result):
    """
    Checks if all tags are in the caption.
    """
    excluded_tags = ['original', 'error']
    tags = get_tags_list(tags)
    tags = [t.replace('_', ' ').replace('-', ' ') for ts in tags for t in ts.split(' ')]
    if result is None:
        return tags
    else:
        result = result.replace('_', ' ').replace('-', ' ')
        tags_not_in_caption = [t for t in tags if t.lower() not in result.lower() and t not in excluded_tags] 
        # if tags_not_in_caption:
        #     return " ".join(tags_not_in_caption)
        return tags_not_in_caption

def merge_strings(strings_or_images:List[Union[str, Image.Image]]) -> str:
    """
    Merge strings or images into one string. This makes single-turn conversation.
    """
    result_container = []
    previous_string = ""
    for s in strings_or_images:
        if not isinstance(s, str):
            result_container.append(previous_string)
            result_container.append(s)
            previous_string = ""
        else:
            # if not endswith \n and next string does not startswith \n then add \n
            if previous_string and not previous_string.endswith('\n') and s and not s.startswith('\n'):
                previous_string += '\n'
            previous_string += s
    if previous_string:
        result_container.append(previous_string)
    return result_container

def load_instruction_templates_from_json(json_file_path, key:str = "INSTRUCTION_TEMPLATE"):
    """
    Loads the instruction template from the given json file path.
    """
    if not json_file_path or not os.path.exists(json_file_path):
        raise FileNotFoundError(f"Instruction file not found: {json_file_path}")
    ### TODO: convert to conditional template
    with open(json_file_path, 'r',encoding='utf-8') as file:
        templates = json.load(file)
        instruction = templates.get(key)
    return instruction

def load_tag_templates_from_json(json_file_path, key:str = "TAGS_TEMPLATE"):
    """
    Loads the tag template from the given json file path.
    Corresponding result template should be given with the key + "_RESULT".
    """
    if not json_file_path or not os.path.exists(json_file_path):
        raise FileNotFoundError(f"Tag template file not found: {json_file_path}")
    with open(json_file_path, 'r',encoding='utf-8') as file:
        templates = json.load(file)
        tag_template = templates.get(key)
        template_result = templates.get(key + "_RESULT")
    return tag_template, template_result


def generate_text(image_path, return_input=False, previous_result=None, api_key=None, proxy=None, proxy_auth=None):
    """
    Generate text from the given image and tags.
    We assume we have the tags in the same directory as the image. as filename.txt
    If previous result was given, we will use it as input.
    """
    # read txt tag file and if tag has 'solo' then use solo template
    if image_path.endswith('.txt') or image_path.endswith('.json'):
        return None
    extension = pathlib.Path(image_path).suffix
    if not os.path.exists(image_path.replace(extension, '.txt')):
        print(f"Tags not found for {image_path}!")
        raise FileNotFoundError(f"Tags not found for {image_path}!")
    dump_path = image_path.replace(extension, '_gemini_request.txt')
    with open(image_path.replace(extension, '.txt'), 'r',encoding='utf-8') as f:
        tags = f.read()
    tags = get_tags_list(tags)
    if 'solo' in tags and 'solo_focus' not in tags:
        instruction = load_instruction_templates_from_json('Templates/instruction.json', 'INSTRUCTION_TEMPLATE')
        tags_template, template_result = load_tag_templates_from_json('Templates/tag_results.json','TAGS_TEMPLATE')
    else:
        print("Multiple people detected!")
        instruction = load_instruction_templates_from_json('Templates/instruction.json', 'INSTRUCTION_TEMPLATE_MULTIPLE')
        tags_template, template_result = load_tag_templates_from_json('Templates/tag_results.json', 'TAGS_TEMPLATE_MULTIPLE')
    ### TODO : convert to Factory pattern
    inputs = [
        instruction, # instruction for everything
        tags_template, # tags example 1
        image_inference(), # image example 1
        template_result, # result example 1
        tags_formatted(image_path), # tags given
        image_inference(image_path), # image given
        "RESPONSE INCLUDES ALL GIVEN TAGS:", # now generate
    ]

    if previous_result is not None:
        print("Previous result found, checking sanity...")
        tags_not_in_caption = sanity_check(tags_formatted(image_path), previous_result)
        if len(tags_not_in_caption):
            inputs.append(format_missing_tags(previous_result, tags_not_in_caption))
            inputs = merge_strings(inputs)
            response = None
            try:
                response = generate_request(inputs, api_key, proxy=proxy, proxy_auth=proxy_auth, dump_path=dump_path)
                candidates = analyze_model_response(response)
                if len(candidates) > 1:
                    print("WARNING: Multiple candidates found! You can use multiple responses to generate the final response.")
                candidate = candidates[0]
                previous_result = candidate
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    raise e
                print(f"Error occured while generating text for {image_path}! {e}")
                print(f"Inputs: {inputs}")
                # dump response if exists
                if response:
                    with open(image_path.replace(extension, '_gemini_error.txt'), 'w', encoding='utf-8') as f:
                        f.write(str(response))
            return previous_result
        
        else:
            print(f"No need to generate for {image_path}. 0 sanity")
            return previous_result if return_input else None
    else:    
        print(f"No previous result found for {image_path}, generating for the first time...")
        inputs = merge_strings(inputs)
    try:
        response = generate_request(inputs, api_key, proxy=proxy, proxy_auth=proxy_auth)
        candidates = analyze_model_response(response)
        if len(candidates) > 1:
            print("WARNING: Multiple candidates found! You can use multiple responses to generate the final response.")
        candidate = candidates[0]
        previous_result = candidate
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            raise e
        print(f"Error occurred while generating text for {image_path}! {e}")
        print(f"Inputs: {inputs}")
        return None
    return previous_result

def query_gemini(path:str, extension:str = '.png', api_key=None, proxy=None, proxy_auth=None, repeat_count:int = 3, max_retries=5):
    """
    Query gemini with the given image path.
    """
    files = load_paths(path, extension)
    if not files:
        print(f"No files found for {os.path.join(path, f'*{extension}')}!")
        return
    for file in tqdm.tqdm(files):
        actual_extension = pathlib.Path(file).suffix
        result_expected_file = file.replace(actual_extension, '_gemini.txt')
        if POLICY == 'skip_existing' and os.path.exists(result_expected_file):
            continue
        if not os.path.exists(file):
            print(f"File not found: {file}")
            continue
        query_gemini_file(file, None, repeats=repeat_count, api_key=api_key, proxy=proxy, proxy_auth=proxy_auth, max_retries=max_retries)

def generate_repeat_text(image_path:str, previous_result:str, api_key=None, proxy=None, proxy_auth=None,repeats=3, result_container:Optional[List] = None) -> List[str]:
    """
    Generates the repeat text from the given image path and previous result.
    """
    results = []
    for _ in range(repeats):
        results.append(generate_text(image_path, return_input=True, previous_result=previous_result, api_key=api_key, proxy=proxy, proxy_auth=proxy_auth))
        if result_container is not None:
            result_container.append(results[-1])
        if results[-1] is not None:
            previous_result = results[-1]
    results = [result for result in results if result is not None]
    return results

def query_gemini_file(image_path:str, optional_progress_bar:tqdm.tqdm = None, max_retries=5, repeats=3, api_key=None, proxy=None, proxy_auth=None):
    """
    Query gemini with the given image path.
    repeats: number of repeats to generate
    WARNING: if you increase the repeats, you must increase time between threads.
    """
    extension = pathlib.Path(image_path).suffix
    least_sanity_count = float('inf')
    best_text = None
    sanity_count_list = []
    # if exists, skip by policy
    for attempt in range (max_retries + 1):
        all_generated_texts = []
        try:
            texts = generate_repeat_text(image_path, best_text, api_key=api_key, proxy=proxy, proxy_auth=proxy_auth, repeats=repeats, result_container= all_generated_texts)
            sanity_checks = [sanity_check(tags_formatted(image_path), text) for text in all_generated_texts]
            sanity_count_list = [len(sanity_check) for sanity_check in sanity_checks]
            if not sanity_count_list:
                print(f"Sanity check failed for {image_path}!")
                raise ValueError("Empty sanity check list! Responses were not generated!")
            least_sanity_count = min(sanity_count_list)
            best_text = texts[sanity_count_list.index(least_sanity_count)]
            if best_text is not None:
                with open(image_path.replace(extension, '_gemini.txt'), 'w', encoding='utf-8') as f:
                    f.write(best_text)
                # write other texts
                for i, text in enumerate(texts):
                    if i == sanity_count_list.index(least_sanity_count):
                        continue
                    with open(image_path.replace(extension, f'_gemini_{i}.txt'), 'w', encoding='utf-8') as f:
                        f.write(text)
            return
        except Exception as e:
            if isinstance(e, FileExistsError):
                optional_progress_bar.update(1)
                return # skip
            print(f"Error occured while processing {image_path}!")
            print(f"Error: {e}")
            print(f"\nAttempt: {attempt}")
            if attempt < max_retries:
                print("trying again in 2 seconds...")
                time.sleep(2)
            else:
                print("Max retry has exceed!!")
                raise e
        finally:
            if optional_progress_bar is not None:
                optional_progress_bar.update(1)

def query_gemini_threaded(path:str, extension:str = '.png', sleep_time:float = 1.1, max_threads:int = 10, repeat_count:int = 3, api_key=None, proxy=None, proxy_auth=None, max_retries=5):
    """
    Query gemini with the given image path.
    For all extensions, use extension='.*'
    """
    files = load_paths(path, extension)
    if not files:
        print(f"No files found for {os.path.join(path, f'*{extension}')}!")
        return
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        pbar = tqdm.tqdm(total=len(files))
        for file in files:
            actual_extension = pathlib.Path(file).suffix
            result_expected_file = file.replace(actual_extension, '_gemini.txt')
            if POLICY == 'skip_existing' and os.path.exists(result_expected_file):
                pbar.update(1)
                continue
            if not os.path.exists(file):
                print(f"File not found: {file}")
                pbar.update(1)
                continue
            executor.submit(query_gemini_file, file, pbar, repeats=3, api_key=api_key, proxy=proxy, proxy_auth=proxy_auth, max_retries=max_retries)
            time.sleep(sleep_time * repeat_count)

def load_paths(string:str, extension:str=".png") -> List[str]:
    """
    Loads paths from the given string.
    """
    if os.path.isfile(string):
        # handle txt
        if string.endswith('.txt'):
            with open(string, 'r',encoding='utf-8') as f:
                paths = f.read().split('\n')
        # handle json
        elif string.endswith('.json'):
            with open(string, 'r',encoding='utf-8') as f:
                paths = json.load(f)
    else:
        paths = glob.glob(os.path.join(string, f'*{extension}'))
    # filter out txt and json
    paths = [path for path in paths if not path.endswith('.txt') and not path.endswith('.json')]
    return paths

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str, default=None, help='Path to the images folder')
    # single file
    parser.add_argument('--single-file', type=str, help='If given, query single file')
    parser.add_argument('--ext', type=str, default='.png', help='File extension of the image')
    parser.add_argument('--api_key', type=str, default="", help='Google API Key')
    parser.add_argument('--threaded', action='store_true', help='Use threaded version')
    parser.add_argument('--max_threads', type=int, default=8, help='Max threads to use')
    parser.add_argument('--sleep_time', type=float, default=1.1, help='Sleep time between threads')
    parser.add_argument('--proxy', type=str, default=None, help='Proxy to use')
    parser.add_argument('--proxy_auth', type=str, default=None, help='Proxy auth to use')
    parser.add_argument('--repeat_count', type=int, default=3, help='Repeat count to use')
    parser.add_argument('--max_retries', type=int, default=5, help='Max retries to use')
    # policy, skip_existing, default
    parser.add_argument('--policy', type=str, default='default', help='Policy to use, skip_existing, default')
    args = parser.parse_args()
    api_arg = args.api_key
    POLICY = args.policy
    api_arg = load_secret(api_arg)
    MAX_THREADS = args.max_threads
    if args.single_file: # query single file
        # python query-gemini-v2.py --single-file assets/5841101.jpg --api_key <api_key>
        query_gemini_file(args.single_file, None, repeats=args.repeat_count, api_key=api_arg, proxy=args.proxy, proxy_auth=args.proxy_auth, max_retries=args.max_retries)
        sys.exit(0)
    if args.threaded:
        # python query-gemini-v2.py --path assets --ext .png --api_key <api_key> --threaded
        query_gemini_threaded(args.path, args.ext, args.sleep_time, args.max_threads, args.repeat_count, api_key=api_arg, proxy=args.proxy, proxy_auth=args.proxy_auth, max_retries=args.max_retries)
    else:
        query_gemini(args.path, args.ext, api_key=api_arg, proxy=args.proxy, proxy_auth=args.proxy_auth, repeat_count=args.repeat_count, max_retries=args.max_retries)
