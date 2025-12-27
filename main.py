import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Query, Depends, HTTPException, status, Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2PasswordBearer
from pydantic import BaseModel
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

# --- IMPORTAÇÕES DE SEGURANÇA E BANCO ---
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship
from passlib.context import CryptContext # Para hash de senha
from jose import JWTError, jwt # Para Token JWT
from google.oauth2 import id_token # Para validar Google
from google.auth.transport import requests as google_requests

load_dotenv()

# --- CONFIGURAÇÕES GERAIS ---
SECRET_KEY = os.getenv("SECRET_KEY", "sua_chave_secreta_super_segura")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 dias de login

# Configuração do Banco de Dados (Pega do Render/Neon)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback para teste local se esquecer a env
    DATABASE_URL = "sqlite:///./teste_local.db" 

# Corrige URL do Postgres se vier com 'postgres://' (padrão antigo do Render)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Ferramenta de Hash de Senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
security_basic = HTTPBasic()

app = FastAPI(title="MoneyLayer SaaS V15")

# CORS (Permite que o navegador aceite requisições)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. MODELOS DO BANCO DE DADOS (Tabelas)
# ==========================================

class UsuarioBD(Base):
    __tablename__ = "users" # Mudei para inglês para evitar conflitos antigos
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String) # Senha Criptografada
    role = Column(String, default="user") # 'admin' ou 'user'
    
    # Dados da Empresa (Perfil)
    nome_empresa = Column(String, nullable=True)
    cnpj_cpf = Column(String, nullable=True)
    telefone = Column(String, nullable=True)
    endereco_completo = Column(String, nullable=True)

class TransacaoBD(Base):
    __tablename__ = "transacoes"
    
    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String)
    valor = Column(Float)
    tipo = Column(String) # 'receita' ou 'despesa'
    instituicao = Column(String)
    forma_pagamento = Column(String)
    qtd_parcelas = Column(Integer)
    data_vencimento = Column(String) # Guardando como ISO String (YYYY-MM-DD)
    tipo_documento = Column(String)
    numero_documento = Column(String, nullable=True)
    
    # BLINDAGEM: Dono da Transação
    dono_id = Column(Integer, ForeignKey("users.id"))
    dono = relationship("UsuarioBD")

# --- RECRIAR TABELAS (ATENÇÃO: ISSO RESETA O BANCO PARA APLICAR MUDANÇAS) ---
# Se quiser limpar tudo e começar do zero, descomente a linha abaixo UMA VEZ:
# Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ==========================================
# 2. SISTEMA DE SEGURANÇA (O Cérebro) 🧠
# ==========================================

