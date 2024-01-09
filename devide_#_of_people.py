import argparse
import os
import shutil
import pathlib


def move_file(folder_path, save_path, txtfile):
    for file in txtfile: 
        img_file_png = file.replace('.txt', '.png')
        img_file_jpg = file.replace('.txt', '.jpg')
        img_file_webp = file.replace('.txt', '.webp')
        json_file = file.replace('.txt', '.json')
        
        try:
            shutil.copy(os.path.join(folder_path, img_file_png), save_path)
        except FileNotFoundError:
            try:
                shutil.copy(os.path.join(folder_path, img_file_jpg), save_path)
            except FileNotFoundError:
                try:
                    shutil.copy(os.path.join(folder_path, img_file_webp), save_path)
                except FileNotFoundError:
                    print(f" {file}  is GIF.")
                    
        shutil.copy(os.path.join(folder_path, file), save_path)
        shutil.copy(os.path.join(folder_path, json_file), save_path)

    
def load_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"파일 '{file_path}'를 찾을 수 없습니다.")
    except Exception as e:
        print(f"파일을 열 때 오류가 발생했습니다: {e}")

def main(folder_path, save_path):
    sololist = []
    files = [filename for filename in os.listdir(folder_path)]
    for filename in files:
        if filename.endswith(".txt"):
            json_data = load_file(os.path.join(folder_path, filename))
            if ('solo' in json_data) and ('solo_focus' not in json_data):
                sololist.append(filename)
    move_file(folder_path, save_path, sololist)            

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder_path', type=str, default="/Users/hoyeonmoon/Downloads/onoma/")
    parser.add_argument('--save_path', type=str, default="/Users/hoyeonmoon/Downloads/onoma/")
    args = parser.parse_args()

    if not args.folder_path or not args.save_path:
        print("Please provide both --folder_path and --save_path.")
    else:
        main(args.folder_path, args.save_path)
        
