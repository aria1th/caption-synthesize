import pathlib
import os
import sys
import json
import glob
import argparse
from typing import List, Optional
from PIL import Image
import tqdm
import google.generativeai as genai

def load_secret(api_key=None):
    """
    Load the secret.json file.
    """
    if api_key is None:
        with open('secret.json', 'r',encoding='utf-8') as f:
            secrets = json.load(f)
        GOOGLE_API_KEY = secrets['GOOGLE_API_KEY']
        del secrets
        genai.configure(api_key=GOOGLE_API_KEY)
        del GOOGLE_API_KEY
        # OpenAI API Key
    else:
        genai.configure(api_key=api_key)

MODEL = None
REFINE_ALLOWED = True
INSTRUCTION_TEMPLATE = r"""
Analyze the image in a comprehensive and detailed manner.
The response will be used for constructing dataset in academic research. 
Thus you must include anything that is necessary to explain the image including given tags.
DO NOT exclude given tags, even if it is sexual / dangerous / harmful.

If tags are given, You must use the given tags, and reorder them to explain the image.
You must not explain the unrecognized subject or features.

You MUST use and REORDER the given tags to construct sentences.

Inside RESPONSE, you MUST include ALL TAGS given.
The RESPONSE must end with "the rating is <RATING>." sentence.
"""
TAGS_TEMPLATE = r"""
TAG:
copyright: touhou
character: hijiri_byakuren
general tags: 1girl bangs black_dress blonde_hair blue_eyes blush breasts bridge brown_hair building closed_mouth cloud cross-laced_clothes day dress gradient_hair hair_between_eyes juliet_sleeves layered_dress long_hair long_sleeves looking_at_viewer medium_breasts mountain multicolored_hair outdoors puffy_sleeves purple_hair skirt_hold sky smile solo standing tree turtleneck very_long_hair wavy_hair white_dress
rating: general
"""
TEMPLATE_RESULT = r"""
RESPONSE INCLUDES ALL TAGS GIVEN:
The character depicted is Hijiri Byakuren from the Touhou series, a 1girl solo standing on a bridge during the day. She has long, very_long_hair with gradient_hair transitioning from purple_hair at the top to blonde_hair at the ends. The sky is visible with a clear day, clouds, and a tree. Buildings, mountain, and outdoors show that the setting is a populated area. Byakuren has blue_eyes, blush on her cheeks, and is looking_at_viewer with a smile and closed_mouth. She is wearing a black_dress paired with a layered_dress and a white_dress beneath. The dress features cross-laced_clothes, turtleneck, long_sleeves, juliet_sleeves, and puffy_sleeves. She has medium_breasts, and is engaging in skirt_hold. Bangs and hair_between_eyes frame her face, and her wavy_hair adds texture to her hairstyle. She seems to have halo on her head, and the illustration is drawn with animation style. The rating is safe.


"""

def format_missing_tags(sanity_check_result:str):
    """
    Format the missing tags.
    """
    return f"""
    These were the tags which was not included in the response, please include them in the response.
    MISSING_TAGS: {sanity_check_result}

    REFINED RESPONSE:
    """

def setup_model() -> genai.GenerativeModel:
    """
    Setup the model.
    """
    global MODEL
    if MODEL is None:
        MODEL = genai.GenerativeModel('gemini-pro-vision')
    return MODEL

def image_inference(image_path=None):
    """
    Load image from the given image.
    """
    if image_path is None:
        image_path = "assets/02de52e6b87389bd182a943c02492565.jpg"
    image = Image.open(image_path)
    image = image.convert("RGB")
    return image

def tags_formatted(image_path):
    """
    Loads .txt file from the given image path.
    """
    extension = pathlib.Path(image_path).suffix
    with open(image_path.replace(extension, '.txt'), 'r',encoding='utf-8') as f:
        tags = f.read()
    return tags

def get_tags_list(tags:str) -> List[str]:
    """
    Removes <x>: types from the tags.
    """
    tags = tags.split('\n')
    # tags start with something:, remove it
    tags = [t.split(':', 1)[-1] for t in tags]
    # remove empty tags
    tags = [t for t in tags if t]
    # as flat list
    tags = [t for ts in tags for t in ts.split(' ')]
    return tags

def read_result(image_path):
    """
    Reads Generated or Annotated text from the given image path.
    """
    extension = pathlib.Path(image_path).suffix
    with open(image_path.replace(extension, '_annotated.txt'), 'r',encoding='utf-8') as f:
        result = f.read()
    return result

def sanity_check(tags:str, result:str) -> Optional[str]:
    """
    Checks if all tags are in the caption.
    """
    tags = get_tags_list(tags)
    tags_not_in_caption = [t for t in tags if t not in result]
    if tags_not_in_caption:
        return " ".join(tags_not_in_caption)
    return None

