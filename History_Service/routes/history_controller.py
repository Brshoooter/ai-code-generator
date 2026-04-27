from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from database.database import get_db
from models.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationSummary,
    MessageCreate,
    MessageResponse,
)
from services.history_service import (
    add_message,
    create_conversation,
    delete_conversation,
    get_conversation,
    get_messages,
    list_conversations,
)
from services.jwt_auth import get_current_user_id

router = APIRouter()


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation_endpoint(
    data: ConversationCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return create_conversation(user_id, data.title, db)


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations_endpoint(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return list_conversations(user_id, db)


@router.get("/conversations/{conv_id}", response_model=ConversationResponse)
def get_conversation_endpoint(
    conv_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return get_conversation(conv_id, user_id, db)


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageResponse])
def get_messages_endpoint(
    conv_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return get_messages(conv_id, user_id, db)


@router.post("/conversations/{conv_id}/messages", response_model=MessageResponse, status_code=201)
def add_message_endpoint(
    conv_id: str,
    data: MessageCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return add_message(conv_id, user_id, data.role, data.content, db)


@router.delete("/conversations/{conv_id}", status_code=204)
def delete_conversation_endpoint(
    conv_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    delete_conversation(conv_id, user_id, db)
    return Response(status_code=204)
