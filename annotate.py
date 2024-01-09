### annotation
# loads png file + _gpt4.json (or maybe optional filename schema)
# shows to user, and asks for annotation (to adjust text)

import glob
import gradio as gr
import json
import os
from PIL import Image
import textdistance as td
import re


file_exts = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
def load_image(path, caption_ext='_gpt4.json', tags_ext='.txt'):
    """
    Loads image, caption and tags from given path.
    """
    image = Image.open(path)
    caption = ''
    caption_path = path.replace(os.path.splitext(path)[-1], caption_ext)
    if os.path.exists(caption_path):
        if caption_ext == '_gpt4.json':
            with open(caption_path, 'r') as f:
                caption = json.load(f)
                caption = caption['choices'][0]['message']['content']
                # ```json\n{}...` -> json
                caption = caption.replace('```json\n', '')
                caption = caption.replace('\n```', '')
                # load
                caption = json.loads(caption)
                # to string, with pretty print
                caption = json.dumps(caption, indent=4)
        else:
            with open(caption_path, 'r') as f:
                caption = f.read()
    else:
        raise Exception(f"Caption file not found for {path}, expected at {caption_path}")
    tags = ''
    tags_path = path.replace(os.path.splitext(path)[-1], tags_ext)
    if os.path.exists(tags_path):
        with open(tags_path, 'r') as f:
            tags = f.read()
    return image, caption, tags

def save_captions(original_path, annotation_dir, image, caption):
    filename = os.path.basename(original_path)
    caption_path = os.path.join(annotation_dir, filename.replace(os.path.splitext(filename)[-1], '.txt'))
    with open(caption_path, 'w') as f:
        f.write(caption)
    # copy image to annotation dir
    image.save(os.path.join(annotation_dir, filename))

def sanity_check(tags, caption):
    """
    Checks if all tags are in the caption.
    """
    excluded_tags = ['original', 'error']
    
    tags = tags.split('\n')
    # tags start with something:, remove it
    tags = [t.split(':', 1)[-1] for t in tags]
    # remove empty tags
    tags = [t for t in tags if t]
    # as flat list
    # tags = [t for ts in tags for t in ts.split(' ')] 
    tags = [t.replace('_', ' ').replace('-', ' ') for ts in tags for t in ts.split(' ')]
    caption = caption.replace('_', ' ').replace('-', ' ')
    split_caption = split_sentence(caption)


    # Set a threshold for similarity
    threshold = 0.13

    # Check if any word has similarity above the threshold for each sentence
    for t in tags:
        for c in split_caption:
            if td.levenshtein.normalized_similarity(t, c) >= threshold:
                excluded_tags.append(t)
            
    # import pdb; pdb.set_trace()       
    tags_with_parenthesis = [t for t in tags if '(' in t]
    excluded_tags.extend(tags_with_parenthesis) 

    if 'solo' in caption and '1girl' not in caption:
        excluded_tags.append('1girl')
    elif '1girl' in caption and 'solo' not in caption:
        excluded_tags.append('solo')
    elif 'kimono' in caption and 'yukata' not in caption:
        excluded_tags.append('yukata')
        
    # remove underscores from caption as well
    tags_not_in_caption = [t for t in tags if t.lower() not in caption.lower() and t not in excluded_tags] 
    
    return tags_not_in_caption

def split_sentence(sentence):
    result = [token.strip() for token in re.split('[,\\s]*\\sand\\s|[.,]', sentence) if token.strip()]
    return result

