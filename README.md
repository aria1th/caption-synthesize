## Synthesizing Captions for booru-tag style database

Recently, LAION type dataset research have discovered that it has insufficient information, `alttexts` were disasterously lacking information about actual images.

Rather we can call it miracle that models which were dependent at the open dataset, working despite of those discrepencies.

[Google](https://arxiv.org/pdf/2310.16656.pdf), [OpenAi](https://cdn.openai.com/papers/dall-e-3.pdf
) has discovered that synthetic captions are far ![image](https://github.com/aria1th/caption-synthesize/assets/35677394/9055b913-6603-4836-a2bf-6f5872c28565)
beneficial for dependent task, and CapsFusion project tries to annotate the large scale dataset with synthetic way.

[Meta](https://github.com/facebookresearch/DCI) also tries to make a high-quality refined dataset, with hierarchical way.

Unfortunately, locally we don't have enough resources to process all the large database.

But we can cover it in several way, 

1. Tag-retrieval
2. Focal crop - Tag - Grouping
3. Tag relevance based reordering.

Which should help understanding what the tags actually belongs to.



## extract-exif.py

The file supports Gradio Demo to to extract Stealth-PNGInfo type image metadata.

## query-gpt4.py

The file is example template to query GPT-4V API to get annnotation, based on image and tag.

In the directory, the image should have same name with tag .txt file.
![image](https://github.com/aria1th/caption-synthesize/assets/35677394/626ee09a-0a32-47eb-939d-1aec0c75a68e)

The txt file format:
```plaintext

copyright: 
character: erica_blandelli
general tags: 1girl arm_up blonde_hair blue_eyes breasts choker cleavage closed_mouth day full_body high_heels long_hair looking_at_viewer miniskirt outdoors pleated_skirt red_skirt sitting skirt smile solo

```

## annotate.py
Gradio Demo of the annotation.
Hooman should refine the GPT4V annotation. The sanitize cell, which shows the 'unused tags' will be added soon.



### Note that GPT-4V **DOES NOT ACCEPT ANY TYPES OF NSFW CONTENTS**
For those work, one might need company contact, or fair-use agreement for those annotations.

Unfortunately, most of the open source / crawled dataset has potential risk to contain unclassified data.

And since Data Poisoning is being a severe issue, the problem will be important soon :tm:.





If booru database supported 'where' is related with specific tag, then it could have been a novel dataset, which also have semantic information too.

