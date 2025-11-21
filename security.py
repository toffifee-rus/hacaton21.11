from passlib.context import CryptContext

# Настройка алгоритма хеширования
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """Проверяет, совпадает ли введенный пароль с хешем в БД"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Превращает пароль '1234' в набор символов"""
    return pwd_context.hash(password)