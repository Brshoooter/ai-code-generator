import logging, time
from config import settings

class RateLimiter():

    def __init__(self):
        self.request: dict[str, list] = {}

        logging.basicConfig(level = logging.INFO)
        self.logger = logging.getLogger(__name__)

    def is_allowed(self, key: str) -> bool:

        curent_time = time.time()

        self.request = {
            k : [t for t in timestamps if curent_time - t < settings.rate_limit_time_window] 
            for k, timestamps in self.request.items()
        }
        self.request = {k: t for k, t in self.request.items() if t}

        if key not in self.request:
            self.request[key] = []

        if len(self.request[key]) < settings.rate_limit_requests:
            self.request[key].append(curent_time)
            return True
        
        self.logger.warning(f"Limita depasita de request uri pentru {key}")
        return False