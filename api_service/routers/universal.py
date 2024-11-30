from fastapi import Query, Depends, APIRouter
from sqlalchemy.orm import Session
from check_uuid import check_uuid
from models import get_db
import qrcode
import base64
import io

router = APIRouter()

# Генератор QR кодов
@router.get("/api/v1/qr_generate", tags=["UNIVERSAL"])
async def qr_generate(
        address: str = Query(..., description="Адрес кошелька"),
        user_uuid: str = Query(..., description="UUID"),
        db: Session = Depends(get_db)
):
    # Проверка UUID пользователя
    check_uuid(user_uuid, db)

    # Создание объекта QR-кода
    QRcode = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)

    # Добавление текста в QR-код
    QRcode.add_data(address)

    # Генерация QR-кода
    QRcode.make()

    # Цвета QR-кода
    qr_color = '#FA5252'  # Основной цвет
    back_color = "#262831"  # Цвет фона

    # Генерация изображения QR-кода
    QRimg = QRcode.make_image(fill_color=qr_color, back_color=back_color).convert('RGB')

    # Сохранение QR-кода в объект bytesIO
    img_bytes = io.BytesIO()
    QRimg.save(img_bytes, format='PNG')

    # Конвертация изображения в base64
    img_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')

    return img_base64