
import json
import time
import requests
# url encode
import urllib.parse
class ProxyHandler:
    """
    Sends request to http://{ip}:{port}/get_response_raw?url={url} with auth 
    """
    def __init__(self, proxy_list_file,proxy_auth="user:pass",port=80, wait_time=0.1,timeouts=10):
        self.proxy_auth = proxy_auth
        self.port = port
        self.proxy_list = []
        self.commit_time = {}
        self.timeouts = timeouts
        self.wait_time = wait_time
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
    def wait_until_commit(self, proxy_index=None):
        """
        Waits until the commit time
        """
        if proxy_index is None:
            proxy_index = self.proxy_index
        if proxy_index not in self.commit_time:
            self.commit_time[proxy_index] = 0
        while time.time() < self.commit_time[proxy_index] + self.wait_time:
            time.sleep(0.01)
        self.commit_time[proxy_index] = time.time()
    def get_response(self, url):
        """
        Returns the response of the url
        """
        url = urllib.parse.quote(url, safe='')
        try:
            self.proxy_index = (self.proxy_index + 1) % len(self.proxy_list)
            self.wait_until_commit()
            response = requests.get(self.proxy_list[self.proxy_index] + f"get_response?url={url}", timeout=self.timeouts, auth=tuple(self.proxy_auth.split(":")))
            if response.status_code == 200:
                json_response = response.json()
                if json_response["success"]:
                    return json.loads(json_response["response"])
                else:
                    print(f"Failed in proxy side: {json_response['response']}")
                    return None
            else:
                print(f"Failed in proxy side: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error while processing response from proxy: {e}")
            return None
    def get(self, url):
        """
        Returns the response of the url
        """
        url = urllib.parse.quote(url, safe='')
        try:
            self.proxy_index = (self.proxy_index + 1) % len(self.proxy_list)
            self.wait_until_commit()
            response = requests.get(self.proxy_list[self.proxy_index] + f"get_response_raw?url={url}", timeout=self.timeouts, auth=tuple(self.proxy_auth.split(":")))
            if response.status_code == 200:
                return response
            else:
                print(f"Error: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception: {e}")
            return None
    def filesize(self, url):
        """
        Returns the filesize of the url
        """
        url = urllib.parse.quote(url, safe='')
        try:
            self.proxy_index = (self.proxy_index + 1) % len(self.proxy_list)
            self.wait_until_commit()
            response = requests.get(self.proxy_list[self.proxy_index] + f"file_size?url={url}", timeout=self.timeouts, auth=tuple(self.proxy_auth.split(":")))
            if response.status_code == 200:
                return int(response.text)
            else:
                print(f"Error: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception: {e}")
            return None
    def get_filepart(self, url, start, end):
        """
        Returns the response of the url with range
        """
        url = urllib.parse.quote(url, safe='')
        try:
            self.proxy_index = (self.proxy_index + 1) % len(self.proxy_list)
            self.wait_until_commit()
            response = requests.get(self.proxy_list[self.proxy_index] + f"filepart?url={url}&start={start}&end={end}", timeout=self.timeouts, auth=tuple(self.proxy_auth.split(":")))
            if response.status_code == 200:
                return response
            else:
                print(f"Error: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception: {e}")
            return None
    def check(self,raise_exception=False):
        # access root
        failed_proxies = []
        for i in range(len(self.proxy_list)):
            try:
                response = requests.get(self.proxy_list[i], auth=tuple(self.proxy_auth.split(":")), timeout=2)
                if response.status_code == 200:
                    continue
                else:
                    print(f"Proxy {self.proxy_list[i]} is not working")
                    failed_proxies.append(i)
            except Exception as e:
                print(f"Proxy {self.proxy_list[i]} is not working")
                failed_proxies.append(i)
        if len(failed_proxies) > 0:
            if raise_exception:
                raise Exception(f"Proxies {failed_proxies} are not working")
            else:
                print(f"Proxies {failed_proxies} are not working, total {len(failed_proxies)} proxies of {len(self.proxy_list)} are not working")
                # remove failed proxies
                for i in failed_proxies[::-1]:
                    del self.proxy_list[i]
                if len(self.proxy_list) == 0:
                    raise Exception("No proxies available")

class SingleProxyHandler(ProxyHandler):
    def __init__(self, proxy_url, proxy_auth="user:pass",port=80):
        self.proxy_auth = proxy_auth
        self.port = port
        self.proxy_list = [proxy_url]
        self.proxy_index = -1
