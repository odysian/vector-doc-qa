from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.document import DocumentResponse
from app.schemas.query import PipelineMeta


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class WorkspaceUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class WorkspaceAddDocuments(BaseModel):
    document_ids: list[int] = Field(..., min_length=1)


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    user_id: int
    created_at: datetime
    updated_at: datetime
    document_count: int


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceResponse]
    total: int


class WorkspaceDetailResponse(WorkspaceResponse):
    documents: list[DocumentResponse]


class WorkspaceSearchResult(BaseModel):
    chunk_id: int
    content: str
    similarity: float
    chunk_index: int
    page_start: int | None = None
    page_end: int | None = None
    document_id: int
    document_filename: str


class WorkspaceQueryResponse(BaseModel):
    query: str
    answer: str
    sources: list[WorkspaceSearchResult]
    pipeline_meta: PipelineMeta | None = None
