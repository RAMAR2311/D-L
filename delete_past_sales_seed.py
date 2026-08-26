from app import create_app
from models import db, Sale, SaleDetail

app = create_app()

with app.app_context():
    sample_names = [
        "Funda Silicona iPhone 14 Pro",
        "Vidrio Templado 9D",
        "Cargador Rápido 20W USB-C",
        "Audífonos Bluetooth ProMax",
        "Cable Carga Rápida 2m",
        "Soporte Celular Auto MagSafe",
        "Powerbank 10.000 mAh Slim",
        "Cable USB-C 1m Trenzado",
        "Anillo de Luz LED Selfie",
        "Funda Uso Rudo Samsung S23",
        "Vidrio Cámara Trasera"
    ]
    
    detalles = SaleDetail.query.filter(SaleDetail.nombre_manual.in_(sample_names)).all()
    sale_ids = list(set([d.sale_id for d in detalles if d.sale_id]))
    
    deleted_count = 0
    for sid in sale_ids:
        sale = Sale.query.get(sid)
        if sale:
            db.session.delete(sale)
            deleted_count += 1
            
    db.session.commit()
    print(f"Eliminadas exitosamente {deleted_count} ventas de prueba.")