def criar_token_jwt(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    authorization: Optional[str] = Header(None), # Lê o Header "Authorization"
    db: Session = Depends(get_db)
):
    """
    Função Híbrida: Aceita tanto 'Basic Auth' (Login manual antigo)
    quanto 'Bearer Token' (Login Google/Novo)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Não autenticado")

    # CASO 1: Login Manual (Basic Auth)
    if authorization.startswith("Basic "):
        import base64
        try:
            encoded = authorization.split(" ")[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, senha = decoded.split(":")
            
            # Verifica no Banco
            user = db.query(UsuarioBD).filter(UsuarioBD.username == username).first()
            if not user or not pwd_context.verify(senha, user.hashed_password):
                raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
            return user
        except:
            raise HTTPException(status_code=401, detail="Erro no login manual")

    # CASO 2: Login Moderno (Bearer Token / JWT)
    elif authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None: raise HTTPException(status_code=401)
            
            user = db.query(UsuarioBD).filter(UsuarioBD.username == username).first()
            if user is None: raise HTTPException(status_code=401)
            return user
        except JWTError:
            raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    
    else:
        raise HTTPException(status_code=401, detail="Método de autenticação não suportado")

# ==========================================
# 3. MODELOS DE DADOS (Pydantic)
# ==========================================
class GoogleToken(BaseModel):
    token: str

class UsuarioSignup(BaseModel):
    username: str
    password: str

class TransacaoInput(BaseModel):
    descricao: str
    valor: float
    tipo: str
    instituicao: str
    forma_pagamento: str
    qtd_parcelas: int = 1
    data_base: str # Espera data em string (YYYY-MM-DD)
    tipo_documento: str
    numero_documento: Optional[str] = None

class PerfilInput(BaseModel):
    nome_empresa: Optional[str] = None
    cnpj_cpf: Optional[str] = None
    telefone: Optional[str] = None
    endereco_completo: Optional[str] = None

# ==========================================
# 4. ROTAS DO SISTEMA
# ==========================================

@app.get("/")
def home():
    if os.path.exists("index.html"): return FileResponse("index.html")
    return {"msg": "API MoneyLayer Online 🚀"}

# --- ROTA 1: SIGN UP (CRIAR CONTA MANUAL) ---
@app.post("/signup")
def cadastrar_usuario(dados: UsuarioSignup, db: Session = Depends(get_db)):
    # Verifica duplicidade
    if db.query(UsuarioBD).filter(UsuarioBD.username == dados.username).first():
        raise HTTPException(400, "Usuário já existe.")
    
    # Cria usuário com senha criptografada
    novo = UsuarioBD(
        username=dados.username,
        hashed_password=pwd_context.hash(dados.password),
        role="user"
    )
    db.add(novo); db.commit()
    return {"msg": "Criado com sucesso"}

# --- ROTA 2: LOGIN COM GOOGLE ---
@app.post("/auth/google")
def login_google(dados: GoogleToken, db: Session = Depends(get_db)):
    try:
        # 1. Valida o token com o Google
        # IMPORTANTE: Substitua pelo SEU CLIENT_ID do Google Cloud
        CLIENT_ID = "344647037718-DK6q4Jgad9g8NTMKuWJaovRBCxvKXMYzta.apps.googleusercontent.com"
        
        idinfo = id_token.verify_oauth2_token(dados.token, google_requests.Request(), CLIENT_ID)
        email = idinfo['email']

        # 2. Verifica/Cria Usuário
        user = db.query(UsuarioBD).filter(UsuarioBD.username == email).first()
        if not user:
            # Cria conta automática para usuário Google
            senha_random = str(uuid.uuid4())
            user = UsuarioBD(
                username=email, 
                hashed_password=pwd_context.hash(senha_random),
                role="user"
            )
            db.add(user); db.commit(); db.refresh(user)
        
        # 3. Gera nosso Token de Acesso
        access_token = criar_token_jwt(data={"sub": user.username})
        return {"access_token": access_token, "token_type": "bearer"}
        
    except ValueError:
        raise HTTPException(401, "Token Google Inválido")

# --- ROTA 3: CRIAR TRANSAÇÃO (BLINDADA) ---
@app.post("/lancar/")
def criar_transacao(
    d: TransacaoInput, 
    db: Session = Depends(get_db), 
    usuario: UsuarioBD = Depends(get_current_user)
):
    try:
        data_base = datetime.strptime(d.data_base[0:10], "%Y-%m-%d")
    except:
        data_base = datetime.now()

    valor_parcela = d.valor / d.qtd_parcelas
    
    for i in range(d.qtd_parcelas):
        prox_mes = data_base + relativedelta(months=i)
        desc_final = d.descricao
        if d.qtd_parcelas > 1:
            desc_final = f"{d.descricao} ({i+1}/{d.qtd_parcelas})"

        nova = TransacaoBD(
            descricao=desc_final,
            valor=valor_parcela,
            tipo=d.tipo,
            instituicao=d.instituicao,
            forma_pagamento=d.forma_pagamento,
            qtd_parcelas=d.qtd_parcelas,
            data_vencimento=prox_mes.strftime("%Y-%m-%d"),
            tipo_documento=d.tipo_documento,
            numero_documento=d.numero_documento,
            dono_id=usuario.id # <--- AQUI ESTÁ A SEGURANÇA (Dono = Usuário Logado)
        )
        db.add(nova)
    
    db.commit()
    return {"msg": "Lançamento Salvo"}

# --- ROTA 4: EXTRATO (BLINDADO) ---
@app.get("/extrato")
def ver_extrato(db: Session = Depends(get_db), usuario: UsuarioBD = Depends(get_current_user)):
    # FILTRA: Só traz onde dono_id == meu id
    lista = db.query(TransacaoBD).filter(TransacaoBD.dono_id == usuario.id).all()
    
    # Ordena no Python para garantir
    lista.sort(key=lambda x: x.data_vencimento, reverse=True)
    return lista

# --- ROTA 5: SALDO (BLINDADO) ---
@app.get("/saldo")
def ver_saldo(db: Session = Depends(get_db), usuario: UsuarioBD = Depends(get_current_user)):
    # FILTRA: Só soma o que é meu
    lista = db.query(TransacaoBD).filter(TransacaoBD.dono_id == usuario.id).all()
    
    entradas = sum(t.valor for t in lista if t.tipo == "receita")
    saidas = sum(t.valor for t in lista if t.tipo == "despesa")
    
    return {
        "entradas": entradas,
        "saidas": saidas,
        "saldo_final": entradas - saidas,
        "usuario_funcao": usuario.role
    }

# --- ROTA 6: PERFIL DA EMPRESA ---
@app.get("/usuario/perfil")
def get_perfil(db: Session = Depends(get_db), usuario: UsuarioBD = Depends(get_current_user)):
    # Retorna o perfil do próprio usuário logado
    return usuario

@app.put("/usuario/perfil")
def update_perfil(dados: PerfilInput, db: Session = Depends(get_db), usuario: UsuarioBD = Depends(get_current_user)):
    usuario.nome_empresa = dados.nome_empresa
    usuario.cnpj_cpf = dados.cnpj_cpf
    usuario.telefone = dados.telefone
    usuario.endereco_completo = dados.endereco_completo
    db.commit()
    return {"msg": "Perfil atualizado"}

# --- ROTA 7: DELETAR ---
@app.delete("/transacao/{id}")
def deletar(id: int, db: Session = Depends(get_db), usuario: UsuarioBD = Depends(get_current_user)):
    # Só deleta se o ID for igual E o DONO for o usuário logado
    t = db.query(TransacaoBD).filter(TransacaoBD.id == id, TransacaoBD.dono_id == usuario.id).first()
    if not t: raise HTTPException(404, "Não encontrado ou sem permissão")
    db.delete(t)
    db.commit()
    return {"msg": "Apagado"}

# --- ROTA ADMIN: CRIAR USUÁRIOS MANUALMENTE ---
@app.post("/admin/usuarios")
def admin_criar(dados: UsuarioSignup, db: Session = Depends(get_db), usuario: UsuarioBD = Depends(get_current_user)):
    if usuario.role != 'admin':
        raise HTTPException(403, "Apenas Admin")
    
    novo = UsuarioBD(username=dados.username, hashed_password=pwd_context.hash(dados.password), role="funcionario")
    db.add(novo); db.commit()
    return {"msg": "Funcionário criado"}