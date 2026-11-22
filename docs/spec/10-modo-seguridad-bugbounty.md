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
  distintos caminos), siempre como guía de verificación, no como ejecución automática.

## Límites / Guardarraíles (NFR-030 — son REQUISITOS, van como código, no solo prompt)
- **G-1 Gate de alcance y autorización.** No se puede usar el modo sin un `engagement` con
  `autorizacion_confirmada=1` y un alcance declarado (ST-030, SCR-020). Sin eso, el chat está bloqueado.
- **G-2 Nada de ejecución autónoma ofensiva.** La IA no lanza ataques por su cuenta. Si existe integración
  con tus herramientas (MCP a Burp/Caido/ZAP), es **solo lectura** o **cada acción activa requiere tu
  confirmación explícita** (API-002b). Por defecto, el modo funciona pegando/importando datos.
- **G-3 Lista "nunca".** La IA no genera malware ni exploits armados listos para causar daño, ni ayuda a
  atacar objetivos **fuera de alcance** o sin autorización, ni a ocultar la actividad. Si una petición
  cruza esa línea, responde explicando el límite y reconduce a lo que sí puede (análisis, verificación
  segura dentro de alcance, informe).
- **G-4 Enfoque defensivo/responsable.** La orientación prioriza verificación de bajo impacto, respeto del
  alcance y del programa, y divulgación responsable.
- **G-5 Auditoría.** Cambios de alcance, confirmaciones de acciones y envíos a Nube se registran (DB-008).

> Estos límites no te quitan capacidad para tu trabajo legítimo de bug bounty: encajan exactamente con tu
> flujo (la IA orienta, tú ejecutas con tu licencia, la IA redacta el informe). Lo que evitan es que la
> herramienta se convierta en algo que ataque solo o actúe donde no debe.

## Tono y fricción: ver `21-politica-de-restricciones.md`
La **Política de Restricciones** (doc 21) fija el tono: **mínima fricción en lo legítimo**. El Modo
Seguridad debe ayudar a tope con reconocimiento, fuzzing, scripts de prueba (incl. credenciales en scope),
PoCs que demuestren el fallo y uso de frameworks (Metasploit/Hydra/ffuf/Burp/nuclei), **sin moralinas**,
sobre objetivos autorizados. Los guardarraíles G-1..G-5 de abajo (gate, no malware para dañar, no fuera de
alcance, auditoría) se mantienen como código: son el mínimo, no la fricción.

## Prompt de sistema (resumen; final en `prompts/seguridad.txt`)
- Rol: analista de seguridad que asiste a un investigador de bug bounty **autorizado**.
- Siempre: recuerda el alcance activo; enmarca todo como verificación dentro de alcance; no produce
  payloads destructivos ni pasos para dañar; ante lo dudoso, explica el límite (G-3) y ofrece la vía
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
