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


def image_inference(image_path):
    """
    Load image from the given image.
    """
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

def savefile(dir, imgfile, txtfile):
    #save job image file
    imgfile.save(os.path.join(dir, imgfile))
     #save txt file
    with open(os.path.join(dir, txtfile)) as f:
        f.write()
    

def devide_file(path:str, extension:str = '.jpg'):
    files = glob.glob(os.path.join(path, f'*{extension}'))
    if not files:
        print(f"No files found for {os.path.join(path, f'*{extension}')}!")
        return
    for file in tqdm.tqdm(files):
        imgfile = image_inference(file)
        txtfile = tags_formatted(file)
        savefile('/Users/hoyeonmoon/Downloads/aibooru_jpg', imgfile, txtfile)
        

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str, default='/Users/hoyeonmoon/Downloads/aibooru', help='Path to the images folder')
    parser.add_argument('--ext', type=str, default='.png', help='File extension of the image')
    
    args = parser.parse_args()
    
    devide_file(args.path, args.ext)