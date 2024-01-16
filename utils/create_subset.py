"""
Creates subset from the original dataset.
Dataset : Folder containing images and corresponding text files.

Count : Number of images to be selected.
Seed : Seed for random number generator.
Path : Path to the new dataset.
"""
from random import Random
import os
import pathlib
import shutil
import argparse
from tqdm import tqdm

def create_subset(dataset, count, seed, path, dataset_tag_path=None, filter_func: callable = None, behavior="copy"):
    """
    Creates subset from the original dataset.
    Dataset : Folder containing images and corresponding text files.
    Count : Number of images to be selected.
    Seed : Seed for random number generator.
    Path : Path to the new dataset.
    Dataset_tag_path : Path to the dataset tags.
    Filter_func : Function to filter the files. (filename) -> bool
    """
    # Create the folder if it doesn't exist.
    # if exists and files are present, then it will throw an error.
    if behavior == "copy":
        copyfunc = shutil.copy
    elif behavior == "symlink":
        copyfunc = os.symlink
    elif behavior == "move":
        copyfunc = shutil.move
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)
    if count <= 0:
        return
    # count files in subset folder.
    files = os.listdir(path)
    print("Files in subset folder : ", len(files))
    # Get all the files in the dataset.
    files = os.listdir(dataset)
    # exclude the text files.
    files = [file for file in files if file.split('.')[-1] != 'txt']
    print("Sampling from : ", len(files), " files.")
    # Shuffle the files.
    Random(seed).shuffle(files)
    # Copy the first count files to the new dataset.
    moved = 0
    pbar = tqdm(total=count)
    for file in files:
        if moved >= count:
            break
        if filter_func and not filter_func(os.path.abspath(os.path.join(dataset, file))):
            continue
        #print(f"Copying {file} to {path}")
        # if already exists, then skip.
        if os.path.exists(os.path.join(path, file)):
            continue
        target_path = os.path.join(path, file)
        copyfunc(os.path.join(dataset, file), target_path)
        moved += 1
        pbar.update(1)
        # Copy the corresponding text file.
        if os.path.exists(os.path.join(path, file.split('.')[0] + '.txt')):
            continue
        if dataset_tag_path:
            file_base = file.split('.')[0]
            if os.path.exists(os.path.join(dataset_tag_path, file_base + '.txt')):
                copyfunc(os.path.join(dataset_tag_path, file_base + '.txt'), os.path.join(path, file_base + '.txt'))
        else:
            if os.path.exists(os.path.join(dataset, file.split('.')[0] + '.txt')):
                copyfunc(os.path.join(dataset, file.split('.')[0] + '.txt'), os.path.join(path, file.split('.')[0] + '.txt'))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, required=True, help='Path to the dataset.')
    parser.add_argument('--count', type=int, required=True, help='Number of images to be selected.')
    parser.add_argument('--seed', type=int, required=True, help='Seed for random number generator.')
    parser.add_argument('--path', type=str, required=True, help='Path to the new dataset.')
    parser.add_argument('--dataset_tag_path', type=str, required=False, help='Path to the dataset tags.')
    # behavior
    parser.add_argument('--behavior', type=str, required=False, default="copy", help='Behavior for copying files. copy, symlink, move')
    # include and exclude behavior
    args = parser.parse_args()
    create_subset(args.dataset, args.count, args.seed, args.path, args.dataset_tag_path, behavior=args.behavior)