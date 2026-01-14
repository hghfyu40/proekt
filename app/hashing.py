import bcrypt
import hashlib
import secrets

def _canonicalize(text: str) -> str:
    return " ".join(text.strip().lower().split())

def create_combined_hash(question: str, answer: str) -> tuple[str, str]:
    # Канонизация
    q = _canonicalize(question)
    a = _canonicalize(answer)

    # Криптографическая соль
    salt = secrets.token_hex(16)

    # 1️⃣ Сначала SHA-256 (фиксированная длина)
    preimage = f"{q}|{a}|{salt}".encode("utf-8")
    digest = hashlib.sha256(preimage).digest()

    # 2️⃣ Потом bcrypt (медленно и безопасно)
    hashed = bcrypt.hashpw(digest, bcrypt.gensalt())

    return hashed.decode("utf-8"), salt

def verify_answer(
    question: str,
    answer: str,
    stored_hash: str,
    salt: str
) -> bool:
    q = _canonicalize(question)
    a = _canonicalize(answer)

    preimage = f"{q}|{a}|{salt}".encode("utf-8")
    digest = hashlib.sha256(preimage).digest()

    return bcrypt.checkpw(
        digest,
        stored_hash.encode("utf-8")
    )