from typing import List
from ultralytics import YOLO
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from PIL import Image
import os
import argparse
import numpy as np
import glob
from tqdm import tqdm

def active_preprocessor(imgs, batch_size=1):
    """
    Generator, but actively preprocesses images and return as prepared
    :param imgs: image paths
    """
    pooling_executor = ThreadPoolExecutor(max_workers=1)
    futures = []
    # split imgs into minibatch
    divmod_result = divmod(len(imgs), batch_size)
    batch_count = divmod_result[0]
    if divmod_result[1] != 0:
        batch_count += 1
    minibatches = []
    for i in range(batch_count):
        minibatches.append(imgs[i*batch_size:min((i+1)*batch_size, len(imgs))])
    for minibatch in minibatches:
        # handle Image.open in thread
        futures.append(pooling_executor.submit(lambda x: [Image.open(img).convert("RGB") for img in x], minibatch))
    for future in futures:
        yield future.result()

def detect(imgs, cuda_device=0, model='yolov8n.pt', batch_size=-1,stream:bool=False):
    if not len(imgs):
        return []
    thread_pool = ThreadPoolExecutor(max_workers=1) # 1 thread per device, allows asynchronous execution and preprocessing
    os.environ['CUDA_VISIBLE_DEVICES'] = str(cuda_device)
    model = YOLO(model) #YOLO('yolov8n-face.pt') # for face only
    result_list = []
    if batch_size == -1:
        batch_size = len(imgs)
    else:
        batch_size = min(batch_size, len(imgs))
    # split imgs into minibatch
    divmod_result = divmod(len(imgs), batch_size)
    batch_count = divmod_result[0]
    if divmod_result[1] != 0:
        batch_count += 1
    minibatches_provider = active_preprocessor(imgs, batch_size)
    futures = []
    for minibatch in tqdm(minibatches_provider, desc=f'minibatch with device {cuda_device}', total=batch_count):
        # print(f"handling {minibatch}") # debug once
        #result_list.extend(model(minibatch))
        # send to thread and get future, do not block
        # verbose=False
        futures.append(thread_pool.submit(model, minibatch, verbose=False))
    # wait for all futures
    for future in tqdm(futures, desc=f'Waiting for futures with device {cuda_device}'):
        if stream:
            # wait for each future
            #print("Yielding")
            yield from future.result()
        else:
            result_list.extend(future.result())
    if not stream:
        return result_list

def crop_by_person(image: Image.Image, box_xyxy: list):
    """
    Crop image by person's box
    :param image: image to crop
    :param box_xyxy: person's box
    :return: cropped images as list
    """
    cropped_images = []
    for box in box_xyxy:
        # convert tensor to list
        box = box.tolist()
        cropped_images.append(image.crop(box))
    return cropped_images

def save_cropped_images(image: Image.Image, box_xyxy: list, original_filepath:str, save_dir: str):
    """
    Save cropped images to save_dir
    :param image: image to crop
    :param box_xyxy: person's box as list
    :param original_filepath: original image's filepath
    :param save_dir: directory to save cropped images
    :return: None
    """
    #print(box_xyxy)
    filename_without_ext = os.path.splitext(os.path.basename(original_filepath))[0] # pure filename without extension
    cropped_images = crop_by_person(image, box_xyxy)
    if not cropped_images:
        return # debugging
    for i, cropped_image in enumerate(cropped_images):
        cropped_image.save(os.path.join(save_dir, f'{filename_without_ext}_{i}.jpg'))

def detect_and_save_cropped_images(image_paths: List[str], save_dir: str, cuda_device: int = 0, model:str = 'yolov8n.pt', idx: int = 0, batch_size: int = -1):
    """
    Detect person and save cropped images
    :param image_path: image path
    :param save_dir: directory to save cropped images
    :param cuda_device: cuda device number
    :param model: model name, 'yolov8n.pt' or 'yolov8n-face.pt'
    :param idx: index of box to use as person box
    :param batch_size: minibatch size, -1 means all images at once
    :return: None
    
    # xyxy[idx] is used for person box as index 0
    """
    if len(image_paths) == 0:
        return
    results = detect(image_paths, cuda_device, model, batch_size, stream=True)
    for path, r in zip(image_paths, results):
        #print(f'handling {path}')
        #print(r.boxes)
        image = Image.open(path).convert("RGB")
        where_idx = r.boxes.cls.cpu().numpy() == 0 # person classes # [True, False, True, ...]
        xyxy = r.boxes.xyxy[where_idx] # [tensor([x1, y1, x2, y2]), tensor([x1, y1, x2, y2]), ...]
        save_cropped_images(image, xyxy, path, save_dir)

def main(cuda_devices:str, image_path:str, recursive:bool, save_dir:str, batch_size:int):
    image_exts = ['jpg', 'jpeg', 'png', 'webp']
    image_paths = []
    if recursive:
        # use os.walk
        for root, dirs, files in os.walk(image_path):
            for file in files:
                if file.split('.')[-1] in image_exts:
                    image_paths.append(os.path.join(root, file))
    else:
        for ext in image_exts:
            image_paths.extend(glob.glob(os.path.join(image_path, f'*.{ext}'), recursive=False))
    print(f'found {len(image_paths)} images')
    # detect and save cropped images
    available_cuda_devices = cuda_devices.split(',')
    available_cuda_devices = [int(cuda_device) for cuda_device in available_cuda_devices]
    # split image_paths into cuda_devices using numpy.array_split
    image_paths_split = np.array_split(image_paths, len(available_cuda_devices))
    # debug with raw execution
    #for cuda_device, image_paths in zip(available_cuda_devices, image_paths_split):
    #    detect_and_save_cropped_images(image_paths, save_dir, cuda_device, batch_size=batch_size)
    #return
    try:
        with ProcessPoolExecutor(max_workers=len(available_cuda_devices)) as executor:
            for cuda_device, image_paths in zip(available_cuda_devices, image_paths_split):
                executor.submit(detect_and_save_cropped_images, image_paths, save_dir, cuda_device, batch_size=batch_size)
    except KeyboardInterrupt:
        executor.shutdown(wait=False)
        print('KeyboardInterrupt')
        exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cuda-devices', type=str, default='0', help='cuda device numbers, comma separated')
    parser.add_argument('--image-path', type=str, default='/data/dataset/', help='image path')
    parser.add_argument('--recursive', action='store_true', help='recursive')
    parser.add_argument('--save-dir', type=str, default='/data/dataset_cropped', help='directory to save cropped images')
    parser.add_argument('--batch-size', type=int, default=-1, help='minibatch size, -1 means all images at once')
    args = parser.parse_args()
    main(args.cuda_devices, args.image_path, args.recursive, args.save_dir, args.batch_size)
