/* FORJA — UI (SCR-001 shell, SCR-002 selector, SCR-008 estado, SCR-010 chat Scripts). */
(() => {
  "use strict";

  const TOKEN = window.FORJA_TOKEN;
  const { render, separarPlan, esc } = window.ForjaMD;
  const MODOS = [
    { id: "scripts", icono: "i-codigo" },
    { id: "seguridad", icono: "i-escudo" },
    { id: "tareas", icono: "i-tareas" },
  ];
  const TIERS = ["pequeno", "grande", "nube"];
  const ESFUERZOS = ["bajo", "medio", "extra"];
  const SEG = () => window.ForjaSeguridad;
  const esChat = () => st.modo === "scripts" || (st.modo === "seguridad" && !!SEG()?.chatActivo());
  // Hilo activo: uno para Scripts y uno por engagement en Seguridad.
  const clave = () => (st.modo === "seguridad" ? `seg:${SEG()?.engagementId() ?? ""}` : "scripts");
  const MARCA_INTERRUMPIDA = "\n\n_[respuesta interrumpida]_";

  let T = {};
  const t = (k) => (k in T ? T[k] : k);
  const $ = (s, r = document) => r.querySelector(s);

  const st = {
    modo: "scripts", tier: "pequeno", esfuerzo: "medio",
    hilo: { scripts: null }, hilos: [],
    salud: null, modelos: [], familia: {},
    gen: null,           // AbortController de la generación activa (ST-010: una a la vez)
    cargaSeq: 0,         // para ignorar cargas de modelo obsoletas
    cargandoModelo: false,
    descargas: {},       // alias -> {pct, estado, error, fin}
    confirmarDescarga: null,
    tel: null,           // último evento `telemetria` (doc 22) + momento en que llegó
    telFin: null,        // resumen de la última generación (se muestra en la línea hasta la siguiente acción)
    elIA: null,          // nodo del mensaje que se está generando (para BTN-100)
  };

  // ---------------------------------------------------------------- red
  class ErrorApi extends Error {
    constructor(codigo, mensaje) { super(mensaje); this.codigo = codigo; }
  }
  const cabeceras = () => ({ "Content-Type": "application/json", "X-Forja-Token": TOKEN });

  async function api(path, { method = "GET", body } = {}) {
    let r;
    try {
      r = await fetch(path, { method, headers: cabeceras(), body: body === undefined ? undefined : JSON.stringify(body) });
    } catch (e) {
      throw new ErrorApi("BACKEND_CAIDO", "No se pudo contactar con el backend local.");
    }
    if (r.status === 204) return null;
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const e = data.error || {};
      throw new ErrorApi(e.codigo || `HTTP_${r.status}`, e.mensaje || t("error.generico"));
    }
    return data;
  }

  /* POST que responde text/event-stream (API-003). */
  async function sse(path, body, onEvento, signal) {
    const r = await fetch(path, { method: "POST", headers: cabeceras(), body: JSON.stringify(body), signal });
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      const e = data.error || {};
      throw new ErrorApi(e.codigo || `HTTP_${r.status}`, e.mensaje || t("error.generico"));
    }
    const lector = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await lector.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const bloque = buf.slice(0, i);
        buf = buf.slice(i + 2);
        let ev = "message", datos = "";
        for (const l of bloque.split("\n")) {
          if (l.startsWith("event:")) ev = l.slice(6).trim();
          else if (l.startsWith("data:")) datos += l.slice(5).trim();
        }
        if (datos) onEvento(ev, JSON.parse(datos));
      }
    }
  }

  // ---------------------------------------------------------------- estado persistente
  let temporizadorGuardar = null;
  function guardarEstado() {
    clearTimeout(temporizadorGuardar);
    temporizadorGuardar = setTimeout(() => {
      api("/ajustes", {
        method: "PUT",
        body: {
          "estado.modo": st.modo, "estado.tier": st.tier, "estado.esfuerzo": st.esfuerzo,
          "estado.hilo.scripts": st.hilo.scripts == null ? "" : String(st.hilo.scripts),
        },
      }).catch(() => {});
    }, 250);
  }

  /* G2: "oscuro" | "claro" | "sistema" (sigue a Windows y cambia en vivo si cambias Windows). */
  const oscuroSistema = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  let temaElegido = "oscuro";
  function aplicarTema(tema) {
    temaElegido = ["claro", "oscuro", "sistema"].includes(tema) ? tema : "oscuro";
    const t2 = temaElegido === "sistema" ? (oscuroSistema && !oscuroSistema.matches ? "claro" : "oscuro") : temaElegido;
    document.documentElement.dataset.theme = t2;
    document.documentElement.dataset.temaElegido = temaElegido;
    $("#btn-tema use").setAttribute("href", t2 === "oscuro" ? "#i-sol" : "#i-luna");
  }
  oscuroSistema?.addEventListener?.("change", () => { if (temaElegido === "sistema") aplicarTema("sistema"); });

  /* BTN-063 + Rama 6: apariencia global (G2–G5) e interfaz por pantalla (doc 13), aplicadas en vivo. */
  function aplicarApariencia(a) {
    const r = document.documentElement;
    aplicarTema(a["ui.tema"]);
    r.dataset.acento = a["ui.acento"] || "naranja-forja";
    r.dataset.densidad = a["ui.densidad"] || "comoda";
    r.dataset.fuente = a["ui.tipografia"] || "sistema";
    window.ForjaInterfaz?.aplicar(a);
    if (st.listo) { pintarModos(); pintarSelector(); tabAjustes(st.ajTab || "modelos"); }
  }
  const ajuste = (k, def) => (window.ForjaApp.ajustes?.[k] ?? def);

  // ---------------------------------------------------------------- utilidades
  function etiquetaPara(modo, tier, esfuerzo = st.esfuerzo) {
    // Override por esfuerzo del router (doc 04): Seguridad + bajo usa el modelo de código.
    const alias = st.override?.[`${modo}:${esfuerzo}`]?.[tier] || st.familia?.[modo]?.[tier];
    const m = st.modelos.find((x) => x.alias === alias);
    return m ? m.etiqueta : "";
  }
  function modeloSalud(etiqueta) {
    return (st.salud?.modelos || []).find((m) => m.etiqueta === etiqueta);
  }
  const gb = (mb) => (mb / 1024).toLocaleString("es-ES", { maximumFractionDigits: 1 });
  function fechaCorta(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const hoy = new Date();
    if (d.toDateString() === hoy.toDateString()) return d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString("es-ES", { day: "numeric", month: "short" });
  }
  function cercaDelFinal(el) { return el.scrollHeight - el.scrollTop - el.clientHeight < 120; }

  // ---------------------------------------------------------------- SCR-001: selector de modo
  function pintarModos() {
    const nav = $("#modos");
    nav.innerHTML = "";
    for (const m of MODOS) {
      const b = document.createElement("button");
      b.className = "modo";
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(m.id === st.modo));
      b.innerHTML = `<svg><use href="#${m.icono}"/></svg><span>${esc(t("modo." + m.id))}</span>` +
        (m.id === "seguridad" ? '<svg class="candado"><use href="#i-candado"/></svg>' : "");
      b.title = t("modo." + m.id);
      b.addEventListener("click", () => cambiarModo(m.id));
      nav.append(b);
    }
  }

  function cambiarModo(modo) {
    if (modo === st.modo) return;
    st.modo = modo;
    pintarModos();
    mostrarVista();
    pintarSelector();
    actualizarCompositor();
    actualizarLinea();
    guardarEstado();
  }

  /* El chat (hilos + mensajes) es uno solo: se coloca en Scripts o dentro del engagement de Seguridad. */
  function colocarChat() {
    const destino = st.modo === "seguridad" && SEG()?.contenedorChat() ? SEG().contenedorChat() : $('.vista[data-vista="scripts"]');
    const hilos = $("#hilos"), chat = $(".chat");
    if (hilos.parentElement !== destino) { destino.append(hilos, chat); }
  }

  async function alEntrarModoChat() {
    colocarChat();
    await cargarHilos();
    const id = st.hilo[clave()];
    if (id && st.hilos.some((h) => h.id === id)) await abrirHilo(id);
    else { st.hilo[clave()] = null; pintarVacio(); pintarHilos(); }
  }

  function mostrarVista() {
    document.querySelectorAll(".vista").forEach((v) => v.classList.toggle("activa", v.dataset.vista === st.modo));
    if (st.modo === "scripts") { colocarChat(); if (st.hilosDe && st.hilosDe !== "scripts") alEntrarModoChat(); }
    if (st.modo === "seguridad") SEG()?.mostrar();
    if (st.modo === "tareas") window.ForjaTareas?.mostrar();
  }

  // ---------------------------------------------------------------- SCR-002: selector de modelo + esfuerzo
  function pintarSelector() {
    const segT = $("#seg-tier");
    segT.innerHTML = "";
    for (const tier of TIERS) {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", String(tier === st.tier));
      b.textContent = t("tier." + tier);
      if (tier === "nube" && !st.salud?.nube_activada) {
        b.disabled = true;
        b.title = t(st.salud?.nube_estado === "sin_sesion" ? "tier.nube.sin_sesion" : "tier.nube.deshabilitado");
      } else {
        const et = etiquetaPara(st.modo, tier);
        b.title = et ? `${t("tier." + tier)}: ${et}` : t("tier." + tier); // S3: tier + modelo real en tooltip
        // S3 = "tier+modelo": el modelo real del tier elegido, también a la vista.
        if (et && tier === st.tier && ajuste("ui.mostrar_modelo", "tier+tooltip") === "tier+modelo") {
          b.innerHTML = `${esc(t("tier." + tier))}<small class="tier-modelo">${esc(et)}</small>`;
        }
      }
      b.addEventListener("click", () => cambiarTier(tier));
      segT.append(b);
    }
    const segE = $("#seg-esfuerzo");
    segE.innerHTML = "";
    const elegir = (e) => {
      if (e === st.esfuerzo) return;
      st.esfuerzo = e; pintarSelector(); guardarEstado(); actualizarLinea();
      if (st.modo === "seguridad") cargarModeloActual();   // el esfuerzo puede cambiar de modelo (override)
      window.ForjaTareas?.alCambiarSelector();
      SEG()?.alCambiarSelector();
    };
    if (ajuste("ui.esfuerzo_control", "segmentos") === "deslizador") {
      // S2 = deslizador: 3 posiciones (bajo · medio · extra) con su etiqueta.
      segE.classList.add("deslizador");
      const i = ESFUERZOS.indexOf(st.esfuerzo);
      segE.innerHTML = `<input type="range" class="esf-rango" min="0" max="${ESFUERZOS.length - 1}" step="1" value="${i}" ` +
        `aria-label="${esc(t("esfuerzo.titulo"))}" aria-valuetext="${esc(t("esfuerzo." + st.esfuerzo))}" title="${esc(t(`esfuerzo.${st.esfuerzo}.ayuda`))}">` +
        `<span class="esf-etq">${esc(t("esfuerzo." + st.esfuerzo))}</span>`;
      const r = segE.querySelector("input");
      r.addEventListener("input", () => { segE.querySelector(".esf-etq").textContent = t("esfuerzo." + ESFUERZOS[r.value]); });
      r.addEventListener("change", () => { elegir(ESFUERZOS[r.value]); segE.querySelector("input")?.focus(); });
      return;
    }
    segE.classList.remove("deslizador");
    for (const e of ESFUERZOS) {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", String(e === st.esfuerzo));
      b.textContent = t("esfuerzo." + e);
      b.title = t(`esfuerzo.${e}.ayuda`);
      b.addEventListener("click", () => elegir(e));
      segE.append(b);
    }
  }

  function cambiarTier(tier) {
    if (tier === st.tier) return;
    st.tier = tier;
    pintarSelector();
    guardarEstado();
    cargarModeloActual();
    window.ForjaTareas?.alCambiarSelector();
  }

  /* BTN-020/021: cambiar de tier recarga el modelo (uno a la vez, ST-020). */
  async function cargarModeloActual() {
    if (!esChat() || st.tier === "nube" || st.gen) { actualizarLinea(); return; }
    if (st.salud?.ollama !== "ok") { actualizarLinea(); return; }
    const etiqueta = etiquetaPara(st.modo, st.tier);
    const m = modeloSalud(etiqueta);
    if (!m || !m.instalado || st.salud.modelo_cargado === etiqueta) { actualizarLinea(); return; }
    const seq = ++st.cargaSeq;
    st.cargandoModelo = true;
    actualizarLinea();
    try {
      await api("/modelos/cargar", { method: "POST", body: { alias: m.alias } });
      if (seq !== st.cargaSeq) return;
      st.salud.modelo_cargado = etiqueta;
    } catch (e) {
      if (seq !== st.cargaSeq) return;
      st.cargandoModelo = false;
      linea(`<span class="mal">${esc(e.message)}</span>`);
      return;
    }
    st.cargandoModelo = false;
    pintarChip();
    actualizarLinea();
  }

  function linea(html) { $("#linea-estado").innerHTML = html; }

  // ---------------------------------------------------------------- telemetría (FR-077/078/079, doc 22)
  function duracion(ms) {
    const s = Math.max(0, Math.round(ms / 1000));
    if (s < 60) return `${s} s`;
    const m = Math.floor(s / 60), r = s % 60;
    return r ? `${m} min ${String(r).padStart(2, "0")} s` : `${m} min`;
  }
  /* ETA honesta: siempre con "~", redondeada (nunca una cuenta atrás exacta) y nunca negativa. */
  function textoEta(ms) {
    if (ms == null) return t("tel.estimando");
    const s = Math.max(0, ms / 1000);
    if (s < 4) return t("tel.casi");
    if (s < 60) return fmt("tel.restantes", { t: `${Math.max(5, Math.round(s / 5) * 5)} s` });
    return fmt("tel.restantes", { t: `${Math.round(s / 60)} min` });
  }
  const tokS = (v) => (v == null ? null : v.toLocaleString("es-ES", { maximumFractionDigits: v < 10 ? 1 : 0 }));

  function pintarTelemetria() {
    const d = st.tel;
    if (!st.gen || !d) return false;
    const corriendo = d.elapsed_ms + (performance.now() - d.recibido);   // el reloj corre entre ticks
    const partes = [`<span class="tel-t">⏱ ${esc(duracion(corriendo))}</span>`,
      `<span class="tel-fase f-${esc(d.fase)}">${esc(t("tel." + d.fase))}</span>`];
    if (d.tokens_out) partes.push(`<span>${miles(d.tokens_out)} tok</span>`);
    if (d.tok_s) partes.push(`<span>${esc(tokS(d.tok_s))} tok/s</span>`);
    if (d.fase !== "esperando" && d.fase !== "cargando") partes.push(`<span class="tel-eta">${esc(textoEta(d.eta_ms))}</span>`);
    let html = partes.join('<span class="sep">·</span>');
    const det = st.elIA?.querySelector("details.razon");
    if (det) html += ` <button type="button" class="tel-btn" data-accion="razon" aria-pressed="${det.open}">${esc(t(det.open ? "tel.plegar_razon" : "tel.ver_razon"))}</button>`;
    html += ` <button type="button" class="tel-btn" data-accion="detener">${esc(t("tel.detener"))}</button>`;
    const el = $("#linea-estado");
    el.classList.add("tel");
    el.title = t("tel.titulo");
    if (ajuste("ui.telemetria", "1") === "0") {
      linea(`<span class="chispa"></span><span>${esc(t("tel." + d.fase))}</span> <button type="button" class="tel-btn" data-accion="detener">${esc(t("tel.detener"))}</button>`);
      return true;
    }
    linea(html);
    return true;
  }

  function resumenGen(genMs, tokensOut, thinkingMs) {
    if (!genMs) return "";
    let r = fmt("tel.resumen", { t: duracion(genMs), tok: tokensOut ? miles(tokensOut) : "—" });
    if (thinkingMs) r += ` · ${fmt("tel.penso", { t: duracion(thinkingMs) })}`;
    return r;
  }

  /* BTN-100: ver/plegar el razonamiento del mensaje en curso (o del último). */
  function alternarRazon() {
    const el = st.elIA || [...document.querySelectorAll("#mensajes .msg-ia")].pop();
    const det = el?.querySelector("details.razon");
    if (!det) return;
    det.open = !det.open;
    if (el._estado) el._estado._plegado = true;     // el usuario manda: no volver a plegar/abrir solo
    if (!pintarTelemetria()) actualizarLinea();
  }

  function actualizarLinea() {
    $("#linea-estado").classList.remove("tel");
    $("#linea-estado").title = "";
    if (st.gen && st.tel && pintarTelemetria()) return;
    if (st.modo === "tareas" && st.salud) {
      // Modo Tareas: qué hará "Organizar" con el selector actual (bajo = reglas, sin IA).
      if (st.esfuerzo === "bajo") { linea(`<span>${esc(t("tareas.linea.bajo"))}</span>`); return; }
      const et = st.tier === "nube" ? `${etiquetaPara("tareas", "nube")} · ${st.salud.nube_backend === "claude_code" ? "tu suscripción" : "API Anthropic"}` : etiquetaPara("tareas", st.tier);
      const m = st.tier === "nube" ? null : modeloSalud(et);
      linea(`<span>${esc(fmt("tareas.linea.ia", { modelo: et || "" }))}</span>` +
        (m && !m.instalado ? ` · <span class="mal">${esc(t("estado.modelo_falta"))}</span> <button type="button" data-accion="s008">${esc(t("estado.descargar"))}</button>` : ""));
      return;
    }
    if (st.modo === "seguridad" && SEG()?.aprendiendo?.() && window.ForjaAcademia) {
      linea(`<span>${esc(window.ForjaAcademia.linea())}</span>`);
      return;
    }
    if (st.modo === "seguridad" && !esChat() && st.salud) {
      const et = st.tier === "nube" ? "Claude" : etiquetaPara("seguridad", st.tier);
      linea(SEG()?.engagementId() ? `<span>${esc(fmt("seg.linea", { modelo: et || "" }))}</span>` : `<span>${esc(t("seg.linea.gate"))}</span>`);
      return;
    }
    if (!esChat() || !st.salud) { linea(""); return; }
    if (st.tier === "nube") {
      linea(`<span>${esc(etiquetaPara(st.modo, "nube"))}</span> · <span>${st.salud?.nube_backend === "claude_code" ? "tu suscripción" : "API Anthropic"}</span>`);
      return;
    }
    if (st.salud.ollama !== "ok") {
      linea(`<span class="mal">${esc(t("estado.ollama_caido"))}</span> <button type="button" data-accion="s008">${esc(t("chat.ver_estado"))}</button>`);
      return;
    }
    const etiqueta = etiquetaPara(st.modo, st.tier);
    if (!etiqueta) { linea(""); return; }
    if (st.cargandoModelo) { linea(`<span class="chispa"></span>${esc(t("estado.cambiando_modelo"))} <span>${esc(etiqueta)}</span>`); return; }
    const m = modeloSalud(etiqueta);
    if (m && !m.instalado) {
      linea(`<span>${esc(etiqueta)}</span> · <span class="mal">${esc(t("estado.modelo_falta"))}</span> <button type="button" data-accion="s008">${esc(t("estado.descargar"))}</button>`);
      return;
    }
    const fin = st.telFin ? ` · <span class="tel-fin">✓ ${esc(st.telFin)}</span>` : "";
    if (st.salud.modelo_cargado === etiqueta) { linea(`<span>${esc(etiqueta)}</span> · <span class="ok">${esc(t("estado.modelo_listo"))}</span>${fin}`); return; }
    linea(`<span>${esc(etiqueta)}</span>${fin}`);
  }

  // ---------------------------------------------------------------- chip de estado (cabecera)
  function pintarChip() {
    const chip = $("#chip-estado");
    const s = st.salud;
    if (!s || s.ollama !== "ok") {
      chip.dataset.estado = "caido";
      $("#chip-txt").textContent = t("estado.ollama_caido");
    } else {
      chip.dataset.estado = s.faltan_necesarios ? "aviso" : "ok";
      $("#chip-txt").textContent = `${t("estado.ollama_ok")} · ${s.modelo_cargado || t("estado.sin_modelo")}`;
    }
    chip.title = t("s008.titulo");
  }

  async function refrescarSalud() {
    try {
      st.salud = await api("/salud");
    } catch (e) {
      st.salud = { ollama: "caido", modelos: [], backend_caido: true };
    }
    pintarChip();
    pintarSelector();
    if (!st.cargandoModelo) actualizarLinea();
    return st.salud;
  }
  const necesitaS008 = (s) => s.ollama !== "ok" || s.faltan_necesarios;

  // ---------------------------------------------------------------- compositor
  const entrada = () => $("#entrada");

  function actualizarCompositor() {
    const chat = esChat();
    const ta = entrada();
    ta.disabled = !chat;
    ta.placeholder = chat ? t(st.modo === "seguridad" ? "compositor.placeholder.seguridad" : "compositor.placeholder") : t(`compositor.bloqueado.${st.modo}`);
    $("#compositor").classList.toggle("bloqueado", !chat);
    $("#compositor").hidden = st.modo === "tareas" || (st.modo === "seguridad" && !esChat());
    if (!esChat()) $("#banner-justo").hidden = true;
    actualizarBotonEnviar();
  }

  function actualizarBotonEnviar() {
    const b = $("#btn-enviar");
    const generando = !!st.gen;
    b.classList.toggle("parar", generando);
    b.querySelector("use").setAttribute("href", generando ? "#i-parar" : "#i-enviar");
    b.title = generando ? t("compositor.detener") : t("compositor.enviar");
    b.setAttribute("aria-label", b.title);
    b.disabled = !generando && !esChat();
  }

  function autoAltura() {
    const ta = entrada();
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 220) + "px";
  }

  // ---------------------------------------------------------------- hilos
  async function cargarHilos() {
    try {
      const eng = st.modo === "seguridad" ? `&engagement=${SEG()?.engagementId() ?? 0}` : "";
      st.hilos = (await api(`/conversaciones?modo=${st.modo === "seguridad" ? "seguridad" : "scripts"}${eng}`)).conversaciones;
      st.hilosDe = clave();
    } catch { st.hilos = []; }
    pintarHilos();
  }

  function pintarHilos() {
    const ul = $("#hilos-lista");
    ul.innerHTML = "";
    if (!st.hilos.length) {
      ul.innerHTML = `<li class="hilos-vacio">${esc(t("hilos.vacio"))}</li>`;
    }
    for (const h of st.hilos) {
      const li = document.createElement("li");
      li.className = "hilo" + (h.id === st.hilo[clave()] ? " activo" : "");
      li.innerHTML = `<div class="hilo-txt"><span class="hilo-titulo"></span><span class="hilo-meta"></span></div>` +
        `<button class="hilo-borrar" type="button">${esc(t("hilos.borrar"))}</button>`;
      li.querySelector(".hilo-titulo").textContent = h.titulo || t("hilos.sin_titulo");
      li.querySelector(".hilo-meta").textContent = `${fechaCorta(h.updated_at)} · ${h.n_mensajes} msj`;
      li.addEventListener("click", () => abrirHilo(h.id));
      const borrar = li.querySelector(".hilo-borrar");
      borrar.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        if (!borrar.classList.contains("confirmar")) {
          borrar.classList.add("confirmar");
          borrar.textContent = t("hilos.borrar.confirmar");
          setTimeout(() => { borrar.classList.remove("confirmar"); borrar.textContent = t("hilos.borrar"); }, 3000);
          return;
        }
        await api(`/conversaciones/${h.id}`, { method: "DELETE" }).catch(() => {});
        if (st.hilo[clave()] === h.id) nuevoHilo();
        cargarHilos();
      });
      ul.append(li);
    }
    const actual = st.hilos.find((h) => h.id === st.hilo[clave()]);
    $("#chat-titulo").textContent = actual ? (actual.titulo || t("hilos.sin_titulo")) : t("hilos.sin_titulo");
    window.ForjaProyectos?.alCambiarHilo(actual || null);
  }
  const hiloActual = () => st.hilos.find((h) => h.id === st.hilo[clave()]) || null;

  async function abrirHilo(id) {
    if (st.gen) return;
    try {
      const { mensajes } = await api(`/conversaciones/${id}/mensajes`);
      st.hilo[clave()] = id;
      pintarMensajes(mensajes);
    } catch {
      st.hilo[clave()] = null;
      pintarVacio();
    }
    pintarHilos();
    guardarEstado();
  }

  function nuevoHilo() {
    if (st.gen) return;
    st.hilo[clave()] = null; // se crea en el primer mensaje (el backend devuelve sesion_id)
    pintarVacio();
    pintarHilos();
    guardarEstado();
    entrada().focus();
  }

  function alternarHilos() {
    const a = $("#hilos");
    a.classList.toggle("abierto");
    $("#btn-hilos").setAttribute("aria-expanded", String(a.classList.contains("abierto")));
  }

  // ---------------------------------------------------------------- mensajes
  function pintarVacio() {
    const cont = $("#mensajes");
    const k = st.modo === "seguridad" ? "chat.seg." : "chat.";
    cont.innerHTML = `<div class="vacio"><h1>${esc(t(k + "vacio.titulo"))}</h1><p>${esc(t(k + "vacio.sub"))}</p>` +
      `<div class="sugerencias">${[1, 2, 3].map((n) => `<button class="sugerencia" type="button">${esc(t(k + "sugerencia." + n))}</button>`).join("")}</div></div>`;
    cont.querySelectorAll(".sugerencia").forEach((b) => b.addEventListener("click", () => {
      entrada().value = b.textContent;
      autoAltura();
      entrada().focus();
    }));
  }

  function nodoUsuario(texto) {
    const d = document.createElement("div");
    d.className = "msg msg-user";
    d.innerHTML = '<div class="burbuja"></div>';
    d.firstChild.textContent = texto;
    return d;
  }

  function nodoIA() {
    const d = document.createElement("div");
    d.className = "msg msg-ia";
    d.innerHTML = `<div class="cab"><svg class="marca-mini"><use href="#i-yunque"/></svg><span class="modelo"></span><span class="metricas"></span></div>` +
      `<div class="razon-wrap"></div><div class="cuerpo"></div><div class="pie"></div>`;
    return d;
  }

  function ponerCabecera(el, modelo, tier, esfuerzo) {
    el.querySelector(".modelo").textContent = [modelo, tier && t("tier." + tier), esfuerzo].filter(Boolean).join(" · ");
  }
  function ponerMetricas(el, tokensOut, tps, genMs, thinkingMs) {
    const partes = [];
    if (genMs) partes.push(duracion(genMs));
    if (tokensOut) partes.push(`${tokensOut} tokens`);
    if (tps) partes.push(`${tps.toLocaleString("es-ES")} tok/s`);
    if (thinkingMs) partes.push(fmt("tel.penso", { t: duracion(thinkingMs) }));
    el.querySelector(".metricas").textContent = partes.join(" · ");
  }

  /* s = {contenido, thinking, streaming, fase, error, interrumpida} */
  function renderIA(el, s) {
    const { plan, resto, planAbierto } = separarPlan(s.contenido);
    const razon = s.thinking || plan;
    const razonando = s.streaming && ((s.thinking && !s.contenido) || planAbierto);
    let det = el.querySelector("details.razon");
    if (razon) {
      if (!det) {
        det = document.createElement("details");
        det.className = "razon";
        det.innerHTML = '<summary></summary><div class="razon-txt"></div>';
        el.querySelector(".razon-wrap").append(det);
        if (s.streaming) { det.open = true; s._autoAbierto = true; }
      }
      det.querySelector("summary").textContent = razonando ? t("chat.razonando")
        : (plan && !s.thinking ? t("chat.plan") : t(s.tope ? "chat.razon_tope" : "chat.razonamiento"));
      const txt = det.querySelector(".razon-txt");
      txt.textContent = razon;
      if (razonando) txt.scrollTop = txt.scrollHeight;
      if (!razonando && s._autoAbierto && !s._plegado && ajuste("ui.razonamiento", "plegar") !== "mostrar") { det.open = false; s._plegado = true; }
    }
    const cuerpo = el.querySelector(".cuerpo");
    if (!resto && s.streaming && !razonando) {
      const msg = s.fase === "cargando" ? t("chat.cargando_modelo") : t("chat.esperando");
      cuerpo.innerHTML = `<div class="espera"><span class="chispa"></span>${esc(msg)}</div>`;
    } else {
      // BTN-031 Guardar solo en Scripts/Firmware (y en bloques ya cerrados).
      cuerpo.innerHTML = render(resto, t("code.copiar"), st.modo === "scripts" ? t("code.guardar") : null);
    }
    const pie = el.querySelector(".pie");
    pie.innerHTML = "";
    if (s.interrumpida) pie.innerHTML = `<p class="nota-interrumpida">${esc(t("chat.interrumpida"))}</p>`;
    if (s.error) {
      const accion = ["OLLAMA_CAIDO", "MODELO_FALTANTE", "BACKEND_CAIDO"].includes(s.error.codigo)
        ? `<button class="boton-txt" type="button" data-accion="s008">${esc(t("chat.ver_estado"))}</button>` : "";
      pie.innerHTML += `<div class="aviso"><span>${esc(s.error.mensaje || t("error.generico"))}</span>${accion}</div>`;
    }
  }

  function pintarMensajes(mensajes) {
    const cont = $("#mensajes");
    cont.innerHTML = "";
    if (!mensajes.length) { pintarVacio(); return; }
    for (const m of mensajes) {
      if (m.rol === "user") cont.append(nodoUsuario(m.contenido));
      else if (m.rol === "assistant") {
        const el = nodoIA();
        let contenido = m.contenido;
        const interrumpida = contenido.endsWith(MARCA_INTERRUMPIDA);
        if (interrumpida) contenido = contenido.slice(0, -MARCA_INTERRUMPIDA.length);
        ponerCabecera(el, m.modelo, m.tier, m.esfuerzo);
        ponerMetricas(el, m.tokens_out, null, m.gen_ms, m.thinking_ms);
        cont.append(el);
        renderIA(el, { contenido, thinking: m.thinking || "", streaming: false, interrumpida });
      }
    }
    cont.scrollTop = cont.scrollHeight;
  }

  // ---------------------------------------------------------------- envío (API-002 / ST-010)
  /* opts: {texto, tier, forzar}. Sin opts usa el compositor y el selector. */
  async function enviar(opts = {}) {
    if (st.gen) { st.gen.abort(); return; }           // botón Detener → cancelado
    if (!esChat()) return;
    const ta = entrada();
    const texto = (opts.texto ?? ta.value).trim();
    if (!texto) return;
    const tier = opts.tier || st.tier;
    const forzar = !!opts.forzar;
    cerrarAvisos();

    const cont = $("#mensajes");
    const estabaVacio = !!cont.querySelector(".vacio");
    if (estabaVacio) cont.innerHTML = "";
    const nodoU = nodoUsuario(texto);
    cont.append(nodoU);
    const el = nodoIA();
    ponerCabecera(el, etiquetaPara(st.modo, tier), tier, st.esfuerzo);
    cont.append(el);
    const s = { contenido: "", thinking: "", streaming: true, fase: "esperando", error: null, interrumpida: false };
    el._estado = s;
    st.elIA = el;
    st.tel = null;
    st.telFin = null;
    renderIA(el, s);
    cont.scrollTop = cont.scrollHeight;
    ta.value = "";
    autoAltura();

    const ctrl = new AbortController();
    st.gen = ctrl;
    actualizarBotonEnviar();
    const reloj = setInterval(pintarTelemetria, 250);   // el contador corre aunque no lleguen ticks

    let pendiente = false;
    const repintar = () => {
      if (pendiente) return;
      pendiente = true;
      requestAnimationFrame(() => {
        pendiente = false;
        const pegado = cercaDelFinal(cont);
        renderIA(el, s);
        if (pegado) cont.scrollTop = cont.scrollHeight;
      });
    };

    let sugerencia = null;
    try {
      const engagement_id = st.modo === "seguridad" ? SEG()?.engagementId() : null;
      await sse("/chat", { sesion_id: st.hilo[clave()] ?? null, modo: st.modo, tier, esfuerzo: st.esfuerzo, texto, forzar, engagement_id }, (ev, d) => {
        if (ev === "sugerencia_escalado") {
          sugerencia = d;
          return;
        }
        if (ev === "telemetria") {
          st.tel = { ...d, recibido: performance.now() };
          pintarTelemetria();
          return;
        }
        if (ev === "inicio") {
          st.hilo[clave()] = d.sesion_id;
          s.fase = d.requiere_carga ? "cargando" : "esperando";
          ponerCabecera(el, d.modelo, d.tier, d.esfuerzo);
          if (d.requiere_carga) linea(`<span class="chispa"></span>${esc(t("estado.cambiando_modelo"))} <span>${esc(d.modelo)}</span>`);
          if (st.salud && d.tier !== "nube") st.salud.modelo_cargado = d.modelo;
        } else if (ev === "tope_razonamiento") {
          s.tope = true;                                // doc 04: thinking cortado, llega la respuesta final
          if (st.salud && d.modelo_respuesta) st.salud.modelo_cargado = d.modelo_respuesta;
        } else if (ev === "reclasificar") {
          // doc 04 (B): lo que se mostraba como respuesta era razonamiento (llegó un "</think>").
          s.thinking = d.thinking; s.contenido = "";
        } else if (ev === "thinking") {
          s.thinking += d.texto_parcial; s.fase = "generando";
        } else if (ev === "token") {
          s.contenido += d.texto; s.fase = "generando";
          if (s.contenido.length === d.texto.length) actualizarLinea();
        } else if (ev === "fin") {
          s.streaming = false;
          ponerMetricas(el, d.tokens_out, d.tokens_por_segundo, d.gen_ms, d.thinking_ms);
          st.telFin = resumenGen(d.gen_ms, d.tokens_out, d.thinking_ms);
        } else if (ev === "error") {
          // G-3: el rechazo explica el límite y reconduce (TST-033).
          s.error = d.reconduccion ? { ...d, mensaje: `${d.mensaje} ${d.reconduccion}` } : d;
          s.streaming = false;
        }
        repintar();
      }, ctrl.signal);
    } catch (e) {
      if (e.name === "AbortError") s.interrumpida = true;
      else s.error = { codigo: e.codigo || "BACKEND_CAIDO", mensaje: e.message };
    } finally {
      clearInterval(reloj);
      s.streaming = false;
      st.gen = null;
      st.tel = null;
      st.elIA = null;
      actualizarBotonEnviar();
      if (sugerencia) {
        // ST-010 esperando_decision_escalado: no se generó ni guardó nada; devolvemos el texto al usuario.
        nodoU.remove();
        el.remove();
        if (estabaVacio && !cont.children.length) pintarVacio();
        if (!opts.texto) { ta.value = texto; autoAltura(); }
        mostrarSugerencia(sugerencia, texto);
        return;
      }
      renderIA(el, s);
      if (cercaDelFinal(cont)) cont.scrollTop = cont.scrollHeight;
      actualizarLinea();
      guardarEstado();
      await cargarHilos();
      await refrescarSalud();
    }
  }

  // ---------------------------------------------------------------- SCR-006 aviso de escalado (ST-050)
  const fmt = (k, vars) => t(k).replace(/\{(\w+)\}/g, (_, n) => (n in vars ? vars[n] : `{${n}}`));
  const miles = (n) => Number(n).toLocaleString("es-ES");

  function cerrarAvisos() {
    $("#banner-justo").hidden = true;
    $("#scr-006").hidden = true;
  }

  /* SE1 (ui.aviso_escalado): "modal-nube+banner-justo" (DEFAULT) = modal si se recomienda la Nube y banner
     no bloqueante si es JUSTO · "modal" = siempre modal · "banner" = siempre banner. Lo FIJADO no cambia:
     siempre se explica el motivo y decides tú. */
  function mostrarSugerencia(sug, texto) {
    st.pendiente = { texto, sug };
    const modo = ajuste("ui.aviso_escalado", "modal-nube+banner-justo");
    const justo = sug.veredicto === "JUSTO";
    const enGrande = sug.tier === "grande";
    if (justo ? modo !== "modal" : modo === "banner") {
      $("#banner-txt").textContent = justo
        ? (enGrande ? t("s006.justo_grande") : fmt("s006.justo", { tier: t("tier." + sug.tier) }))
        : `${t("s006.titulo")}: ${sug.motivo}`;
      $("#bj-grande").hidden = enGrande;
      const bn = $("#bj-nube");
      bn.hidden = justo;
      bn.textContent = sug.nube_activada ? t("s006.escalar") : t("s006.activar");
      bn.dataset.accion = sug.nube_activada ? "escalar" : "ajustes";
      $("#banner-justo").classList.toggle("nube", !justo);
      $("#banner-justo").hidden = false;
      return;
    }
    $("#s006-grande").hidden = !justo || enGrande;          // JUSTO en modal: también se puede subir a Grande
    $("#s006-motivo").textContent = sug.motivo;
    const alerta = (c) => (sug.motivo_codigo === c ? " alerta" : "");
    $("#s006-datos").innerHTML =
      `<div class="dato${alerta("contexto")}"><b>~${miles(sug.tokens_entrada)}</b><span>${esc(t("s006.dato.entrada"))} (tokens)</span></div>` +
      `<div class="dato${alerta("salida")}"><b>~${miles(sug.salida_prevista)}</b><span>${esc(t("s006.dato.salida"))} (tokens)</span></div>` +
      `<div class="dato${alerta("complejidad")}"><b>${sug.complejidad}/100</b><span>${esc(t("s006.dato.complejidad"))}</span></div>`;
    $("#s006-envio").innerHTML = sug.nube_activada
      ? `<h4>${esc(t("s006.envio"))}</h4>${esc(sug.resumen_envio.texto)}`
      : esc(t("s006.sin_nube"));
    const bNube = $("#s006-nube");
    bNube.textContent = sug.nube_activada ? t("s006.escalar") : t("s006.activar");
    bNube.dataset.accion = sug.nube_activada ? "escalar" : "ajustes";
    $("#scr-006").hidden = false;
    bNube.focus();
  }

  function decidir(accion) {
    const p = st.pendiente;
    if (!p) return;
    if (accion === "ajustes") { cerrarAvisos(); abrirAjustes(); return; }
    st.pendiente = null;
    cerrarAvisos();
    if (accion === "grande") {                       // BTN-026
      st.tier = "grande"; pintarSelector(); guardarEstado();
      enviar({ texto: p.texto, forzar: true });
    } else if (accion === "escalar") {               // BTN-028: solo esta petición va a la Nube
      enviar({ texto: p.texto, tier: "nube", forzar: true });
    } else if (accion === "seguir") {
      enviar({ texto: p.texto, forzar: true });
    } else if (accion === "trocear") {               // BTN-027 / BTN-029
      trocear(p.texto);
    }
  }

  async function trocear(texto) {
    const cont = $("#mensajes");
    if (cont.querySelector(".vacio")) cont.innerHTML = "";
    entrada().value = ""; autoAltura();
    const el = nodoIA();
    el.classList.add("troceo");
    ponerCabecera(el, t("troceo.titulo"), null, null);
    el.querySelector(".cuerpo").innerHTML = `<div class="espera"><span class="chispa"></span>${esc(t("troceo.trabajando"))}</div>`;
    cont.append(nodoUsuario(texto));
    cont.append(el);
    cont.scrollTop = cont.scrollHeight;
    let r;
    try {
      r = await api("/trocear", { method: "POST", body: { modo: st.modo, texto } });
    } catch (e) {
      el.querySelector(".cuerpo").innerHTML = `<div class="aviso"><span>${esc(e.message)}</span></div>`;
      return;
    }
    const n = r.pasos.length;
    const lista = r.pasos.map((p) =>
      `<li><span></span><span class="mins">~${p.estimacion_min} min</span><button class="boton-txt" type="button">${esc(t("troceo.hacer"))}</button></li>`).join("");
    const cuerpo = el.querySelector(".cuerpo");
    cuerpo.innerHTML = `<ol>${lista}</ol><p class="nota">${esc(fmt("troceo.guardado", { titulo: r.titulo }))}` +
      (r.origen === "heuristica" ? ` ${esc(t("troceo.heuristica"))}` : "") + "</p>";
    cuerpo.querySelectorAll("li").forEach((li, i) => {
      li.querySelector("span").textContent = r.pasos[i].texto;
      li.querySelector("button").addEventListener("click", () => {
        if (st.gen) return;
        enviar({ texto: fmt("troceo.paso_prompt", { i: i + 1, n, original: texto.slice(0, 160), paso: r.pasos[i].texto }), forzar: true });
      });
    });
    cont.scrollTop = cont.scrollHeight;
  }

  // ---------------------------------------------------------------- SCR-007 ajustes (SA1: pestañas)
  function tabAjustes(tab) {
    const pagina = document.documentElement.dataset.ajustes === "pagina";   // SA1
    document.querySelectorAll("#aj-tabs [role=tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    document.querySelectorAll("#scr-007 .aj-panel").forEach((p) => {
      p.hidden = !pagina && p.dataset.tab !== tab;
      if (!p.dataset.titulo) p.dataset.titulo = $(`#aj-tabs [data-tab="${p.dataset.tab}"]`)?.textContent || "";
    });
    st.ajTab = tab;
  }
  function segValor(id, v) {
    document.querySelectorAll(`#${id} [data-v]`).forEach((b) => b.setAttribute("aria-checked", String(b.dataset.v === v)));
  }
  const segLeer = (id, def) => document.querySelector(`#${id} [aria-checked=true]`)?.dataset.v || def;
  /* Vista previa en vivo de la apariencia mientras eliges (se persiste al Guardar; Cerrar la deshace). */
  function previaApariencia() {
    aplicarApariencia({ ...window.ForjaApp.ajustes, ...(window.ForjaInterfaz?.leer() || {}),
      "ui.tema": segLeer("aj-tema", "oscuro"), "ui.acento": segLeer("aj-acento", "naranja-forja"),
      "ui.densidad": segLeer("aj-densidad", "comoda"), "ui.tipografia": segLeer("aj-tipografia", "sistema") });
  }

  function pintarModelosAjustes() {
    const cont = $("#aj-modelos");
    if (!cont) return;
    const s = st.salud || { modelos: [] };
    const lista = s.modelos?.length ? s.modelos : st.modelos.filter((m) => m.tier !== "nube");
    cont.innerHTML = "";
    for (const m of lista) {
      const dl = st.descargas[m.alias];
      const fila = document.createElement("div");
      fila.className = "fila";
      let der;
      if (m.instalado) der = `<span class="estado-ok">${esc(t("s008.instalado"))}${s.modelo_cargado === m.etiqueta ? " · " + esc(t("estado.modelo_listo")) : ""}</span>`;
      else if (dl && !dl.fin && !dl.error) der = `<span class="detalle">${esc(dl.pct != null ? dl.pct.toLocaleString("es-ES") + " %" : t("s008.descargando"))}</span>`;
      else {
        const conf = st.confirmarDescarga === m.alias;
        der = `<button class="${conf ? "boton" : "boton-txt"} peq" type="button" data-descargar-aj="${esc(m.alias)}" ${s.ollama === "ok" ? "" : "disabled"}>${esc(conf ? `${t("s008.confirmar")} (${gb(m.tamano_disco_mb)} GB)` : t("s008.descargar"))}</button>`;
      }
      fila.innerHTML = `<span class="nombre">${esc(m.etiqueta)}</span><span class="detalle">${esc(t("tier." + m.tier))} · ~${gb(m.tamano_disco_mb || 0)} GB · ${esc(m.notas || "")}</span><span class="der">${der}</span>` +
        (dl && !dl.fin && !dl.error ? `<div class="barra"><span style="width:${dl.pct || 0}%"></span></div>` : "") +
        (dl && dl.error ? `<span class="instrucciones" style="color:var(--bad)">${esc(dl.error)}</span>` : "");
      cont.append(fila);
    }
    cont.querySelectorAll("[data-descargar-aj]").forEach((b) => b.addEventListener("click", () => {
      const alias = b.dataset.descargarAj;
      if (st.confirmarDescarga !== alias) { st.confirmarDescarga = alias; pintarModelosAjustes(); return; }
      st.confirmarDescarga = null;
      descargarModelo(alias);
    }));
    const fam = st.familia || {};
    const filas = Object.keys(fam).map((modo) => `<tr><th>${esc(t("modo." + modo))}</th>` +
      ["pequeno", "grande", "nube"].map((tier) => `<td>${esc(etiquetaPara(modo, tier) || "—")}</td>`).join("") + "</tr>").join("");
    $("#aj-familia").innerHTML = `<h3>${esc(t("s007.familia"))}</h3><table><thead><tr><th></th><th>${esc(t("tier.pequeno"))}</th><th>${esc(t("tier.grande"))}</th><th>${esc(t("tier.nube"))}</th></tr></thead><tbody>${filas}</tbody></table><p class="nota">${esc(t("s007.familia.nota"))}</p>`;
  }

  async function abrirAjustes(tab) {
    const { ajustes } = await api("/ajustes");
    window.ForjaApp.ajustes = ajustes;
    st.ajAntes = { ...ajustes };
    pintarEstadoClave(ajustes["nube.tiene_clave"] === "1");
    st.tieneCli = ajustes["nube.tiene_cli"] === "1";
    $("#aj-backend").value = ajustes["nube.backend"] || "claude_code";
    $("#aj-bin").value = ajustes["nube.claude_bin"] || "";
    $("#aj-bin").placeholder = ajustes["nube.claude_bin_detectado"]
      ? `${t("s007.claude_bin.auto")}: ${ajustes["nube.claude_bin_detectado"]}` : t("s007.claude_bin.no");
    pintarProveedor();
    $("#aj-modelo").value = ajustes["nube.modelo"] || "claude-opus-5-5";
    $("#aj-activar").checked = ajustes["nube.activada"] === "1";
    $("#aj-u-justo").value = ajustes["umbral.complejidad_justo"] || 45;
    $("#aj-u-nube").value = ajustes["umbral.complejidad_nube"] || 70;
    $("#aj-u-salida").value = ajustes["umbral.factor_salida"] || 2;
    // Modelos
    $("#aj-precargar").checked = ajustes["modelos.precargar"] !== "0";
    pintarModelosAjustes();
    // Apariencia
    segValor("aj-tema", ajustes["ui.tema"] || "oscuro");
    segValor("aj-acento", ajustes["ui.acento"] || "naranja-forja");
    segValor("aj-densidad", ajustes["ui.densidad"] || "comoda");
    segValor("aj-tipografia", ajustes["ui.tipografia"] || "sistema");
    segValor("aj-razonamiento", ajustes["ui.razonamiento"] || "plegar");
    $("#aj-telemetria").checked = ajustes["ui.telemetria"] !== "0";
    $("#aj-nombre-app").value = ajustes["ui.nombre_app"] || "FORJA";
    // Interfaces (Rama 6, doc 13): una fila por pregunta PREGUNTAR de cada pantalla
    window.ForjaInterfaz.construir(previaApariencia);
    await window.ForjaInterfaz.pintar(ajustes);
    // Rutas ('' = la de serie, que se enseña en gris)
    const rutas = await Promise.all([api("/proyectos").catch(() => ({})), api("/plantillas").catch(() => ({}))]);
    $("#aj-dir-proyectos").value = ajustes["proyectos.dir"] || "";
    $("#aj-dir-proyectos").placeholder = rutas[0].dir_base || "";
    $("#aj-dir-export").value = ajustes["export.dir"] || "";
    $("#aj-dir-export").placeholder = "Documentos\\FORJA exportados";
    $("#aj-dir-plantillas").value = ajustes["plantillas.dir"] || "";
    $("#aj-dir-plantillas").placeholder = rutas[1].dir_usuario || "";
    $("#aj-dir-lab").value = ajustes["lab.working_dir"] || "";
    $("#aj-dir-lab").placeholder = "%USERPROFILE%\\FORJA-lab";
    // Avanzado: laboratorio
    $("#aj-lab-backend").value = ajustes["lab.backend"] || "";
    $("#aj-lab-distro").value = ajustes["lab.distro"] || "";
    $("#aj-lab-url").value = ajustes["lab.attackbox_url"] || "";
    $("#aj-probar-res").textContent = "";
    $("#aj-msg").textContent = "";
    tabAjustes(tab || st.ajTab || "modelos");
    $("#scr-007").hidden = false;
  }

  function cerrarAjustes() {
    if (st.ajAntes) aplicarApariencia(st.ajAntes);      // deshace la vista previa no guardada
    $("#scr-007").hidden = true;
  }

  async function guardarAjustes() {
    const cuerpo = {
      "nube.backend": $("#aj-backend").value,
      "nube.claude_bin": $("#aj-bin").value.trim(),
      "nube.modelo": $("#aj-modelo").value,
      "umbral.complejidad_justo": String($("#aj-u-justo").value),
      "umbral.complejidad_nube": String($("#aj-u-nube").value),
      "umbral.factor_salida": String($("#aj-u-salida").value),
      "modelos.precargar": $("#aj-precargar").checked ? "1" : "0",
      "ui.tema": segLeer("aj-tema", "oscuro"),
      "ui.acento": segLeer("aj-acento", "naranja-forja"),
      "ui.densidad": segLeer("aj-densidad", "comoda"),
      "ui.tipografia": segLeer("aj-tipografia", "sistema"),
      "ui.razonamiento": segLeer("aj-razonamiento", "plegar"),
      "ui.telemetria": $("#aj-telemetria").checked ? "1" : "0",
      "ui.nombre_app": $("#aj-nombre-app").value.trim() || "FORJA",
      ...window.ForjaInterfaz.leer(),
      "proyectos.dir": $("#aj-dir-proyectos").value.trim(),
      "export.dir": $("#aj-dir-export").value.trim(),
      "plantillas.dir": $("#aj-dir-plantillas").value.trim(),
      "lab.working_dir": $("#aj-dir-lab").value.trim(),
      "lab.distro": $("#aj-lab-distro").value.trim(),
      "lab.attackbox_url": $("#aj-lab-url").value.trim(),
    };
    if ($("#aj-lab-backend").value) cuerpo["lab.backend"] = $("#aj-lab-backend").value;
    const nuevaClave = $("#aj-backend").value === "api" ? $("#aj-clave").value.trim() : "";
    if (nuevaClave) cuerpo["nube.api_key"] = nuevaClave;
    cuerpo["nube.activada"] = $("#aj-activar").checked ? "1" : "0";
    const msg = $("#aj-msg");
    let r;
    try {
      r = await api("/ajustes", { method: "PUT", body: cuerpo });
    } catch (e) {
      msg.textContent = e.message; msg.className = "nota mal";
      return false;
    }
    window.ForjaApp.ajustes = r.ajustes;
    st.ajAntes = { ...r.ajustes };
    aplicarApariencia(r.ajustes);
    $("#app-nombre").textContent = r.ajustes["ui.nombre_app"] || t("app.nombre");
    document.title = r.ajustes["ui.nombre_app"] || t("app.nombre");
    st.modelos = (await api("/modelos")).modelos;   // la etiqueta del tier Nube puede haber cambiado
    await refrescarSalud();
    msg.textContent = t("s007.guardado"); msg.className = "nota ok";
    return true;
  }

  async function borrarClave() {
    await api("/ajustes", { method: "PUT", body: { "nube.api_key": "" } }).catch(() => {});
    if (st.tier === "nube") { st.tier = "pequeno"; guardarEstado(); }
    await refrescarSalud();
    await abrirAjustes();
  }

  function pintarProveedor() {
    const sus = $("#aj-backend").value === "claude_code";
    $("#aj-bloque-clave").hidden = sus;
    $("#aj-bloque-bin").hidden = !sus;
    const est = $("#aj-prov-estado");
    if (sus) {
      est.textContent = t(st.tieneCli ? "s007.prov.cli_si" : "s007.prov.cli_no");
      est.className = "nota" + (st.tieneCli ? " ok" : " mal");
    } else {
      est.textContent = t("s007.prov.api"); est.className = "nota";
    }
  }

  function pintarEstadoClave(hay) {
    $("#aj-clave").value = "";
    $("#aj-clave").placeholder = hay ? t("s007.clave.placeholder_hay") : t("s007.clave.placeholder_no");
    $("#aj-clave-estado").textContent = hay ? t("s007.clave.hay") : t("s007.clave.no");
    $("#aj-clave-estado").className = "nota" + (hay ? " ok" : "");
    $("#aj-borrar-clave").hidden = !hay;
  }

  async function probarNube() {
    const res = $("#aj-probar-res");
    if (!(await guardarAjustes())) return;            // guarda primero la clave/modelo escritos
    const { ajustes } = await api("/ajustes");
    pintarEstadoClave(ajustes["nube.tiene_clave"] === "1");
    res.textContent = t("s007.probando"); res.className = "nota";
    try {
      const r = await api("/nube/probar", { method: "POST" });
      res.textContent = `${t("s007.probar_ok")} · ${r.nombre || r.modelo}`; res.className = "nota ok";
    } catch (e) {
      res.textContent = e.message; res.className = "nota mal";
    }
  }

  // ---------------------------------------------------------------- SCR-008 estado del sistema
  function abrirS008() { pintarS008(); $("#scr-008").hidden = false; }
  function cerrarS008() { $("#scr-008").hidden = true; }

  function pintarS008() {
    const s = st.salud || { ollama: "caido", modelos: [] };
    const motor = $("#s008-motor");
    if (s.ollama === "ok") {
      motor.innerHTML = `<span class="nombre">Ollama ${esc(s.ollama_version || "")}</span><span class="der"><span class="estado-ok">${esc(t("s008.motor.ok"))}</span></span>`;
    } else if (s.ollama_instalado === false) {
      motor.innerHTML = `<span class="nombre">Ollama</span><span class="der"><span class="estado-mal">${esc(t("s008.motor.no_instalado"))}</span></span>` +
        `<span class="instrucciones">${esc(t("s008.instalar")).replace("winget install Ollama.Ollama", "<code>winget install Ollama.Ollama</code>")}</span>`;
    } else {
      motor.innerHTML = `<span class="nombre">Ollama</span><span class="detalle">${esc(t("s008.motor.caido"))}</span>` +
        `<span class="der"><button class="boton" type="button" id="s008-arrancar">${esc(t("s008.arrancar"))}</button></span>`;
      $("#s008-arrancar").addEventListener("click", arrancarOllama);
    }

    const cont = $("#s008-modelos");
    cont.innerHTML = "";
    const lista = s.modelos?.length ? s.modelos : st.modelos.filter((m) => m.tier !== "nube");
    for (const m of lista) {
      const fila = document.createElement("div");
      fila.className = "fila";
      const dl = st.descargas[m.alias];
      const nec = m.necesario ? `<span class="etq-necesario si">${esc(t("s008.necesario"))}</span>` : `<span class="etq-necesario">${esc(t("s008.opcional"))}</span>`;
      let der;
      if (m.instalado) der = `<span class="estado-ok">${esc(t("s008.instalado"))}</span>`;
      else if (dl && !dl.fin && !dl.error) der = `<span class="detalle">${esc(dl.pct != null ? dl.pct.toLocaleString("es-ES") + " %" : t("s008.descargando"))}</span>`;
      else {
        const conf = st.confirmarDescarga === m.alias;
        const txt = conf ? `${t("s008.confirmar")} (${gb(m.tamano_disco_mb)} GB)` : t("s008.descargar");
        der = `<button class="${conf ? "boton" : "boton-txt"}" type="button" data-descargar="${esc(m.alias)}" ${s.ollama === "ok" ? "" : "disabled"}>${esc(txt)}</button>`;
      }
      fila.innerHTML = `<span class="nombre">${esc(m.etiqueta)}</span>` +
        `<span class="detalle">${esc(t("tier." + m.tier))} · ~${gb(m.tamano_disco_mb)} GB</span>${nec}<span class="der">${der}</span>` +
        (dl && !dl.fin && !dl.error ? `<div class="barra"><span style="width:${dl.pct || 0}%"></span></div><span class="instrucciones">${esc(dl.estado || "")}</span>` : "") +
        (dl && dl.error ? `<span class="instrucciones" style="color:var(--bad)">${esc(dl.error)}</span>` : "");
      cont.append(fila);
    }
    cont.querySelectorAll("[data-descargar]").forEach((b) => b.addEventListener("click", () => {
      const alias = b.dataset.descargar;
      if (st.confirmarDescarga !== alias) { st.confirmarDescarga = alias; pintarS008(); return; }
      st.confirmarDescarga = null;
      descargarModelo(alias);
    }));

    // ADR-0006: Claude Code (tier Nube) — solo si la Nube está activada por suscripción.
    const nubeSec = $("#s008-nube-sec");
    const ne = s.nube_estado;
    nubeSec.hidden = !ne;
    if (ne) {
      const ok = ne === "ok";
      $("#s008-nube").innerHTML = `<span class="nombre">Claude Code</span>` +
        `<span class="der"><span class="${ok ? "estado-ok" : "estado-mal"}">${esc(t("s008.nube." + ne))}</span></span>` +
        (ok ? "" : `<span class="instrucciones">${esc(t("s008.nube.guia." + ne)).replace(/(claude auth login)/, "<code>$1</code>")}</span>`);
    }

    const met = [];
    if (s.ram_libre_mb != null) met.push(`${t("s008.ram")}: ${gb(s.ram_libre_mb)} GB`);
    if (s.disco_libre_mb != null) met.push(`${t("s008.disco")}: ${gb(s.disco_libre_mb)} GB`);
    $("#s008-metricas").textContent = met.join(" · ");
  }

  async function arrancarOllama() {
    const b = $("#s008-arrancar");
    if (b) { b.disabled = true; b.textContent = t("s008.arrancando"); }
    try {
      const r = await api("/ollama/arrancar", { method: "POST" });
      if (r.instalado === false && st.salud) st.salud.ollama_instalado = false;
    } catch { /* se refleja al refrescar */ }
    await refrescarSalud();
    pintarS008();
    if (!necesitaS008(st.salud)) { cerrarS008(); cargarModeloActual(); }
  }

  async function descargarModelo(alias) {
    const dl = (st.descargas[alias] = { pct: null, estado: "", error: null, fin: false });
    pintarS008();
    let pendiente = false;
    const repintar = () => {
      if (pendiente) return;
      pendiente = true;
      requestAnimationFrame(() => { pendiente = false; pintarS008(); pintarModelosAjustes(); });
    };
    try {
      await sse("/modelos/descargar", { alias }, (ev, d) => {
        if (ev === "progreso") { if (d.porcentaje != null) dl.pct = d.porcentaje; dl.estado = d.estado; }
        else if (ev === "fin") dl.fin = true;
        else if (ev === "error") dl.error = d.mensaje;
        repintar();
      });
    } catch (e) {
      dl.error = e.message;
    }
    await refrescarSalud();
    pintarS008();
    pintarModelosAjustes();
    if (dl.fin) cargarModeloActual();
  }

  // ---------------------------------------------------------------- arranque (ST-060)
  function textosEstaticos() {
    document.querySelectorAll("[data-t]").forEach((n) => { n.textContent = t(n.dataset.t); });
    $("#btn-tema").title = t("tema.cambiar");
    $("#btn-tema").setAttribute("aria-label", t("tema.cambiar"));
    $("#btn-hilos").title = t("hilos.titulo");
    $("#btn-nuevo-hilo").title = t("hilos.nuevo");
    $("#btn-ajustes").title = t("ajustes.abrir");
    $("#btn-ajustes").setAttribute("aria-label", t("ajustes.abrir"));
    document.querySelectorAll("[data-t-ph]").forEach((n) => { n.placeholder = t(n.dataset.tPh); });
    document.querySelectorAll("[data-t-title]").forEach((n) => { n.title = t(n.dataset.tTitle); n.setAttribute("aria-label", n.title); });
    $("#tl-entrada").placeholder = t("tareas.placeholder");
  }

  function enlazarEventos() {
    $("#btn-enviar").addEventListener("click", () => enviar());
    entrada().addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!st.gen) enviar(); }
    });
    entrada().addEventListener("input", autoAltura);
    $("#btn-hilos").addEventListener("click", alternarHilos);
    $("#btn-nuevo-hilo").addEventListener("click", nuevoHilo);
    $("#btn-nuevo-hilo-2").addEventListener("click", nuevoHilo);
    $("#chip-estado").addEventListener("click", async () => { await refrescarSalud(); abrirS008(); });
    $("#btn-tema").addEventListener("click", () => {
      const nuevo = document.documentElement.dataset.theme === "oscuro" ? "claro" : "oscuro";   // fija uno (deja "sistema")
      aplicarTema(nuevo);
      window.ForjaApp.ajustes["ui.tema"] = nuevo;
      api("/ajustes", { method: "PUT", body: { "ui.tema": nuevo } }).catch(() => {});
    });
    $("#s008-reintentar").addEventListener("click", async () => {
      await refrescarSalud();
      pintarS008();
      if (!necesitaS008(st.salud)) { cerrarS008(); cargarModeloActual(); }
    });
    $("#s008-continuar").addEventListener("click", cerrarS008);
    // SCR-006
    $("#bj-grande").addEventListener("click", () => decidir("grande"));
    $("#bj-trocear").addEventListener("click", () => decidir("trocear"));
    $("#bj-seguir").addEventListener("click", () => decidir("seguir"));
    $("#bj-cerrar").addEventListener("click", () => { st.pendiente = null; cerrarAvisos(); });
    $("#bj-nube").addEventListener("click", (e) => decidir(e.currentTarget.dataset.accion));
    $("#s006-grande").addEventListener("click", () => decidir("grande"));
    $("#s006-nube").addEventListener("click", (e) => decidir(e.currentTarget.dataset.accion));
    $("#s006-local").addEventListener("click", () => decidir("trocear"));
    $("#s006-igual").addEventListener("click", () => decidir("seguir"));
    // SCR-007
    $("#btn-ajustes").addEventListener("click", () => abrirAjustes().catch(() => {}));
    $("#aj-guardar").addEventListener("click", async () => { if (await guardarAjustes()) $("#scr-007").hidden = true; });
    $("#aj-cancelar").addEventListener("click", cerrarAjustes);
    document.querySelectorAll("#aj-tabs [role=tab]").forEach((b) => b.addEventListener("click", () => tabAjustes(b.dataset.tab)));
    for (const id of ["aj-tema", "aj-acento", "aj-densidad", "aj-tipografia", "aj-razonamiento"]) {
      document.querySelectorAll(`#${id} [data-v]`).forEach((b) => b.addEventListener("click", () => { segValor(id, b.dataset.v); previaApariencia(); }));
    }
    document.querySelectorAll("#aj-acento [data-v]").forEach((b) => { b.title = b.dataset.v.replace("-", " "); b.setAttribute("aria-label", b.title); });
    $("#aj-borrar-clave").addEventListener("click", borrarClave);
    $("#aj-probar").addEventListener("click", probarNube);
    $("#aj-backend").addEventListener("change", pintarProveedor);
    document.addEventListener("keydown", (e) => {
      if (e.key === "." && (e.ctrlKey || e.metaKey)) { e.preventDefault(); alternarRazon(); return; }
      if (e.key !== "Escape") return;
      if (!$("#scr-008").hidden) cerrarS008();
      if (!$("#scr-007").hidden) cerrarAjustes();
      if (!$("#scr-006").hidden) { $("#scr-006").hidden = true; st.pendiente = null; }
    });
    document.addEventListener("click", async (e) => {
      const acc = e.target.closest("[data-accion='s008']");
      if (acc) { await refrescarSalud(); abrirS008(); return; }
      if (e.target.closest("[data-accion='detener']")) { st.gen?.abort(); return; }
      if (e.target.closest("[data-accion='razon']")) { alternarRazon(); return; }
      const guardar = e.target.closest(".code-guardar");
      if (guardar) { window.ForjaProyectos?.guardarBloque(guardar); return; }
      const copiar = e.target.closest(".code-copiar");
      if (copiar) {
        const codigo = copiar.closest(".code").querySelector("code").textContent;
        try { await navigator.clipboard.writeText(codigo); }
        catch {
          const tmp = document.createElement("textarea");
          tmp.value = codigo; document.body.append(tmp); tmp.select(); document.execCommand("copy"); tmp.remove();
        }
        copiar.textContent = t("code.copiado");
        copiar.classList.add("ok");
        setTimeout(() => { copiar.textContent = t("code.copiar"); copiar.classList.remove("ok"); }, 1500);
      }
    });
  }

  // Puente para módulos de modo (ui/tareas.js).
  window.ForjaApp = {
    api, t, fmt, esc, st, etiquetaPara, refrescarSalud, actualizarLinea, ajustes: {},
    colocarChat, actualizarCompositor, pintarVacio, cargarHilos: alEntrarModoChat,
    // Rama 5 (ui/proyectos.js)
    clave, hiloActual, recargarHilos: cargarHilos, entrada, autoAltura, abrirAjustes, alternarRazon,
  };

  async function init() {
    T = await (await fetch("/ui/strings.es.json")).json();
    textosEstaticos();
    enlazarEventos();

    const { ajustes } = await api("/ajustes");
    window.ForjaApp.ajustes = ajustes;
    aplicarApariencia(ajustes);
    $("#app-nombre").textContent = ajustes["ui.nombre_app"] || t("app.nombre");
    document.title = ajustes["ui.nombre_app"] || t("app.nombre");
    if (MODOS.some((m) => m.id === ajustes["estado.modo"])) st.modo = ajustes["estado.modo"];
    if (TIERS.includes(ajustes["estado.tier"])) st.tier = ajustes["estado.tier"];
    if (ESFUERZOS.includes(ajustes["estado.esfuerzo"])) st.esfuerzo = ajustes["estado.esfuerzo"];
    const hilo = parseInt(ajustes["estado.hilo.scripts"], 10);
    st.hilo.scripts = Number.isFinite(hilo) ? hilo : null;

    const m = await api("/modelos");
    st.modelos = m.modelos;
    st.familia = m.familia;
    st.override = m.override || {};

    pintarModos();
    st.listo = true;              // a partir de aquí, aplicarApariencia repinta selectores al momento
    mostrarVista();
    actualizarCompositor();
    await refrescarSalud();
    if (st.tier === "nube" && !st.salud.nube_activada) { st.tier = "pequeno"; pintarSelector(); }

    if (st.modo === "scripts") {
      await cargarHilos();
      if (st.hilo.scripts && st.hilos.some((h) => h.id === st.hilo.scripts)) await abrirHilo(st.hilo.scripts);
      else { st.hilo.scripts = null; pintarVacio(); pintarHilos(); }
    } else st.hilosDe = "pendiente";

    window.ForjaProyectos?.init();
    if (necesitaS008(st.salud)) abrirS008();
    else if (esChat()) entrada().focus();

    // Refresco ligero del estado (p. ej. si arrancas Ollama por fuera).
    setInterval(() => { if (!st.gen && !st.cargandoModelo) refrescarSalud(); }, 20000);
  }

  init().catch((e) => {
    document.body.innerHTML = `<pre style="padding:20px;color:#e2584a">FORJA no pudo iniciar la interfaz:\n${esc(String(e && e.message || e))}</pre>`;
  });
})();
