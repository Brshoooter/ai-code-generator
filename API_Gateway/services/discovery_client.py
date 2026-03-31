from config import settings
import httpx, logging, asyncio
import time


class DiscoveryClient:
    
    def __init__(self):
        self.client = httpx.AsyncClient()

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)    

        self.cache ={}
        self.rr_counter = {}

    async def fetch_services(self, name: str) -> list:
        try:
            request_url = settings.sd_url + "/api/services/" + name
            response = await self.client.get(
                url = request_url,
                timeout = settings.request_timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"Nu exista instante in viata de tipul {name}")
                return []
        except Exception as e:
            self.logger.warning(f"Service discovery este cazut: {e}")
            return []

    async def get_services(self, name: str) -> list:
        if name not in self.cache:
            self.cache[name] = {"instances": [],
                                "timestamp": -30 }

        curent_time = time.time()
        time_difference = curent_time - self.cache[name]["timestamp"]
        if time_difference < settings.cache_ttl:
            return self.cache[name]["instances"]
        
        instances = await self.fetch_services(name)

        if instances:
            self.cache[name]["instances"] = instances
            self.cache[name]["timestamp"] = curent_time

        return self.cache[name]["instances"]
        

    async def get_instance(self, name: str) -> any:

        instances = await self.get_services(name)
        if instances == []:
            return None
        
        if name not in self.rr_counter:
            self.rr_counter[name] = 0

        instance = instances[self.rr_counter[name] % len(instances)]
        self.rr_counter[name] += 1

        if self.rr_counter[name] == len(instances):
            self.rr_counter[name] = 0

        return instance
        
        