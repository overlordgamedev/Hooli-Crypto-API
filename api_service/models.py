import uuid
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import bcrypt

# Ссылка на адрес базы данных для подключения
DATABASE_URL = "postgresql://postgres:postgres@localhost/postgres"

# Инициализация create_engine для подключения к базе данных и работы с ней
engine = create_engine(DATABASE_URL)
# Инициализация объекта сессии для работы с базой данных, умеет обновлять, добавлять, удалять данные
# autocommit=False — настройка автоматического применения изменений из сессии в базу данных сразу же
# autoflush=False — настройка автоматического применения изменений данных из сессии в базу данных перед выполнением новых действий
# bind=engine — привязка сессий к конкретному engine, который управляет подключением к базе данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Создание базового класса от которого будут наследоваться все таблицы
# ООП в действии. Позволит как минимум связывать таблицы друг с другом
Base = declarative_base()

# Получение сессии для базы данных
def get_db():
    # Подключение к инициализированной сессии
    db = SessionLocal()
    try:
        # Возвращаем сессию при вызове функции get_db
        # yield нужен для того что бы функция, которая вызвала эту функцию - остановилась пока get_db не закончит работу
        # Также yield сохраняет состояние и не завершает функцию, и при следующем вызове продолжить работу с того же места
        # Но эта фишка аннулируется т.к в конце прописано db.close() и сессия в любом случае закроется
        yield db
    finally:
        db.close()  # Выход из сессии

class User(Base):
    # Название таблицы
    __tablename__ = 'users'
    # Столбцы
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    unique_id = Column(String, unique=True, index=True, default=str(uuid.uuid4()))  # Поле для уникального ID

    # Связь с таблицей кошельков
    wallets = relationship("DWallet", back_populates="user", cascade="all, delete-orphan")

    # Функции для расшифровки пароля из хэша и шифровки пароля в хэш
    def set_password(self, password: str):
        # При вызове set_password из функции регистрации с передачей сюда пароля, пароль начнет шифроваться и запишется в память как password_hash
        # В функции регистрации после этого данные запишутся в таблицу и сохранятся
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password: str):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))


# Таблица кошельков
class DWallet(Base):
    __tablename__ = 'dwallets'
    id = Column(Integer, primary_key=True, index=True)
    wallet_name = Column(String, unique=True, index=True)  # Название кошелька
    user_unique_id = Column(String, ForeignKey('users.unique_id'), nullable=False)  # Внешний ключ на таблицу пользователей

    # Связь с таблицей пользователей
    user = relationship("User", back_populates="wallets")


# Создание всех таблиц
# bind=engine определяет в какой базе данных создавать таблицы
Base.metadata.create_all(bind=engine)