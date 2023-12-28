import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import io
import os
import requests
from typing import Generator, List, Optional
from tqdm import tqdm
from PIL import Image
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

def download_image_web(image_url:str) -> Image.Image:
    """
    Download image from web.
    """
    # if path, read
    if os.path.exists(image_url):
        return Image.open(image_url).convert("RGB")
    # download the image
    image_file = requests.get(image_url)
    # check response
    if image_file.status_code != 200:
        raise RuntimeError(f"Image download failed with status code {image_file.status_code}")
    image_file_content = image_file.content
    # return the image
    return Image.open(io.BytesIO(image_file_content)).convert("RGB")

def parse_args():
    """
    Parse input arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--model-name", type=str,
                        default="Lin-Chen/ShareCaptioner")
    parser.add_argument("--images-file", type=str, default="images_to_describe.json",
                        help="a list, each element is a string for image path")
    parser.add_argument("--single-image-url", type=str, default=None) # for demo-like
    parser.add_argument("--save-path", type=str, default="captions.json")
    # device
    parser.add_argument("--device", type=str, default="cuda:0")
    parser.add_argument("--reference-tags-file", type=str, default=None, help="a list of tags, to be references or reordered.")
    parser.add_argument("--tag-txt", action="store_true", help="use txt files with the same name as images as tags")
    parser.add_argument("--tags-suffix", type=str, default="_tags")
    parser.add_argument("--image-dir", type=str, default=None)
    
    arguments = parser.parse_args()
    return arguments

model = None

def format_text(text, tags:str=None):
    """
    Format text.
    """
    if tags is None:
        return text
    else:
        return text.replace("%tags", tags)

def inference(model, imgs:Generator, tags:List[Optional[str]], seg2, seg_emb1, batch_size=4, stream=False, generation_params=None):
    """
    Inference.
    if stream is True, yield each result.
    """
    captions = []
    part_len = len(tags)
    chunk_size = part_len//batch_size
    if part_len % batch_size != 0:
        chunk_size += 1
    _i = 0
    for i in tqdm(range(chunk_size), desc='BATCH'):
        print(f'{i}/{chunk_size}')
        subs = []
        for j in tqdm(range(batch_size), desc='ITEMS'):
            if i*batch_size+j < part_len:
                try:
                    image = next(imgs)
                except StopIteration:
                    break
                subs.append(model.vis_processor(image).unsqueeze(0))
        if len(subs) == 0:
            break
        subs = torch.cat(subs, dim=0).cuda()
        tmp_bs = subs.shape[0]
        tmp_seg_emb1 = seg_emb1.repeat(tmp_bs, 1, 1)
        emb2_list = []
        for j in range(tmp_bs):
            emb2_list.append(model.encode_text(format_text(seg2, tags[i*batch_size+j]), add_special_tokens=False))
        tmp_seg_emb2 = torch.stack(emb2_list, dim=0).cuda()
        
        with torch.cuda.amp.autocast():
            with torch.no_grad():
                subs = model.encode_img(subs)
                input_emb = torch.cat(
                    [tmp_seg_emb1, subs, tmp_seg_emb2], dim=1)
                out_embeds = model.internlm_model.generate(inputs_embeds=input_emb,
                                                           eos_token_id=model.tokenizer.eos_token_id,
                                                           num_return_sequences=1,
                                                           **generation_params
                                                           )
        for j, out in enumerate(out_embeds):
            out[out == -1] = 2
            response = model.decode_text([out])
            if stream:
                yield response
            captions.append(response)
    return captions

def active_yield_images(image_path:List[str], max_workers = 4) -> Image.Image:
    """
    Thread pool for downloading images or reading images from disk.
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # submit tasks
        futures = []
        for path in image_path:
            futures.append(executor.submit(download_image_web, path))
        # yield results orderly
        for future in futures:
            # if future has thrown exception, it will be raised here
            yield future.result()


def main(args):
    """
    Inference.
    """
    global model
    default_generation_params = {
        "max_length": 500,
        "num_beams": 3,
        "min_length": 1,
        "do_sample": True,
        "repetition_penalty": 1.5,
        "length_penalty": 1.0,
        "temperature": 1.0,
    }
    if model is None:
        tokenizer = AutoTokenizer.from_pretrained(
            args.model_name, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            args.model_name, device_map=args.device, trust_remote_code=True).eval()
        model.tokenizer = tokenizer

    model.cuda()
    model.half()
    # imgs : [path1, path2, ...]
    image_paths = []
    if args.single_image_url is not None:
        imgs = [args.single_image_url]
        # download
        image = download_image_web(imgs[0])
        image.save('tmp.jpg')
        imgs = ['tmp.jpg']
    elif args.images_file:
        with open(args.images_file, 'r', encoding="utf-8") as f:
            imgs = json.load(f)
    elif args.image_dir:
        imgs = []
        img_paths = []
        for file in os.listdir(args.image_dir):
            if file.endswith('.jpg') or file.endswith('.png') or file.endswith('.webp'):
                imgs.append(os.path.join(args.image_dir, file))
                img_paths.append(file)
    if args.reference_tags_file:
      # read
      with open(args.reference_tags_file, 'r', encoding="utf-8") as f:
        tags = json.load(f)
    elif args.tag_txt:
        # read
        # in imgs, there are corresponding txt files with the same name or with prefix
        tags = []
        with open(args.images_file, 'r', encoding="utf-8") as f:
          image_paths = json.load(f)
        for image_path in image_paths:
            # remove extension
            image_path = image_path.split('.')[0]
            # find file with .txt or _<suffix>.txt
            txt_path = image_path + args.tags_suffix + '.txt'
            if not os.path.exists(txt_path):
                txt_path = image_path + '.txt'
            if not os.path.exists(txt_path):
                tags.append(None)
            with open(txt_path, 'r', encoding="utf-8") as f:
                tags.append(f.read())
    else:
      tags = [None,] * len(imgs)
    part_len = len(imgs)

    seg1 = '<|User|>:'
    seg2 = fr'''Analyze the image in a comprehensive and detailed manner.
Reorder the following tags according to the image content.
DO NOT ignore any tags.
%tags
{model.eoh}\n<|Bot|>:'''
    # use inference
    seg_emb1 = model.encode_text(seg1, add_special_tokens=True)
    imgs = active_yield_images(imgs) # generator
    infer_results = inference(model, imgs, tags, seg2, seg_emb1, batch_size=args.batch_size, stream=True, generation_params=default_generation_params)
    _i = 0
    for responses in infer_results:
        if args.save_path:
            with open(args.save_path, 'a+', encoding='utf-8') as f:
                json.dump({f"{image_paths[_i]}": responses}, f, ensure_ascii=False)
                f.write('\n')
        else:
            print(f"{image_paths[_i]}: {responses}")
    print('Done')

if __name__ == "__main__":
    args = parse_args()
    main(args)

