from dotenv import load_dotenv
load_dotenv()

from app import create_app
from models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Iniciando migracion de columna local_id en tabla arqueo_caja...")
    
    with db.engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE arqueo_caja ADD COLUMN IF NOT EXISTS local_id INTEGER DEFAULT 1;
        """))
        conn.commit()

    print("Columna local_id agregada exitosamente a la tabla arqueo_caja.")

print("Migracion completada exitosamente.")
