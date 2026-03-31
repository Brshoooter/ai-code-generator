from fastapi import APIRouter, Request, HTTPException
from services.discovery_client import DiscoveryClient
from services.proxy import ProxyService

discovery = DiscoveryClient()
proxy = ProxyService()

router = APIRouter()

@router.api_route("/api/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_request(request: Request, service_name: str, path: str):
    instance = await discovery.get_instance(service_name)
    if instance is None:
        raise HTTPException(503, "Serviciu indisponibil")
    
    url = instance["url"]
    return await proxy.forward_request(request, url, "/" + path)

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway"} 