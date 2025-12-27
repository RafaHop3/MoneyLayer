from fastapi import FastAPI, Query, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
from dateutil.relativedelta import relativedelta 
import secrets
import os
import random
from dotenv import load_dotenv

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship

load_dotenv()

app = FastAPI(title="MoneyLayer ERP V15 - Equipe")

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = "sqlite:///./money_layer.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 1. TABELAS (COM FUNÇÃO DE USUÁRIO)
# ==========================================
class UsuarioBD(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    senha = Column(String) # Em produção, use hash!
    
    # PERMISSÃO: 'admin' ou 'funcionario'
    funcao = Column(String, default="funcionario") 
    
    # Dados da Empresa (Só preenchido se for Admin)
    nome_empresa = Column(String, nullable=True)
    cnpj_cpf = Column(String, nullable=True)
    email_contato = Column(String, nullable=True)
    telefone = Column(String, nullable=True)
    endereco_completo = Column(String, nullable=True)
    
    # Em um sistema simples, todos operam na conta do Admin
    # Mas mantemos o relacionamento para saber QUEM lançou
    transacoes = relationship("TransacaoBD", back_populates="criador")

class TransacaoBD(Base):
    __tablename__ = "transacoes"
    id = Column(Integer, primary_key=True, index=True)
    
    descricao = Column(String)
    valor_total = Column(Float)
    valor_parcela = Column(Float)
    tipo = Column(String)
    instituicao = Column(String)
    moeda = Column(String)
    forma_pagamento = Column(String)
    
    parcela_atual = Column(Integer, default=1)
    total_parcelas = Column(Integer, default=1)
    
    tipo_documento = Column(String)
    numero_documento = Column(String, nullable=True)
    detalhes_fiscais = Column(String, nullable=True)
    
    data_emissao = Column(DateTime, default=datetime.now)
    data_vencimento = Column(DateTime, default=datetime.now)

    # Vincula a quem criou o lançamento
    criador_id = Column(Integer, ForeignKey("usuarios.id"))
    criador = relationship("UsuarioBD", back_populates="transacoes")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ==========================================
# 2. SISTEMA DE LOGIN INTELIGENTE
# ==========================================
security = HTTPBasic()

def get_usuario_atual(credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)):
    """
    Verifica se é o Admin do .env OU um funcionário do Banco
    """
    env_user = os.getenv("USUARIO_MESTRE")
    env_pass = os.getenv("SENHA_MESTRA")
    
    # 1. É o Admin Supremo?
    if secrets.compare_digest(credentials.username, env_user) and secrets.compare_digest(credentials.password, env_pass):
        # Garante que ele existe no banco
        admin = db.query(UsuarioBD).filter(UsuarioBD.username == env_user).first()
        if not admin:
            admin = UsuarioBD(username=env_user, senha="***", funcao="admin")
            db.add(admin); db.commit(); db.refresh(admin)
        return admin

    # 2. É um Funcionário comum?
    user = db.query(UsuarioBD).filter(UsuarioBD.username == credentials.username).first()
    if user and secrets.compare_digest(credentials.password, user.senha):
        return user
    
    raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

def apenas_admin(usuario: UsuarioBD = Depends(get_usuario_atual)):
    if usuario.funcao != "admin":
        raise HTTPException(status_code=403, detail="Acesso Negado: Apenas Admin pode fazer isso.")
    return usuario

# ==========================================
# 3. MODELOS PYDANTIC
# ==========================================
class UsuarioCriar(BaseModel):
    username: str
    senha: str
    funcao: str = "funcionario" # admin ou funcionario

class LancamentoCompleto(BaseModel):
    descricao: str
    valor: float
    tipo: str 
    instituicao: str 
    moeda: str = "BRL"
    forma_pagamento: str
    qtd_parcelas: int = 1
    tipo_documento: str 
    numero_documento: Optional[str] = None
    detalhes_fiscais: Optional[str] = None
    data_base: datetime = datetime.now()

class TransacaoExibir(BaseModel):
    id: int
    descricao: str
    valor_parcela: float
    data_vencimento: datetime
    parcela_atual: int
    total_parcelas: int
    tipo_documento: Optional[str]
    numero_documento: Optional[str]
    instituicao: str
    forma_pagamento: Optional[str]
    tipo: str
    criador_id: int # Para saber quem lançou
    class Config: from_attributes = True

class PerfilUpdate(BaseModel):
    nome_empresa: Optional[str]
    cnpj_cpf: Optional[str]
    email_contato: Optional[str]
    telefone: Optional[str]
    endereco_completo: Optional[str]

# ==========================================
# 4. ROTAS
# ==========================================

@app.get("/")
def home():
    if os.path.exists("index.html"): return FileResponse("index.html")
    return {"erro": "index.html não encontrado"}

