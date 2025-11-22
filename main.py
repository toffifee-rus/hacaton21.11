from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional  # Добавлен Optional и List
from datetime import timedelta, datetime, date, UTC  # Добавлен UTC и date
import models, database, security, auth, schemas


# --- DEPENDENCY: Получение сессии БД ---

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- КОНФИГУРАЦИЯ ---

app = FastAPI(title="Metallurgy MES API")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




@app.post("/token", response_model=schemas.Token, tags=["Auth"])
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=schemas.UserOut, tags=["Auth"])
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user



@app.post("/products/", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED, tags=["Reference"])
def create_product(
        product: schemas.ProductCreate,
        db: Session = Depends(get_db),
        user: models.User = Depends(auth.RoleChecker([models.UserRole.DISPATCHER, models.UserRole.TECHNOLOGIST]))
):
    """Создание нового Изделия."""
    new_product = models.Product(**product.model_dump())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@app.put("/products/{product_id}", response_model=schemas.ProductOut, tags=["Reference"])
def update_product(
        product_id: int,
        product_update: schemas.ProductCreate,
        db: Session = Depends(get_db),
        user: models.User = Depends(auth.RoleChecker([models.UserRole.DISPATCHER, models.UserRole.TECHNOLOGIST]))
):
    """Обновление существующего Изделия."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    for key, value in product_update.model_dump(exclude_unset=True).items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product


@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Reference"])
def delete_product(
        product_id: int,
        db: Session = Depends(get_db),
        user: models.User = Depends(auth.RoleChecker([models.UserRole.DISPATCHER, models.UserRole.TECHNOLOGIST]))
):
    """Удаление Изделия (если нет активных заказов)."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Дополнительная проверка: нельзя удалить продукт, если есть активные заказы
    active_orders = db.query(models.ProductionOrder).filter(
        models.ProductionOrder.product_id == product_id,
        models.ProductionOrder.status.in_(
            [models.OrderStatus.NEW, models.OrderStatus.IN_PROGRESS, models.OrderStatus.DELAYED])
    ).count()

    if active_orders > 0:
        raise HTTPException(status_code=400, detail="Cannot delete product: There are active orders linked to it.")

    db.delete(product)
    db.commit()
    return {"message": "Product deleted successfully"}


# --- Управление Материалами (CRUD) ---
@app.get("/materials/", response_model=List[schemas.MaterialOut], tags=["Reference"])
def get_materials(db: Session = Depends(get_db), user=Depends(auth.get_current_user)):
    """Показывает текущие остатки на складе."""
    return db.query(models.Material).all()


@app.post("/materials/", response_model=schemas.MaterialOut, status_code=status.HTTP_201_CREATED, tags=["Reference"])
def create_material(
        material: schemas.MaterialCreate,
        db: Session = Depends(get_db),
        user: models.User = Depends(auth.RoleChecker([models.UserRole.DISPATCHER, models.UserRole.TECHNOLOGIST]))
):
    """Создание нового типа материала (Только Технолог/Диспетчер)."""
    new_material = models.Material(**material.model_dump())
    db.add(new_material)
    db.commit()
    db.refresh(new_material)
    return new_material


