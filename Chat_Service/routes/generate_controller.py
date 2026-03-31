from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from services.generate_service import GenerateResponseService, CodeGenerationError
from models import GenerateRequest

router = APIRouter()

service = GenerateResponseService()

@router.post("/")
async def generate_code(request: GenerateRequest):
    try:
        return StreamingResponse(
            service.generate_code(request.prompt),
            media_type="text/plain"
        )
    except CodeGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))  