import sys
from app import create_app, db
from sqlalchemy import inspect, text

def migrar():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        
        tablas_cols = {
            'arqueo_caja': 'asesor_id',
            'punto_transactions': 'asesor_id',
            'provider_payments': 'asesor_id',
            'abonos_bodega': 'asesor_id'
        }
        
        with db.engine.connect() as conn:
            for tabla, col in tablas_cols.items():
                if tabla in inspector.get_table_names():
                    cols_existentes = [c['name'] for c in inspector.get_columns(tabla)]
                    if col not in cols_existentes:
                        print(f"Agregando columna '{col}' a la tabla '{tabla}'...")
                        conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {col} INTEGER NULL"))
                        conn.commit()
                        print(f"Columna '{col}' agregada con éxito a '{tabla}'.")
                    else:
                        print(f"La columna '{col}' ya existe en '{tabla}'.")
                else:
                    print(f"Tabla '{tabla}' no existe en la base de datos.")
        
        print("Migración de asesor_id en movimientos completada exitosamente.")

if __name__ == '__main__':
    migrar()
