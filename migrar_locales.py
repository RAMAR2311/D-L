from dotenv import load_dotenv
load_dotenv()

from app import create_app
from models import db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    print("Iniciando migracion de stock para 3 locales...")
    inspector = inspect(db.engine)
    existing_tables = inspector.get_table_names()
    print("Conectado a BD URI:", app.config['SQLALCHEMY_DATABASE_URI'])
    print("Tablas encontradas:", existing_tables)

    with db.engine.connect() as conn:
        for tname in ['products', 'productos']:
            if tname in existing_tables:
                for col in ['stock_local_1', 'stock_local_2', 'stock_local_3']:
                    conn.execute(text(f"ALTER TABLE {tname} ADD COLUMN IF NOT EXISTS {col} INTEGER NOT NULL DEFAULT 0;"))
                conn.execute(text(f"""
                    UPDATE {tname} 
                    SET stock_local_1 = cantidad_stock 
                    WHERE (stock_local_1 = 0 AND stock_local_2 = 0 AND stock_local_3 = 0) AND cantidad_stock > 0;
                """))
                print(f"Columnas creadas y stock migrado en tabla '{tname}'.")

        for vname in ['product_variants', 'variantes']:
            if vname in existing_tables:
                for col in ['stock_local_1', 'stock_local_2', 'stock_local_3']:
                    conn.execute(text(f"ALTER TABLE {vname} ADD COLUMN IF NOT EXISTS {col} INTEGER NOT NULL DEFAULT 0;"))
                conn.execute(text(f"""
                    UPDATE {vname} 
                    SET stock_local_1 = cantidad_stock 
                    WHERE (stock_local_1 = 0 AND stock_local_2 = 0 AND stock_local_3 = 0) AND cantidad_stock > 0;
                """))
                print(f"Columnas creadas y stock migrado en tabla '{vname}'.")

        conn.commit()

print("Migracion completada exitosamente.")
