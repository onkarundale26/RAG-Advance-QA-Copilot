from pydantic import BaseModel
from typing import Optional, List

class Chunk(BaseModel):
    text: str
    source_type: str
    source_file: str
    page_number: Optional[int] = None
    tc_id: Optional[str] = None
    jira_id: Optional[str] = None
    class_name: Optional[str] = None
    method_name: Optional[str] = None
    artifact_type: Optional[str] = None

    def to_payload(self):
        return self.model_dump(exclude_none=True)
