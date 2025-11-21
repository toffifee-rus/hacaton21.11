from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from models import UserRole

# --- Auth ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# --- Users ---
class UserOut(BaseModel):
    id: int
    username: str
    role: UserRole
    class Config:
        orm_mode = True

# --- Orders ---
class OrderCreate(BaseModel):
    client_name: str
    product_id: int
    quantity: int
    deadline_date: datetime

class OrderOut(BaseModel):
    id: int
    client_name: str
    product_id: int
    quantity: int
    status: str
    start_date: datetime
    class Config:
        orm_mode = True

# --- Tasks ---
class TaskOut(BaseModel):
    id: int
    stage_name: str
    status: str
    order_id: int
    class Config:
        orm_mode = True

# --- Gantt Data ---
class GanttTask(BaseModel):
    id: int
    text: str
    start_date: str
    duration: int
    progress: float
    parent: int = 0

class GanttData(BaseModel):
    data: List[GanttTask]