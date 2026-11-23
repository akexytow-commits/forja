# 10 — Modo Seguridad / Bug Bounty (MOD-030)

Asistente de **investigación de seguridad autorizada**. Tu flujo (según lo que describiste): la IA analiza
y te dice **por dónde enfocar** y **qué problemas** podrías tener; **tú**, con tu licencia y tus
herramientas, lo compruebas y validas; luego le pides que **redacte el informe** para enviarlo al programa
de bug bounty. La IA **orienta y documenta**; **tú ejecutas y validas**.

## Dos ejes del Modo Seguridad
- **Enfoque**: **Ofensivo** (red team) o **Defensivo** (blue team) — selector nuevo (FR-035).
- **Actividad**: **Trabajo** (bug bounty autorizado — este documento) o **Aprender** (la **Academia**,
  estilo HTB/TryHackMe, detallada en `18-modo-seguridad-aprendizaje.md`, módulo MOD-090).

Ambas actividades comparten los guardarraíles de abajo. La Academia añade además un gate de "entorno de
laboratorio autorizado" (FR-038).

## Papel de la IA (lo que SÍ hace)
- Analiza datos de **reconocimiento que tú aportas** (salida de tus herramientas, notas, respuestas HTTP
  que tú pegues) y señala **clases de problema** plausibles y **dónde mirar**.
- Explica el **posible impacto** y cómo **tú** podrías verificarlo de forma segura y dentro de alcance.
- Ayuda a **organizar hallazgos** y a **redactar informes** claros y presentables a partir de la
  evidencia que **tú** validaste.
- Sugiere **varios ángulos** para confirmar una misma hipótesis (como pediste: llegar a la misma idea por
  distintos caminos), siempre como guía de verificación, no como ejecución automáta

## Tono y fricción: ver `21-politica-de-restricciones.md`
.
## Prompt de sistema (resumen; final en `prompts/seguridad.txt`)
- Rol: analista de seguridad que asiste a un investigador de bug bounty **autorizado**.
- Siempre: recuerda el alcance activo; enmarca todo como verificación dentro de alcance;  produce
  payloads destructivos pasos para dañar; ante lo dudoso, explica el límite (G-3) y ofrece la vía
  responsable.
- Salidas útiles: lista priorizada de "dónde enfocar", clases de problema, cómo verificarlo con seguridad,
  qué evidencia hace falta para un buen informe.

## Pantallas y botones
### SCR-020 — Alcance y autorización (GATE)
- **BTN-037 Nuevo engagement** → nombre + alcance (dominios/activos).
- **BTN-038 Confirmar autorización** → checkbox + confirmación: "Declaro que tengo autorización para
  probar estos activos (programa de bug bounty / permiso explícito)." Sin esto, no se desbloquea (ST-030).
- **BTN-039 Entrar al engagement** → desbloquea SCR-021/022/023. Registra en auditoría (DB-008).

### SCR-021 — Análisis de reconocimiento
- Campo grande para **pegar/importar** datos (tu recon). **BTN-041 Importar archivo**.
- **BTN-042 Analizar** → API-051 → crea `findings` en estado `idea` con "dónde enfocar" y clase.
- El chat queda disponible para profundizar ("¿cómo verifico X dentro de alcance?").

### SCR-023 — Hallazgos
- Lista de `findings` (DB-006b) con estado. 
- **BTN-043 Marcar validado por mí** → cambia a `validado_por_usuario` + adjuntar evidencia (API-052).
- **BTN-044 Añadir hallazgo manual** → por si tú detectas algo y quieres documentarlo.

### SCR-022 — Redactor de informe
- **BTN-040 Generar informe** → API-053. Puedes subir **dos enfoques/evidencias** y pedir que los **una**
  en un informe presentable (justo tu caso de uso). Resultado editable en `informe_md`.
- **BTN-045 Exportar informe** → API-062 (Markdown/archivo) para enviarlo al programa.

## Flujo completo (tu caso de uso, explícito)
1. Declaras alcance + autorización (SCR-020) → entras.
2. Pegas tu recon → **Analizar** → la IA te dice **por dónde enfocar** y **qué problemas** podrías tener.
3. **Tú**, con tu licencia/herramientas, lo compruebas; pruebas **varios caminos** para la misma idea.
4. Marcas lo validado y adjuntas evidencia (los "dos enfoques").
5. **Generar informe** → la IA une ambos en un informe presentable → **Exportar** → lo envías al programa.

## Pruebas asociadas
TST-030 (gate bloquea sin autorización), TST-031 (análisis crea findings), TST-032 (no ejecuta acciones /
pide confirmación), TST-033 (rechazo de petición fuera de límites G-3), TST-034 (informe une dos enfoques).
