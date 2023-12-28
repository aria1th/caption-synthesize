import argparse
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import json
import io
import os
import threading
import time
import requests
from typing import Generator, List, Optional
from tqdm import tqdm
from PIL import Image
import logging

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
    
log_file = 'inference.log'
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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
        logging.error(f"Image download failed with status code {image_file.status_code}")
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
    parser.add_argument("--images-file", type=str, default=None,
                        help="a list, each element is a string for image path")
    parser.add_argument("--single-image-url", type=str, default=None) # for demo-like
    parser.add_argument("--save-path", type=str, default="captions.json")
    # device
    parser.add_argument("--device", type=str, default="cuda:0")
    parser.add_argument("--reference-tags-file", type=str, default=None, help="a list of tags, to be references or reordered.")
    parser.add_argument("--tag-txt", action="store_true", help="use txt files with the same name as images as tags")
    parser.add_argument("--tags-suffix", type=str, default="_tags")
    parser.add_argument("--image-dir", type=str, default=None)
    # cache-dir
    parser.add_argument("--cache-dir", type=str, default=None)
    # floating point
    parser.add_argument("--precision", type=str, default="bf16") # fp16, fp32, fp8?
    
    arguments = parser.parse_args()
    return arguments

def format_text(text, tags:str=None):
    """
    Format text.
    """
    if tags is None:
        return text
    else:
        return text.replace("%tags", tags)

def inference(model, imgs:Generator, tags:List[Optional[str]], seg2, seg_emb1, batch_size=4, stream=False, generation_params=None, dtype="float32"):
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
    with tqdm(range(chunk_size),total=part_len, desc='BATCH') as pbar:
        for i in pbar:
            print(f'{i}/{chunk_size}')
            subs = []
            logging.info(f"Processing batch {i}")
            pbar.set_postfix_str(f'Preparing items...')
            for j in range(batch_size):
                if i*batch_size+j < part_len:
                    try:
                        image = next(imgs)
                    except StopIteration:
                        break
                    subs.append(model.vis_processor(image).unsqueeze(0))
            if len(subs) == 0:
                break
            logging.info(f"Batch {i} prepared")
            pbar.set_postfix_str(f'Inference...')
            subs = torch.cat(subs, dim=0).cuda()
            tmp_bs = subs.shape[0]
            tmp_seg_emb1 = seg_emb1.repeat(tmp_bs, 1, 1)
            emb2_list = []
            for j in range(tmp_bs):
                emb2_list.append(model.encode_text(format_text(seg2, tags[i*batch_size+j]), add_special_tokens=False))
            # to dim 3
            tmp_seg_emb2 = torch.stack(emb2_list, dim=0).squeeze(-1).cuda() #[1, 1, 160, 4096]
            tmp_seg_emb2 = tmp_seg_emb2.squeeze(1)
            with torch.cuda.amp.autocast():
                with torch.no_grad():
                    subs = model.encode_img(subs)
                    # validate number of dims
                    input_emb = torch.cat(
                        [tmp_seg_emb1, subs, tmp_seg_emb2], dim=1).to(dtype=dtype)
                    out_embeds = model.internlm_model.generate(inputs_embeds=input_emb,
                                                            eos_token_id=model.tokenizer.eos_token_id,
                                                            num_return_sequences=1,
                                                            **generation_params
                                                            )
            pbar.set_postfix_str(f'Ended batch...')
            logging.info(f"Batch {i} ended")
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
    default_generation_params = {
        "max_length": 500,
        "num_beams": 3,
        "min_length": 1,
        "do_sample": True,
        "repetition_penalty": 1.5,
        "length_penalty": 1.0,
        "temperature": 1.0,
    }
    device = args.device
    precision = args.precision
    cache_dir = args.cache_dir
    model_name = args.model_name
    batch_size = args.batch_size
    save_path = args.save_path
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
                img_paths.append(os.path.join(args.image_dir, file))
    if args.reference_tags_file:
        # read
        with open(args.reference_tags_file, 'r', encoding="utf-8") as f:
            tags = json.load(f)
    elif args.tag_txt:
        # read
        # in imgs, there are corresponding txt files with the same name or with prefix
        tags = []
        if args.images_file:
            with open(args.images_file, 'r', encoding="utf-8") as f:
                image_paths = json.load(f)
        elif args.image_dir:
            image_paths = img_paths
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
    # Now image_paths and tags are ready
    if "," in device:
        device = device.split(",")
        # add cuda: for each device
        device = [f"cuda:{i}" for i in device if "cuda:" not in i]
    elif "cuda:" in device:
        device = [device]
    elif device.isnumeric():
        device = [f"cuda:{device}"]
    else:
        # Unfortunately, model does not support auto device
        # we will use find all cuda devices and use all parallelly
        raise NotImplementedError("Model does not support auto device")
    # split tags, image_paths into chunks corresponding to devices
    assert len(tags) == len(imgs), f"Number of tags {len(tags)} does not match number of images {len(imgs)}"
    assert len(device) > 0, "No device is specified"
    chunk_size = len(tags)//len(device)
    tags_chunks = [list() for _ in range(len(device))]
    image_paths_chunks = [list() for _ in range(len(device))]
    for i in range(len(device)):
        tags_chunks[i] = tags[i*chunk_size:(i+1)*chunk_size]
        image_paths_chunks[i] = image_paths[i*chunk_size:(i+1)*chunk_size]
    if len(tags) % len(device) != 0:
        # add leftover to first device
        tags_chunks[0].extend(tags[len(device)*chunk_size:])
        image_paths_chunks[0].extend(image_paths[len(device)*chunk_size:])
    assert sum([len(i) for i in tags_chunks]) == len(tags), "Tags chunks are not correct"
    assert sum([len(i) for i in image_paths_chunks]) == len(image_paths), "Image paths chunks are not correct"
    # inference
    generation_params = default_generation_params
    events = []
    futures = []
    with ProcessPoolExecutor(max_workers=len(device), initializer=torch.multiprocessing.set_sharing_strategy('file_system'), mp_context=torch.multiprocessing.get_context('spawn')) as executor:
        for i in range(len(device)):
            logging.info(f"Starting process {i} for device {device[i]}")
            futures.append(executor.submit(log_infer_tags, model_name, cache_dir, precision, device[i], image_paths_chunks[i], batch_size, generation_params, tags_chunks[i], image_paths_chunks[i], save_path))
    try:
        for future in futures:
            future.result()
    except KeyboardInterrupt:
        logging.info(f"KeyboardInterrupt, stopping...")
        for event in events:
            event.set()

