# ADR-0001 — Motor de inferencia: Ollama

**Estado:** aceptada · **Fecha:** 2026-11-21

## Contexto
Necesitamos ejecutar modelos locales en Windows, CPU-only, con gestión sencilla de modelos y una API que
el backend pueda consumir, incluyendo descarga/carga y tool-calling.

## Decisión
Usar **Ollama** como motor local. Expone API compatible OpenAI en `localhost:11434`, instala con un solo
paquete en Windows, gestiona la descarga de modelos (`pull`), la carga/descarga y `keep_alive`, y soporta
tool-calling. El backend habla con él por HTTP.

## Alternativas consideradas
- **llama.cpp (llama-server) directo:** ~15–25% más rápido y más control fino, pero más fricción de
  configuración. Se deja como **optimización futura** cuando queramos exprimir la CPU.
- **LM Studio:** buena GUI, pero añade una app extra; preferimos un motor headless orquestado por nosotros.

## Consecuencias
- +Simplicidad de instalación y de gestión de modelos; API estable.
- −Algo menos de rendimiento que llama.cpp puro. Aceptable en v1.
- El backend aísla el motor (MOD-011), así que migrar a llama.cpp después no toca el resto.
