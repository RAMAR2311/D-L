import logging
import traceback
from app import create_app
from models import db, Sale, ProductVariant, Product, PuntoTransaction, StockTransfer

logging.basicConfig(level=logging.INFO)
app = create_app()
with app.app_context():
    try:
        venta = Sale.query.first()
        if not venta:
            print('No hay ventas registradas para probar.')
        else:
            print(f'Probando anulación segura de Venta #{venta.id} (Local {venta.local_id})')
            loc_id = venta.local_id or 1
            for detalle in venta.detalles:
                if detalle.variant_id:
                    variante = ProductVariant.query.with_for_update().get(detalle.variant_id)
                    producto = Product.query.with_for_update().get(detalle.product_id)
                    print(f'Variante: {variante.id if variante else "N/A"}, Producto: {producto.id if producto else "N/A"}')
                elif detalle.product_id:
                    producto = Product.query.with_for_update().get(detalle.product_id)
                    print(f'Producto: {producto.id if producto else "N/A"}')
            
            # PuntoTransactions asociadas
            for pt in PuntoTransaction.query.filter_by(sale_id=venta.id).all():
                db.session.delete(pt)

            # StockTransfers asociados
            for st in StockTransfer.query.filter_by(sale_id=venta.id).all():
                db.session.delete(st)

            print('Simulación de verificación exitosa.')
    except Exception as e:
        print('Error:', e)
        traceback.print_exc()
        db.session.rollback()
