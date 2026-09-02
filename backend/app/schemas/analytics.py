"""
ResolveAI — Analytics & Operational KPI Schemas
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DailyTrendPoint(BaseModel):
    date: str = Field(..., description="ISO formatted date YYYY-MM-DD")
    opened: int = Field(default=0, description="Tickets opened on this date")
    resolved: int = Field(default=0, description="Tickets resolved on this date")
    breached: int = Field(default=0, description="Tickets breached on this date")


class AnalyticsOverview(BaseModel):
    total_tickets: int = Field(default=0, description="Total tickets in scope")
    open_tickets: int = Field(default=0, description="Tickets currently in OPEN or ASSIGNED status")
    in_progress_tickets: int = Field(default=0, description="Tickets in IN_PROGRESS or WAITING status")
    resolved_today: int = Field(default=0, description="Tickets resolved today (UTC)")
    sla_breached_count: int = Field(default=0, description="Total tickets with SLA breach")
    sla_compliance_rate: float = Field(default=100.0, description="SLA compliance percentage (0.0 - 100.0)")
    avg_mtta_minutes: float = Field(default=0.0, description="Mean Time to Acknowledge / First Response (minutes)")
    avg_mttr_hours: float = Field(default=0.0, description="Mean Time to Resolution (hours)")
    
    volume_by_category: dict[str, int] = Field(default_factory=dict, description="Ticket counts by category")
    volume_by_priority: dict[str, int] = Field(default_factory=dict, description="Ticket counts by priority")
    daily_trends: list[DailyTrendPoint] = Field(default_factory=list, description="Historical volume and resolution trends")
