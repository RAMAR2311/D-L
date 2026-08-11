# Walkthrough: Solución al Error de Subida de Fotos en "Editar Producto Maestro"

Se analizaron y corrigieron **dos causas raíz** que impedían la subida y actualización de fotos de productos maestros al ingresar al formulario de edición.

---

## Análisis de Causas Raíz

1. **Inclusión de Scripts en la Plantilla Base (`templates/base.html`)**:
   - En la plantilla `templates/inventory/form.html`, el código JavaScript encargado de la **compresión client-side y generación de la imagen optimizada Base64** estaba dentro de un bloque `{% block scripts %}`.
   - Sin embargo, la plantilla principal `base.html` no tenía definido `{% block scripts %}{% endblock %}` al final del archivo.
   - Como resultado, **Jinja omitía el script de compresión de imágenes al editar un producto**, obligando al navegador a enviar la foto pesada sin comprimir y provocando que el servidor o la red rechazaran la carga.

2. **IndexError en la Lectura de Precios de Variantes (`routes/inventory.py`)**:
   - Al guardar la edición del producto, el backend intentaba leer `v_costos[i]` y `v_mins[i]` sin verificar la longitud del arreglo. Como las variantes no envían esos campos en el formulario, Python arrojaba un error `IndexError: list index out of range`, deshaciendo la transacción (`db.session.rollback()`) y mostrando una alerta de error.

---

## Cambios Implementados

1. **Inclusión de `{% block scripts %}` en `templates/base.html`**:
   - Se añadió la etiqueta `{% block scripts %}{% endblock %}` al final de `base.html` para garantizar que la compresión e inserción Base64 se ejecute en la vista de edición.

2. **Validación de Límites en Arreglos de Variantes (`routes/inventory.py`)**:
   - Se actualizó la lectura de `costo_v`, `min_v` y `sug_v` con validación de longitud de lista (`i < len(...)`).

---

## Verificación Realizada

- **Test Automatizado:** Edición exitosa de producto maestro enviando imagen Base64:
  - Estado HTTP: `302 FOUND` (Redirección limpia a `/inventory`).
  - `db.session.commit()`: Exitoso.
  - Actualización de imagen: **1e2d9d4d.jpg** guardada correctamente.
- **Despliegue a Git:** Código subido a GitHub (`RAMAR2311/D-L`).
