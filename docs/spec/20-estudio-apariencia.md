# 20 — Estudio de Apariencia (MOD-100) — el módulo del final

Dijiste que la imagen de la app se ve "un poco seca" y que se puede mejorar bastante. Este es el **módulo
del final**: un **Estudio de Apariencia** para dejar FORJA con la cara que tú quieras, con vista previa en
vivo. Sustituye y amplía el simple "Apariencia" de Ajustes (BTN-063 pasa a ser un acceso directo a aquí).

## Qué permite (FR-073)
- **Presets de tema:** varios temas listos (oscuro, claro, alto contraste, y un par con personalidad) para
  empezar con un clic. → BTN-095.
- **Color y acento:** editar el color de acento y los colores base, con contraste comprobado para que el
  texto siempre se lea. → BTN-096.
- **Tipografía y densidad:** elegir fuente (del sistema o una concreta) y densidad (compacta/cómoda). →
  BTN-097.
- **Fondo / imagen:** fondo liso, degradado suave o una imagen tuya (local) con opacidad para que no reste
  legibilidad. → BTN-098.
- **Vista previa en vivo y aplicar:** ves los cambios al momento sobre una maqueta de las pantallas reales;
  al aplicar se guardan y toda la app los toma. → BTN-099.
- **Por modo (opcional):** permitir un acento distinto por modo (p. ej. Seguridad en otro tono) para
  distinguirlos de un vistazo.

## Cómo se guarda
- Todo en `settings` con claves `ui.*` (ya existen): `ui.tema`, `ui.acento`, `ui.fuente`, `ui.densidad`,
  `ui.fondo`, `ui.acento_por_modo`. Al aplicar, la UI relee y repinta sin reiniciar.
- Encaja con el **Protocolo de Personalización** (`13-...md`): lo que decidas aquí queda persistido para que
  tú y Claude Code sigáis puliendo sin perder nada.

## Principios para que no quede "seca" (guía para el builder)
- Un color de acento con intención, fondos que llegan a los bordes, jerarquía tipográfica clara (título
  grande, cuerpo legible), espacios generosos y estados cuidados (vacío, cargando, error). Una sola
  animación sutil, desactivable. Coherencia clara/oscuro.
- La maqueta de vista previa debe mostrar los **dos selectores** y una conversación de ejemplo, para juzgar
  el resultado como se usa de verdad.

## Pantalla y botones
- **SCR-040 Estudio de Apariencia** (módulo MOD-100): contiene BTN-095..099.
- Acceso desde Ajustes (BTN-063 → abre SCR-040) y, opcionalmente, desde un icono en el shell.

## Datos / pruebas / orden
- Requisito **FR-073**. Prueba **TST-073** (aplicar un tema cambia la app y persiste, con contraste válido).
- Es la **Rama 8** (la última), "al final", como pediste: cuando el resto ya funciona, se le da la cara.
