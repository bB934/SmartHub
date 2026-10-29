"""接口出入参模型。集中在一个文件，避免每个 router 各自定义一份。"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    topk: int | None = Field(None, ge=1, le=50)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    topk: int = Field(10, ge=1, le=50)


class DocOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    source_type: str
    space_id: int
    visibility: int
    chunk_count: int
    index_status: int
    index_version: int
    created_by: int | None


class TaskOut(BaseModel):
    model_config = {"from_attributes": True}

    doc_id: int
    stage: str
    retry_count: int
    error_msg: str | None
