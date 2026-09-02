from pydantic import BaseModel, Field

class ThreadSummaryOut(BaseModel):
    core_issue: str = Field(..., description="The main issue the customer is experiencing")
    actions_taken: list[str] = Field(..., description="A list of actions taken so far by the agent or customer")
    pending_action: str = Field(..., description="What needs to happen next")
    interaction_id: int | None = Field(default=None, description="Observability telemetry interaction ID")

class SuggestedReplyOut(BaseModel):
    reply: str = Field(..., description="The AI-generated suggested reply")
    interaction_id: int | None = Field(default=None, description="Observability telemetry interaction ID")
