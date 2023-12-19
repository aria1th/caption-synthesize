from typing import List
import aiohttp

from aiodanbooru.api import DanbooruAPI
from aiodanbooru.models import DanbooruPost

class AIBooruPost(DanbooruPost):
    @property
    def link(self):
        return f"https://aibooru.online/posts/{self.id}"

import requests
def get_tags_all(base_url: str = "https://aibooru.online"):
    # https://aibooru.online/tags.json?page=idx
    all_tags = []
    idx = 1
    while True:
        url = f"{base_url}/tags.json?page={idx}"
        response = requests.get(url)
        try:
            response.raise_for_status()
        except Exception as exception:
            break
        tags = response.json()
        if not tags:
            break
        all_tags += tags
        idx += 1
    # tags: {"id": 1, "name": "tag_name", "category": 1} remove others
    tag_name_category = [(tag["name"], tag["category"]) for tag in all_tags]
    return dict(tag_name_category)

# save tags to tags.json
import json
def save_tags(filepath="tags.json"):
    all_tags_dict = get_tags_all()
    with open(filepath, "w", encoding='utf-8') as file:
        json.dump(all_tags_dict, file)

class AIBooruAPI(DanbooruAPI):
    def __init__(self, base_url: str = "https://aibooru.online"):
        super().__init__(base_url)

    async def get_posts(
        self, tags: List[str] = None, limit: int = None, page: int = None
    ) -> List[DanbooruPost]:
        async with aiohttp.ClientSession() as session:
            endpoint = "/posts.json"
            params = {}
            if tags is not None:
                params["tags"] = " ".join(tags)
            if limit is not None:
                params["limit"] = str(limit)
            if page is not None:
                params["page"] = str(page)
            response = await self._get(session, endpoint, params)
            posts = []
            for post in response:
                posts.append(AIBooruPost(**post)) 
            return posts
    
    async def get_posts_pages(
        self, tags: List[str] = None, limit: int = None, page_start: int = 1, page_end: int = 1
    ) -> List[DanbooruPost]:
        posts = []
        for page in range(page_start, page_end + 1):
            posts += await self.get_posts(tags=tags, limit=limit, page=page)
        # remove duplicates with id
        posts = list({post.id:post for post in posts}.values())
        return posts
    
    async def get_all_posts(
        self, tags: List[str] = None, limit: int = None
    ) -> List[DanbooruPost]:
        posts = []
        page = 1
        while True:
            try:
                new_posts = await self.get_posts(tags=tags, limit=limit, page=page)
            except Exception as exception:
                break # no more pages
            if not new_posts:
                break
            posts += new_posts
            page += 1
        # remove duplicates with id
        posts = list({post.id:post for post in posts}.values())
        # limit
        if limit is not None:
            posts = posts[:limit]
        return posts
import pathlib
import os
import logging
import json
import tqdm
async def main(dir="aibooru",tags=["novelai"]):
    api = AIBooruAPI(base_url="https://aibooru.online")
    path = pathlib.Path(dir)
    if not path.exists():
        path.mkdir()
    posts = await api.get_all_posts(tags=tags, limit=None) # coroutine
    _i = 0
    if posts:
        for post in tqdm.tqdm(posts):
            _i += 1
            filepath = path / post.filename
            if not filepath.exists():
                try:
                    media_data = await post.get_media()
                except Exception as exception:
                    logging.error(f"Failed to download {post.filename} from {post.link} due to {exception}")
                    continue
                with open(filepath, "wb") as file:
                    file.write(media_data)
            json_path = path / f"{post.md5}.json"
            if not json_path.exists():
                with open(json_path, "w", encoding='utf-8') as file:
                    json.dump(post.dict(), file)
            meta_tag_text_path = path / f"{post.md5}.txt"
            if not meta_tag_text_path.exists():
                generate_text_from_json(json_path)
            logging.info(f"Downloaded {post.filename}, {_i} / {len(posts)}")
    else:
        logging.error("No posts found")

