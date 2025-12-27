from fastapi import FastAPI
from routes import auth, transacoes, usuarios

app = FastAPI(title="MoneyLayer SaaS")

# ⚠️ NÃO usar Base.metadata.create_all quando há Alembic
# As tabelas serão criadas via migrations

app.include_router(auth.router)
app.include_router(transacoes.router)
app.include_router(usuarios.router)

@app.get("/")
def home():
    return {"status": "API Online 🚀"}
