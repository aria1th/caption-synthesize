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
    image = Image.open(path)
    caption = ''
    caption_path = path.replace(os.path.splitext(path)[-1], caption_ext)
    if os.path.exists(caption_path):
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
        
        annotation_text_box = gr.Textbox(label="Annotation", interactive=True)
        reference_text_box = gr.Textbox(label="Reference", interactive=False)
        
        save_button = gr.Button(value="Save")
        next_button = gr.Button(value="Next")
        prev_button = gr.Button(value="Prev")
        refresh_button = gr.Button(value="Refresh")
        
        def refresh(path_input, caption_input):
            path = path_input
            #file_exts
            image_paths = glob.glob(os.path.join(path, '*'))
            image_paths = [p for p in image_paths if os.path.splitext(p)[-1] in file_exts]
            image_paths.sort()
            print(path)
            image_path = image_paths[int(caption_input)]
            image, caption, tags = load_image(image_path)
            reference_text_box.value = tags
            return image, caption, tags
        
        next_button.click(
            lambda x : x + 1,
            inputs=[caption_index],
            outputs=[caption_index],
        )
        prev_button.click(
            lambda x : x - 1,
            inputs=[caption_index],
            outputs=[caption_index],
        )
        
        refresh_button.click(
            refresh,
            inputs=[path_input_box, caption_index],
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