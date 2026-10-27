from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    tenant_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,39}$")
    question: str = Field(min_length=3, max_length=2000)


class Source(BaseModel):
    document_id: str
    title: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
