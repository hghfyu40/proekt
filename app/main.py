from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import random

from app.database import SessionLocal, engine
from app.models import Base, User, UserQuestion
from app.hashing import create_combined_hash, verify_answer

# ---------------------------------------------------------------------
# Создаём таблицы автоматически при старте
# ---------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------
# Инициализация FastAPI
# ---------------------------------------------------------------------
app = FastAPI(
    title="Система аутентификации по вопросам",
    version="1.0.0",
    description="Аутентификация без пароля с использованием секретных вопросов"
)

# ---------------------------------------------------------------------
# Общие вопросы
# ---------------------------------------------------------------------
COMMON_QUESTIONS = [
    "Девичья фамилия матери?",
    "Имя первого питомца?",
    "Город рождения?",
    "Любимый школьный предмет?",
    "Название первой компании?"
]

# ---------------------------------------------------------------------
# Dependency: DB Session
# ---------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------------------
# GET /questions — Получить список вопросов
# ---------------------------------------------------------------------
@app.get("/questions")
def get_questions():
    return {"вопросы": COMMON_QUESTIONS}

# ---------------------------------------------------------------------
# POST /register — Регистрация пользователя
# ---------------------------------------------------------------------
@app.post("/register")
def register(payload: dict, db: Session = Depends(get_db)):
    username = payload.get("username")
    questions = payload.get("questions")

    if not username or not isinstance(questions, list) or len(questions) < 3:
        raise HTTPException(status_code=400, detail="Неверные данные регистрации")

    if db.query(User).filter_by(username=username).first():
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    user = User(username=username)
    db.add(user)
    db.commit()
    db.refresh(user)

    for item in questions:
        question = item.get("question")
        answer = item.get("answer")
        if not question or not answer:
            continue
        combined_hash, salt = create_combined_hash(question, answer)
        uq = UserQuestion(
            user_id=user.id,
            question_text=question,
            combined_hash=combined_hash,
            salt=salt
        )
        db.add(uq)

    db.commit()
    return {"статус": "зарегистрирован"}

# ---------------------------------------------------------------------
# POST /login/request — Запрос случайного вопроса
# ---------------------------------------------------------------------
@app.post("/login/request")
def login_request(payload: dict, db: Session = Depends(get_db)):
    username = payload.get("username")
    if not username:
        raise HTTPException(status_code=400, detail="Необходимо указать имя пользователя")

    user = db.query(User).filter_by(username=username).first()
    if not user or not user.questions:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    question = random.choice(user.questions)
    return {"id_вопроса": question.id, "текст_вопроса": question.question_text}

# ---------------------------------------------------------------------
# POST /login/verify — Проверка ответа
# ---------------------------------------------------------------------
@app.post("/login/verify")
def login_verify(payload: dict, db: Session = Depends(get_db)):
    username = payload.get("username")
    question_id = payload.get("question_id")
    answer = payload.get("answer")

    if not username or question_id is None or not answer:
        raise HTTPException(status_code=400, detail="Неверные данные входа")

    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    question = db.query(UserQuestion).filter_by(
        id=question_id,
        user_id=user.id
    ).first()
    if not question:
        raise HTTPException(status_code=400, detail="Неверный вопрос")

    is_valid = verify_answer(
        question.question_text,
        answer,
        question.combined_hash,
        question.salt
    )

    if not is_valid:
        raise HTTPException(status_code=401, detail="Аутентификация не пройдена")