async def get_metadata_dict(dir="aibooru",tags=["novelai"]):
    api = AIBooruAPI(base_url="https://aibooru.online")
    path = pathlib.Path(dir)
    if not path.exists():
        path.mkdir()
    #posts = await api.get_posts(tags=["novelai"], limit=None)
    posts = await api.get_all_posts(tags=tags, limit=None) # coroutine
    if posts:
        for post in tqdm.tqdm(posts):
            try:
                metadata_dict = post.dict()
            except Exception as exception:
                logging.error(f"Failed to get metadata dict from {post.link} due to {exception}")
                continue
            json_read = metadata_dict
            id = metadata_dict["md5"]
            filepath = path / f"{id}.json"
            metadata_dict_stringify = f"""
copyright: {json_read["tag_string_copyright"]}
character: {json_read["tag_string_character"]}
general tags: {json_read["tag_string_general"]}
"""
            if not filepath.exists():
                with open(filepath, "w", encoding='utf-8') as file:
                    json.dump(metadata_dict, file)
                logging.info(f"Saved metadata dict for {post.link}")
            filepath_txt = path / f"{id}.txt"
            with open(filepath_txt, "w", encoding='utf-8') as file:
                file.write(metadata_dict_stringify)
            logging.info(f"Saved metadata dict for {post.link}")
    else:
        logging.error("No posts found")

def cleanup_get_txt_from_existing(dir="aibooru"):
    """
    Cleanup .txt files from existing .json files
    """
    path = pathlib.Path(dir)
    if not path.exists():
        path.mkdir()
    for filepath in path.glob("*.json"):
        id = filepath.stem
        filepath_txt = path / f"{id}.txt"
        if filepath_txt.exists():
            continue
        json_read = json.load(open(filepath, "r", encoding='utf-8'))
        metadata_dict_stringify = f"""
copyright: {json_read["tag_string_copyright"]}
character: {json_read["tag_string_character"]}
general tags: {json_read["tag_string_general"]}
"""
        with open(filepath_txt, "w", encoding='utf-8') as file:
            file.write(metadata_dict_stringify)
        logging.info(f"Saved metadata dict for {filepath}")

def generate_text_from_json(filepath):
    """
    Generate text from json file.
    """
    if isinstance(filepath, pathlib.Path):
        filepath = str(filepath)
    json_read = json.load(open(filepath, "r", encoding='utf-8'))
    string = ""
    for i, j in [
        ["copyright", "tag_string_copyright"],
        ["character", "tag_string_character"],
        ["general tags", "tag_string_general"],
    ]:
        string += f"{i}: {json_read[j]}\n"
    if not string or string.isspace() or os.path.exists(filepath.replace(".json", ".txt")):
        print(f"Skipping {filepath}")
        return
    with open(filepath.replace(".json", ".txt"), "w", encoding='utf-8') as file:
        file.write(string)

def create_subset(dir="aibooru", subset_dir="aibooru_subset", filter = lambda x: True, subset_size=10000, strategy="move"):
    path = pathlib.Path(dir)
    subset_path = pathlib.Path(subset_dir)
    if not subset_path.exists():
        subset_path.mkdir()
    pbar = tqdm.tqdm(total=subset_size)
    for filepath in path.glob("*.json"):
        pbar.update(1)
        with open(filepath, "r", encoding='utf-8') as file:
            metadata_dict = json.load(file)
        if filter(metadata_dict):
            # move .json and matching another extension file
            id = metadata_dict["md5"]
            for extension in ["jpg", "jpeg", "png", "webp", "gif", "gifv", "mp4", "webm"]:
                filepath_origin = path / f"{id}.{extension}"
                if filepath.exists():
                    break
            # move json and file
            if filepath_origin.exists():
                if strategy == "move":
                    filepath_origin.rename(subset_path / filepath_origin.name)
                    filepath.rename(subset_path / filepath.name)
                elif strategy == "copy":
                    filepath_origin.replace(subset_path / filepath_origin.name)
                    filepath.replace(subset_path / filepath.name)
                else:
                    raise ValueError(f"Unknown strategy {strategy}")
                subset_size -= 1
                if subset_size <= 0:
                    break
            else:
                logging.error(f"Failed to find file for {filepath}")
                continue

def translate_tags(tag_json):
    # 0 general tags
    # 1 user
    # 2 does not exist
    # 3 copyright
    # 4 character
    # 5 tensorart / platforms
    # 6 SD model
    # we only want 0, 3, 4
    pass
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main()) # download all images
    loop.run_until_complete(get_metadata_dict()) # get metadata dict
    #filter = lambda x : 'yaoi' in x['tag_string'] or 'bara' in x['tag_string']
    #safety_filter = lambda x : x['rating'] == 'g'
    #create_subset(filter = safety_filter, dir='aibooru', subset_dir="aibooru_subset_g", subset_size=10000, strategy="move") # create subset with 'general' rating
    #create_subset(filter = filter, dir='aibooru_subset_g', subset_dir="aibooru_subset_g_removed", subset_size=10000, strategy="move") # remove yaoi and bara, it is not safe for work but how is it general!?
    save_tags() # get tags (all)
    #cleanup_get_txt_from_existing('aibooru_subset_g_100img') # from json file, create .txt file for captioning (if txt file does not exist)