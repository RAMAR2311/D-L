from dotenv import load_dotenv
load_dotenv()

from app import create_app
from models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Iniciando migracion de columna descontar_inventario en productos y variantes...")
    
    with db.engine.connect() as conn:
        # Agregar columna descontar_inventario a productos si no existe
        conn.execute(text("""
            ALTER TABLE products ADD COLUMN IF NOT EXISTS descontar_inventario BOOLEAN NOT NULL DEFAULT FALSE;
        """))
        
        # Agregar columna descontar_inventario a product_variants si no existe
        conn.execute(text("""
            ALTER TABLE product_variants ADD COLUMN IF NOT EXISTS descontar_inventario BOOLEAN NOT NULL DEFAULT FALSE;
        """))
        
        conn.commit()

    print("Columnas descontar_inventario agregadas exitosamente a products y product_variants.")

print("Migracion completada exitosamente.")
