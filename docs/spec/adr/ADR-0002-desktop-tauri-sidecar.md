# ADR-0002 — Shell de escritorio: pywebview + FastAPI (Tauri como futuro)

**Estado:** aceptada · **Fecha:** 2026-11-21

## Contexto
Hardware modesto (8 GB RAM, ~29 GB libres). Queremos una ventana de escritorio con buena UI web, sin
consumir mucha RAM ni exigir un toolchain de compilación pesado (Rust+Node) en esta máquina.

## Decisión
**v1: pywebview + FastAPI.** El backend Python (FastAPI) sirve una SPA estática y `pywebview` la muestra
en una ventana nativa usando WebView2 (ya presente en Windows 10/11). Todo Python + web; sin compilar
Rust ni Node. Footprint mínimo.

## Alternativas consideradas
- **Tauri v2 + sidecar (FastAPI empaquetado con PyInstaller):** resultado más "nativo" y binario pequeño,
  pero exige toolchain de Rust y Node para construir, pesado para esta máquina. Se adopta como **mejora
  futura** (el backend desacoplado permite el cambio sin tocar lógica — NFR-060).
- **Electron:** descartado por consumo de RAM.

## Consecuencias
- +Mínimo consumo y cero toolchain pesado; desarrollo ágil en la propia máquina.
- +El backend es independiente del shell: migrar a Tauri después es cambiar solo la capa de ventana.
- −Menos "nativo" que Tauri y dependiente de WebView2 (aceptable en Windows actual).
