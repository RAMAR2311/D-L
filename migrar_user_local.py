from dotenv import load_dotenv
load_dotenv()

from app import create_app
from models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Iniciando migracion de columna local_asignado en tabla users...")
    
    with db.engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS local_asignado INTEGER DEFAULT 1;
        """))
        conn.commit()

    print("Columna local_asignado agregada exitosamente a la tabla users.")

print("Migracion completada exitosamente.")
