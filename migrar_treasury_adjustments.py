import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'crm_inventory.db')

def migrar():
    print(f"Conectando a {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS treasury_adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_movimiento VARCHAR(20) NOT NULL DEFAULT 'ingreso',
        categoria VARCHAR(100) NOT NULL,
        concepto VARCHAR(255) NOT NULL,
        monto NUMERIC(12, 2) NOT NULL,
        metodo_pago VARCHAR(50) NOT NULL,
        local_id INTEGER NULL,
        fecha_efectiva DATETIME NOT NULL,
        fecha_registro DATETIME NOT NULL,
        usuario_id INTEGER NOT NULL REFERENCES users(id),
        asesor_id INTEGER NULL REFERENCES asesores(id),
        comprobante VARCHAR(255) NULL,
        grupo_operacion_id VARCHAR(50) NULL
    );
    """)

    # Indices para optimizar consultas de rango de fechas y métodos
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_treasury_adj_fecha ON treasury_adjustments(fecha_efectiva);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_treasury_adj_metodo ON treasury_adjustments(metodo_pago);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_treasury_adj_local ON treasury_adjustments(local_id);")

    conn.commit()
    conn.close()
    print("¡Tabla 'treasury_adjustments' creada e indexada exitosamente!")

if __name__ == '__main__':
    migrar()