def create_block(default_path=None, default_annotation_dir=None, default_caption_type=None):
    with gr.Blocks(analytics_enabled=False) as block:
        with gr.Tab("Anntation") as tab:
            with gr.Row():
                show_image = gr.Image(type="pil", label="Image")
                annotation_text_box = gr.Textbox(label="Annotation", interactive=True, lines=3)
                
            path_input_box = gr.Textbox(label="Path to Images and tag/caption files", value=default_path)
            path_input_box.visible = not default_path # if default path is given, hide
            annotation_dir = gr.Textbox(label="Annotation dir", value=default_annotation_dir)
            annotation_dir.visible = not default_annotation_dir # if default path is given, hide
            caption_type = gr.Dropdown(label="Caption type", choices=['gpt4', 'gemini', 'custom'], value="gemini" if not default_caption_type else default_caption_type)
            caption_type.visible = not default_caption_type
            caption_index = gr.Number(value=0,label="Caption_idx",interactive=True)
            reference_text_box = gr.Textbox(label="Reference", interactive=False, lines=5)
            sanity_checkbox = gr.Textbox(label="Sanity check", interactive=False, lines=2) # used for missing tags
            with gr.Row():
                save_button = gr.Button(value="Save")
            with gr.Row():
                next_button = gr.Button(value="Next")
                prev_button = gr.Button(value="Prev")
            with gr.Row():
                refresh_button = gr.Button(value="Refresh")
                sanity_check_button = gr.Button(value="Sanity check")
            
            def refresh(path_input, caption_input, caption_type_selected):
                caption_ext = {
                    'gpt4' : '_gpt4.json',
                    'gemini' : '_gemini.txt',
                    'custom' : '.txt',
                }[caption_type_selected]
                path = path_input
                #file_exts
                image_paths = glob.glob(os.path.join(path, '*'))
                image_paths = [p for p in image_paths if os.path.splitext(p)[-1] in file_exts]
                # remove if no caption
                image_paths = [p for p in image_paths if os.path.exists(p.replace(os.path.splitext(p)[-1], caption_ext))]
                image_paths.sort()
                #print(path)
                image_path = image_paths[int(caption_input)]
                image, caption, tags = load_image(image_path, caption_ext, '.txt')
                reference_text_box.value = tags
                return image, caption, tags, sanity_check(tags, caption)
            
            def refresh_next(caption_input, path_input, caption_type_selected):
                result = refresh(path_input, caption_input + 1, caption_type_selected)
                return caption_input + 1, *result
            def refresh_prev(caption_input, path_input, caption_type_selected):
                result = refresh(path_input, caption_input - 1, caption_type_selected)
                return caption_input - 1, *result
            next_button.click(
                refresh_next,
                inputs=[caption_index, path_input_box, caption_type],
                outputs=[caption_index, show_image, annotation_text_box, reference_text_box, sanity_checkbox],
            )
            prev_button.click(
                fn=refresh_prev,
                inputs=[caption_index, path_input_box, caption_type],
                outputs=[caption_index, show_image, annotation_text_box, reference_text_box, sanity_checkbox],
            )
            sanity_check_button.click(
                sanity_check,
                inputs=[reference_text_box, annotation_text_box],
                outputs=[sanity_checkbox],
            )
            refresh_button.click(
                refresh,
                inputs=[path_input_box, caption_index, caption_type],
                outputs=[show_image, annotation_text_box, reference_text_box, sanity_checkbox],
            )
            def save(image_path, image, caption_index, annotation_dir, annotation_text):
                image_paths = glob.glob(os.path.join(image_path, '*'))
                image_paths = [p for p in image_paths if os.path.splitext(p)[-1] in file_exts]
                image_paths.sort()
                save_captions(image_paths[int(caption_index)], annotation_dir, image, annotation_text)
            
            save_button.click(
                save,
                inputs=[path_input_box, show_image, caption_index, annotation_dir, annotation_text_box],
                outputs=[],
            )
    return block
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str, help='Path to the images folder')
    parser.add_argument('--annotation-dir', type=str, help='Path to the annotation folder')
    parser.add_argument('--caption-type', type=str, help='Caption type')
    parser.add_argument('--share', action='store_true', help='Share Gradio')
    args = parser.parse_args()
    block = create_block(args.path, args.annotation_dir, args.caption_type)
    block.launch(share=args.share)
