# Walkthrough: Módulo Independiente de Traslados entre Sedes en el Menú Principal y Dashboard

Hemos elevado el módulo de **Traslados entre Sedes** a un **módulo principal e independiente** en la barra lateral del sistema y agregado su correspondiente tarjeta de métricas en el Dashboard Principal.

---

## Cambios Implementados

1. **Opción Directa en el Menú Lateral (`templates/base.html`)**:
   - Ahora aparece como una opción destacada independiente: **`🚚 Traslados entre Sedes`** directamente en el menú de la izquierda, visible tanto para Administradores como para Vendedores.
2. **Tarjeta de Métricas en el Dashboard (`templates/admin/dashboard.html` & `routes/admin.py`)**:
   - Se añadió la tarjeta **Traslados entre Sedes** en el Dashboard Principal con el conteo de movimientos registrados y enlace directo a la auditoría del módulo.

---

## Verificación Realizada

- **Test Automatizado:** Ejecutados tests de renderizado para `/admin/dashboard` y `/traslados/`. Resultado: **200 OK**.
- **Despliegue a Git:** Cambios subidos correctamente al repositorio GitHub (`RAMAR2311/D-L`).
