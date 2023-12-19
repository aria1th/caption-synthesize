import pathlib
import os
import sys
import json
import glob
import argparse
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

TAGS_TEMPLATE = r"""
Analyze the image in a comprehensive and detailed manner.
The response will be used for constructing dataset in academic research. 
Thus you must include anything that is necessary to explain the image including given tags.
DO NOT exclude given tags, if it is duplicate, then just concatenate them as group

If tags are given, You must use the given tags, and reorder them to explain the image.
You must not explain the unrecognized subject or features.

You MUST use and REORDER the given tags to construct sentences.

Inside RESPONSE, you MUST include ALL TAGS given.
The RESPONSE must end with "the rating is <RATING>." sentence.
TAG:
copyright: touhou
character: hijiri_byakuren
general tags: 1girl bangs black_dress blonde_hair blue_eyes blush breasts bridge brown_hair building closed_mouth cloud cross-laced_clothes day dress gradient_hair hair_between_eyes juliet_sleeves layered_dress long_hair long_sleeves looking_at_viewer medium_breasts mountain multicolored_hair outdoors puffy_sleeves purple_hair skirt_hold sky smile solo standing tree turtleneck very_long_hair wavy_hair white_dress
rating: general

RESPONSE INCLUDES ALL TAGS GIVEN:
The character depicted is Hijiri Byakuren from the Touhou series, a 1girl solo standing on a bridge during the day. She has long, very_long_hair with gradient_hair transitioning from purple_hair at the top to blonde_hair at the ends. The sky is visible with a clear day, clouds, and a tree. Buildings, mountain, and outdoors show that the setting is a populated area. Byakuren has blue_eyes, blush on her cheeks, and is looking_at_viewer with a smile and closed_mouth. She is wearing a black_dress paired with a layered_dress and a white_dress beneath. The dress features cross-laced_clothes, turtleneck, long_sleeves, juliet_sleeves, and puffy_sleeves. She has medium_breasts, and is engaging in skirt_hold. Bangs and hair_between_eyes frame her face, and her wavy_hair adds texture to her hairstyle. She seems to have halo on her head, and the illustration is drawn with animation style. The rating is safe.
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

def read_result(image_path):
    """
    Reads Generated or Annotated text from the given image path.
    """
    extension = pathlib.Path(image_path).suffix
    with open(image_path.replace(extension, '_annotated.txt'), 'r',encoding='utf-8') as f:
        result = f.read()
    return result

def generate_text(image_path, return_input=False):
    """
    Generate text from the given image and tags.
    We assume we have the tags in the same directory as the image. as filename.txt
    """
    inputs = [
        TAGS_TEMPLATE,
        image_inference(),
        tags_formatted('assets/04a0102966be49b7a97548994b228065.jpg'),
        image_inference('assets/04a0102966be49b7a97548994b228065.jpg'),
        "RESPONSE INCLUDES ALL TAGS GIVEN:",
        read_result('assets/04a0102966be49b7a97548994b228065.jpg'),
        tags_formatted(image_path),
        image_inference(image_path),
        "RESPONSE INCLUDES ALL TAGS GIVEN:",
    ]
    response = setup_model().generate_content(
        inputs,
        stream=True,
        safety_settings = {
            "harassment" : "BLOCK_NONE",
            "hate_speech" : "BLOCK_NONE",
            "sexual" : "BLOCK_NONE",
            "dangerous" : "BLOCK_NONE",
        }
    )
    response.resolve()
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
        text = generate_text(image_path)
        with open(image_path.replace(extension, '_gemini.txt'), 'w',encoding='utf-8') as f:
            f.write(text)
    except Exception as e:
        print(f"Error occured while processing {image_path}!")
        print(e)
    finally:
        if optional_progress_bar is not None:
            optional_progress_bar.update(1)

def query_gemini_threaded(path:str, extension:str = '.png', sleep_time:float = 1.1, max_threads:int = 10):
    """
    Query gemini with the given image path.
    """
    files = glob.glob(os.path.join(path, f'*{extension}'))
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
    args = parser.parse_args()
    load_secret(args.api_key)
    MAX_THREADS = args.max_threads
    if args.single_file: # query single file
        query_gemini_file(args.single_file)
        sys.exit(0)
    if args.threaded:
        query_gemini_threaded(args.path, args.ext, args.sleep_time, args.max_threads)
    else:
        query_gemini(args.path, args.ext)
