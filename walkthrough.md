# Walkthrough: Módulo de Traslados de Inventario entre Sedes y Solicitud Directa en Caja POS

Hemos implementado el sistema completo de **Traslados de Inventario entre Sedes**, permitiendo solicitar traslados de mercancía directamente desde la **Caja POS** cuando no hay existencias en el local actual, e integrando un **Módulo de Traslados** para auditoría y control.

---

## Características Implementadas

### 1. Solicitud Directa de Traslado en Caja POS (`templates/sales/caja_visual.html`)
- **Indicador Multi-Sede:** Cuando un producto o subcategoría (variante) no tiene stock en el local activo (ej: **D&L 1** con `0` unidades), la Caja POS detecta automáticamente si hay existencias en locales vecinos (ej: **D&L 2** o **D&L 3**).
- **Etiqueta y Botón Visual:** Muestra el aviso `🚚 Pedir Traslado (X disponibles en otras sedes)`.
- **Modal Emergente:** Al hacer clic, abre el modal flotante para seleccionar:
  - **Sede Origen:** Menú desplegable con los locales vecinos que tienen stock real.
  - **Sede Destino:** Preseleccionada la sede del POS actual.
  - **Cantidad:** Número de unidades a transferir.
  - **Asesor Solicitante:** Menú desplegable con los Asesores Comerciales activos.
  - **Observaciones:** Comentario opcional (ej: *"Solicitado desde POS para cliente en espera"*).
- **Carga Inmediata al Carrito:** Al confirmar el traslado:
  - Descuenta el stock de la Sede Origen y suma el stock a la Sede Destino de inmediato.
  - Registra el traslado en la base de datos.
  - **Carga el producto automáticamente al carrito de ventas del POS** para que el cajero proceda a facturar sin demoras.

### 2. Módulo de Traslados de Inventario (`/traslados`)
- **Visualización Administrador:** Pestañas multi-sede para filtrar entre `D&L CENTRAL`, `D&L 1`, `D&L 2` y `D&L 3`, o ver la consolidación global de todos los movimientos.
- **Visualización por Sede:** Para vendedores y administradores de sede, muestra únicamente las operaciones vinculadas a ese local (tanto mercancía **recibida** como **enviada**).
- **Detalle Completo por Operación:**
  - Fecha y hora exacta.
  - Producto y subcategoría.
  - Cantidad movilizada.
  - **Relación Origen ➔ Destino** (ej: `D&L 2 ➔ D&L 1`).
  - **Asesor Solicitante destacado**.
  - Cajero / Usuario que ejecutó la transacción.
  - Observaciones y motivos.

---

## Verificación Realizada

- **Modelo de Base de Datos:** Creada la tabla `stock_transfers` en PostgreSQL/SQLite.
- **Pruebas de Backend:** Test en Python simulando un traslado de 2 unidades desde D&L 2 a D&L 1:
  - Stock Origen (D&L 2): `10 ➔ 8`
  - Stock Destino (D&L 1): `0 ➔ 2`
  - Renderizado `/traslados`: **200 OK**.
- **Despliegue a Git:** Código compilado y subido correctamente al repositorio GitHub (`RAMAR2311/D-L`).
