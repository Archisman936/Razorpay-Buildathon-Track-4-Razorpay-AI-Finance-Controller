from pydantic import BaseModel


class TransactionLookupRequest(BaseModel):
    source_type: str
    source_id: str
