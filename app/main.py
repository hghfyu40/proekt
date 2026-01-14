from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import random

from app.database import SessionLocal, engine
from app.models import Base, User, UserQuestion
from app.hashing import create_combined_hash, verify_answer


# =========================
# Инициализация приложения
# =========================

app = FastAPI(
    title="Система аутентификации по контрольным вопросам",
    description="""
    API для регистрации и аутентификации пользователей
    без использования паролей.

    Пользователь подтверждает личность,
    отвечая на заранее заданный контрольный вопрос.
    """,
    version="1.0.0",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1}
)


# =========================
# Создание таблиц БД
# =========================

Base.metadata.create_all(bind=engine)


# =========================
# Зависимость БД
# =========================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================
# Pydantic-модели запросов
# =========================

class RegisterRequest(BaseModel):
    username: str = Field(..., description="Логин пользователя")
    question: str = Field(..., description="Контрольный вопрос")
    answer: str = Field(..., description="Секретный ответ")


class LoginRequest(BaseModel):
    username: str = Field(..., description="Логин пользователя")


class VerifyRequest(BaseModel):
    username: str = Field(..., description="Логин пользователя")
    question_id: int = Field(..., description="ID контрольного вопроса")
    answer: str = Field(..., description="Ответ на контрольный вопрос")


# =========================
# Регистрация пользователя
# =========================

@app.post(
    "/register",
    summary="Регистрация пользователя",
    description="Создаёт нового пользователя и сохраняет контрольный вопрос с ответом"
)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    user = User(username=data.username)
    db.add(user)
    db.commit()
    db.refresh(user)

    combined_hash, salt = create_combined_hash(data.question, data.answer)

    question = UserQuestion(
        user_id=user.id,
        question_text=data.question,
        combined_hash=combined_hash,
        salt=salt
    )

    db.add(question)
    db.commit()

    return {"статус": "пользователь успешно зарегистрирован"}


# =========================
# Запрос контрольного вопроса
# =========================

@app.post(
    "/login/request",
    summary="Запрос контрольного вопроса",
    description="Возвращает случайный контрольный вопрос пользователя"
)
def login_request(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    questions = db.query(UserQuestion).filter(UserQuestion.user_id == user.id).all()
    if not questions:
        raise HTTPException(status_code=404, detail="Контрольные вопросы не найдены")

    question = random.choice(questions)

    return {
        "question_id": question.id,
        "question": question.question_text
    }


# =========================
# Проверка ответа
# =========================

@app.post(
    "/login/verify",
    summary="Проверка ответа",
    description="Проверяет ответ на контрольный вопрос и выполняет аутентификацию"
)
def login_verify(data: VerifyRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    question = db.query(UserQuestion).filter(
        UserQuestion.id == data.question_id,
        UserQuestion.user_id == user.id
    ).first()

    if not question:
        raise HTTPException(status_code=400, detail="Контрольный вопрос не найден")

    is_valid = verify_answer(
        question.question_text,
        data.answer,
        question.combined_hash,
        question.salt
    )

    if not is_valid:
        raise HTTPException(status_code=401, detail="Неверный ответ")

    return {"статус": "успешная аутентификация"}
