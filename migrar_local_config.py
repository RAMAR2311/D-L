from dotenv import load_dotenv
load_dotenv()

from app import create_app
from models import db, LocalConfig
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Iniciando migracion de configuracion por local...")
    
    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS local_configs (
                id SERIAL PRIMARY KEY,
                local_id INTEGER UNIQUE NOT NULL,
                descontar_inventario BOOLEAN NOT NULL DEFAULT FALSE,
                fecha_actualizacion TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """))
        conn.commit()

    # Asegurar filas para Local 1, Local 2 y Local 3
    for lid in [1, 2, 3]:
        cfg = LocalConfig.query.filter_by(local_id=lid).first()
        if not cfg:
            cfg = LocalConfig(local_id=lid, descontar_inventario=False)
            db.session.add(cfg)
    
    db.session.commit()
    print("Tabla local_configs verificada e inicializada para los 3 locales con descontar_inventario=False.")

print("Migracion de configuracion completada exitosamente.")
