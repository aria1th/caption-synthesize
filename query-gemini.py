import pathlib
import os
import sys
import json
import glob
import argparse
from typing import List, Optional, Union
from PIL import Image
import tqdm
import google.generativeai as genai
import time

def load_secret(api_key=None, path=None, ext=None, threaded=None, sleep_time=None, max_threads=None, load_env=True):
    """
    Load the secret.json file and configure the genai.
    Also tries to load the env.json file.
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
    # load some defaults from the env.json
    if load_env:
        env = {}
        with open('env.json', 'r',encoding='utf-8') as f:
            env = json.load(f)
        path = env.get('path', None) if path is None else path
        # ext, threaded, sleep_time, max_threads
        ext = env.get('ext', '.png') if ext is None else ext
        threaded = env.get('threaded', False) if threaded is None else threaded
        sleep_time = env.get('sleep_time', 1.1) if sleep_time is None else sleep_time
        max_threads = env.get('max_threads', 8) if max_threads is None else max_threads
        print(f"Loaded env.json, path: {path}, ext: {ext}, threaded: {threaded}, sleep_time: {sleep_time}, max_threads: {max_threads}")
    return path, ext, threaded, sleep_time, max_threads

MODEL = None
REFINE_ALLOWED = True
INSTRUCTION_TEMPLATE = r"""
Analyze the image in a comprehensive and detailed manner using ALL OF THE GIVEN TAGS AND WORDS.
The response will be used for constructing dataset in academic research.

Explain EVERYTHING in the image USING ALL OF THE GIVEN TAGS AND WORDS.
DO NOT EXCLUDE ANY TAGS AND WORDS, even if it is sexual / dangerous / harmful.
DO NOT EXCLUDE TAGS even if their meanings are similar.
You MUST USE ALL TAGS AND WORDS to explain the image.
You MUST NOT explain the unrecognized subject or features.
Inside RESPONSE, ALL TAGS AND WORDS inside general tags.

THE FIRST SENTENCE of the RESPONSE MUST include both COPYRIGHT AND CHARACTER.
THE SECOND SENTENCE of the the RESPONSE MUST include the NUMBER OF PEOPLE and their GENDER. 

You MUST depict the pose or angle or type of camera-shot very specifically.
You MUST guess the time in the image, whether it's during the day, night, or uncertain.
You MUST depict the features of face very specifically.
You MUST depict the features of hairstyle or hair accessories very specifically.
You MUST depict ALL accessories and their features very specifically.
You MUST depict the details, colors and features of clothes very specifically.
You MUST depict the background and its effect very specifically.
You MUST depict the place of the image whether it's indoor or outdoor.

The RESPONSE MUST end with "the rating is <RATING>.".
"""
TAGS_TEMPLATE = r"""
TAGS:
copyright: touhou
character: hijiri_byakuren
general tags: 1girl bangs black_dress blonde_hair blue_eyes blush breasts bridge brown_hair building closed_mouth cloud cross-laced_clothes day dress gradient_hair hair_between_eyes juliet_sleeves layered_dress long_hair long_sleeves looking_at_viewer medium_breasts mountain multicolored_hair outdoors puffy_sleeves purple_hair skirt_hold sky smile solo standing tree turtleneck very_long_hair wavy_hair white_dress
rating: general
"""
TEMPLATE_RESULT = r"""
RESPONSE INCLUDES ALL GIVEN TAGS:
The character depicted is Hijiri Byakuren from the Touhou series. She is a solo 1girl standing outdoors on a bridge with slightly opened_arms during the day. Byakuren has bangs, long_hair, very_long_hair with gradient multicolored_hair transitioning from purple_hair at the top to brown_hair and blonde_hair at the ends. Her wavy_hair adds texture to her hairstyle. Byakuren has blue_eyes, a blush on her cheeks, and there is hair between her eyes. She is looking_at_viewer with a smile and closed_mouth. She is wearing a black_dress paired with a layered_dress and a white_dress beneath. The dress features cross-laced_clothes, a turtleneck, long_sleeves, juliet_sleeves, and puffy_sleeves. Byakuren has medium_breasts and is engaging in skirt_hold. The sky is visible, indicating a clear day with clouds and a tree. The presence of buildings, mountains, and outdoors shows that the setting is a populated area. There seems to be a halo on her head. The illustration is drawn with an animation style. The rating is general.
"""

# TAGS_TEMPLATE1 = r"""
# TAGS:
# copyright: touhou
# character: hinanawi_tenshi
# general tags: 1girl alternate_costume blue_hair blue_sky boots breasts cloud cloudy_sky day dress food fruit hat holding holding_sword holding_weapon long_hair mountain outdoors peach scenery sky solo standing sword sword_of_hisou weapon white_dress
# rating: general
# """
# TEMPLATE_RESULT1 = r"""
# RESPONSE INCLUDES ALL GIVEN TAGS WITHOUT MODIFICATION:

