from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from services.generate_service import GenerateResponseService
from services import files_client
from models import GenerateRequest

router = APIRouter()

service = GenerateResponseService()


@router.post("/")
async def generate_code(request: GenerateRequest, http_request: Request):
    # Retrieval RAG, doar daca request-ul are conversation_id. Se face AICI
    # (controller async) cu await, NU in generatorul sincron din service.
    context_chunks = []
    if request.conversation_id is not None:
        # Header-ul brut "Bearer <jwt>"; il forwardam neschimbat la Files Service.
        authorization = http_request.headers.get("authorization")
        # Ultimul mesaj user e query-ul pentru cautarea vectoriala.
        last_user = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            None,
        )
        if authorization and last_user:
            context_chunks = await files_client.retrieve_context(
                authorization,
                request.conversation_id,
                last_user,
            )

    return StreamingResponse(
        service.generate_code(
            [m.model_dump() for m in request.messages],
            context_chunks,
        ),
        media_type="text/plain"
    )