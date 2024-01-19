import os
import time

class AbstractAPIIterator:
    def __init__(self, list_of_api, rate_limit=1):
        self.list_of_api = list_of_api
        self.api_index = -1
        self.rate_limit = rate_limit
        self.commit_time = {}
    def wait_until_commit(self):
        """
        Waits until the commit time
        """
        if self.api_index not in self.commit_time:
            self.commit_time[self.api_index] = 0
        while time.time() < self.commit_time[self.api_index] + self.rate_limit:
            time.sleep(0.01)
        self.commit_time[self.api_index] = time.time()
    def get(self):
        """
        Waits and returns the next api
        """
        self.api_index = (self.api_index + 1) % len(self.list_of_api)
        self.wait_until_commit()
        return self.list_of_api[self.api_index]

class APIKeyIterator(AbstractAPIIterator):
    def __init__(self, api_key_file, rate_limit=1):
        self.api_key_list = []
        with open(api_key_file, 'r') as f:
            for line in f:
                self.api_key_list.append(line.strip())
        super().__init__(self.api_key_list, rate_limit)

class SingleAPIkey(AbstractAPIIterator):
    def __init__(self, api_key, rate_limit=1):
        self.api_key = api_key
        super().__init__([self.api_key], rate_limit)
