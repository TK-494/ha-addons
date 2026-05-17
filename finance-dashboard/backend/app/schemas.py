from pydantic import BaseModel
from datetime import date
from typing import Optional


class CategoryBase(BaseModel):
    name: str
    color: str = "#6366f1"
    icon: str = "💳"
    keywords: str = ""


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    id: int
    model_config = {"from_attributes": True}


class TransactionBase(BaseModel):
    date: date
    amount: float
    description: str = ""
    counter_name: str = ""
    counter_iban: str = ""
    own_iban: str = ""
    note: str = ""
    category_id: Optional[int] = None
    is_income: bool = False
    is_transfer: bool = False


class TransactionCreate(TransactionBase):
    import_hash: str


class TransactionOut(TransactionBase):
    id: int
    category: Optional[CategoryOut] = None
    model_config = {"from_attributes": True}


class BudgetBase(BaseModel):
    category_id: int
    month: int
    year: int
    amount: float


class BudgetCreate(BudgetBase):
    pass


class BudgetOut(BudgetBase):
    id: int
    category: Optional[CategoryOut] = None
    model_config = {"from_attributes": True}


class CAOScaleBase(BaseModel):
    scale: int
    step: int
    monthly_gross: float


class CAOScaleCreate(CAOScaleBase):
    pass


class CAOScaleOut(CAOScaleBase):
    id: int
    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_income: float
    total_expenses: float
    net: float
    transaction_count: int


class MonthlyTrend(BaseModel):
    month: str
    income: float
    expenses: float


class CategorySpend(BaseModel):
    category: str
    amount: float
    color: str
    icon: str
