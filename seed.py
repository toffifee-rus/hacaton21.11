from database import SessionLocal, engine
import models
from security import get_password_hash
from datetime import datetime, timedelta, timezone, UTC
from sqlalchemy.orm import Session
from typing import List

# 1. Чистим базу данных
models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)

db = SessionLocal()


# --- Хелпер-функции для упрощения создания данных ---

def create_order_and_tasks(
        db: Session,
        product: models.Product,
        quantity: int,
        client_name: str,
        status: models.OrderStatus,
        days_ago_start: int,
        stages_completed: int,
        operator_user: models.User,
        is_fully_completed: bool = False,
        rework_needed: bool = False
) -> models.ProductionOrder:
    start_date = datetime.now(UTC) - timedelta(days=days_ago_start)
    deadline_date = datetime.now(UTC) + timedelta(days=7)

    order = models.ProductionOrder(
        client_name=client_name,
        product_id=product.id,
        quantity=quantity,
        start_date=start_date,
        deadline_date=deadline_date,
        status=status
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    tech_stages = db.query(models.TechStage).filter(models.TechStage.product_id == product.id).order_by(
        models.TechStage.order_in_chain).all()

    for i, stage in enumerate(tech_stages):
        task_status = "pending"

        if is_fully_completed:
            task_status = "done"
        elif i < stages_completed:
            task_status = "done"
        elif i == stages_completed and not is_fully_completed:
            task_status = "working"

        # Логика Rework для демонстрационного заказа
        if rework_needed and i == stages_completed:
            task_status = "rework_needed"

        task = models.ProductionTask(
            order_id=order.id,
            stage_name=stage.name,
            status=task_status
        )

        if task_status == "done":
            deduct_materials(db, stage, quantity)
            task.start_time_actual = start_date + timedelta(hours=i * 2)
            task.end_time_actual = start_date + timedelta(hours=(i + 1) * 2)

        db.add(task)

    db.commit()
    return order


def deduct_materials(db: Session, stage: models.TechStage, order_qty: int):
    """Логика списания материалов для выполненного этапа."""
    for req in stage.requirements:
        total_needed = req.quantity_needed * order_qty

        material = db.query(models.Material).filter(models.Material.id == req.material_id).first()
        if material:
            material.quantity_in_stock -= total_needed
            db.add(material)


def seed_data():
    print("🏭 Начинаем загрузку сфокусированных тестовых данных (Пром. Насосы/Клапаны)...")

    # --- 1. Пользователи (10 шт.) ---

    users = [
        models.User(username="chief_engineer", hashed_password=get_password_hash("1234"),
                    role=models.UserRole.DISPATCHER),
        models.User(username="dispatch_junior", hashed_password=get_password_hash("1234"),
                    role=models.UserRole.DISPATCHER),
        models.User(username="tech_sidorov", hashed_password=get_password_hash("1234"),
                    role=models.UserRole.TECHNOLOGIST),
        models.User(username="tech_antonov", hashed_password=get_password_hash("1234"),
                    role=models.UserRole.TECHNOLOGIST),
        models.User(username="foreman_petrov", hashed_password=get_password_hash("1234"),
                    role=models.UserRole.OPERATOR),
        models.User(username="operator_ivanov", hashed_password=get_password_hash("1234"),
                    role=models.UserRole.OPERATOR),
        models.User(username="operator_smirnov", hashed_password=get_password_hash("1234"),
                    role=models.UserRole.OPERATOR),
        models.User(username="operator_vasin", hashed_password=get_password_hash("1234"),
                    role=models.UserRole.OPERATOR),
        models.User(username="operator_kuznetsov", hashed_password=get_password_hash("1234"),
                    role=models.UserRole.OPERATOR),
        models.User(username="qc_maria", hashed_password=get_password_hash("1234"), role=models.UserRole.OPERATOR),
    ]
    db.add_all(users)
    db.commit()
    print("✅ 10 пользователей созданы.")

    operator_user = db.query(models.User).filter(models.User.username == "foreman_petrov").first()

    # --- 2. Материалы (10 шт.) ---
    mat_iron_cast = models.Material(name="Чугун литейный (СЧ20)", unit="кг", quantity_in_stock=8000.0)
    mat_steel_rod_40 = models.Material(name="Стальной пруток Ø40", unit="м", quantity_in_stock=500.0)
    mat_steel_sheet = models.Material(name="Лист стальной 5мм", unit="м²", quantity_in_stock=300.0)
    mat_motor_10kw = models.Material(name="Электродвигатель 10 кВт", unit="шт", quantity_in_stock=80.0)
    mat_paint_blue = models.Material(name="Эмаль промышленная синяя", unit="л", quantity_in_stock=200.0)
    mat_seal_kit = models.Material(name="Комплект уплотнений", unit="шт", quantity_in_stock=500.0)
    mat_flange_dn100 = models.Material(name="Фланец ДУ-100", unit="шт", quantity_in_stock=200.0)
    mat_bearing_large = models.Material(name="Подшипник 30212", unit="шт", quantity_in_stock=400.0)
    mat_welding_wire = models.Material(name="Проволока сварочная", unit="кг", quantity_in_stock=100.0)
    mat_filter_mesh = models.Material(name="Сетка фильтрующая", unit="м²", quantity_in_stock=150.0)

    materials = [mat_iron_cast, mat_steel_rod_40, mat_steel_sheet, mat_motor_10kw, mat_paint_blue, mat_seal_kit,
                 mat_flange_dn100, mat_bearing_large, mat_welding_wire, mat_filter_mesh]
    db.add_all(materials)
    db.commit()
    print("✅ 10 видов сырья и комплектующих на складе.")

    # --- 3. Изделия (6 шт. - Насосы/Клапаны) ---
    p1 = models.Product(name="Насос центробежный НЦ-10", code="PUMP-NC10", description="Промышленный насос")
    p2 = models.Product(name="Корпус редуктора РК-05", code="HOUSING-RK05", description="Литой корпус")
    p3 = models.Product(name="Задвижка клиновая ДЗ-100", code="VALVE-DZ100", description="Запорная арматура")
    p4 = models.Product(name="Вал насосный длинный ВН-12", code="SHAFT-VN12", description="Высокоточный вал")
    p5 = models.Product(name="Элемент фильтрующий ЭФ-03", code="FILTER-EF03", description="Сварочный узел")
    p6 = models.Product(name="Рама-основание универсальная", code="FRAME-UBASE", description="Сварная рама")

    products = [p1, p2, p3, p4, p5, p6]
    db.add_all(products)
    db.commit()

    # --- 4. Технологические карты (5 общих этапов) ---

    # Этапы: 1. Литье, 2. Механическая обр., 3. Сварка, 4. Сборка, 5. Окраска

    # P1: Насос НЦ-10 (4 этапа)
    s1_p1 = models.TechStage(product_id=p1.id, name="Литье корпуса", order_in_chain=1, norm_time_minutes=300)
    s2_p1 = models.TechStage(product_id=p1.id, name="Механическая обработка", order_in_chain=2, norm_time_minutes=180)
    s3_p1 = models.TechStage(product_id=p1.id, name="Сборка и Тестирование", order_in_chain=3, norm_time_minutes=120)
    s4_p1 = models.TechStage(product_id=p1.id, name="Окраска", order_in_chain=4, norm_time_minutes=60)
    db.add_all([s1_p1, s2_p1, s3_p1, s4_p1])
    db.commit()
    db.add_all([
        models.StageMaterialRequirement(tech_stage_id=s1_p1.id, material_id=mat_iron_cast.id, quantity_needed=50.0),
        # 50 кг чугуна
        models.StageMaterialRequirement(tech_stage_id=s3_p1.id, material_id=mat_motor_10kw.id, quantity_needed=1.0),
        models.StageMaterialRequirement(tech_stage_id=s3_p1.id, material_id=mat_seal_kit.id, quantity_needed=1.0),
        models.StageMaterialRequirement(tech_stage_id=s4_p1.id, material_id=mat_paint_blue.id, quantity_needed=0.8),
    ])

    # P2: Корпус редуктора РК-05 (2 этапа)
    s1_p2 = models.TechStage(product_id=p2.id, name="Литье заготовки", order_in_chain=1, norm_time_minutes=240)
    s2_p2 = models.TechStage(product_id=p2.id, name="Механическая обработка", order_in_chain=2, norm_time_minutes=150)
    db.add_all([s1_p2, s2_p2])
    db.commit()
    db.add_all([
        models.StageMaterialRequirement(tech_stage_id=s1_p2.id, material_id=mat_iron_cast.id, quantity_needed=30.0),
        models.StageMaterialRequirement(tech_stage_id=s2_p2.id, material_id=mat_bearing_large.id, quantity_needed=2.0),
    ])

    # P3: Задвижка клиновая ДЗ-100 (3 этапа)
    s1_p3 = models.TechStage(product_id=p3.id, name="Литье корпуса", order_in_chain=1, norm_time_minutes=180)
    s2_p3 = models.TechStage(product_id=p3.id, name="Механическая обработка", order_in_chain=2, norm_time_minutes=120)
    s3_p3 = models.TechStage(product_id=p3.id, name="Сборка и Тестирование", order_in_chain=3, norm_time_minutes=90)
    db.add_all([s1_p3, s2_p3, s3_p3])
    db.commit()
    db.add_all([
        models.StageMaterialRequirement(tech_stage_id=s1_p3.id, material_id=mat_iron_cast.id, quantity_needed=20.0),
        models.StageMaterialRequirement(tech_stage_id=s3_p3.id, material_id=mat_flange_dn100.id, quantity_needed=2.0),
        # Два фланца на задвижку
    ])

    # P4: Вал насосный длинный ВН-12 (1 этап)
    s1_p4 = models.TechStage(product_id=p4.id, name="Механическая обработка", order_in_chain=1,
                             norm_time_minutes=480)  # Долгий этап
    db.add_all([s1_p4])
    db.commit()
    db.add_all([
        models.StageMaterialRequirement(tech_stage_id=s1_p4.id, material_id=mat_steel_rod_40.id, quantity_needed=8.0),
        # 8 м прутка
    ])

    # P5: Элемент фильтрующий ЭФ-03 (3 этапа)
    s1_p5 = models.TechStage(product_id=p5.id, name="Резка листа", order_in_chain=1, norm_time_minutes=60)
    s2_p5 = models.TechStage(product_id=p5.id, name="Сварка сетки", order_in_chain=2, norm_time_minutes=120)
    s3_p5 = models.TechStage(product_id=p5.id, name="Окраска", order_in_chain=3, norm_time_minutes=30)
    db.add_all([s1_p5, s2_p5, s3_p5])
    db.commit()
    db.add_all([
        models.StageMaterialRequirement(tech_stage_id=s1_p5.id, material_id=mat_filter_mesh.id, quantity_needed=1.2),
        models.StageMaterialRequirement(tech_stage_id=s2_p5.id, material_id=mat_welding_wire.id, quantity_needed=0.5),
        models.StageMaterialRequirement(tech_stage_id=s3_p5.id, material_id=mat_paint_blue.id, quantity_needed=0.1),
    ])

    # P6: Рама-основание универсальная (3 этапа)
    s1_p6 = models.TechStage(product_id=p6.id, name="Резка листа", order_in_chain=1, norm_time_minutes=90)
    s2_p6 = models.TechStage(product_id=p6.id, name="Сварочный узел", order_in_chain=2, norm_time_minutes=180)
    s3_p6 = models.TechStage(product_id=p6.id, name="Окраска", order_in_chain=3, norm_time_minutes=90)
    db.add_all([s1_p6, s2_p6, s3_p6])
    db.commit()
    db.add_all([
        models.StageMaterialRequirement(tech_stage_id=s1_p6.id, material_id=mat_steel_sheet.id, quantity_needed=5.0),
        # 5 м² листа
        models.StageMaterialRequirement(tech_stage_id=s2_p6.id, material_id=mat_welding_wire.id, quantity_needed=1.0),
        models.StageMaterialRequirement(tech_stage_id=s3_p6.id, material_id=mat_paint_blue.id, quantity_needed=1.5),
    ])

    db.commit()
    print("✅ 6 техкарт настроены с общими этапами (Литье, Мех. обр., Сварка, Сборка, Окраска).")

    # --- 5. Создание заказов (8 шт.) ---

    # O1: ВЫПОЛНЕННЫЙ ЗАКАЗ (15 шт НЦ-10)
    create_order_and_tasks(
        db, p1, 15, "Нефтемаш Холдинг", models.OrderStatus.COMPLETED, 10, 4, operator_user, is_fully_completed=True
    )
    # O2: В ПРОЦЕССЕ (100 шт Задвижка ДЗ-100) - 2 этапа готовы
    create_order_and_tasks(
        db, p3, 100, "ГазПромЭнерго", models.OrderStatus.IN_PROGRESS, 5, 2, operator_user, is_fully_completed=False
    )
    # O3: В ПРОЦЕССЕ (20 шт Корпус РК-05) - 1 этап готов, 2й в работе
    create_order_and_tasks(
        db, p2, 20, "ПроектИнвест", models.OrderStatus.IN_PROGRESS, 1, 1, operator_user, is_fully_completed=False
    )
    # O4: ЗАДЕРЖАН (50 шт Вал ВН-12) - Единственный этап в работе долго
    create_order_and_tasks(
        db, p4, 50, "ОборонТех", models.OrderStatus.DELAYED, 7, 0, operator_user, is_fully_completed=False
    )
    # O5: ВЫПОЛНЕННЫЙ ЗАКАЗ (5 шт Рама-основание)
    create_order_and_tasks(
        db, p6, 5, "СтройМаш", models.OrderStatus.COMPLETED, 2, 3, operator_user, is_fully_completed=True
    )
    # O6: НОВЫЙ ЗАКАЗ (50 шт Фильтрующий Элемент) - Не начат
    create_order_and_tasks(
        db, p5, 50, "АкваСтрой", models.OrderStatus.NEW, 0, 0, operator_user, is_fully_completed=False
    )
    # O7: НОВЫЙ ЗАКАЗ (3 шт Насос НЦ-10) - Не начат
    create_order_and_tasks(
        db, p1, 3, "Ремзавод №2", models.OrderStatus.NEW, 0, 0, operator_user, is_fully_completed=False
    )
    # O8: В ПРОЦЕССЕ (Rework) - 10 шт Задвижка. Последний этап требует переделки
    create_order_and_tasks(
        db, p3, 10, "СпецКран", models.OrderStatus.DELAYED, 3, 2, operator_user, is_fully_completed=False,
        rework_needed=True
    )

    print("✅ 8 тестовых заказов с разными статусами созданы.")
    print("✅ Материалы списаны для всех выполненных этапов.")

    db.close()
    print("🚀 Успех! База данных полностью готова к демонстрации (Металлургия/Машиностроение).")


if __name__ == "__main__":
    seed_data()
