# Walkthrough: Corrección del Service Worker (`sw.js`) para Subida de Fotos

Se corrigió la configuración del Service Worker PWA (`static/sw.js`) para evitar que el caché de la aplicación interceptara envíos de formularios HTTP POST y la subida de fotos de productos.

---

## Cambios Implementados

1. **Exclusión Estricta de Peticiones POST/PUT/DELETE (`static/sw.js`)**:
   - Se incluyó la validación:
     ```javascript
     if (event.request.method !== 'GET') {
         return; // Pasa directo a la red sin ser interceptado por el Service Worker
     }
     ```
   - Ahora el navegador envía las fotografías pesadas (desde celular y computador) directamente al servidor Flask sin pasar por la capa de caché.

2. **Exclusión de Rutas Dinámicas de la App**:
   - Rutas como `/inventory`, `/sales`, `/admin`, `/traslados`, etc. no se guardan en caché local ni interfieren en los envíos de datos.

3. **Actualización de Versión de Caché (`koba-app-v3`)**:
   - Se incrementó la versión a `koba-app-v3` para invalidar y limpiar automáticamente el Service Worker antiguo en los celulares y computadores de los usuarios.

---

## Verificación Realizada

- **Endpoint `/sw.js`:** Respuesta **200 OK** verificada.
- **Git Push:** Cambios subidos correctamente a GitHub (`RAMAR2311/D-L`).