# --- ROTA PARA CRIAR USUÁRIOS (SÓ ADMIN) ---
@app.post("/admin/usuarios")
def criar_usuario_equipe(
    novo_user: UsuarioCriar, 
    db: Session = Depends(get_db), 
    admin: UsuarioBD = Depends(apenas_admin) # <--- BLOQUEIO DE SEGURANÇA
):
    # Verifica se já existe
    if db.query(UsuarioBD).filter(UsuarioBD.username == novo_user.username).first():
        raise HTTPException(400, "Usuário já existe")
    
    usuario = UsuarioBD(
        username=novo_user.username,
        senha=novo_user.senha,
        funcao=novo_user.funcao
    )
    db.add(usuario)
    db.commit()
    return {"mensagem": f"Usuário {novo_user.username} criado como {novo_user.funcao}!"}

# --- PERFIL (LEITURA LIBERADA, EDIÇÃO SÓ ADMIN) ---
@app.get("/usuario/perfil")
def ver_perfil(
    db: Session = Depends(get_db),
    usuario: UsuarioBD = Depends(get_usuario_atual)
):
    # Retorna sempre o perfil do ADMIN (Empresa), não do funcionário
    # Assume que o ID 1 é sempre o Admin ou busca pelo .env
    env_user = os.getenv("USUARIO_MESTRE")
    empresa = db.query(UsuarioBD).filter(UsuarioBD.username == env_user).first()
    return empresa

@app.put("/usuario/perfil")
def atualizar_perfil(
    dados: PerfilUpdate, 
    db: Session = Depends(get_db), 
    admin: UsuarioBD = Depends(apenas_admin) # <--- SÓ ADMIN
):
    admin.nome_empresa = dados.nome_empresa
    admin.cnpj_cpf = dados.cnpj_cpf
    admin.email_contato = dados.email_contato
    admin.telefone = dados.telefone
    admin.endereco_completo = dados.endereco_completo
    db.commit()
    return {"mensagem": "Perfil atualizado!"}

# --- ROTAS FINANCEIRAS (TODOS PODEM USAR) ---
@app.post("/lancar/", status_code=201)
def criar_lancamento(
    item: LancamentoCompleto, 
    db: Session = Depends(get_db), 
    usuario: UsuarioBD = Depends(get_usuario_atual)
):
    valor_parcelado = round(item.valor / item.qtd_parcelas, 2)
    for i in range(item.qtd_parcelas):
        data_venc = item.data_base + relativedelta(months=i)
        nova = TransacaoBD(
            descricao=item.descricao,
            valor_total=item.valor,
            valor_parcela=valor_parcelado,
            tipo=item.tipo,
            instituicao=item.instituicao,
            moeda=item.moeda,
            forma_pagamento=item.forma_pagamento,
            parcela_atual=i+1,
            total_parcelas=item.qtd_parcelas,
            tipo_documento=item.tipo_documento,
            numero_documento=item.numero_documento,
            detalhes_fiscais=item.detalhes_fiscais,
            data_emissao=item.data_base,
            data_vencimento=data_venc,
            criador_id=usuario.id # Grava quem lançou
        )
        db.add(nova)
    db.commit()
    return {"mensagem": "Salvo!"}

def aplicar_filtros(query, instituicao, data_inicio, data_fim):
    if instituicao: query = query.filter(TransacaoBD.instituicao == instituicao)
    if data_inicio: query = query.filter(TransacaoBD.data_vencimento >= data_inicio)
    if data_fim: query = query.filter(TransacaoBD.data_vencimento <= data_fim)
    return query

@app.get("/extrato", response_model=List[TransacaoExibir])
def ver_extrato(
    instituicao: str | None = Query(None),
    data_inicio: date | None = None,
    data_fim: date | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioBD = Depends(get_usuario_atual)
):
    # TODOS veem tudo da empresa (Transparência interna)
    query = db.query(TransacaoBD)
    query = aplicar_filtros(query, instituicao, data_inicio, data_fim)
    return query.order_by(TransacaoBD.data_vencimento.desc()).all()

@app.get("/saldo")
def calcular_saldo(
    instituicao: str | None = Query(None),
    data_inicio: date | None = None,
    data_fim: date | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioBD = Depends(get_usuario_atual)
):
    query = db.query(TransacaoBD)
    query = aplicar_filtros(query, instituicao, data_inicio, data_fim)
    dados = query.all()
    
    entradas = sum(i.valor_parcela for i in dados if i.tipo == "receita")
    saidas = sum(i.valor_parcela for i in dados if i.tipo == "despesa")
    
    # Retorna também a função do usuário para o Front saber o que esconder
    return {
        "entradas": entradas, 
        "saidas": saidas, 
        "saldo_final": entradas - saidas,
        "usuario_funcao": usuario.funcao # <--- IMPORTANTE
    }

# --- ROTA DELETAR (SÓ ADMIN) ---
@app.delete("/transacao/{id}")
def deletar(id: int, db: Session = Depends(get_db), admin: UsuarioBD = Depends(apenas_admin)):
    t = db.query(TransacaoBD).filter(TransacaoBD.id == id).first()
    if not t: raise HTTPException(404, "Não encontrado")
    db.delete(t)
    db.commit()
    return {"msg": "Apagado"}