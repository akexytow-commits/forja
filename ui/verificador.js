/* FORJA — Rama 6b: Verificador de código (MOD-110, doc 23) en los bloques de SCR-010.
   BTN-101 «Comprobar» → POST /scripts/verificar (análisis ESTÁTICO; el código nunca se ejecuta) y pinta los
   errores con su línea bajo el bloque. BTN-102 «Corregir con la IA» → POST /scripts/corregir, que reusa el
   Motor de Chat: llega como una respuesta más del hilo, con un bloque nuevo que se puede volver a Comprobar. */
(function () {
  "use strict";

  const A = () => window.ForjaApp;
  const resultados = new Map();          // lenguaje + código → último resultado (sobrevive al repintado)
  const clave = (lang, codigo) => `${(lang || "").toLowerCase()}\u0000${codigo}`;
  const NOMBRE = { git: "Git-Bash", node: "Node.js", shellcheck: "ShellCheck", ruff: "Ruff" };

  const codigoDe = (bloque) => bloque.querySelector("pre code").textContent;

  async function comprobar(btn) {
    const bloque = btn.closest(".code");
    const lang = btn.dataset.lang || "";
    const codigo = codigoDe(bloque);
    btn.disabled = true;
    const txt = btn.textContent;
    btn.textContent = A().t("verif.comprobando");
    let r;
    try {
      r = await A().api("/scripts/verificar", { method: "POST", body: { lenguaje: lang, codigo } });
    } catch (e) {
      r = { fallo: e.message };
    } finally {
      btn.disabled = false;
      btn.textContent = txt;
    }
    r.lang = lang;
    resultados.set(clave(lang, codigo), r);
    pintar(bloque, r);
  }

  function pintar(bloque, r) {
    const { t, fmt, esc } = A();
    let panel = bloque.querySelector(".verif");
    if (!panel) {
      panel = document.createElement("div");
      panel.className = "verif";
      panel.setAttribute("role", "status");
      bloque.append(panel);
    }
    const errores = r.errores || [];
    const graves = errores.filter((e) => e.severidad === "error");
    let estado, cuerpo = "", acciones = "";
    if (r.fallo) {
      estado = "mal";
      cuerpo = `<p class="verif-cab">${esc(fmt("verif.fallo", { mensaje: r.fallo }))}</p>`;
    } else if (!r.disponible) {
      estado = "nodisp";
      cuerpo = `<p class="verif-cab">${esc(r.aviso || "")}</p>`;
      if (r.instalar) {
        acciones += `<button type="button" class="boton-txt peq verif-instalar" data-id="${esc(r.instalar.id)}" ` +
          `data-comando="${esc(r.instalar.comando)}" data-descripcion="${esc(r.instalar.descripcion)}">` +
          `${esc(fmt("verif.instalar", { nombre: NOMBRE[r.instalar.id] || r.instalar.id }))}</button>`;
      }
    } else {
      estado = graves.length ? "mal" : (errores.length ? "aviso" : "ok");
      const cab = graves.length ? fmt("verif.errores", { n: graves.length, herramienta: r.herramienta })
        : errores.length ? fmt("verif.ok_avisos", { n: errores.length, herramienta: r.herramienta })
          : fmt("verif.ok", { herramienta: r.herramienta });
      cuerpo = `<p class="verif-cab">${esc(cab)}</p>`;
      if (errores.length) {
        cuerpo += `<ul class="verif-lista">${errores.map((e) =>
          `<li class="${e.severidad === "error" ? "err" : "av"}"><span class="verif-linea">${esc(e.linea ? fmt("verif.linea", { n: e.linea }) + (e.columna ? `:${e.columna}` : "") : t("verif.sin_linea"))}</span>` +
          `<span class="verif-msg">${esc(e.mensaje)}</span></li>`).join("")}</ul>`;
      }
      cuerpo += `<p class="verif-nota">${esc(t("verif.nota"))}</p>`;
      if (graves.length) {
        acciones += `<button type="button" class="boton peq verif-corregir" title="${esc(t("verif.corregir_ayuda"))}">${esc(t("verif.corregir"))}</button>`;
      }
    }
    panel.className = `verif ${estado}`;
    panel.innerHTML = cuerpo + (acciones ? `<div class="verif-acc">${acciones}</div>` : "");
  }

  /* Tras repintar un mensaje (streaming, plegar razonamiento…), vuelve a poner los resultados ya obtenidos. */
  function reaplicar(cont) {
    if (!resultados.size) return;
    cont.querySelectorAll(".code").forEach((bloque) => {
      const btn = bloque.querySelector(".code-comprobar");
      if (!btn) return;
      const r = resultados.get(clave(btn.dataset.lang, codigoDe(bloque)));
      if (r) pintar(bloque, r);
    });
  }

  /* BTN-102: el código + los errores van al modelo (Motor de Chat) en este mismo hilo. */
  function corregir(btn) {
    const app = A();
    if (app.ocupado()) { window.ForjaProyectos?.toast(app.esc(app.t("verif.ocupado")), 2500); return; }
    const bloque = btn.closest(".code");
    const lang = bloque.querySelector(".code-comprobar")?.dataset.lang || "";
    const codigo = codigoDe(bloque);
    const r = resultados.get(clave(lang, codigo));
    const errores = (r?.errores || []).filter((e) => e.severidad === "error");
    app.enviar({
      ruta: "/scripts/corregir",
      texto: app.fmt("verif.burbuja", { lenguaje: lang || "código", n: errores.length }),
      cuerpo: { lenguaje: lang, codigo, errores },
    });
  }

  /* ST-040: la instalación de la herramienta que falta, solo tras confirmar. */
  async function instalar(btn) {
    const app = A();
    const ok = window.confirm(app.fmt("verif.instalar_conf", { comando: btn.dataset.comando, descripcion: btn.dataset.descripcion }));
    if (!ok) return;
    try {
      const r = await app.api("/scripts/verificar/instalar", { method: "POST", body: { id: btn.dataset.id, confirmado: true } });
      window.ForjaProyectos?.toast(app.esc(r.mensaje || ""), 7000);
    } catch (e) {
      window.ForjaProyectos?.toast(`<span class="mal">${app.esc(e.message)}</span>`, 6000);
    }
  }

  window.ForjaVerif = { comprobar, pintar, reaplicar, corregir, instalar };
})();