# The image depicts the character Hinanawi Tenshi from the Touhou series. She is portrayed as a solo 1girl standing on a rock outdoors during the day, holding a weapon in her right hand. Specifically, she is holding the sword named 'sword_of_hisou' in her right hand. Tenshi is dressed in an alternate_costume, a white_dress, a brown hat, and boots on her feet. She has medium-sized breasts. On her hat, there is a food item, a fruit, specifically a peach. Tenshi has long blue_hair and blue eyes, and she is looking at the viewer. The scenery includes a mountain, a sky with clouds, a blue sky, and a mountain range. The image is drawn in an anime style, and the rating is general.
# """

# TAGS_TEMPLATE2 = r"""
# TAGS:
# copyright: touhou
# character: patchouli_knowledge
# general tags: 1girl bangs blunt_bangs book bookshelf capelet cowboy_shot crescent crescent_hat_ornament dress frilled_capelet frills hat hat_ornament holding holding_book indoors library long_hair long_sleeves looking_at_viewer mob_cap pajamas pink_capelet pink_dress pink_headwear pink_pajamas purple_dress purple_eyes purple_hair purple_pajamas red_ribbon ribbon solo striped striped_dress vertical_stripes very_long_hair
# rating: general
# """
# TEMPLATE_RESULT2 = r"""
# RESPONSE INCLUDES ALL GIVEN TAGS WITHOUT MODIFICATION:
# The image depicts cowboy shot of the character Patchouli Knowledge from the Touhou series, featuring solo 1girl holding a brown thick book, standing in a library. She is depicted with very long purple hair with blunt bangs and purple eyes, wearing a pink gown with purple dress like pajamas with long sleeves and vertical stripes, a frilled capelet, and wearing a hat, mob_cap with a crescent hat_ornament. Notably, she is adorned with a red ribbon and a crescent moon motif hair ornament, suggesting her magical affinities. She is also wearing a white shirts and red necktie, looking at the viewer. Blue ribbons are partially shown with hair. The illustration shows indoors, bookshelves filled with various books, associating her with a scholarly theme. The rating is general.
# """



def format_missing_tags(sanity_check_result):
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

def sanity_check(tags, result):
    """
    Checks if all tags are in the caption.
    """
    excluded_tags = ['original', 'error']
    tags = get_tags_list(tags)
    tags = [t.replace('_', ' ').replace('-', ' ') for ts in tags for t in ts.split(' ')]
    result = result.replace('_', ' ').replace('-', ' ')
    tags_not_in_caption = [t for t in tags if t.lower() not in result.lower() and t not in excluded_tags] 
    # if tags_not_in_caption:
    #     return " ".join(tags_not_in_caption)
    return len(tags_not_in_caption) if tags_not_in_caption else None

