from pydantic import BaseModel
from typing import Optional

class UsuarioSignup(BaseModel):
    username: str
    password: str

class GoogleToken(BaseModel):
    token: str

class TransacaoInput(BaseModel):
    descricao: str
    valor: float
    tipo: str
    instituicao: str
    forma_pagamento: str
    qtd_parcelas: int = 1
    data_base: str
    tipo_documento: str
    numero_documento: Optional[str] = None

class PerfilInput(BaseModel):
    nome_empresa: Optional[str] = None
    cnpj_cpf: Optional[str] = None
    telefone: Optional[str] = None
    endereco_completo: Optional[str] = None
