import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Busca a URL do ambiente. Se não existir, usa o SQLite local como padrão.
# Isso evita o RuntimeError quando você roda o Alembic.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./money_layer.db")

# 2. Ajuste para compatibilidade com versões recentes do SQLAlchemy/Heroku
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. Configurações extras para SQLite (necessário para threads do FastAPI)
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()