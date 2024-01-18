
import requests
class ProxyHandler:
    """
    Sends request to http://{ip}:{port}/get_response_raw?url={url} with auth 
    """
    def __init__(self, proxy_list_file,proxy_auth="user:pass",port=80):
        self.proxy_auth = proxy_auth
        self.port = port
        self.proxy_list = []
        with open(proxy_list_file, 'r') as f:
            for line in f:
                self.proxy_list.append(line.strip())
        for i in range(len(self.proxy_list)):
            if not self.proxy_list[i].startswith("http"):
                self.proxy_list[i] = "http://" + self.proxy_list[i]
            # check :port
            if ":" not in self.proxy_list[i]:
                self.proxy_list[i] += f":{self.port}"
            if not self.proxy_list[i].endswith("/"):
                self.proxy_list[i] += "/"
        self.proxy_index = -1
    def get(self, url):
        """
        Returns the response of the url
        """
        try:
            self.proxy_index = (self.proxy_index + 1) % len(self.proxy_list)
            response = requests.get(self.proxy_list[self.proxy_index] + f"get_response_raw?url={url}", timeout=10, auth=tuple(self.proxy_auth.split(":")))
            if response.status_code == 200:
                return response
            else:
                print(f"Error: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception: {e}")
            return None

class SingleProxyHandler(ProxyHandler):
    def __init__(self, proxy_url, proxy_auth="user:pass",port=80):
        self.proxy_auth = proxy_auth
        self.port = port
        self.proxy_list = [proxy_url]
        self.proxy_index = -1
