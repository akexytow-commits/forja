"""MOD-013 · Telemetría de generación (doc 22, FR-077/078/079).

Indicador estilo Claude Code: tiempo, fase (esperando → pensando → respondiendo), tokens, tok/s y una ETA
**aproximada**. Reglas de honestidad de la ETA:
- `tok_s` es una media móvil de ~2 s (reacciona a cambios de carga), no la media total.
- Mientras la velocidad no es estable, `eta_ms` es null (la UI dice "estimando…").
- `eta_ms = max(0, (objetivo − tokens_out) / tok_s)`. Si el modelo ya escribió más de lo previsto, el
  objetivo crece con él: la ETA nunca es negativa ni se queda en un "0 s" falso.
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any, AsyncIterator, Callable

INTERVALO_S = 0.5          # tick cada ~400–600 ms (07-...md)
VENTANA_S = 2.0            # media móvil de tok/s
MIN_TOKENS_ETA = 8         # menos que esto: "estimando…"
MIN_SEGUNDOS_ETA = 1.5
# Tokens de razonamiento que suele gastar Qwen3 antes de responder, según el esfuerzo (afinado a ojo en CPU).
THINKING_PREVISTO = {"bajo": 0, "medio": 350, "extra": 900}

FASES = ("esperando", "pensando", "respondiendo")


class Telemetria:
    def __init__(self, objetivo_tokens: int, tope_tokens: int | None, modelo: str, tier: str,
                 reloj: Callable[[], float] = time.monotonic):
        self.reloj = reloj
        self.t0 = reloj()
        self.modelo, self.tier = modelo, tier
        self.tope = tope_tokens
        self.objetivo = max(1, min(objetivo_tokens, tope_tokens) if tope_tokens else objetivo_tokens)
        self.fase = "esperando"
        self.tokens_out = 0
        self.tokens_thinking = 0
        self.t_primer_token: float | None = None
        self.t_fin_thinking: float | None = None
        self._muestras: deque[tuple[float, int]] = deque()
        self._ultimo_tick = -1e9

    # --- entradas ----------------------------------------------------------------
    def thinking(self, n: int = 1) -> None:
        self._contar(n)
        self.tokens_thinking += n
        if self.fase == "esperando":
            self.fase = "pensando"

    def token(self, n: int = 1) -> None:
        self._contar(n)
        if self.fase == "pensando" and self.t_fin_thinking is None:
            self.t_fin_thinking = self.reloj()
        self.fase = "respondiendo"

    def _contar(self, n: int) -> None:
        ahora = self.reloj()
        if self.t_primer_token is None:
            self.t_primer_token = ahora
        self.tokens_out += max(0, n)
        self._muestras.append((ahora, self.tokens_out))
        while len(self._muestras) > 2 and ahora - self._muestras[0][0] > VENTANA_S:
            self._muestras.popleft()

    # --- salidas -----------------------------------------------------------------
    def elapsed_ms(self) -> int:
        return round((self.reloj() - self.t0) * 1000)

    def thinking_ms(self) -> int | None:
        if self.t_primer_token is None or self.tokens_thinking == 0:
            return None
        fin = self.t_fin_thinking or self.reloj()
        return round((fin - self.t_primer_token) * 1000)

    def tok_s(self) -> float | None:
        if self.t_primer_token is None or len(self._muestras) < 2:
            return None
        ahora = self.reloj()
        (t_a, n_a), (_, n_b) = self._muestras[0], self._muestras[-1]
        dt = ahora - t_a
        if dt <= 0.05:
            return None
        v = (n_b - n_a) / dt
        # Si lleva >ventana sin llegar nada (p. ej. el equipo va cargado), la media cae: es lo honesto.
        return round(v, 1) if v > 0 else 0.0

    def eta_ms(self) -> int | None:
        v = self.tok_s()
        if (v is None or v <= 0 or self.tokens_out < MIN_TOKENS_ETA or self.t_primer_token is None
                or self.reloj() - self.t_primer_token < MIN_SEGUNDOS_ETA):
            return None
        if self.tokens_out >= self.objetivo:
            # Ya pasó lo previsto: suponemos que le queda ~15 % más (sin pasar del tope de num_predict).
            nuevo = int(self.tokens_out * 1.15) + 1
            self.objetivo = min(nuevo, self.tope) if self.tope else nuevo
        restantes = max(0, self.objetivo - self.tokens_out)
        return max(0, int(restantes / v * 1000))

    def evento(self) -> dict[str, Any]:
        return {"fase": self.fase, "elapsed_ms": self.elapsed_ms(), "tokens_out": self.tokens_out,
                "tok_s": self.tok_s(), "eta_ms": self.eta_ms(), "thinking_ms": self.thinking_ms(),
                "modelo": self.modelo, "tier": self.tier}

    def toca(self) -> bool:
        """True si ha pasado el intervalo desde el último tick (y lo marca)."""
        ahora = self.reloj()
        if ahora - self._ultimo_tick >= INTERVALO_S * 0.8:
            self._ultimo_tick = ahora
            return True
        return False


def objetivo_tokens(salida_prevista: int, esfuerzo: str, thinking_activo: bool,
                    historial: list[int] | None = None) -> int:
    """Salida estimada total (razonamiento + respuesta) para la ETA. Mezcla el estimador (MOD-050) con la
    mediana de lo que tardaron las últimas respuestas de este modelo, si hay."""
    base = salida_prevista + (THINKING_PREVISTO.get(esfuerzo, 0) if thinking_activo else 0)
    previos = sorted(h for h in (historial or []) if h and h > 0)
    if len(previos) >= 3:
        mediana = previos[len(previos) // 2]
        base = int((base + mediana) / 2)
    return max(50, base)


async def con_ticks(origen: AsyncIterator[Any], intervalo: float = INTERVALO_S) -> AsyncIterator[Any]:
    """Reenvía los elementos de `origen` e intercala `None` cada `intervalo` s sin datos (para que el
    contador corra aunque el modelo tarde en dar el primer token). No cancela la lectura pendiente."""
    # El origen (p. ej. el stream de httpx) se consume entero en UNA tarea propia: así sus context managers
    # no saltan de tarea; aquí solo se espera en la cola, que sí se puede interrumpir sin efectos.
    cola: asyncio.Queue = asyncio.Queue()
    FIN = object()

    async def productor():
        try:
            async for x in origen:
                await cola.put((True, x))
            await cola.put((True, FIN))
        except Exception as e:  # noqa: BLE001 — se re-lanza en el consumidor
            await cola.put((False, e))

    tarea = asyncio.create_task(productor())
    try:
        while True:
            try:
                ok, x = await asyncio.wait_for(cola.get(), timeout=intervalo)
            except asyncio.TimeoutError:
                yield None
                continue
            if not ok:
                raise x
            if x is FIN:
                return
            yield x
    finally:
        if not tarea.done():
            tarea.cancel()
            try:
                await tarea
            except BaseException:  # noqa: BLE001
                pass
