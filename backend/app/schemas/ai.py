from pydantic import BaseModel, Field

class ThreadSummaryOut(BaseModel):
    core_issue: str = Field(..., description="The main issue the customer is experiencing")
    actions_taken: list[str] = Field(..., description="A list of actions taken so far by the agent or customer")
    pending_action: str = Field(..., description="What needs to happen next")
    interaction_id: int | None = Field(default=None, description="Observability telemetry interaction ID")

class SuggestedReplyOut(BaseModel):
    reply: str = Field(..., description="The AI-generated suggested reply")
    interaction_id: int | None = Field(default=None, description="Observability telemetry interaction ID")


class ClassifyRequest(BaseModel):
    subject: str = Field(..., description="Subject of the support ticket")
    description: str = Field(..., description="Description of the support ticket")


class ClassifyOut(BaseModel):
    category: str = Field(default="general")
    priority: str = Field(default="medium")
    sentiment: str = Field(default="neutral")
    urgency: int = Field(default=3)
    tags: list[str] = Field(default_factory=list)
