# Walkthrough: Columna de Sede / Local en la Vista Central del Historial de Ventas

Hemos añadido la columna **SEDE / LOCAL** en el **Historial de Registro de Ventas** cuando te encuentras en la vista **Central (Todos)**.

---

## Cambio Implementado

- **Visualización en Vista Central (`templates/sales/historial.html`)**:
  - Al ingresar al Historial de Ventas seleccionando el botón **Central (Todos)** (`/sales/historial?local=central`), la tabla despliega una nueva columna llamada **`SEDE / LOCAL`** entre *Fecha de Cobro* y *Vendedor Responsable*.
  - Muestra la sede donde se originó cada transacción con su respectivo identificador visual:
    - 🏪 **D&L 1** (Badge azul)
    - 🏪 **D&L 2** (Badge turquesa)
    - 🏪 **D&L 3** (Badge verde)

---

## Verificación Realizada

- **Test Automatizado:** Ejecutado test de renderizado con `active_local = 'central'`. Respuesta: **200 OK**.
- **Despliegue a Git:** Cambios subidos correctamente al repositorio GitHub (`RAMAR2311/D-L`).
