"""Genera assets/forja.ico (+ forja.png) a partir del yunque del logo de la UI (ui/index.html, #i-yunque).

Renderiza el SVG con Edge headless (CDP) a cada tamaño y empaqueta los PNG en un .ico (el formato ICO admite
PNG dentro desde Windows Vista), sin Pillow. Solo hace falta al cambiar el icono; el resultado va al repo.

    .venv\\Scripts\\python tools\\generar_icono.py
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

RAIZ = Path(__file__).resolve().parents[1]
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
TAMANOS = [16, 24, 32, 48, 64, 128, 256]
FONDO, ACENTO = "#151517", "#8f64e0"      # tu tema: acento violeta (Protocolo G3) sobre negro FORJA


def svg(tam: int) -> str:
    html = (RAIZ / "ui/index.html").read_text(encoding="utf-8")
    simbolo = re.search(r'<symbol id="i-yunque" viewBox="0 0 24 24">(.*?)</symbol>', html, re.S)[1]
    r = 5.5 if tam >= 32 else 4
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{tam}" height="{tam}" viewBox="0 0 24 24">'
            f'<rect x="0" y="0" width="24" height="24" rx="{r}" fill="{FONDO}"/>'
            f'<g transform="translate(2.4 1.6) scale(.8)" color="{ACENTO}">{simbolo}</g></svg>')


def puerto() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def render() -> dict[int, bytes]:
    p = puerto()
    perfil = tempfile.mkdtemp()
    proc = subprocess.Popen([str(EDGE), "--headless=new", f"--remote-debugging-port={p}", f"--user-data-dir={perfil}",
                             "--no-first-run", "--disable-gpu", "--force-device-scale-factor=1", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                pags = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{p}/json/list").read())
                pag = next(x for x in pags if x["type"] == "page")
                break
            except Exception:
                time.sleep(0.1)
        out: dict[int, bytes] = {}
        async with websockets.connect(pag["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
            n = 0

            async def cmd(m, **kw):
                nonlocal n
                n += 1
                await ws.send(json.dumps({"id": n, "method": m, "params": kw}))
                while True:
                    r = json.loads(await ws.recv())
                    if r.get("id") == n:
                        return r.get("result", {})

            await cmd("Emulation.setDefaultBackgroundColorOverride", color={"r": 0, "g": 0, "b": 0, "a": 0})
            for t in TAMANOS:
                doc = f"<html><body style='margin:0;background:transparent'>{svg(t)}</body></html>"
                await cmd("Page.navigate", url="data:text/html;base64," + base64.b64encode(doc.encode()).decode())
                await asyncio.sleep(0.4)
                r = await cmd("Page.captureScreenshot", format="png",
                              clip={"x": 0, "y": 0, "width": t, "height": t, "scale": 1})
                out[t] = base64.b64decode(r["data"])
        return out
    finally:
        proc.kill()


def ico(pngs: dict[int, bytes]) -> bytes:
    cab = struct.pack("<HHH", 0, 1, len(pngs))
    dirs, datos = b"", b""
    desplaz = 6 + 16 * len(pngs)
    for t, png in sorted(pngs.items()):
        lado = 0 if t >= 256 else t
        dirs += struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(png), desplaz + len(datos))
        datos += png
    return cab + dirs + datos


def main() -> None:
    pngs = asyncio.run(render())
    destino = RAIZ / "assets"
    destino.mkdir(exist_ok=True)
    (destino / "forja.ico").write_bytes(ico(pngs))
    (destino / "forja.png").write_bytes(pngs[256])
    print("assets/forja.ico:", ", ".join(f"{t}px" for t in sorted(pngs)))


if __name__ == "__main__":
    main()
