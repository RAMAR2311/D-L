import sys
from app import create_app, db
from sqlalchemy import inspect, text

def migrar():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        
        # 1. users table
        user_cols = [c['name'] for c in inspector.get_columns('users')]
        if 'permitir_fecha_retroactiva' not in user_cols:
            print("Agregando columna 'permitir_fecha_retroactiva' a la tabla 'users'...")
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN permitir_fecha_retroactiva BOOLEAN DEFAULT 0 NOT NULL"))
                conn.commit()
            print("Columna 'permitir_fecha_retroactiva' agregada con éxito a 'users'.")
        else:
            print("La columna 'permitir_fecha_retroactiva' ya existe en 'users'.")
            
        # 2. local_configs table
        local_cfg_cols = [c['name'] for c in inspector.get_columns('local_configs')]
        if 'permitir_fecha_retroactiva' not in local_cfg_cols:
            print("Agregando columna 'permitir_fecha_retroactiva' a la tabla 'local_configs'...")
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE local_configs ADD COLUMN permitir_fecha_retroactiva BOOLEAN DEFAULT 0 NOT NULL"))
                conn.commit()
            print("Columna 'permitir_fecha_retroactiva' agregada con éxito a 'local_configs'.")
        else:
            print("La columna 'permitir_fecha_retroactiva' ya existe en 'local_configs'.")

        print("Migración de permisos de fecha completada exitosamente.")

if __name__ == '__main__':
    migrar()
