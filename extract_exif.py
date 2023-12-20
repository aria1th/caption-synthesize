from PIL import Image
import gzip
import os
import glob

def read_info_from_image_stealth(image):
    # if tensor, convert to PIL image
    if hasattr(image, 'cpu'):
        image = image.cpu().numpy() #((1, 1, 1280, 3), '<f4')
        image = image[0].astype('uint8') #((1, 1280, 3), 'uint8')
        image = Image.fromarray(image)
    # trying to read stealth pnginfo
    width, height = image.size
    pixels = image.load()

    has_alpha = True if image.mode == 'RGBA' else False
    mode = None
    compressed = False
    binary_data = ''
    buffer_a = ''
    buffer_rgb = ''
    index_a = 0
    index_rgb = 0
    sig_confirmed = False
    confirming_signature = True
    reading_param_len = False
    reading_param = False
    read_end = False
    never_confirmed = True
    for x in range(width):
        for y in range(height):
            if has_alpha:
                r, g, b, a = pixels[x, y]
                buffer_a += str(a & 1)
                index_a += 1
            else:
                r, g, b = pixels[x, y]
            buffer_rgb += str(r & 1)
            buffer_rgb += str(g & 1)
            buffer_rgb += str(b & 1)
            index_rgb += 3
            if confirming_signature:
                if x * height + y > 120 and never_confirmed:
                    return ''
                if index_a == len('stealth_pnginfo') * 8:
                    decoded_sig = bytearray(int(buffer_a[i:i + 8], 2) for i in
                                            range(0, len(buffer_a), 8)).decode('utf-8', errors='ignore')
                    if decoded_sig in {'stealth_pnginfo', 'stealth_pngcomp'}:
                        #print(f"Found signature at {x}, {y}")
                        confirming_signature = False
                        sig_confirmed = True
                        reading_param_len = True
                        mode = 'alpha'
                        if decoded_sig == 'stealth_pngcomp':
                            compressed = True
                        buffer_a = ''
                        index_a = 0
                        never_confirmed = False
                    else:
                        read_end = True
                        break
                elif index_rgb == len('stealth_pnginfo') * 8:
                    decoded_sig = bytearray(int(buffer_rgb[i:i + 8], 2) for i in
                                            range(0, len(buffer_rgb), 8)).decode('utf-8', errors='ignore')
                    if decoded_sig in {'stealth_rgbinfo', 'stealth_rgbcomp'}:
                        #print(f"Found signature at {x}, {y}")
                        confirming_signature = False
                        sig_confirmed = True
                        reading_param_len = True
                        mode = 'rgb'
                        if decoded_sig == 'stealth_rgbcomp':
                            compressed = True
                        buffer_rgb = ''
                        index_rgb = 0
                        never_confirmed = False
            elif reading_param_len:
                if mode == 'alpha':
                    if index_a == 32:
                        param_len = int(buffer_a, 2)
                        reading_param_len = False
                        reading_param = True
                        buffer_a = ''
                        index_a = 0
                else:
                    if index_rgb == 33:
                        pop = buffer_rgb[-1]
                        buffer_rgb = buffer_rgb[:-1]
                        param_len = int(buffer_rgb, 2)
                        reading_param_len = False
                        reading_param = True
                        buffer_rgb = pop
                        index_rgb = 1
            elif reading_param:
                if mode == 'alpha':
                    if index_a == param_len:
                        binary_data = buffer_a
                        read_end = True
                        break
                else:
                    if index_rgb >= param_len:
                        diff = param_len - index_rgb
                        if diff < 0:
                            buffer_rgb = buffer_rgb[:diff]
                        binary_data = buffer_rgb
                        read_end = True
                        break
            else:
                # impossible
                read_end = True
                break
        if read_end:
            break
    geninfo = ''
    if sig_confirmed and binary_data != '':
        # Convert binary string to UTF-8 encoded text
        byte_data = bytearray(int(binary_data[i:i + 8], 2) for i in range(0, len(binary_data), 8))
        try:
            if compressed:
                decoded_data = gzip.decompress(bytes(byte_data)).decode('utf-8')
            else:
                decoded_data = byte_data.decode('utf-8', errors='ignore')
            geninfo = decoded_data
        except:
            pass
    return str(geninfo)

