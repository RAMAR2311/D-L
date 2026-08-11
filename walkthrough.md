# Walkthrough: Eliminación de Traslados No Facturados para Administradores

Se implementó la funcionalidad para que únicamente los **Administradores** puedan eliminar registros de traslados de mercancía, garantizando la restricción estricta de que **no se permite eliminar traslados que ya hayan sido facturados** en una venta real.

---

## Cambios Implementados

1. **Restricción y Control de Eliminación (`routes/traslados.py`)**:
   - Se añadió el endpoint `@traslados_bp.route('/<int:id>/eliminar', methods=['POST'])` exclusivo para administradores (`@admin_required`).
   - **Si el traslado ya fue facturado (`es_facturado = True` o `sale_id != None`)**: El sistema bloquea la acción y muestra la alerta: *"No es posible eliminar este traslado porque ya fue facturado en una venta real."*
   - **Si el traslado NO fue facturado**: El sistema elimina el registro y **devuelve automáticamente la cantidad de mercancía a la sede de origen**, restándola de la sede de destino.

2. **Diferenciación de Estado en la Tabla (`templates/traslados/index.html`)**:
   - Se agregó la columna **`ESTADO / ACCIÓN`** en el historial del módulo de traslados:
     - 🟢 **Badge `Facturado`:** Para aquellos traslados asociados a tickets de venta facturados. No muestra botón de eliminar.
     - 🟡 **Badge `No Facturado`:** Para traslados manuales o pendientes. Muestra el botón 🗑️ **`Eliminar`** únicamente para Administradores.

3. **Modelo de Datos (`models.py`)**:
   - Se añadieron las columnas `sale_id` y `es_facturado` al modelo `StockTransfer`.

---

## Verificación Realizada

- **Test Automatizado:**
  - Intento de eliminar traslado con `es_facturado=True`: **Bloqueado exitosamente** (permanece intacto en BD).
  - Intento de eliminar traslado manual con `es_facturado=False`: **Eliminado con éxito** y stock revertido al origen.
- **Despliegue a Git:** Código subido a GitHub (`RAMAR2311/D-L`).
