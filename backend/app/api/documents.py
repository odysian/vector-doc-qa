import json
from collections.abc import AsyncGenerator

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.constants import QUERY_CONVERSATION_HISTORY_TURNS, QUERY_SIMILARITY_THRESHOLD
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
    UploadResponse,
)
from app.schemas.message import MessageListResponse
from app.schemas.query import QueryRequest, QueryResponse
from app.schemas.search import SearchRequest, SearchResponse
from app.services.document_commands_service import (
    delete_document_command,
    get_document_command,
    get_document_file_command,
    get_document_status_command,
    list_documents_command,
    process_document_command,
    upload_document_command,
)
from app.services.document_query_service import (
    get_document_messages_command,
    query_document_command,
    query_document_stream_events_command,
    search_document_command,
)
from app.utils.rate_limit import get_user_or_ip_key, limiter
from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import EventSourceResponse
from fastapi.sse import ServerSentEvent, format_sse_event
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
# Keep aliases for existing imports/tests that read router constants.
CONVERSATION_HISTORY_WINDOW_TURNS = QUERY_CONVERSATION_HISTORY_TURNS
SIMILARITY_THRESHOLD = QUERY_SIMILARITY_THRESHOLD


def _encode_sse_event(event: ServerSentEvent) -> bytes:
    """Encode a FastAPI ServerSentEvent instance into wire-format bytes."""
    if event.raw_data is not None:
        data_str: str | None = event.raw_data
    elif event.data is not None:
        data_str = json.dumps(event.data)
    else:
        data_str = None

    return format_sse_event(
        data_str=data_str,
        event=event.event,
        id=event.id,
        retry=event.retry,
        comment=event.comment,
    )


@router.post("/upload", response_model=UploadResponse, status_code=201)
@limiter.limit("5/hour", key_func=get_user_or_ip_key)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await upload_document_command(
        db=db,
        current_user=current_user,
        file=file,
    )


@router.get("/", response_model=DocumentListResponse)
@limiter.limit("20/hour", key_func=get_user_or_ip_key)
async def get_documents(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_documents_command(
        db=db,
        user_id=current_user.id,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
@limiter.limit("30/hour", key_func=get_user_or_ip_key)
async def get_document(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_document_command(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )


@router.get("/{document_id}/file")
@limiter.limit("30/hour", key_func=get_user_or_ip_key)
async def get_document_file(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_document_file_command(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
@limiter.limit("120/minute", key_func=get_user_or_ip_key)
async def get_document_status(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_document_status_command(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )


@router.delete("/{document_id}")
@limiter.limit("10/hour", key_func=get_user_or_ip_key)
async def delete_document(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await delete_document_command(
        db=db,
        document_id=document_id,
        current_user=current_user,
    )


# PROCESS DOCUMENT
@router.post("/{document_id}/process", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/hour", key_func=get_user_or_ip_key)
async def process_document(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await process_document_command(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )


@router.post("/{document_id}/search", response_model=SearchResponse)
@limiter.limit("15/hour", key_func=get_user_or_ip_key)
async def search_document(
    request: Request,
    search: SearchRequest,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await search_document_command(
        db=db,
        document_id=document_id,
        current_user=current_user,
        search=search,
    )


@router.post("/{document_id}/query", response_model=QueryResponse)
@limiter.shared_limit("10/hour", scope="query", key_func=get_user_or_ip_key)
async def query_document(
    request: Request,
    document_id: int,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await query_document_command(
        db=db,
        document_id=document_id,
        current_user=current_user,
        body=body,
        history_window_turns=CONVERSATION_HISTORY_WINDOW_TURNS,
        similarity_threshold=SIMILARITY_THRESHOLD,
    )


@router.post("/{document_id}/query/stream")
@limiter.shared_limit("10/hour", scope="query", key_func=get_user_or_ip_key)
async def query_document_stream(
    request: Request,
    document_id: int,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stream_events = await query_document_stream_events_command(
        db=db,
        document_id=document_id,
        current_user=current_user,
        body=body,
        history_window_turns=CONVERSATION_HISTORY_WINDOW_TURNS,
        similarity_threshold=SIMILARITY_THRESHOLD,
    )

    async def _encoded_stream_events() -> AsyncGenerator[bytes, None]:
        async for event in stream_events:
            yield _encode_sse_event(event)

    return EventSourceResponse(_encoded_stream_events())


@router.get("/{document_id}/messages", response_model=MessageListResponse)
@limiter.limit("30/hour", key_func=get_user_or_ip_key)
async def get_document_messages(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_document_messages_command(
        db=db,
        document_id=document_id,
        current_user=current_user,
    )