def log_infer_tags(*args, **kwargs):
    """
    Log inference.
    """
    try:
        logging.info(f"Inference started")
        infer_tags(*args, **kwargs)
    except Exception as e:
        logging.error(f"Inference failed with error {e} at {e.__traceback__}, device {kwargs.get('device', None)}")
        raise e
    finally:
        logging.info(f"Inference finished")
        event = kwargs.get("event", None)
        if event is not None:
            event.set()
        return

def infer_tags(model_name:str, cache_dir:str, precision:str, device:str, imgs:Generator, batch_size=4, generation_params=None, tags:List[Optional[str]]=None, image_paths:List[str]=None, save_path:str=None):
    """
    Inference.
    """
    # load model
    os.environ["CUDA_VISIBLE_DEVICES"] = device.split(":")[-1]
    precision_map = {
        "fp16" : torch.float16,
        "bf16" : torch.bfloat16,
        "fp32" : torch.float32,
    }
    precision = precision_map.get(precision, precision)
    logging.info(f"Loading model {model_name} on device {device}")
    tokenizer = AutoTokenizer.from_pretrained(
        model_name, trust_remote_code=True, cache_dir=cache_dir, device_map="cuda:0",
        torch_dtype=precision)
    model = AutoModelForCausalLM.from_pretrained(
        model_name, device_map="cuda:0", trust_remote_code=True, cache_dir=cache_dir,
        torch_dtype=precision).eval()
    model.tokenizer = tokenizer
    model.cuda()
    logging.info(f"Model {model_name} loaded on device {device}")
    seg1 = '<|User|>:'
    seg2 = fr'''Analyze the image in a comprehensive and detailed manner.
Reorder the following tags according to the image content.
DO NOT ignore any tags.
TAGS: 
%tags
{model.eoh}\n<|Bot|>:'''
    # use inference
    seg_emb1 = model.encode_text(seg1, add_special_tokens=True)
    imgs = active_yield_images(imgs) # generator
    infer_results = inference(model, imgs, tags, seg2, seg_emb1, batch_size=batch_size, stream=True, generation_params=generation_params, dtype=precision)
    _i = 0
    for responses in infer_results:
        logging.info(f"Writing result {_i}")
        with open(save_path, 'a+', encoding='utf-8') as f:
            json.dump({f"{image_paths[_i]}": responses}, f, ensure_ascii=False)
            f.write('\n')
        _i += 1
    print('Done')

if __name__ == "__main__":
    logging.info(f"Starting inference...")
    args = parse_args()
    main(args)

