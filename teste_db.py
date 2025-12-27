from app.database import SessionLocal, engine
from sqlalchemy import text

def testar_conexao():
    try:
        # Tenta abrir uma conexão e rodar um comando simples
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        print("✅ Conexão com o banco de dados estabelecida com sucesso!")
        db.close()
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")

if __name__ == "__main__":
    testar_conexao()