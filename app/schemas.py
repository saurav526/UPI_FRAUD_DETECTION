from pydantic import BaseModel
from typing import Optional, List


class TransactionOut(BaseModel):
    transaction_id: str
    ts: str
    user_id: str
    amount: float
    merchant: str
    decision: str
    risk_score: float


class CheckRequest(BaseModel):
    transaction_id: str


class CheckResponse(BaseModel):
    found: bool
    transaction_id: Optional[str] = None
    decision: Optional[str] = None
    risk_score: Optional[float] = None
    amount: Optional[float] = None
    user_id: Optional[str] = None
    merchant: Optional[str] = None
    ts: Optional[str] = None
    reasons: Optional[List[str]] = None
    ai_explanation: Optional[str] = None
    message: Optional[str] = None


class OverrideRequest(BaseModel):
    transaction_id: str


class NewTransactionRequest(BaseModel):
    user_id: str
    amount: float
    merchant: str
    is_new_device: Optional[bool] = False
    is_new_location: Optional[bool] = False