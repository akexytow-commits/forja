# 19 — Laboratorio Linux integrado (para la Academia)

Tu idea: que desde FORJA, en la parte de laboratorio, puedas **saltar a un Linux con el contexto del
ejercicio** (un botón que te lleva al Linux con la info del lab), sin tener que salir y montar VirtualBox a
mano. Aquí va **hasta qué punto es posible en tu portátil** y cómo lo diseñamos.

## La verdad sobre tu hardware (8 GB RAM · gráfica integrada · ~29 GB libres)
Montar un **Linux completo en VirtualBox** (p. ej. Kali) pide típicamente **2–4 GB de RAM solo para la VM**
y **20–30 GB de disco**. En tu equipo eso es **impráctico**: Windows ya se come 2–4 GB de RAM y te quedan
~29 GB de disco. Correría muy lento y sin margen. **No lo recomiendo como opción principal**, aunque lo
dejamos soportado por si en el futuro amplías RAM/disco.

Hay dos caminos mucho mejores para ti:

### Opción recomendada ① — WSL2 (Linux dentro de Windows, ligero)
- WSL2 ejecuta un Linux real integrado en Windows, **mucho más ligero que VirtualBox**: no es una VM con
  escritorio, comparte recursos de forma dinámica y arranca en segundos. Es **el Linux local realista** en
  tu máquina.
- FORJA puede abrir una terminal WSL en una carpeta de trabajo del laboratorio, con las herramientas de
  línea de comandos instaladas (hay imágenes tipo Kali para WSL). Para 8 GB, **quédate en herramientas de
  consola**, no en escritorio gráfico.

### Opción recomendada ② — "Attack box" hospedado (coste local cero)
- HTB y TryHackMe ofrecen una **máquina de ataque en su nube/navegador** (p. ej. Pwnbox / AttackBox): el
  Linux con todas las herramientas **no corre en tu portátil**, corre en su servidor y tú lo usas desde el
  navegador o por VPN. **Es el que menos castiga tu equipo.** FORJA solo necesita un botón que lo abra y te
  muestre al lado la info del laboratorio.

### Opción ③ — VirtualBox (soportada, pero pesada → desaconsejada aquí)
- Queda como backend elegible para quien tenga RAM/disco de sobra. En tu equipo, aviso de "no recomendado".

> Resumen honesto: **sí**, puedes tener "el Linux dentro del laboratorio" sin salir de un sitio. En tu
> portátil, con **WSL2** (local ligero) o con el **attack box hospedado** (cero coste local). VirtualBox,
> mejor no por ahora.

## Decisión: se construyen las dos (WSL2 + attack box), con interfaz para cambiar
Ambos backends son de primera clase y se construyen de inicio. **SCR-027** incluye un **selector de backend
activo** (BTN-092) para cambiar entre WSL2 y attack box (y VirtualBox si lo activas) cuando quieras, y
también puedes elegir el backend **al abrir cada laboratorio**. Así pruebas lo que mejor te vaya sin
recompilar nada.

## Módulo y comportamiento (MOD-091 "Laboratorio Linux")
- **Autodetección y recomendación:** al entrar, MOD-091 detecta qué hay (WSL instalado, VirtualBox,
  navegador para attack box) y **recomienda** según tu hardware (en tu caso: WSL2 o attack box). Marca
  VirtualBox como "pesado para este equipo".
- **Configuración guiada con permiso (FR-072, ST-040):** si eliges WSL2 y no está, FORJA te muestra el
  comando exacto (p. ej. habilitar WSL e instalar la distro) y **te pide confirmación** antes de ejecutar
  nada; tú das el OK. Nada se instala sin tu permiso. Si Claude Code hace la instalación por ti durante el
  montaje, también te pedirá permiso y te mandará los pasos.
- **El botón que pediste — BTN-089 "Abrir Linux del laboratorio"** (en la lección, SCR-025, y en SCR-027):
  abre la terminal Linux **ya situada** en la carpeta del ejercicio, con un `README_LAB.md` que FORJA
  escribe con el **contexto del laboratorio** (objetivo, pistas desbloqueadas, notas). Así te pones a
  trabajar sin copiar nada a mano. En modo attack box, el botón abre la máquina hospedada y FORJA muestra
  el contexto al lado.
- **Contexto de ida y vuelta:** FORJA pasa al Linux la info del lab (BTN-091) y puede leer notas/resultados
  que guardes en esa carpeta para seguir orientándote (sin ejecutar ataques por su cuenta).

## Copiloto de Laboratorio (asistente en vivo) — FR-075/076
Dentro de la interfaz del laboratorio hay un **panel de copiloto**: un asistente de IA que te acompaña
mientras trabajas, aprovechando que el modelo es experto en código, firmware y scripts.
- **Qué hace:**
  - **Siguiente paso** (BTN-093): a partir de dónde estás y del contexto del lab, te propone el próximo
    paso razonable (a nivel de metodología, no un exploit listo).
  - **Explícame esto** (BTN-094): le pegas un comando, un concepto o la **salida del terminal** y te lo
    explica en claro (qué significa, por qué, qué mirar).
  - **Resolver dudas**: el panel tiene su propio campo de chat; preguntas lo que quieras ("¿qué es esto?",
    "no entiendo este error", "¿por qué no funciona?") y responde con el contexto del laboratorio cargado.
- **Relación con el tutor de la Academia:** es el **mismo tutor** (MOD-090/MOD-013) pero mostrado como
  **copiloto libre** junto a tu terminal Linux: comparte el contexto del lab (README_LAB.md, pistas
  desbloqueadas, tus notas) y respeta el sistema de **pistas progresivas** (no salta al final).
- **Aprovecha la experticia de código:** como la IA ya sabe de scripts/firmware, te ayuda a entender
  comandos, leer logs, interpretar respuestas y corregir pequeños errores de sintaxis mientras practicas.
- **Dónde:** panel acoplado en SCR-027 (y disponible al abrir el Linux del laboratorio). Vive dentro del
  gate de laboratorio autorizado (FR-038).

## Límites (coherentes con el gate de laboratorio, FR-038)
- Solo se abre el Linux del laboratorio tras **declarar el entorno autorizado** (BTN-087). El Linux es para
  practicar en labs/CTF/attack box autorizados, no contra sistemas reales de terceros.
- FORJA **no lanza herramientas ofensivas por su cuenta** en el Linux: te deja la terminal y el contexto;
  tú ejecutas. Cualquier acción que FORJA ejecute en tu sistema (habilitar WSL, crear VM) pasa por
  confirmación explícita (ST-040) y queda auditada (DB-008).
- El **Copiloto** (FR-075/076) orienta, explica y sugiere el siguiente paso, pero **no ejecuta** comandos
  por su cuenta ni entrega exploits armados para sistemas reales; mantiene las pistas progresivas y sigue
  la lista "nunca" global. Opera solo dentro del laboratorio autorizado.

## Datos y ajustes
- `settings.lab.backend` = `wsl` | `attackbox` | `virtualbox` (por defecto, el recomendado tras detección).
- `settings.lab.distro`, `settings.lab.working_dir`, `settings.lab.attackbox_url`.
- Nuevos requisitos: **FR-070** (abrir Linux con contexto), **FR-071** (backends + autodetección/
  recomendación), **FR-072** (instalación guiada con confirmación). Pruebas TST-070..072.

## Orden de construcción
Extensión de la **Rama 4b** (Academia). WSL2 y attack box primero; VirtualBox como backend opcional al final.
