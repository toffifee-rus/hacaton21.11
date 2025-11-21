from database import SessionLocal, engine
import models
from security import get_password_hash  # Не забудь убедиться, что файл security.py существует

# 1. Чистим базу данных
models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)

db = SessionLocal()


def seed_data():
    print("🏭 Начинаем загрузку данных для металлургического завода...")

    # --- 1. Пользователи (С паролями и правильными ролями) ---
    # Пароль для всех: 1234

    # Главный инженер (Роль: Диспетчер)
    user1 = models.User(
        username="chief_engineer",
        hashed_password=get_password_hash("1234"),
        role=models.UserRole.DISPATCHER  # Используем Enum, а не строку "admin"
    )

    # Технолог (Роль: Технолог)
    user2 = models.User(
        username="tech_sidorov",
        hashed_password=get_password_hash("1234"),
        role=models.UserRole.TECHNOLOGIST
    )

    # Мастер цеха (Роль: Оператор)
    user3 = models.User(
        username="foreman_petrov",
        hashed_password=get_password_hash("1234"),
        role=models.UserRole.OPERATOR
    )

    db.add_all([user1, user2, user3])
    db.commit()
    print("✅ Пользователи созданы (chief_engineer / 1234)")

    # --- 2. Материалы (Металлургия) ---
    mat_iron = models.Material(name="Чугун литейный (СЧ20)", unit="кг", quantity_in_stock=5000.0)
    mat_steel_rod = models.Material(name="Стальной круг Ø40мм", unit="м", quantity_in_stock=200.0)
    mat_motor = models.Material(name="Электродвигатель 1.1 кВт", unit="шт", quantity_in_stock=50.0)
    mat_paint = models.Material(name="Эмаль промышленная (Синяя)", unit="л", quantity_in_stock=100.0)

    db.add_all([mat_iron, mat_steel_rod, mat_motor, mat_paint])
    db.commit()
    print("✅ Сырье на складе")

    # --- 3. Изделие ---
    product = models.Product(
        name="Станок сверлильный НС-12",
        code="MACHINE-NS12",
        description="Настольный станок для сверления"
    )
    db.add(product)
    db.commit()

    # --- 4. Технологическая карта ---
    stage1 = models.TechStage(
        product_id=product.id,
        name="Литье станины",
        order_in_chain=1,
        norm_time_minutes=240
    )
    stage2 = models.TechStage(
        product_id=product.id,
        name="Механическая обработка",
        order_in_chain=2,
        norm_time_minutes=120
    )
    stage3 = models.TechStage(
        product_id=product.id,
        name="Сборка и покраска",
        order_in_chain=3,
        norm_time_minutes=90
    )

    db.add_all([stage1, stage2, stage3])
    db.commit()

    # --- 5. Нормы расхода ---
    req1 = models.StageMaterialRequirement(
        tech_stage_id=stage1.id, material_id=mat_iron.id, quantity_needed=45.0
    )
    req2 = models.StageMaterialRequirement(
        tech_stage_id=stage2.id, material_id=mat_steel_rod.id, quantity_needed=1.5
    )
    req3_motor = models.StageMaterialRequirement(
        tech_stage_id=stage3.id, material_id=mat_motor.id, quantity_needed=1.0
    )
    req3_paint = models.StageMaterialRequirement(
        tech_stage_id=stage3.id, material_id=mat_paint.id, quantity_needed=0.4
    )

    db.add_all([req1, req2, req3_motor, req3_paint])
    db.commit()

    print("🚀 Успех! База данных полностью готова.")


if __name__ == "__main__":
    seed_data()
    db.close()