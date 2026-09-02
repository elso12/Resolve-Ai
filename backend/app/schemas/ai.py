from pydantic import BaseModel, Field

class ThreadSummaryOut(BaseModel):
    core_issue: str = Field(..., description="The main issue the customer is experiencing")
    actions_taken: list[str] = Field(..., description="A list of actions taken so far by the agent or customer")
    pending_action: str = Field(..., description="What needs to happen next")

class SuggestedReplyOut(BaseModel):
    reply: str = Field(..., description="The AI-generated suggested reply")