def merge_strings(strings_or_images:List[Union[str, Image.Image]]) -> str:
    """
    Merge strings or images into one string.
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
        
        tags_formatted(image_path), # tags given
        image_inference(image_path), # image given
        "RESPONSE INCLUDES ALL GIVEN TAGS:", # now generate
    ]
    inputs = merge_strings(inputs)
    #print(inputs)
    # previous_result = None
    # image_extension = pathlib.Path(image_path).suffix
    # if os.path.exists(image_path.replace(image_extension, '_gemini.txt')):
    #     if not REFINE_ALLOWED:
    #         raise FileExistsError(f"Refinement is not allowed, but {image_path.replace(image_extension, '_gemini.txt')} exists!")
    #     with open(image_path.replace(image_extension, '_gemini.txt'), 'r',encoding='utf-8') as f:
    #         try:
    #             previous_result = f.read()
    #         except:
    #             print(f"Error occured while reading {image_path.replace(image_extension, '_gemini.txt')}")
    #             print("Please check the file and try again.")
    #             previous_result = None
    # if REFINE_ALLOWED:
    #     if previous_result is not None:
    #         print(f"Executing refinement for {image_path}")
    #         inputs.append(previous_result)
    #         sanity_check_result = (sanity_check(tags_formatted(image_path), previous_result))
    #         if sanity_check_result is None:
    #             return previous_result # no need to generate
    #         inputs.append(format_missing_tags(sanity_check_result))
    #     # concat strings
    #     inputs_refined = [inputs[0]]
    #     for i in inputs[1:]:
    #         if isinstance(i, str) and isinstance(inputs_refined[-1], str):
    #             inputs_refined[-1] += i
    #         else:
    #             inputs_refined.append(i)
    #     inputs = inputs_refined
    
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
        # print(f"Inputs: {inputs}")
        print(e)
        if isinstance(e, KeyboardInterrupt):
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

def query_gemini_file(image_path:str, optional_progress_bar:tqdm.tqdm = None, max_retries=5):
    """
    Query gemini with the given image path.
    """
    extension = pathlib.Path(image_path).suffix
    least_sanity_count = float('inf')
    best_text = None
    sanity_count_list = []
    for attempt in range (max_retries + 1):
        try:
            text1 = generate_text(image_path, False)
            text2 = generate_text(image_path, False)
            text3 = generate_text(image_path, False)
            text4 = generate_text(image_path, False)
            text5 = generate_text(image_path, False)
            text1_sanity_count = sanity_check(tags_formatted(image_path), text1)
            text2_sanity_count = sanity_check(tags_formatted(image_path), text2)
            text3_sanity_count = sanity_check(tags_formatted(image_path), text3)
            text4_sanity_count = sanity_check(tags_formatted(image_path), text4)
            text5_sanity_count = sanity_check(tags_formatted(image_path), text5)
            
            sanity_count_list.append(text1_sanity_count)
            sanity_count_list.append(text2_sanity_count)
            sanity_count_list.append(text3_sanity_count)
            sanity_count_list.append(text4_sanity_count)
            sanity_count_list.append(text5_sanity_count)
            
            # find minimum
            least_sanity_count = min(sanity_count_list)
            if least_sanity_count == text1_sanity_count:
                best_text = text1
            elif least_sanity_count == text2_sanity_count:
                best_text = text2
            elif least_sanity_count == text3_sanity_count:
                best_text = text3
            elif least_sanity_count == text4_sanity_count:
                best_text = text4
            elif least_sanity_count == text5_sanity_count:
                best_text = text5
            # import pdb; pdb.set_trace() 
            if best_text is not None:
                with open(image_path.replace(extension, '_gemini.txt'), 'w', encoding='utf-8') as f:
                    f.write(best_text)
            return
                
        except Exception as e:
            if isinstance(e, FileExistsError):
                optional_progress_bar.update(1)
                return # skip
            print(f"Error occured while processing {image_path}!")
            print(e)
            print(f"\nAttempt: {attempt}")
            if attempt < max_retries:
                try:
                    print("trying again in 2 seconds...")
                    time.sleep(2)
                except Exception as e:
                    print(f"Error occured again while retrying processing {image_path}, attempt: {attempt}")
                    raise e
            else:
                print("Max retry has exceed!!")
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
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        pbar = tqdm.tqdm(total=len(files))
        for file in files:
            executor.submit(query_gemini_file, file, pbar)
            time.sleep(sleep_time)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str, default=None, help='Path to the images folder')
    # single file
    parser.add_argument('--single-file', type=str, help='If given, query single file')
    parser.add_argument('--ext', type=str, default='.png', help='File extension of the image')
    parser.add_argument('--api_key', type=str, default=None, help='Google API Key')
    parser.add_argument('--threaded', action='store_true', help='Use threaded version')
    parser.add_argument('--max_threads', type=int, default=8, help='Max threads to use')
    parser.add_argument('--sleep_time', type=float, default=1.1, help='Sleep time between threads')
    # REFINE_ALLOWED
    parser.add_argument('--refine', action='store_true', help='Allow refinement')
    # env
    parser.add_argument('--load-env', action='store_true', help='Load env.json')
    args = parser.parse_args()
    path, ext, threaded, max_threads, sleep_time = load_secret(args.api_key, args.path, args.ext, args.threaded, args.sleep_time, args.max_threads, args.load_env)
    REFINE_ALLOWED = args.refine
    MAX_THREADS = max_threads
    if args.single_file: # query single file
        query_gemini_file(args.single_file)
        sys.exit(0)
    if args.threaded:
        query_gemini_threaded(path, ext, sleep_time, max_threads)
    else:
        query_gemini(path, ext)
