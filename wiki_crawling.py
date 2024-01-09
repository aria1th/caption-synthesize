import argparse
import requests
import os
import json


def get_profile_info(username, api_key, base_url):
    url = f"{base_url}/profile.json?login={username}&api_key={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check for HTTP errors
        profile_info = response.json()
        print(profile_info)
        return profile_info
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None
    

def open_sanity(sanity_path, save_path):
    files_list = [f for f in os.listdir(sanity_path) if os.path.isfile(os.path.join(sanity_path, f))]
    for f in files_list:
        file_path = os.path.join(sanity_path, f)
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                file_contents = json.load(file)
                sanity_tags_list = file_contents.get('sanity_check', [])
                if not sanity_tags_list:
                    pass
                for tag in sanity_tags_list:
                    try:
                        search_wiki_by_tag(tag, save_path)
                    except Exception as e:
                        print(f"Error Search Fail: {e}")
        except Exception as e:
            print(f"No file exists: {e}")
        
def search_wiki_by_tag(tag, save_path):
    base_url = "https://danbooru.donmai.us"
    endpoint = f"/wiki_pages/{tag}"  # Use the appropriate format based on your needs
    url = f"{base_url}{endpoint}.json"

    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()  # Check for HTTP errors
        wiki_pages = response.json()
        # Save the wiki_pages to a file
        save_file_path = os.path.join(save_path, f"{tag}_wiki_pages.json")
        with open(save_file_path, 'w', encoding='utf-8') as file:
            json.dump(wiki_pages, file, ensure_ascii=False, indent=4)
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
def main():
    parser = argparse.ArgumentParser(description='Retrieve Danbooru profile information.')
    parser.add_argument('--base_url', default='https://danbooru.donmai.us', help='Your Danbooru username')
    parser.add_argument('--username', default='', help='Your Danbooru username')
    parser.add_argument('--api_key', default= '', help='Your Danbooru API key')
    parser.add_argument('--path_to_sanity', default= '/Users/hoyeonmoon/Downloads/onoma/solo_few_sanity', help='Your Danbooru API key')
    parser.add_argument('--save_path', default= '/Users/hoyeonmoon/Downloads/onoma/solo_few_sanity_wiki', help='Path to save search result json file')

    args = parser.parse_args()
    profile_info = get_profile_info(args.username, args.api_key, args.base_url)

    if profile_info:
        print("Profile Information:")
        print(f"Username: {profile_info['name']}")
        open_sanity(args.path_to_sanity, args.save_path)
        

if __name__ == "__main__":
    main()
