"""
Converts gemini generate request into CURL requestable json
"""

from abc import ABC, abstractmethod
from io import BytesIO
import json
import os
from typing import Iterable, Optional, Union
import requests
import base64
from PIL import Image

class JsonSerializable(ABC):
    """
    Abstract class for json serializable objects
    """
    @abstractmethod
    def __init__(self) -> None:
        raise NotImplementedError
    @abstractmethod
    def json(self) -> dict:
        """
        Returns json serializable object
        """
        raise NotImplementedError

class MultiTurnData(JsonSerializable):
    """
    Multi turn data for gemini request
    """
    def __init__(self, iterable_or_item: Union[Iterable["TurnDataPart"], "TurnDataPart"]) -> None:
        if isinstance(iterable_or_item, TurnDataPart):
            self.data = [iterable_or_item]
        else:
            assert all(isinstance(item, TurnDataPart) for item in iterable_or_item), f"iterable_or_item must be TurnDataPart or Iterable[TurnDataPart], not {type(iterable_or_item)}"
            self.data = iterable_or_item
    def json(self) -> dict:
        return [item.json() for item in self.data]

class TurnDataPart(JsonSerializable):
    """
    Single part of the turn data
    """
    def __init__(self, iterable_or_item: Union[Iterable["Item"], "Item"]) -> None:
        if isinstance(iterable_or_item, Item):
            self.data = [iterable_or_item]
        else:
            assert all(isinstance(item, Item) for item in iterable_or_item), f"iterable_or_item must be Item or Iterable[Item], not {type(iterable_or_item)}"
            self.data = iterable_or_item
    def json(self, role:Optional[str] = None) -> dict:
        jsonpart = {"parts": [item.json() for item in self.data]}
        if role:
            assert isinstance(role, str), f"role must be str, not {type(role)}"
            jsonpart["role"] = role
        return jsonpart

class Item(JsonSerializable):
    """
    Abstract item for gemini request, which allows StringItem and ImageItem
    """
    def __init__(self, item: Union[str, "StringItem", "ImageItem"]) -> None:
        if isinstance(item, str):
            self.item = StringItem(item)
        elif isinstance(item, Image.Image):
            self.item = ImageItem(item)
        # check item is Item-subclass but not Item itself
        elif isinstance(item, Item) and item.__class__ != Item:
            self.item = item
        else:
            raise TypeError(f"Item must be str or JsonSerializable, not {type(item)}")
    def json(self) -> dict:
        return self.item.json()

class StringItem(Item):
    """
    String item for gemini request
    """
    def __init__(self, text: str) -> None:
        assert isinstance(text, str), f"text must be str, not {type(text)}"
        self.text = text
    def json(self) -> dict:
        return {"text": str(self.text)}

class ImageItem(Item):
    """
    Image item for gemini request
    """
    def __init__(self, image_or_path: Union[Image.Image, str]) -> None:
        assert isinstance(image_or_path, (str, Image.Image)), f"image_or_path must be str or Image, not {type(image_or_path)}"
        self.image_or_path = image_or_path
    def _load_url(self):
        """
        Loads image from url
        """
        header = requests.head(self.image_or_path).headers
        mime_type = header.get("content-type", "image/jpeg")
        raw_image = requests.get(self.image_or_path).content
        # encode image
        encoded_image = base64.b64encode(raw_image)
        return encoded_image.decode("utf-8"), mime_type
    def _load_path(self):
        """
        Loads image from path
        """
        mime_type = "image/jpeg"
        if self.image_or_path.endswith(".png"):
            mime_type = "image/png"
        elif self.image_or_path.endswith(".webp"):
            mime_type = "image/webp"
        elif self.image_or_path.endswith(".gif"):
            mime_type = "image/gif"
        else:
            mime_type = "image/jpeg"
        with open(self.image_or_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read())
        return encoded_image.decode("utf-8"), mime_type

    def _load_image(self):
        """
        Loads image from Image
        """
        assert isinstance(self.image_or_path, Image.Image), f"image_or_path must be Image, not {type(self.image_or_path)}"
        mime_type = "image/jpeg"
        if self.image_or_path.format == "PNG":
            mime_type = "image/png"
        elif self.image_or_path.format == "WEBP":
            mime_type = "image/webp"
        elif self.image_or_path.format == "GIF":
            mime_type = "image/gif"
        else:
            mime_type = "image/jpeg"
        # to bytes
        with BytesIO() as output:
            self.image_or_path.save(output, format=self.image_or_path.format or "JPEG")
            encoded_image = base64.b64encode(output.getvalue())
        return encoded_image.decode("utf-8"), mime_type

    def json(self) -> dict:
        if isinstance(self.image_or_path, Image.Image):
            encoded_image, mime_type = self._load_image()
        elif self.image_or_path.startswith("http"):
            encoded_image, mime_type = self._load_url()
        elif os.path.exists(self.image_or_path):
            encoded_image, mime_type = self._load_path()
        else:
            raise FileNotFoundError(f"image_or_path {self.image_or_path} not found")
        # save encoded image to json
        with open('log.txt', 'w') as f:
            f.write(encoded_image)
        return {
            "inline_data": {
                "mime_type": mime_type,
                "data": encoded_image
            }
        }

