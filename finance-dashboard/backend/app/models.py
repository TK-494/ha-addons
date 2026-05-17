from sqlalchemy import Column, Integer, String, Float, Date, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String, default="#6366f1")
    icon = Column(String, default="💳")
    keywords = Column(Text, default="")  # comma-separated

    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", back_populates="category")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    description = Column(String, default="")
    counter_name = Column(String, default="")
    counter_iban = Column(String, default="")
    own_iban = Column(String, default="")
    note = Column(String, default="")
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_income = Column(Boolean, default=False)
    is_transfer = Column(Boolean, default=False, nullable=False, server_default="0")
    import_hash = Column(String, unique=True, index=True)

    category = relationship("Category", back_populates="transactions")


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)

    category = relationship("Category", back_populates="budgets")


class CAOScale(Base):
    __tablename__ = "cao_scales"

    id = Column(Integer, primary_key=True, index=True)
    scale = Column(Integer, nullable=False)       # FWG scale number e.g. 10, 15, 20 ...
    step = Column(Integer, nullable=False)         # Periodic step number
    monthly_gross = Column(Float, nullable=False)  # Monthly gross salary in EUR


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)