@app.put("/materials/{material_id}", response_model=schemas.MaterialOut, tags=["Reference"])
def update_material(
        material_id: int,
        material_update: schemas.MaterialCreate,
        db: Session = Depends(get_db),
        user: models.User = Depends(auth.RoleChecker([models.UserRole.DISPATCHER, models.UserRole.TECHNOLOGIST]))
):
    """Обновление существующего материала (Только Технолог/Диспетчер)."""
    material = db.query(models.Material).filter(models.Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    for key, value in material_update.model_dump(exclude_unset=True).items():
        setattr(material, key, value)

    db.commit()
    db.refresh(material)
    return material


# =======================================================
#               III. УПРАВЛЕНИЕ ЗАКАЗАМИ (Диспетчер)
# =======================================================

@app.post("/orders/", response_model=schemas.OrderOut, tags=["Orders"])
def create_order(
        order_data: schemas.OrderCreate,
        db: Session = Depends(get_db),
        user: models.User = Depends(auth.RoleChecker([models.UserRole.DISPATCHER]))
):
    """Создает заказ и автоматически генерирует задачи по техкарте."""
    new_order = models.ProductionOrder(
        client_name=order_data.client_name,
        product_id=order_data.product_id,
        quantity=order_data.quantity,
        deadline_date=order_data.deadline_date,
        start_date=datetime.now(UTC),
        status=models.OrderStatus.NEW
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # Генерация задач на основе техкарты
    product = db.query(models.Product).filter(models.Product.id == order_data.product_id).first()
    for stage in product.tech_stages:
        task = models.ProductionTask(
            order_id=new_order.id,
            stage_name=stage.name,  # Название этапа соответствует цеху
            status="pending"
        )
        db.add(task)

    db.commit()
    return new_order


@app.get("/orders/", response_model=List[schemas.OrderOut], tags=["Orders"])
def get_orders(db: Session = Depends(get_db), user=Depends(auth.get_current_user)):
    """Возвращает список всех заказов."""
    return db.query(models.ProductionOrder).all()


# =======================================================
#              IV. ПРОИЗВОДСТВО И ЛОГИКА ОТК
# =======================================================

@app.get("/tasks/", response_model=List[schemas.TaskOut], tags=["Production"])
def get_all_tasks(db: Session = Depends(get_db), user=Depends(auth.get_current_user)):
    """Возвращает список всех производственных задач (этапов)."""
    return db.query(models.ProductionTask).all()


@app.put("/tasks/{task_id}/assign", response_model=schemas.TaskOut, tags=["Production"])
def assign_responsible_user(
        task_id: int,
        assignment_data: schemas.TaskAssign,
        db: Session = Depends(get_db),
        # Только Диспетчер может назначать
        user: models.User = Depends(auth.RoleChecker([models.UserRole.DISPATCHER]))
):
    """
    Назначает ответственного пользователя на производственную задачу (этап).
    """
    task = db.query(models.ProductionTask).filter(models.ProductionTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    responsible_user = db.query(models.User).filter(models.User.id == assignment_data.responsible_user_id).first()
    if not responsible_user:
        raise HTTPException(status_code=404, detail="Responsible user not found")

    # Проверка роли: назначать можно только Операторов
    if responsible_user.role != models.UserRole.OPERATOR:
        raise HTTPException(status_code=400, detail="Only users with the role 'OPERATOR' can be assigned to tasks.")

    task.responsible_user_id = assignment_data.responsible_user_id

    # Если задача была "pending", ставим ее в "working" при назначении
    if task.status == "pending":
        task.status = "working"
        task.start_time_actual = datetime.now(UTC)

    db.commit()
    db.refresh(task)

    # Добавляем имя пользователя для вывода
    task_out = schemas.TaskOut.model_validate(task)
    task_out.responsible_username = responsible_user.username

    return task_out


@app.get("/tasks/", response_model=List[schemas.TaskOut], tags=["Production"])
def get_all_tasks(db: Session = Depends(get_db), user=Depends(auth.get_current_user)):
    """Возвращает список всех производственных задач (этапов)."""
    tasks = db.query(models.ProductionTask).all()

    # Добавляем имя ответственного для каждой задачи
    tasks_out = []
    for task in tasks:
        task_out = schemas.TaskOut.model_validate(task)
        if task.responsible_user:
            task_out.responsible_username = task.responsible_user.username
        tasks_out.append(task_out)

    return tasks_out


# --- Task Completion/Rework Logic (TaskCompleteData должна быть в schemas.py) ---
@app.post("/tasks/{task_id}/complete", tags=["Production"])
def complete_task(
        task_id: int,
        complete_data: schemas.TaskCompleteData,
        db: Session = Depends(get_db),
        user: models.User = Depends(auth.RoleChecker([models.UserRole.OPERATOR, models.UserRole.DISPATCHER]))
):
    """
    Завершение задачи с проверкой ОТК и логикой Rework.
    """
    task = db.query(models.ProductionTask).filter(models.ProductionTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    order_qty = task.order.quantity
    defective_qty = complete_data.defective_quantity

    if task.status == "done" or task.status == "rework_needed":
        return {"msg": f"Task status is already {task.status}"}

    if defective_qty > order_qty:
        raise HTTPException(status_code=400, detail="Количество брака не может превышать количество в партии.")

    good_qty = order_qty - defective_qty
    logs = []

    # --- 1. ЛОГИКА СПИСАНИЯ ---
    stage = db.query(models.TechStage).join(models.Product).filter(
        models.TechStage.name == task.stage_name,
        models.Product.id == task.order.product_id
    ).first()

    if stage:
        for req in stage.requirements:
            total_needed = req.quantity_needed * order_qty

            # Проверка остатков
            if req.material.quantity_in_stock < total_needed:
                raise HTTPException(status_code=400,
                                    detail=f"Недостаточно {req.material.name}. Нужно {total_needed}, есть {req.material.quantity_in_stock}")

            # Списание
            req.material.quantity_in_stock -= total_needed
            db.add(req.material)
            logs.append(f"Списано {total_needed} {req.material.unit} {req.material.name}")

    # --- 2. ЛОГИКА ОТК И ПЕРЕДЕЛКИ (REWORK) ---
    if defective_qty > 0:
        task.status = "rework_needed"
        task.order.status = models.OrderStatus.DELAYED  # Ставим задержку

        # Комментарий для ответственного за партию
        rework_comment = (
            f"БРАК: {defective_qty} шт. Ответственный: {user.username}. "
            f"Комментарий ОТК: {complete_data.comment or 'Нет'}. Партия отправлена на повторный цикл."
        )
        logs.append(rework_comment)

    else:
        # Если брака нет, этап завершен
        task.status = "done"
        task.end_time_actual = datetime.now(UTC)  # Фиксируем время завершения

    db.commit()
    return {"status": task.status, "good_quantity": good_qty, "defective_quantity": defective_qty, "logs": logs}


# =======================================================
#               V. АНАЛИТИКА И ОТЧЕТНОСТЬ
# =======================================================

@app.get("/reports/materials-by-stage", tags=["Analytics"], response_model=List[schemas.MaterialReportRow])
def get_materials_report(
        db: Session = Depends(get_db),
        user=Depends(auth.RoleChecker([models.UserRole.DISPATCHER, models.UserRole.TECHNOLOGIST])),
        start_date: date = None,
        end_date: date = None
):
    """
    Генерирует отчет об использованных материалах (для отображения на фронте).
    Фильтрация по дате завершения.
    """

    query = db.query(models.ProductionTask).filter(models.ProductionTask.status == 'done')

    if start_date:
        query = query.filter(models.ProductionTask.end_time_actual >= start_date)
    if end_date:
        # Учитываем весь день end_date
        next_day = end_date + timedelta(days=1)
        query = query.filter(models.ProductionTask.end_time_actual < next_day)

    completed_tasks = query.all()

    report_data = []

    for task in completed_tasks:
        stage = db.query(models.TechStage).join(models.Product).filter(
            models.TechStage.name == task.stage_name,
            models.Product.id == task.order.product_id
        ).first()

        if stage and task.order and task.order.product:
            order_qty = task.order.quantity

            for req in stage.requirements:
                total_spent = req.quantity_needed * order_qty

                report_data.append(schemas.MaterialReportRow(
                    order_id=task.order_id,
                    product_name=task.order.product.name,
                    stage_name=task.stage_name,
                    material_name=req.material.name,
                    unit=req.material.unit,
                    quantity_spent=round(total_spent, 2),
                    completion_date=task.end_time_actual
                ))

    return report_data


@app.get("/reports/materials-by-stage/export", tags=["Analytics"])
def export_materials_report(
        db: Session = Depends(get_db),
        user=Depends(auth.RoleChecker([models.UserRole.DISPATCHER, models.UserRole.TECHNOLOGIST])),
        start_date: date = None,
        end_date: date = None
):
    """
    Экспорт отчета об использованных материалах в CSV-файл (для Excel).
    """

    # Получаем отфильтрованные данные
    report_data_list = get_materials_report(db=db, user=user, start_date=start_date, end_date=end_date)

    header = [
        "ID Заказа", "Изделие", "Этап", "Материал", "Ед. изм.",
        "Кол-во потрачено", "Дата завершения"
    ]

    def generate():
        # Первая строка - заголовки
        yield ";".join(header) + "\n"
        for row in report_data_list:
            date_str = row.completion_date.strftime("%Y-%m-%d %H:%M") if row.completion_date else ""

            # Собираем строку CSV, заменяем точку на запятую для корректной работы в русской версии Excel
            csv_row = [
                str(row.order_id),
                row.product_name,
                row.stage_name,
                row.material_name,
                row.unit,
                str(row.quantity_spent).replace('.', ','),
                date_str
            ]
            yield ";".join(csv_row) + "\n"

    # Отдаем файл как StreamingResponse
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=material_report.csv"}
    )


# --- ГАНТ (Использует логику, внедренную ранее) ---

@app.get("/gantt", response_model=schemas.GanttData, tags=["Analytics"])
def get_gantt_data(db: Session = Depends(get_db)):
    """
    Генерирует данные для визуализации на диаграмме Ганта с прогнозированием длительности этапов.
    """
    orders = db.query(models.ProductionOrder).all()
    gantt_tasks = []
    task_id_counter = 1000

    for order in orders:
        order_task_id = order.id

        current_time = order.start_date
        total_progress_minutes = 0
        completed_minutes = 0

        tech_stages = db.query(models.TechStage).filter(models.TechStage.product_id == order.product_id).order_by(
            models.TechStage.order_in_chain).all()
        actual_tasks = db.query(models.ProductionTask).filter(models.ProductionTask.order_id == order.id).all()
        actual_tasks_map = {task.stage_name: task for task in actual_tasks}

        for stage in tech_stages:
            task_id_counter += 1

            duration_minutes = stage.norm_time_minutes * order.quantity
            duration_days = duration_minutes / (8 * 60)  # Переводим в дни (8-часовая смена)

            predicted_end_time = current_time + timedelta(minutes=duration_minutes)

            task_status = actual_tasks_map.get(stage.name, None)

            progress = 0.0
            if task_status and task_status.status == 'done':
                progress = 1.0
                completed_minutes += duration_minutes
            elif task_status and task_status.status == 'working':
                progress = 0.5

            total_progress_minutes += duration_minutes

            gantt_tasks.append(schemas.GanttTask(
                id=task_id_counter,
                text=f"{stage.name} x{order.quantity}",
                start_date=current_time.strftime("%Y-%m-%d %H:%M"),
                duration=max(1, round(duration_days * 100)) / 100,
                progress=progress,
                parent=order_task_id
            ))

            current_time = predicted_end_time

        total_duration_days = total_progress_minutes / (8 * 60)
        order_progress = completed_minutes / total_progress_minutes if total_progress_minutes > 0 else 0

        gantt_tasks.insert(0, schemas.GanttTask(
            id=order_task_id,
            text=f"Заказ #{order.id} ({order.product.name})",
            start_date=order.start_date.strftime("%Y-%m-%d %H:%M"),
            duration=max(1, round(total_duration_days * 100)) / 100,
            progress=order_progress,
            parent=0
        ))

    return {"data": gantt_tasks}


@app.get("/analytics/inventory-check", response_model=List[schemas.AvailabilityCheckItem], tags=["Analytics"])
def check_inventory_availability(
        db: Session = Depends(get_db),
        user=Depends(auth.RoleChecker([models.UserRole.DISPATCHER, models.UserRole.TECHNOLOGIST]))
):
    """
    Проверяет, достаточно ли текущих запасов для всех НОВЫХ и НЕЗАВЕРШЕННЫХ заказов.
    """

    # 1. Получаем все активные заказы (NEW, IN_PROGRESS, DELAYED)
    active_orders = db.query(models.ProductionOrder).filter(
        models.ProductionOrder.status.in_(
            [models.OrderStatus.NEW, models.OrderStatus.IN_PROGRESS, models.OrderStatus.DELAYED])
    ).all()

    material_requirements = {}  # {material_id: total_needed}

    for order in active_orders:
        product_stages = db.query(models.TechStage).filter(models.TechStage.product_id == order.product_id).all()

        # Определяем, какие этапы еще предстоят
        completed_stage_names = {task.stage_name for task in order.tasks if task.status == 'done'}

        for stage in product_stages:
            # Считаем требования только для этапов, которые ЕЩЕ НЕ ВЫПОЛНЕНЫ
            if stage.name not in completed_stage_names:
                for req in stage.requirements:
                    total_needed = req.quantity_needed * order.quantity
                    material_id = req.material_id

                    material_requirements[material_id] = material_requirements.get(material_id, 0.0) + total_needed

    # 2. Собираем итоговый отчет
    report = []
    all_materials = db.query(models.Material).all()

    for material in all_materials:
        required = material_requirements.get(material.id, 0.0)
        stock = material.quantity_in_stock

        is_sufficient = stock >= required
        deficit_amount = max(0.0, required - stock)

        report.append(schemas.AvailabilityCheckItem(
            material_name=material.name,
            unit=material.unit,
            stock_available=round(stock, 2),
            required_for_pending_orders=round(required, 2),
            is_sufficient=is_sufficient,
            deficit_amount=round(deficit_amount, 2)
        ))

    return report