class GenerationConfig(JsonSerializable):
    """
    Generation config for the gemini request
    """
    data = {
        "stopSequences": [
        ],
        "temperature": 0.1,
        "topK": 32,
        "topP": 1,
        "maxOutputTokens": 4096,
    }
    def __init__(self, **kwargs) -> None:
        self.data = GenerationConfig.data
        for key, value in kwargs.items():
            self.data[key] = value
    def json(self) -> dict:
        return self.data

class SafetySettings(JsonSerializable):
    """
    Safety settings for the gemini request
    default: BLOCK_NONE
    """
    data = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]
    def __init__(self):
        self.data = SafetySettings.data

    def json(self):
        return self.data

class GenerationRequest(JsonSerializable):
    """
    Curl requestable json for gemini request
    """
    def __init__(self, data: MultiTurnData, config: GenerationConfig, safety_settings: SafetySettings) -> None:
        assert isinstance(data, MultiTurnData), f"data must be MultiTurnData, not {type(data)}"
        assert isinstance(config, GenerationConfig), f"config must be GenerationConfig, not {type(config)}"
        assert isinstance(safety_settings, SafetySettings), f"safety_settings must be SafetySettings, not {type(safety_settings)}"
        self.data = data
        self.config = config
        self.safety_settings = safety_settings

    def json(self) -> dict:
        return {
            "contents": self.data.json(),
            "generationConfig": self.config.json(),
            "safety_settings": self.safety_settings.json()
        }
    
    @staticmethod
    def load(conversation_context:Iterable[Union[str, Image.Image]]) -> "GenerationRequest":
        """
        Loads GenerationRequest from conversation_context
        """
        assert all(isinstance(item, (str, Image.Image)) for item in conversation_context), f"conversation_context must be Iterable[str] or Iterable[Image.Image], not {type(conversation_context)}"
        data = MultiTurnData([TurnDataPart([Item(item) for item in conversation_context])])
        config = GenerationConfig()
        safety_settings = SafetySettings()
        return GenerationRequest(data, config, safety_settings)

def generate_request_args(conversation_context:Iterable[Union[str, Image.Image]], api_key:str) -> str:
    """
    Generates reqeust args 
    """
    #f"curl -X POST -H 'Content-Type: application/json' -d '{GenerationRequest.load(conversation_context).json()}' https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent?key=${api_key}"
    args = {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent?key=" + api_key,
        "headers": {
            "Content-Type": "application/json"
        },
        "data": GenerationRequest.load(conversation_context).json()
    }
    return args

def generate_request(conversation_context:Iterable[Union[str, Image.Image]], api_key:str, proxy:Optional[str]=None, proxy_auth:Optional[str]=None) -> dict:
    """
    Generates request
    """
    args = generate_request_args(conversation_context, api_key)
    if proxy:
        session = requests.Session()
        if proxy_auth:
            session.auth = tuple(proxy_auth.split(":"))
        # curl -X POST -H 'Content-Type: application/json' -d '{GenerationRequest.load(conversation_context).json()}' http://localhost:8000/post_response
        url = args.pop("url")
        response = session.post(proxy, data={"args_json" : json.dumps(args), "url": url})
        status = response.status_code
        if status != 200:
            raise requests.exceptions.HTTPError(f"Proxy returned status code {status}, error {response.text}")
        else:
            response_json = response.json()
            # get success
            success = response_json.get("success", False)
            if not success:
                raise requests.exceptions.HTTPError(f"Proxy returned success {success}, error {response_json.get('response')}")
            else:
                return json.loads(response_json.get("response"))
    response = requests.post(url=args["url"], headers=args["headers"], data=json.dumps(args["data"]))
    return response.json()

def test_request(api_key:str, proxy:Optional[str] = None, proxy_auth:Optional[str]=None) -> dict:
    """
    Tests request
    """
    context = ["hello",Image.open(r"assets/02de52e6b87389bd182a943c02492565.jpg"), "world"]
    return generate_request(context, api_key, proxy, proxy_auth)

def analyze_model_response(response:dict) -> dict:
    """
    Analyzes model response. Raises if error.
    """
    if 'candidates' not in response:
        if 'error' in response:
            raise ValueError(f"Error in response: {response['error']}")
        raise ValueError('Invalid response: no candidates')
    candidates = [c for c in response['candidates'] if c['finishReason'] == 'STOP']
    if not candidates:
        raise ValueError('Invalid response: no STOP candidates')
    filtered = [filter_candidates(c) for c in candidates]
    filtered = [f for f in filtered if f]
    if not filtered:
        raise ValueError('Invalid response: no filtered candidates')
    return filtered

def filter_candidates(candidate:dict) -> str:
    string = ""
    content = candidate['content']
    if 'parts' not in content:
        return string
    for part in content['parts']:
        if 'text' not in part:
            continue
        string += part['text']
    return string

if __name__ == "__main__":
    secrets = json.load(open("secret.json", "r", encoding="utf-8"))
    cached_api_key = secrets["GOOGLE_API_KEY"]
    result = test_request(api_key=cached_api_key)
    text = analyze_model_response(result)
    print(text)
    #print(test_request(api_key=cached_api_key, proxy="http://localhost:8000/post_response", proxy_auth="user:password_notdefault"))
