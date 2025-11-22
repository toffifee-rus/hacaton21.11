from passlib.context import CryptContext

# Настройка алгоритма хеширования
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """Проверяет, совпадает ли введенный пароль с хешем в БД"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Хеширует пароль, безопасно обрезая его до 72 байт, как того требует bcrypt."""
    # 1. Явно кодируем пароль в байты (UTF-8).
    # 2. Обрезаем его до первых 72 байт.
    # 3. Декодируем обратно в строку для передачи в passlib (passlib/bcrypt сам обрабатывает байты,
    #    но явное обрезание по байтам гарантирует, что мы не превысим лимит).

    safe_password_bytes = password.encode('utf-8')[:72]
    safe_password_str = safe_password_bytes.decode('utf-8', 'ignore')

    return pwd_context.hash(safe_password_str)