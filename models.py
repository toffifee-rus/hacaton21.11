from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import enum
from datetime import datetime

Base = declarative_base()


# --- ENUMS (Статусы) ---
class OrderStatus(enum.Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"


# --- СПРАВОЧНИКИ (Task 3.1) --- [cite: 11]

class UserRole(enum.Enum):
    DISPATCHER = "dispatcher"  # Полный доступ, создание заказов
    TECHNOLOGIST = "technologist"  # Редактирование техкарт и справочников
    OPERATOR = "operator"  # Только отметка о выполнении задач


# 2. Обновляем модель пользователя
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    # --- НОВЫЕ ПОЛЯ ---
    last_name = Column(String, default="")
    first_name = Column(String, default="")
    patronymic = Column(String, nullable=True)  # Отчество может отсутствовать
    # --- КОНЕЦ НОВЫХ ПОЛЕЙ ---

    role = Column(Enum(UserRole), default=UserRole.OPERATOR)
    is_active = Column(Boolean, default=True)


class Product(Base):  # Изделия
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    code = Column(String, unique=True)
    description = Column(String)
    # Связь с техкартой (один ко многим этапам)
    tech_stages = relationship("TechStage", back_populates="product")


class Material(Base):  # Материалы
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    unit = Column(String)  # шт, кг, м
    quantity_in_stock = Column(Float, default=0.0)  # Остаток на складе


# --- ТЕХНОЛОГИЯ ---

class TechStage(Base):  # Этапы производства для изделия (Шаблон)
    __tablename__ = "tech_stages"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    name = Column(String)  # Например: "Распил", "Покраска"
    order_in_chain = Column(Integer)  # Номер по порядку: 1, 2, 3
    norm_time_minutes = Column(Integer)  # Сколько времени занимает этап

    product = relationship("Product", back_populates="tech_stages")
    requirements = relationship("StageMaterialRequirement", back_populates="stage")


class StageMaterialRequirement(Base):  # Сколько материалов нужно на этап
    __tablename__ = "stage_material_requirements"
    id = Column(Integer, primary_key=True, index=True)
    tech_stage_id = Column(Integer, ForeignKey("tech_stages.id"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    quantity_needed = Column(Float)  # Например, 4 (штуки) или 0.5 (кг)

    stage = relationship("TechStage", back_populates="requirements")
    material = relationship("Material")


# --- ПРОИЗВОДСТВО (Task 3.2) --- [cite: 14]

class ProductionTask(Base):
    __tablename__ = "production_tasks"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("production_orders.id"))
    stage_name = Column(String)
    status = Column(String, default="pending")

    # --- НОВОЕ ПОЛЕ: ОТВЕТСТВЕННОЕ ЛИЦО ---
    responsible_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    start_time_actual = Column(DateTime(timezone=True), nullable=True)
    end_time_actual = Column(DateTime(timezone=True), nullable=True)

    # Связи
    order = relationship("ProductionOrder", back_populates="tasks")

    # --- НОВАЯ СВЯЗЬ: ОТВЕТСТВЕННЫЙ ПОЛЬЗОВАТЕЛЬ ---
    responsible_user = relationship("User")

class ProductionOrder(Base):  # Заказ
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)  # Сколько штук производим
    start_date = Column(DateTime, default=datetime.utcnow)
    deadline_date = Column(DateTime)
    status = Column(Enum(OrderStatus), default=OrderStatus.NEW)

    product = relationship("Product")
    tasks = relationship("ProductionTask", back_populates="order")


class ProductionTask(Base):  # Конкретная задача в рамках заказа (на основе TechStage)
    __tablename__ = "production_tasks"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    stage_name = Column(String)  # Копируем имя из TechStage
    status = Column(String, default="pending")  # pending, working, done

    # Для Ганта
    start_time_actual = Column(DateTime, nullable=True)
    end_time_actual = Column(DateTime, nullable=True)

    order = relationship("ProductionOrder", back_populates="tasks")