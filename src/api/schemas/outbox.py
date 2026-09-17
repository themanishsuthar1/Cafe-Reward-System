from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class OutboxEventResponse(BaseModel):
    id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: Dict[str, Any]
    status: str
    created_at: str

class ProcessOutboxResponse(BaseModel):
    status: str
    processed_count: int
    processed_events: Optional[List[Dict[str, Any]]] = None
