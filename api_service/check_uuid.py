from fastapi import HTTPException,Depends
from sqlalchemy.orm import Session
from models import User, get_db

# Функция для проверки UUID пользователя
def check_uuid(user_uuid: str, db: Session = Depends(get_db)):
    # Создается запрос к таблице из модели (класса) User и ищется поле unique_id с таким же значением как передаваемый user_uuid
    db_user = db.query(User).filter(User.unique_id == user_uuid).first()
    if not db_user:
        # Если uuid не найден, то выводить ошибку
        raise HTTPException(status_code=403, detail="Invalid or unauthorized UUID.")
    return db_user