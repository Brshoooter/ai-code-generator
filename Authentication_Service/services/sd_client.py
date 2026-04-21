import httpx
import logging
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SDClient:

    async def register(self):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{settings.sd_url}/api/register",
                    json={
                        "name": settings.service_name,
                        "url": settings.service_url,
                        "health_path": "/health"
                    }
                )
                if response.status_code == 201:
                    logger.info(f"Inregistrat in Service Discovery ca {settings.service_name}")
                else:
                    logger.warning(f"Service Discovery a raspuns cu {response.status_code}")
            except Exception as e:
                logger.warning(f"Nu m-am putut inregistra in Service Discovery: {e}")

    async def deregister(self):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{settings.sd_url}/api/deregister/{settings.service_name}",
                    params={"url": settings.service_url}
                )
                if response.status_code == 200:
                    logger.info("Dezinregistrat din Service Discovery")
                else:
                    logger.warning(f"Dezinregistrare esuata: {response.status_code}")
            except Exception as e:
                logger.warning(f"Nu m-am putut dezinregistra din Service Discovery: {e}")