import tqdm
import json
import re
import sys

PATH = r"F:\comfyui\ComfyUI\output\NAI_1215"
def extract_exif(path):
    for file in tqdm.tqdm(glob.glob(os.path.join(path, '*.png'))):
        image = Image.open(file)
        data = (read_info_from_image_stealth(image))
        if not data:
            continue
        data = json.loads(data)
        data = data["Description"]
        with open(file.replace('.png', '.txt'), 'w') as f:
            f.write(data)
def extract_exif_classify(path):
    # instead of writing, if not exists, move to path / without_exif folder
    for file in tqdm.tqdm(glob.glob(os.path.join(path, '*.png'))):
        image = Image.open(file)
        data = (read_info_from_image_stealth(image))
        if not data:
            # move to path / without_exif folder
            target_path = os.path.join(path, 'without_exif')
            if not os.path.exists(target_path):
                os.makedirs(target_path)
            #print("Moving to", target_path)
            os.rename(file, os.path.join(target_path, os.path.basename(file)))
            continue
def extract_exif_classify_text(path, text, output_path=None, recursive=False):
    # validate output path is not inside input path
    if output_path and os.path.abspath(output_path).startswith(os.path.abspath(path)):
        print("Output path cannot be inside input path")
        return
    # same drive limitation, WinError 17
    if sys.platform == 'win32' and output_path and os.path.splitdrive(os.path.abspath(output_path))[0] != os.path.splitdrive(os.path.abspath(path))[0]:
        print("Output path must be on the same drive as input path, windows limitation")
        return
    lists = []
    if recursive:
        for root, dirs, files in os.walk(path):
            for file in files:
                if not file.endswith('.png'):
                    continue
                lists.append(os.path.join(root, file))
    else:
        lists = glob.glob(os.path.join(path, '*.png'))
    for file in tqdm.tqdm(lists):
        image = Image.open(file)
        data = (read_info_from_image_stealth(image))
        # match regex
        if re.search(text, data, re.IGNORECASE):
            # move to path / without_exif folder
            target_path = os.path.join(output_path or path, 'matched')
            if not os.path.exists(target_path):
                os.makedirs(target_path)
            #print("Moving to", target_path)
            os.rename(file, os.path.join(target_path, os.path.basename(file)))
            continue
import gradio as gr

def classify_image(img):
    img = Image.open(img)
    print("Handling image")
    return read_info_from_image_stealth(img) #returns string

def read_and_extract(img:str):
    return read_info_from_image_stealth(img)
with gr.Blocks(analytics_enabled=False) as block:
    with gr.Tab("Extract Text"):
        #inputs = gr.Image(type="pil", label="Original Image", source="upload")
        input_path = gr.Textbox(label="Path to Image")
        outputs = gr.Textbox(label="Extracted Text")
        
        button = gr.Button(value="Extract")
        button.click(
            fn=classify_image,
            inputs=[input_path],
            outputs=[outputs],
        )
    with gr.Tab("Extract text from image(file)"):
        input = gr.Image(label="source", sources="upload", type="pil",interactive=True,image_mode="RGBA")
        outputs = gr.Textbox(label="Extracted Text")
        button = gr.Button(value="Extract")
        button.click(
            fn=read_and_extract,
            inputs=[input],
            outputs=[outputs],
        )
    with gr.Tab("Classify Folder"):
        inputs = gr.Textbox(label="Folder with Images")
        button = gr.Button(value="Extract")
        button.click(
            fn=extract_exif_classify,
            inputs=[inputs],
        )
    with gr.Tab("Classify Folder with matching prompt"):
        inputs = gr.Textbox(label="Folder with Images")
        text = gr.Textbox(label="Prompt")
        output_path = gr.Textbox(label="Output Path")
        recursive = gr.Checkbox(label="Recursive")
        button = gr.Button(value="Extract")
        button.click(
            fn=extract_exif_classify_text,
            inputs=[inputs, text, output_path, recursive],
        )
    with gr.Tab("Extract Text from Folder"):
        inputs = gr.Textbox(label="Folder with Images")
        button = gr.Button(value="Extract")
        button.click(
            fn=extract_exif,
            inputs=[inputs],
        )
        

block.launch()
