from app import create_app, db
from sqlalchemy import inspect, text

def migrar():
    app = create_app()
    with app.app_context():
        print("=== INICIANDO MIGRACION AUTOMATICA DE BASE DE DATOS ===")
        # 1. Crear tablas nuevas que no existan aún (ej: treasury_adjustments)
        db.create_all()
        print("[OK] Verificacion de tablas base y nuevas completada (db.create_all).")

        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        columnas_a_verificar = [
            # (tabla, columna, definicion_sql)
            ('punto_transactions', 'asesor_id', 'INTEGER NULL'),
            ('arqueo_caja', 'asesor_id', 'INTEGER NULL'),
            ('provider_payments', 'asesor_id', 'INTEGER NULL'),
            ('provider_payments', 'fecha_pago', 'TIMESTAMP NULL'),
            ('provider_payments', 'comprobante', 'VARCHAR(255) NULL'),
            ('provider_payments', 'observaciones', 'TEXT NULL'),
            ('abonos_bodega', 'asesor_id', 'INTEGER NULL'),
            ('maneos', 'asesor_id', 'INTEGER NULL'),
            ('users', 'permitir_fecha_retroactiva', 'BOOLEAN DEFAULT FALSE NOT NULL'),
            ('local_configs', 'permitir_fecha_retroactiva', 'BOOLEAN DEFAULT FALSE NOT NULL'),
        ]

        with db.engine.connect() as conn:
            for tabla, columna, tipo_sql in columnas_a_verificar:
                if tabla in existing_tables:
                    cols = [c['name'] for c in inspector.get_columns(tabla)]
                    if columna not in cols:
                        print(f"-> Agregando columna '{columna}' a tabla '{tabla}'...")
                        try:
                            conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo_sql};"))
                            conn.commit()
                            print(f"[OK] Columna '{columna}' agregada exitosamente a '{tabla}'.")
                        except Exception as e:
                            print(f"[ERROR] Agregando {columna} a {tabla}: {e}")
                    else:
                        print(f"[OK] Columna '{columna}' ya existe en '{tabla}'.")
                else:
                    print(f"[INFO] Tabla '{tabla}' no existe en esta base de datos.")

        print("\n=== MIGRACION FINALIZADA CON EXITO ===")

if __name__ == '__main__':
    migrar()
