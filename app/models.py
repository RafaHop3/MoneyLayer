from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class UsuarioBD(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)

    nome_empresa = Column(String, nullable=True)
    cnpj_cpf = Column(String, nullable=True)
    telefone = Column(String, nullable=True)
    endereco_completo = Column(String, nullable=True)

    # 🔗 Relacionamento
    transacoes = relationship("TransacaoBD", back_populates="dono")


class TransacaoBD(Base):
    __tablename__ = "transacoes"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String, nullable=False)
    valor = Column(Float, nullable=False)
    tipo = Column(String, nullable=False)
    instituicao = Column(String, nullable=False)
    forma_pagamento = Column(String, nullable=False)
    qtd_parcelas = Column(Integer, nullable=False)

    data_vencimento = Column(DateTime, default=datetime.utcnow)
    tipo_documento = Column(String, nullable=False)
    numero_documento = Column(String, nullable=True)

    dono_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # 🔗 Relacionamento
    dono = relationship("UsuarioBD", back_populates="transacoes")
