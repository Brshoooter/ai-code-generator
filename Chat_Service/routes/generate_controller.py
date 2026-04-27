from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from services.generate_service import GenerateResponseService
from models import GenerateRequest

router = APIRouter()

service = GenerateResponseService()


@router.post("/")
async def generate_code(request: GenerateRequest):
    return StreamingResponse(
        service.generate_code([m.model_dump() for m in request.messages]),
        media_type="text/plain"
    )