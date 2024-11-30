import uvicorn
from starlette.middleware.sessions import SessionMiddleware
from routers import dash_api, panel, universal
from fastapi import FastAPI

# Инициализация FastAPI с параметром кастомного заголовка на странице документации.
# Зайти в документацию можно по адресу http://127.0.0.1:8000/docs
app = FastAPI(
    title="Hooli Crypto API",
)

# Вызов метода add_middleware для работы с сессиями.
# Потребуется для того что бы не авторизованный пользователь не смог зайти на страницу профиля
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

# Маршрутизатор (include_router) основного приложения с которым будут связанны сторонние маршруты из других файлов
app.include_router(dash_api.router)
app.include_router(universal.router)
app.include_router(panel.router, include_in_schema=False)


# Запуск приложения
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
