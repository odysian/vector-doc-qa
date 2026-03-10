from app.api.dependencies import get_current_user
from app.database import get_db
from app.constants import QUERY_CONVERSATION_HISTORY_TURNS, QUERY_SIMILARITY_THRESHOLD
from app.models.user import User
from app.schemas.message import MessageListResponse
from app.schemas.query import QueryRequest
from app.schemas.workspace import (
    WorkspaceAddDocuments,
    WorkspaceCreate,
    WorkspaceDetailResponse,
    WorkspaceListResponse,
    WorkspaceQueryResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.workspace_service import (
    add_workspace_documents_command,
    create_workspace_command,
    delete_workspace_command,
    get_workspace_command,
    list_workspace_messages_command,
    list_workspaces_command,
    query_workspace_command,
    remove_workspace_document_command,
    update_workspace_command,
)
from app.utils.rate_limit import get_user_or_ip_key, limiter
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
# Keep aliases for existing imports/tests that read router constants.
CONVERSATION_HISTORY_WINDOW_TURNS = QUERY_CONVERSATION_HISTORY_TURNS
SIMILARITY_THRESHOLD = QUERY_SIMILARITY_THRESHOLD


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour", key_func=get_user_or_ip_key)
async def create_workspace(
    request: Request,
    body: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_workspace_command(
        db=db,
        current_user=current_user,
        body=body,
    )


@router.get("/", response_model=WorkspaceListResponse)
@limiter.limit("20/hour", key_func=get_user_or_ip_key)
async def list_workspaces(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_workspaces_command(
        db=db,
        current_user=current_user,
    )


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
@limiter.limit("20/hour", key_func=get_user_or_ip_key)
async def get_workspace(
    request: Request,
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_workspace_command(
        db=db,
        workspace_id=workspace_id,
        current_user=current_user,
    )


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
@limiter.limit("20/hour", key_func=get_user_or_ip_key)
async def update_workspace(
    request: Request,
    workspace_id: int,
    body: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await update_workspace_command(
        db=db,
        workspace_id=workspace_id,
        current_user=current_user,
        body=body,
    )


@router.delete("/{workspace_id}")
@limiter.limit("20/hour", key_func=get_user_or_ip_key)
async def delete_workspace(
    request: Request,
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await delete_workspace_command(
        db=db,
        workspace_id=workspace_id,
        current_user=current_user,
    )


@router.post("/{workspace_id}/documents", response_model=WorkspaceDetailResponse)
@limiter.limit("20/hour", key_func=get_user_or_ip_key)
async def add_workspace_documents(
    request: Request,
    workspace_id: int,
    body: WorkspaceAddDocuments,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await add_workspace_documents_command(
        db=db,
        workspace_id=workspace_id,
        current_user=current_user,
        body=body,
    )


@router.delete(
    "/{workspace_id}/documents/{document_id}",
    response_model=WorkspaceDetailResponse,
)
@limiter.limit("20/hour", key_func=get_user_or_ip_key)
async def remove_workspace_document(
    request: Request,
    workspace_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await remove_workspace_document_command(
        db=db,
        workspace_id=workspace_id,
        document_id=document_id,
        current_user=current_user,
    )


@router.post("/{workspace_id}/query", response_model=WorkspaceQueryResponse)
@limiter.shared_limit("10/hour", scope="query", key_func=get_user_or_ip_key)
async def query_workspace(
    request: Request,
    workspace_id: int,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await query_workspace_command(
        db=db,
        workspace_id=workspace_id,
        current_user=current_user,
        body=body,
        history_window_turns=CONVERSATION_HISTORY_WINDOW_TURNS,
        similarity_threshold=SIMILARITY_THRESHOLD,
    )


@router.get("/{workspace_id}/messages", response_model=MessageListResponse)
@limiter.limit("30/hour", key_func=get_user_or_ip_key)
async def list_workspace_messages(
    request: Request,
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_workspace_messages_command(
        db=db,
        workspace_id=workspace_id,
        current_user=current_user,
    )
