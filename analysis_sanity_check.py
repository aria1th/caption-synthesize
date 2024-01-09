import os
import json
from collections import Counter
import gradio as gr
import argparse

def list_files_in_directory(directory_path):
    files_list = [f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]
    return files_list

def process_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)
        return data

def analyze_sanity_check(json_data):
    sanity_check_count = json_data.get("sanity_check_count", 0)
    sanity_check_list = json_data.get("sanity_check", [])
    return sanity_check_count, sanity_check_list

def find_files_with_word(word, folder_path):
    files_list = list_files_in_directory(folder_path)
    filtered_files = [file for file in files_list if 'total' in file]

    total_files = len(filtered_files)
    total_sanity_check_count = 0
    sanity_check_words_counter = Counter()

    for file_name in filtered_files:
        file_path = os.path.join(folder_path, file_name)
        json_data = process_json_file(file_path)

        sanity_check_count, sanity_check_list = analyze_sanity_check(json_data)
        total_sanity_check_count += sanity_check_count
        sanity_check_words_counter.update(sanity_check_list)

        if word in sanity_check_list:
            print("Image Name:", json_data["image_name"])
            print("Tag Count General:", json_data["tag_count_general"])
            print("Tags:", json_data["tag_string"])
            print("Captions:", json_data["captions"])
            print("Sanity Check:", json_data["sanity_check"])
            print("\n")

    if not word:
        print("Average sanity_check_count:", total_sanity_check_count / total_files)
        print("Word frequencies in sanity_check list:")
        for word, count in sanity_check_words_counter.items():
            print(f"{word}: {count}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Search for a word in sanity_check list.')
    parser.add_argument('--word_to_search', type=str, help='The word to search for in the sanity_check list.')
    parser.add_argument('--folder_path', type=str, default='/Users/mina/Desktop/onoma/few_sanity', help='Path to the sanity folder')

    args = parser.parse_args()

    find_files_with_word(args.word_to_search, args.folder_path)
