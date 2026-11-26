import os
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    classify_method: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    invoice_no: Mapped[str] = mapped_column(String(20))
    invoice_date: Mapped[date] = mapped_column(Date)
    seller: Mapped[str] = mapped_column(String(100))
    item: Mapped[str] = mapped_column(String(200))
    qty: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class PowerBill(Base):
    __tablename__ = "power_bills"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    meter_no: Mapped[str] = mapped_column(String(30))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    kwh: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20))


def init_db():
    Base.metadata.create_all(engine)
