# 13 — Protocolo de Personalización de Interfaces

Pediste que, al construir, Claude Code te **pregunte** cómo quieres cada interfaz antes de maquetarla. Este
documento es ese guion: para cada pantalla, qué está **fijado** (no se discute, viene de la ingeniería) y
qué debe **PREGUNTARTE** (decisiones de estética/UX que son tuyas). Así tú ya tienes toda la función
decidida y solo personalizas la forma.

> Regla para el builder: antes de implementar una pantalla, haz las preguntas `PREGUNTAR` de su bloque.
> Usa los `DEFAULT` si el usuario no responde. Nunca cambies lo `FIJADO`.

## Preguntas globales (una vez, al empezar)
- **PREGUNTAR G1 — Nombre de la app.** DEFAULT: "FORJA".
- **PREGUNTAR G2 — Tema visual.** Opciones: claro / oscuro / seguir el sistema. DEFAULT: oscuro.
- **PREGUNTAR G3 — Acento de color** (un color principal). DEFAULT: a elección del builder, sobrio.
- **PREGUNTAR G4 — Densidad** (compacta / cómoda). DEFAULT: cómoda.
- **PREGUNTAR G5 — Tipografía** (sistema / una concreta). DEFAULT: tipografía del sistema.
- **FIJADO:** idioma español; dos selectores (modo arriba, modelo/esfuerzo abajo); persistencia local.

## SCR-001 Shell + selectores
- FIJADO: selector de **modo arriba** (pestañas), selector de **modelo+esfuerzo abajo** junto al
  compositor; ambos siempre visibles.
- PREGUNTAR S1: ¿las pestañas de modo como texto, icono+texto o solo icono? DEFAULT: icono+texto.
- PREGUNTAR S2: ¿el selector de esfuerzo como segmentos [bajo|medio|extra] o como deslizador? DEFAULT:
  segmentos.
- PREGUNTAR S3: ¿mostrar el modelo real en uso (p. ej. "qwen3:4b") o solo el tier? DEFAULT: tier, con el
  modelo real en un tooltip.

## SCR-010 Chat Scripts/Firmware
- FIJADO: streaming, bloques de código con Copiar y Guardar, plantillas.
- PREGUNTAR SC1: ¿panel de proyectos a la izquierda fijo o desplegable? DEFAULT: desplegable.
- PREGUNTAR SC2: ¿tema de resaltado de código? DEFAULT: acorde al tema global.

## SCR-020/021/022/023 Seguridad
- FIJADO: gate de alcance/autorización (no se salta); análisis solo sobre datos que aportas; redactor de
  informes; guardarraíles.
- PREGUNTAR SG1: ¿el gate como pantalla a pantalla completa o como paso en un asistente? DEFAULT: pantalla
  completa (deja claro que es un control serio).
- PREGUNTAR SG2: ¿la lista de hallazgos como tabla o como tarjetas? DEFAULT: tabla.
- PREGUNTAR SG3: ¿plantilla de informe? (p. ej. estilo HackerOne con secciones Resumen/Impacto/Pasos/
  Evidencia/Mitigación). DEFAULT: esa estructura, editable.

## SCR-030/031 Tareas
- FIJADO: captura libre, botón Organizar, plan por días editable y persistente.
- PREGUNTAR ST1: ¿el plan como columnas tipo tablero (Hoy/Mañana/…) o como lista vertical por secciones?
  DEFAULT: columnas (tablero).
- PREGUNTAR ST2: ¿mostrar estimación de minutos y "carga del día"? DEFAULT: sí.

## SCR-006 Aviso de escalado
- FIJADO: explica motivo + qué se enviaría + decisión del usuario.
- PREGUNTAR SE1: ¿como modal que interrumpe o como banner no bloqueante? DEFAULT: modal para
  RECOMENDADO_NUBE, banner para JUSTO.

## SCR-007 Ajustes
- FIJADO: modelos, activar Nube (con clave en keyring), tema, carpeta de proyectos, umbrales del estimador.
- PREGUNTAR SA1: ¿agrupar ajustes por pestañas (Modelos / Nube / Apariencia / Avanzado) o una sola página?
  DEFAULT: pestañas.

## Cómo registrar tus respuestas
El builder guarda tus elecciones en `settings` (DB-001) con claves `ui.*` para que la app arranque ya con
tu estética y para poder regenerar/retocar sin volver a preguntar. (Esto permite que, más adelante, tú y
Claude Code sigáis "puliendo" cada interfaz sin perder lo decidido.)
