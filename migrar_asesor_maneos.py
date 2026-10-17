from app import create_app
from models import db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    print("--- Verificando columna asesor_id en la tabla 'maneos' ---")
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('maneos')]
    
    if 'asesor_id' not in columns:
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE maneos ADD COLUMN asesor_id INTEGER NULL REFERENCES asesores(id)"))
                conn.commit()
            print("[OK] Columna asesor_id agregada exitosamente a la tabla 'maneos'.")
        except Exception as e:
            print(f"Error al agregar columna asesor_id a 'maneos': {e}")
    else:
        print("[OK] Columna asesor_id ya existe en la tabla 'maneos'.")

    # Verificar que ahora esté presente
    inspector = inspect(db.engine)
    columns_after = [col['name'] for col in inspector.get_columns('maneos')]
    print("Columnas actuales en 'maneos':", columns_after)