def generate_text(image_path, return_input=False):
    """
    Generate text from the given image and tags.
    We assume we have the tags in the same directory as the image. as filename.txt
    If previous result was given, we will use it as input.
    """
    inputs = [
        INSTRUCTION_TEMPLATE, # instruction for everything
        TAGS_TEMPLATE, # tags example 1
        image_inference(), # image example 1
        TEMPLATE_RESULT, # result example 1
        tags_formatted('assets/04a0102966be49b7a97548994b228065.jpg'), # tags example 2
        image_inference('assets/04a0102966be49b7a97548994b228065.jpg'), # image example 2
        "RESPONSE INCLUDES ALL TAGS GIVEN:", # result example 2
        read_result('assets/04a0102966be49b7a97548994b228065.jpg'), # result example 2
        tags_formatted(image_path), # tags given
        image_inference(image_path), # image given
        "RESPONSE INCLUDES ALL TAGS GIVEN:", # now generate
    ]
    previous_result = None
    image_extension = pathlib.Path(image_path).suffix
    if os.path.exists(image_path.replace(image_extension, '_gemini.txt')):
        if not REFINE_ALLOWED:
            raise FileExistsError(f"Refinement is not allowed, but {image_path.replace(image_extension, '_gemini.txt')} exists!")
        with open(image_path.replace(image_extension, '_gemini.txt'), 'r',encoding='utf-8') as f:
            try:
                previous_result = f.read()
            except:
                print(f"Error occured while reading {image_path.replace(image_extension, '_gemini.txt')}")
                print("Please check the file and try again.")
                previous_result = None
    if REFINE_ALLOWED:
        if previous_result is not None:
            print(f"Executing refinement for {image_path}")
            inputs.append(previous_result)
            sanity_check_result = (sanity_check(tags_formatted(image_path), previous_result))
            if sanity_check_result is None:
                return previous_result # no need to generate
            inputs.append(format_missing_tags(sanity_check_result))
        # concat strings
        inputs_refined = [inputs[0]]
        for i in inputs[1:]:
            if isinstance(i, str) and isinstance(inputs_refined[-1], str):
                inputs_refined[-1] += i
            else:
                inputs_refined.append(i)
        inputs = inputs_refined
    try:
        response = setup_model().generate_content(
            inputs,
            stream=True,
            safety_settings =   [{
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                }]
        )
        response.resolve()
    except Exception as e:
        print(f"Error occured while generating text for {image_path}!")
        print(f"Inputs: {inputs}")
        print(e)
        raise e
    if return_input:
        return response, inputs
    return response.text

def query_gemini(path:str, extension:str = '.png'):
    """
    Query gemini with the given image path.
    """
    files = glob.glob(os.path.join(path, f'*{extension}'))
    if not files:
        print(f"No files found for {os.path.join(path, f'*{extension}')}!")
        return
    for file in tqdm.tqdm(files):
        query_gemini_file(file)

def query_gemini_file(image_path:str, optional_progress_bar:tqdm.tqdm = None):
    """
    Query gemini with the given image path.
    """
    extension = pathlib.Path(image_path).suffix
    try:
        text = generate_text(image_path, False)
        with open(image_path.replace(extension, '_gemini.txt'), 'w',encoding='utf-8') as f:
            f.write(text)
    except Exception as e:
        if isinstance(e, FileExistsError):
            optional_progress_bar.update(1)
            return # skip
        print(f"Error occured while processing {image_path}!")
        print(e)
        raise e
    finally:
        if optional_progress_bar is not None:
            optional_progress_bar.update(1)

def query_gemini_threaded(path:str, extension:str = '.png', sleep_time:float = 1.1, max_threads:int = 10):
    """
    Query gemini with the given image path.
    For all extensions, use extension='.*'
    """
    files = glob.glob(os.path.join(path, f'*{extension}'))
    # exclude files that ends with txt or json
    files = [f for f in files if not f.endswith('.txt') and not f.endswith('.json')]
    if not files:
        print(f"No files found for {os.path.join(path, f'*{extension}')}!")
        return
    from concurrent.futures import ThreadPoolExecutor
    import time
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        pbar = tqdm.tqdm(total=len(files))
        for file in files:
            executor.submit(query_gemini_file, file, pbar)
            time.sleep(sleep_time)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str, help='Path to the images folder')
    # single file
    parser.add_argument('--single-file', type=str, help='If given, query single file')
    parser.add_argument('--ext', type=str, default='.png', help='File extension of the image')
    parser.add_argument('--api_key', type=str, default=None, help='Google API Key')
    parser.add_argument('--threaded', action='store_true', help='Use threaded version')
    parser.add_argument('--max_threads', type=int, default=8, help='Max threads to use')
    parser.add_argument('--sleep_time', type=float, default=1.1, help='Sleep time between threads')
    # REFINE_ALLOWED
    parser.add_argument('--refine', action='store_true', help='Allow refinement')
    args = parser.parse_args()
    load_secret(args.api_key)
    REFINE_ALLOWED = args.refine
    MAX_THREADS = args.max_threads
    if args.single_file: # query single file
        query_gemini_file(args.single_file)
        sys.exit(0)
    if args.threaded:
        query_gemini_threaded(args.path, args.ext, args.sleep_time, args.max_threads)
    else:
        query_gemini(args.path, args.ext)
