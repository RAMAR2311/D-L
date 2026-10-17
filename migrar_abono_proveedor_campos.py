from dotenv import load_dotenv
load_dotenv()

from app import create_app
from models import db
from sqlalchemy import inspect, text

app = create_app()

with app.app_context():
    print("Iniciando migración segura y compatible para provider_payments...")
    
    inspector = inspect(db.engine)
    existing_columns = [col['name'] for col in inspector.get_columns('provider_payments')]
    print("Columnas actuales:", existing_columns)
    
    columns_to_add = [
        ("metodo_pago", "VARCHAR(50) DEFAULT 'efectivo' NOT NULL"),
        ("usuario_id", "INTEGER"),
        ("local_id", "INTEGER DEFAULT 1"),
        ("expense_id", "INTEGER"),
        ("comprobante", "VARCHAR(255)")
    ]
    
    with db.engine.connect() as conn:
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                print(f"Agregando columna {col_name} ({col_type})...")
                conn.execute(text(f"ALTER TABLE provider_payments ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"-> Columna {col_name} agregada.")
            else:
                print(f"-> Columna {col_name} ya existe. Omitiendo.")

    # Verificar de nuevo
    inspector_updated = inspect(db.engine)
    cols_now = [col['name'] for col in inspector_updated.get_columns('provider_payments')]
    print("Columnas finales en provider_payments:", cols_now)

print("Migración completada exitosamente.")
