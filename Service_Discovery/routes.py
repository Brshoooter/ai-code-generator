from fastapi import APIRouter, HTTPException
from registry import ServiceRegistry
from models import RegisterRequest, ServiceDiscoveryResponse
from pydantic import AnyHttpUrl

registry = ServiceRegistry()

router = APIRouter()

@router.post("/register", status_code = 201)
async def register_request(request: RegisterRequest):
    response = registry.register(request=request)
    return ServiceDiscoveryResponse.model_validate(response.model_dump())

@router.delete("/deregister/{name}")
async def deregister_request(name: str, url: AnyHttpUrl):
    response = registry.deregister(name, url)
    if response:
        return {"mesaj": f"microserviciul {name} cu url: {url} a fost sters cu succes"}
    else:
        raise HTTPException(404, detail=f"nu s-a gasit microserviciului {name}")
    
@router.get("/services/{name}")
async def get_services_request(name: str):
    services = registry.get_service(name)
    if services is None:
        raise HTTPException(status_code=404, detail=f"Microserviciul {name} nu exista")
    if len(services) == 0:
        raise HTTPException(status_code=503, detail=f"Microserviciul {name} exista dar toate instantele lui sunt cazute")
    else:
        return [ServiceDiscoveryResponse.model_validate(x.model_dump()) for x in services]
    
@router.get("/services")
async def get_all_services_request():
    services = registry.get_all_services()
    return{
        name : [ServiceDiscoveryResponse.model_validate(x.model_dump()) for x in instances]
        for name, instances in services.items()
    }

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "service-discovery"}
