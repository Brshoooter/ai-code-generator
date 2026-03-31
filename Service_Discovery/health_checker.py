from models import ServiceInformation
from registry import ServiceRegistry
import httpx, logging, asyncio
from config import settings


class HealthChecker:

    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self.running = False
        self.client = httpx.AsyncClient()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    async def checking_health(self):
        
        self.running = True
        self.logger.info("health checker pornit!")

        while self.running:
            services = self.registry.get_all_services()
            for name in services:
                for instance in services[name]:
                    await self.check_instance(instance, name)
            await asyncio.sleep(settings.health_check_interval)

    async def check_instance(self, instance: ServiceInformation, name: str):
        url = str(instance.url).rstrip("/") + instance.health_path
        try:
            response = await self.client.get(
                url,
                timeout = settings.service_response_timeout
            )
            if response.status_code == 200:
                self.registry.update_health(name, instance.url, True)
            else:
                self.registry.update_health(name, instance.url, False)
        except Exception as e:

            self.registry.update_health(name, instance.url, False)

    async def stop(self):
        self.running = False
        await self.client.aclose()
        self.logger.info("health checker oprit")
