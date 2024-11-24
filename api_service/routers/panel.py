from fastapi import HTTPException, Depends, Form, Request, APIRouter
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from models import User, get_db
import uuid

# Маршрутизатор который будет связан с маршрутизатором основного приложения FastAPI
# (app.include_router(panel.router, include_in_schema=False))
router = APIRouter()
# Создание объекта для работы с Jinja2 через FastAPI. Потребуется для того что бы передавать данные и бекенд в фронтенд
templates = Jinja2Templates(directory="templates")

#TODO:ИЗМЕНИТЬ РАБОТУ С USER_ID НА UUID ПРИ РЕГИСТРАЦИИ И ПЕРЕХОДЕ НА ПРОФИЛЬ

# Маршрут, доступный в маршрутизаторе основного приложения FastAPI через маршрутизатор (router = APIRouter())
@router.api_route("/register", methods=["GET", "POST"])
async def register(request: Request, username: str = Form(None), password: str = Form(None), db: Session = Depends(get_db)):
    if request.method == "POST":
        # Проверяет логин из формы с логином из таблицы в модели (классе) User
        # Если логин сходится, то получает ошибку
        db_user = db.query(User).filter(User.username == username).first()
        if db_user:
            raise HTTPException(status_code=400, detail="Username already registered")

        # Генерируется uuid
        unique_id = str(uuid.uuid4())
        # Добавление логина из формы и сгенерированный uuid в сессию базы данных
        new_user = User(username=username, unique_id=unique_id)
        # Добавление зашифрованного пароля в сессию базы данных
        new_user.set_password(password)
        # Добавление в базу данных
        db.add(new_user)
        # Сохранение в базе данных
        db.commit()
        # Обновление базы данных
        db.refresh(new_user)

        # Сохраняем user_id из таблицы в ключ ['user_id'] в http сессии
        request.session['user_id'] = new_user.id

        return RedirectResponse(url=f"/profile/{new_user.id}", status_code=303)

    return templates.TemplateResponse("register.html", {"request": request})


# Декоратор api_route позволяет обрабатывать все виды запросов, это фишка FastAPI
# Методы methods=["GET", "POST"] все равно указаны для того что бы лишние типы запросов не срабатывали
@router.api_route("/login", methods=["GET", "POST"])
async def login(request: Request, username: str = Form(None), password: str = Form(None), db: Session = Depends(get_db)):
    if request.method == "POST":
        # Проверяет логин из формы с логином из таблицы в модели (классе) User
        # Если логин сходится, то получает все данные пользователя из базы данных
        db_user = db.query(User).filter(User.username == username).first()
        # Если нету пользователя или нету пользователя с таким же паролем как из формы на сайте, то выдавать ошибку
        # Перед сравнением, пароль шифруется через check_password и уже в виде хеша сравнивается с паролем из бд
        if not db_user or not db_user.check_password(password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Сохраняем user_id в сессию
        request.session['user_id'] = db_user.id
        return RedirectResponse(url=f"/profile/{db_user.id}", status_code=303)

    # Если запрос GET, отображаем страницу логина
    return templates.TemplateResponse("login.html", {"request": request})


# Страница профиля
@router.get("/profile/{user_id}")
async def profile_page(request: Request, user_id: int, db: Session = Depends(get_db)):
    # Проверка http сессии (cookie): только если id из сессии соответствует user_id из ссылки на маршрут
    #('user_id') это ключ в http сессии который хранит ид пользователя
    if request.session.get('user_id') != user_id:
        return RedirectResponse(url="/login", status_code=303)

    # Проверяет id из ссылки с id из таблицы в модели (классе) User
    # Если id сходится, то получает все данные пользователя из базы данных
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    # Возвращает html страницу и передает в нее все данные пользователя
    return templates.TemplateResponse("profile.html", {"request": request, "user": db_user})


# Выход
@router.get("/logout")
async def logout(request: Request):
    # Удаляем http сессию
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)