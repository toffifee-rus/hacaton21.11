from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
import models
import security
import database
import auth, schemas
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Metallurgy MES API")

# --- КОНФИГУРАЦИЯ CORS (Добавьте это) ---
origins = [
    "http://localhost:3000", # Стандартный порт для React (Лева)
    "http://127.0.0.1:3000",
    # Здесь потом будет адрес продакшена
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Разрешаем все методы (GET, POST, etc)
    allow_headers=["*"], # Разрешаем все заголовки
)
# --- КОНЕЦ КОНФИГУРАЦИИ CORS ---

@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=schemas.UserOut)
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# --- СПРАВОЧНИКИ (Доступно всем авторизованным) ---

@app.get("/products/", tags=["Reference"])
def get_products(db: Session = Depends(database.get_db), user=Depends(auth.get_current_user)):
    return db.query(models.Product).all()


@app.get("/materials/", tags=["Reference"])
def get_materials(db: Session = Depends(database.get_db), user=Depends(auth.get_current_user)):
    return db.query(models.Material).all()


# --- ЗАКАЗЫ (Только Диспетчер) ---

@app.post("/orders/", response_model=schemas.OrderOut, tags=["Orders"])
def create_order(
        order_data: schemas.OrderCreate,
        db: Session = Depends(database.get_db),
        user: models.User = Depends(auth.RoleChecker([models.UserRole.DISPATCHER]))
):
    # 1. Создаем заказ
    new_order = models.ProductionOrder(
        client_name=order_data.client_name,
        product_id=order_data.product_id,
        quantity=order_data.quantity,
        deadline_date=order_data.deadline_date,
        status=models.OrderStatus.NEW
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # 2. Генерируем задачи (Production Tasks) на основе техкарты
    product = db.query(models.Product).filter(models.Product.id == order_data.product_id).first()
    for stage in product.tech_stages:
        task = models.ProductionTask(
            order_id=new_order.id,
            stage_name=stage.name,
            status="pending"
        )
        db.add(task)

    db.commit()
    return new_order


@app.get("/orders/", response_model=List[schemas.OrderOut], tags=["Orders"])
def get_orders(db: Session = Depends(database.get_db), user=Depends(auth.get_current_user)):
    return db.query(models.ProductionOrder).all()


# --- ПРОИЗВОДСТВО (Оператор и Диспетчер) ---

@app.get("/tasks/", response_model=List[schemas.TaskOut], tags=["Production"])
def get_all_tasks(db: Session = Depends(database.get_db), user=Depends(auth.get_current_user)):
    return db.query(models.ProductionTask).all()


@app.post("/tasks/{task_id}/complete", tags=["Production"])
def complete_task(
        task_id: int,
        db: Session = Depends(database.get_db),
        user: models.User = Depends(auth.RoleChecker([models.UserRole.OPERATOR, models.UserRole.DISPATCHER]))
):
    """
    Завершение задачи и АВТОМАТИЧЕСКОЕ списание материалов
    """
    task = db.query(models.ProductionTask).filter(models.ProductionTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == "done":
        return {"msg": "Task already completed"}

    # Логика списания
    # Ищем этап техкарты по имени (упрощение для хакатона)
    stage = db.query(models.TechStage).join(models.Product).filter(
        models.TechStage.name == task.stage_name,
        models.Product.id == task.order.product_id
    ).first()

    logs = []
    if stage:
        order_qty = task.order.quantity
        for req in stage.requirements:
            total_needed = req.quantity_needed * order_qty
            if req.material.quantity_in_stock < total_needed:
                raise HTTPException(status_code=400,
                                    detail=f"Not enough {req.material.name}. Need {total_needed}, have {req.material.quantity_in_stock}")

            req.material.quantity_in_stock -= total_needed
            logs.append(f"Deducted {total_needed} {req.material.unit} of {req.material.name}")

    task.status = "done"
    db.commit()
    return {"status": "success", "deduction_logs": logs}


# --- АНАЛИТИКА (Для Диаграммы Ганта) ---

@app.get("/gantt", response_model=schemas.GanttData, tags=["Analytics"])
def get_gantt_data(db: Session = Depends(database.get_db)):
    orders = db.query(models.ProductionOrder).all()
    data = []

    for order in orders:
        # Задача-родитель (Сам Заказ)
        data.append(schemas.GanttTask(
            id=order.id,
            text=f"Order #{order.id} ({order.product.name})",
            start_date=order.start_date.strftime("%Y-%m-%d %H:%M"),
            duration=5,  # Условно
            progress=0.5 if order.status == models.OrderStatus.IN_PROGRESS else 0,
            parent=0
        ))
        # Подзадачи (Этапы)
        # Тут можно добавить реальные задачи, если нужно детализировать

    return {"data": data}