### annotation
# loads png file + _gpt4.json (or maybe optional filename schema)
# shows to user, and asks for annotation (to adjust text)

import glob
import gradio as gr
import json
import os
from PIL import Image


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


with gr.Blocks() as block:
    with gr.Tab("Anntation") as tab:
        show_image = gr.Image(type="pil", label="Image")
        caption_index = gr.Number(value=0,label="Caption_idx",interactive=True)
        path_input_box = gr.Textbox(label="Path to Images and tag/caption files")
        annotation_dir = gr.Textbox(label="Annotation dir")
        caption_type = gr.Dropdown(label="Caption type", choices=['gpt4', 'gemini', 'custom'])
        
        annotation_text_box = gr.Textbox(label="Annotation", interactive=True)
        reference_text_box = gr.Textbox(label="Reference", interactive=False)
        
        save_button = gr.Button(value="Save")
        next_button = gr.Button(value="Next")
        prev_button = gr.Button(value="Prev")
        refresh_button = gr.Button(value="Refresh")
        
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
            print(path)
            image_path = image_paths[int(caption_input)]
            image, caption, tags = load_image(image_path, caption_ext, '.txt')
            reference_text_box.value = tags
            return image, caption, tags
        
        def refresh_next(caption_input, path_input, caption_type_selected):
            result = refresh(path_input, caption_input + 1, caption_type_selected)
            return caption_input + 1, *result
        def refresh_prev(caption_input, path_input, caption_type_selected):
            result = refresh(path_input, caption_input - 1, caption_type_selected)
            return caption_input - 1, *result
        next_button.click(
            refresh_next,
            inputs=[caption_index, path_input_box, caption_type],
            outputs=[caption_index, show_image, annotation_text_box, reference_text_box],
        )
        prev_button.click(
            fn=refresh_prev,
            inputs=[caption_index, path_input_box, caption_type],
            outputs=[caption_index, show_image, annotation_text_box, reference_text_box],
        )
        
        refresh_button.click(
            refresh,
            inputs=[path_input_box, caption_index, caption_type],
            outputs=[show_image, annotation_text_box, reference_text_box],
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

block.launch()