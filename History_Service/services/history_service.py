import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.conversation_model import Conversation, Message


def _get_owned_conversation(conv_id: str, user_id: str, db: Session) -> Conversation:
    """
    Functie interna refolosita de toate operatiile care primesc un conv_id.
    Returneaza conversatia daca exista si apartine user-ului, altfel 404.

    De ce 404 si nu 403? Daca am raspunde 403 (Forbidden), un atacator ar afla
    ca id-ul exista dar e al altcuiva. 404 ascunde existenta — defense against ID enumeration.
    """
    try:
        conv_uuid = uuid.UUID(conv_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")

    conv = db.query(Conversation).filter(Conversation.id == conv_uuid).first()
    if conv is None or str(conv.user_id) != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")

    return conv


def create_conversation(user_id: str, title: str | None, db: Session) -> Conversation:
    conv = Conversation(
        user_id=uuid.UUID(user_id),
        title=title if title else "New Conversation",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_conversations(user_id: str, db: Session) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == uuid.UUID(user_id))
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def get_conversation(conv_id: str, user_id: str, db: Session) -> Conversation:
    return _get_owned_conversation(conv_id, user_id, db)


def get_messages(conv_id: str, user_id: str, db: Session) -> list[Message]:
    # verifica ownership inainte sa returneze mesajele
    conv = _get_owned_conversation(conv_id, user_id, db)
    return (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .all()
    )


def add_message(conv_id: str, user_id: str, role: str, content: str, db: Session) -> Message:
    conv = _get_owned_conversation(conv_id, user_id, db)

    # daca e primul mesaj de la user, titlul conversatiei devine primele 50 de caractere
    if role == "user" and conv.title == "New Conversation":
        existing = db.query(Message).filter(Message.conversation_id == conv.id).first()
        if existing is None:
            conv.title = content[:50]

    msg = Message(
        conversation_id=conv.id,
        role=role,
        content=content,
    )
    db.add(msg)

    # actualizeaza updated_at la fiecare mesaj nou
    conv.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(msg)
    return msg


def delete_conversation(conv_id: str, user_id: str, db: Session) -> None:
    conv = _get_owned_conversation(conv_id, user_id, db)
    db.delete(conv)
    db.commit()
