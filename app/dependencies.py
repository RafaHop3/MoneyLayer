from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError
from app.database import SessionLocal
from app.models import UsuarioBD
from security import SECRET_KEY, ALGORITHM

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Não autenticado")

    token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(UsuarioBD).filter_by(username=username).first()
        if not user:
            raise HTTPException(401)
        return user
    except JWTError:
        raise HTTPException(401)
