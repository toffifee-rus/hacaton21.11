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



class MaterialBase(BaseModel):
    name: str
    unit: str
    quantity_in_stock: float


class MaterialCreate(MaterialBase):
    pass


class MaterialOut(MaterialBase):
    id: int

    class Config:
        from_attributes = True

class TaskCompleteData(BaseModel):
    defective_quantity: int = 0
    comment: Optional[str] = None

class ProductBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductOut(ProductBase):
    id: int
    class Config:
        from_attributes = True


class TaskAssign(BaseModel):
    """Схема для назначения ответственного пользователя на задачу."""
    responsible_user_id: int


class TaskOut(BaseModel):
    id: int
    order_id: int
    stage_name: str
    status: str

    # --- НОВЫЕ ПОЛЯ ---
    responsible_user_id: Optional[int] = None

    # Полезное поле для фронтенда: полное ФИО или логин
    responsible_username: Optional[str] = None
    # --- КОНЕЦ НОВЫХ ПОЛЕЙ ---

    start_time_actual: Optional[datetime] = None
    end_time_actual: Optional[datetime] = None

    class Config:
        from_attributes = True

class AvailabilityCheckItem(BaseModel):
    material_name: str
    unit: str
    stock_available: float
    required_for_pending_orders: float
    is_sufficient: bool
    deficit_amount: float


class MaterialReportRow(BaseModel):
    order_id: int
    product_name: str
    stage_name: str
    material_name: str
    unit: str
    quantity_spent: float
    completion_date: Optional[datetime]

    class Config:
        from_attributes = True