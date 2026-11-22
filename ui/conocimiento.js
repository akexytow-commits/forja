/* FORJA — Rama 9: Base de Conocimiento / RAG local (MOD-120, doc 24).
   SCR-050 Bases de conocimiento: BTN-103 Nueva base · BTN-104 Añadir documento (pegar / archivos / carpeta /
   paquete Flipper Zero; lanza el indexado) · BTN-105 Reindexar.
   Compositor (SCR-001): BTN-106 «Usar base: <nombre>» · BTN-107 «Ver fuentes citadas» bajo cada respuesta. */
(() => {
  "use strict";

  const A = () => window.ForjaApp;
  const $ = (s, r = document) => r.querySelector(s);
  const t = (k) => A().t(k);
  const fmt = (k, v) => A().fmt(k, v);
  const esc = (s) => A().esc(String(s ?? ""));
  const MAX_ARCHIVO = 5 * 1024 * 1024;

  const st = {
    bases: [], activa: null, ultima: null, sel: null, detalle: null, tab: "pegar",
    modelo: "nomic-embed-text", k: 6, selectorNativo: false, progreso: null, msg: null, resultados: null,
  };
  const base = (id) => st.bases.find((b) => b.id === id) || null;

  // ---------------------------------------------------------------- datos
  async function cargar() {
    try {
      const r = await A().api("/kb");
      st.bases = r.bases;
      st.modelo = r.modelo_embeddings;
      st.k = r.k;
      st.selectorNativo = r.selector_nativo;
      const id = parseInt(r.activa, 10);
      st.activa = base(id) ? id : null;
    } catch { st.bases = []; }
    pintarChip();
  }

  function guardarActiva() {
    A().api("/ajustes", { method: "PUT", body: { "estado.kb": st.activa ? String(st.activa) : "" } }).catch(() => {});
  }

  function activar(id) {
    st.activa = id && base(id) ? id : null;
    if (st.activa) st.ultima = st.activa;
    guardarActiva();
    pintarChip();
    if (!$("#scr-050").hidden) pintarLista();
  }

  // ---------------------------------------------------------------- BTN-106 chip del compositor
  function pintarChip() {
    const grupo = $("#kb-grupo");
    if (!grupo || !A()) return;
    const app = A();
    grupo.hidden = app.st.modo === "tareas" || (app.esChat && !app.esChat());
    const b = base(st.activa);
    const btn = $("#btn-kb-usar");
    $("#btn-kb-txt").textContent = b ? fmt("kb.usar", { nombre: b.nombre }) : t("kb.sin_base");
    btn.classList.toggle("con", !!b);
    btn.setAttribute("aria-pressed", String(!!b));
    btn.title = b ? `${fmt("kb.meta", { docs: b.documentos, frag: b.fragmentos })}` : t("kb.elegir");
  }

  function alternarUso() {
    if (st.activa) { st.ultima = st.activa; activar(null); return; }
    if (st.ultima && base(st.ultima)) { activar(st.ultima); return; }
    if (st.bases.length === 1) { activar(st.bases[0].id); return; }
    abrirPop();
  }

  function abrirPop() {
    const pop = $("#pop-kb");
    const abrir = pop.hidden;
    pop.hidden = !abrir;
    $("#btn-kb-elegir").setAttribute("aria-expanded", String(abrir));
    if (!abrir) return;
    const ul = $("#kb-pop-lista");
    const filas = [`<li><button type="button" class="plant kb-op${st.activa ? "" : " activo"}" data-kb=""><strong>${esc(t("kb.ninguna"))}</strong></button></li>`];
    for (const b of st.bases) {
      filas.push(`<li><button type="button" class="plant kb-op${b.id === st.activa ? " activo" : ""}" data-kb="${b.id}">` +
        `<strong>${esc(b.nombre)}</strong><span>${esc(metaBase(b))}</span></button></li>`);
    }
    if (!st.bases.length) filas.push(`<li class="pop-vacio">${esc(t("kb.vacio"))}</li>`);
    ul.innerHTML = filas.join("");
  }
  function cerrarPop() { $("#pop-kb").hidden = true; $("#btn-kb-elegir").setAttribute("aria-expanded", "false"); }

  const metaBase = (b) => fmt("kb.meta", { docs: b.documentos, frag: b.fragmentos }) +
    (b.pendientes ? ` · ${fmt("kb.meta_pend", { pend: b.pendientes })}` : "");

  // ---------------------------------------------------------------- BTN-107 fuentes bajo la respuesta
  function corto(origen) {
    if (!origen || (!origen.includes("/") && !origen.includes("\\"))) return origen || "";
    return origen.split(/[\\/]/).slice(-3).join("/");
  }

  function pintarFuentes(pie, s) {
    const f = s.fuentes;
    if (!f) return;
    const frs = f.fragmentos || [];
    const caja = document.createElement("div");
    caja.className = "kb-fuentes";
    if (!frs.length) {
      if (f.aviso) caja.innerHTML = `<p class="kb-nota">${esc(f.aviso)}</p>`;
      pie.append(caja);
      return;
    }
    if (s.streaming) {
      caja.innerHTML = `<p class="kb-nota"><svg><use href="#i-libro"/></svg>${esc(fmt("kb.fuentes.usando", { n: frs.length, nombre: f.nombre }))}</p>`;
      pie.append(caja);
      return;
    }
    const cit = f.citadas || [];
    const abierto = !!s._fuentesAbiertas;
    const etiqueta = abierto ? t("kb.fuentes.ocultar")
      : cit.length ? fmt("kb.fuentes.ver", { n: cit.length }) : fmt("kb.fuentes.ver_consultadas", { n: frs.length });
    // Primero las citadas (en el orden en que las citó), luego el resto.
    const orden = [...cit.map((n) => frs.find((x) => x.n === n)).filter(Boolean), ...frs.filter((x) => !cit.includes(x.n))];
    caja.innerHTML = `<button type="button" class="boton-txt peq kb-ver" aria-expanded="${abierto}"><svg><use href="#i-libro"/></svg><span>${esc(etiqueta)}</span></button>` +
      (abierto ? `<div class="kb-lista-f"><p class="kb-de">${esc(fmt("kb.fuentes.de", { nombre: f.nombre }))}</p><ol>` + orden.map((x) =>
        `<li class="${cit.includes(x.n) ? "citada" : ""}"><details><summary><span class="kb-n">[${x.n}]</span> <strong>${esc(x.titulo)}</strong>` +
        ` <span class="kb-org">${esc(corto(x.origen))}</span> <span class="kb-score">${esc(t(cit.includes(x.n) ? "kb.fuentes.citada" : "kb.fuentes.consultada"))} · ${Number(x.score).toFixed(2)}</span></summary>` +
        `<pre class="kb-txt">${esc(x.texto)}</pre></details></li>`).join("") + "</ol></div>" : "");
    caja.querySelector(".kb-ver").addEventListener("click", () => {
      s._fuentesAbiertas = !s._fuentesAbiertas;
      caja.remove();
      pintarFuentes(pie, s);
    });
    pie.append(caja);
  }

  // ---------------------------------------------------------------- SCR-050
  async function abrir(id) {
    $("#scr-050").hidden = false;
    cerrarPop();
    await cargar();
    st.sel = (id && base(id)) ? id : (base(st.sel) ? st.sel : (st.activa || st.bases[0]?.id || null));
    st.msg = null; st.resultados = null;
    pintarLista();
    await cargarDetalle();
    if (!st.bases.length) $("#kb-nueva-nombre").focus();
  }
  function cerrar() { $("#scr-050").hidden = true; pintarChip(); }

  function pintarLista() {
    const ul = $("#kb-lista");
    $("#kb-modelo").textContent = fmt("kb.modelo", { modelo: st.modelo });
    const sel = $("#kb-k");
    if (!sel.options.length) sel.innerHTML = Array.from({ length: 10 }, (_, i) => `<option value="${i + 1}">${i + 1}</option>`).join("");
    sel.value = String(st.k);
    if (!st.bases.length) { ul.innerHTML = `<li class="pop-vacio">${esc(t("kb.vacio"))}</li>`; return; }
    ul.innerHTML = st.bases.map((b) => `<li><button type="button" class="kb-item${b.id === st.sel ? " sel" : ""}" data-sel="${b.id}">` +
      `<strong>${esc(b.nombre)}${b.id === st.activa ? ` <span class="kb-pastilla">${esc(t("kb.en_uso"))}</span>` : ""}</strong>` +
      `<span>${esc(metaBase(b))}</span></button></li>`).join("");
  }

  async function cargarDetalle() {
    if (!st.sel) { st.detalle = null; pintarDetalle(); return; }
    try { st.detalle = await A().api(`/kb/${st.sel}`); } catch (e) { st.detalle = null; st.msg = { mal: true, txt: e.message }; }
    pintarDetalle();
  }

  function pintarDetalle() {
    const cont = $("#kb-det");
    const d = st.detalle;
    if (!d) { cont.innerHTML = st.bases.length ? "" : `<div class="kb-intro">${esc(t("kb.docs_vacio"))}</div>`; return; }
    const ocupado = !!st.progreso;
    const docs = d.lista.length
      ? `<ul class="kb-docs">${d.lista.map((x) => `<li><span class="kb-doc-t" title="${esc(x.origen)}">${esc(x.titulo)}</span>` +
        `<span class="kb-doc-e ${x.indexado_at ? "ok" : "pend"}">${esc(x.indexado_at ? fmt(x.num_chunks === 1 ? "kb.doc_indexado1" : "kb.doc_indexado", { n: x.num_chunks }) : t("kb.doc_pendiente"))}</span>` +
        `<button type="button" class="icono-btn peq" data-borrar-doc="${x.id}" title="${esc(t("kb.doc_borrar"))}" aria-label="${esc(t("kb.doc_borrar"))}"${ocupado ? " disabled" : ""}>✕</button></li>`).join("")}</ul>`
      : `<p class="kb-nota">${esc(t("kb.docs_vacio"))}</p>`;
    const tabs = ["pegar", "archivos", "carpeta", "flipper"].map((k) =>
      `<button type="button" role="tab" class="kb-tab${st.tab === k ? " on" : ""}" aria-selected="${st.tab === k}" data-tab="${k}">${esc(t("kb.tab." + k))}</button>`).join("");
    let form = "";
    if (st.tab === "pegar") {
      form = `<input id="kb-pegar-titulo" type="text" maxlength="200" placeholder="${esc(t("kb.pegar.titulo"))}">` +
        `<textarea id="kb-pegar-txt" rows="6" spellcheck="false" placeholder="${esc(t("kb.pegar.ph"))}"></textarea>`;
    } else if (st.tab === "archivos") {
      form = `<p class="kb-ayuda">${esc(t("kb.archivos.ayuda"))}</p><input type="file" id="kb-archivos" multiple accept=".md,.markdown,.txt,.pdf" hidden>` +
        `<button type="button" class="boton-txt" id="kb-archivos-btn">${esc(t("kb.archivos.elegir"))}</button> <span class="kb-nota" id="kb-archivos-n"></span>`;
    } else {
      const fl = st.tab === "flipper";
      form = `<p class="kb-ayuda">${esc(t(fl ? "kb.flipper.ayuda" : "kb.carpeta.ayuda"))}</p><div class="kb-ruta">` +
        `<input id="kb-ruta" type="text" spellcheck="false" placeholder="${esc(t(fl ? "kb.flipper.ph" : "kb.carpeta.ph"))}">` +
        (st.selectorNativo ? `<button type="button" class="boton-txt" id="kb-ruta-elegir">${esc(t("kb.carpeta.elegir"))}</button>` : "") + "</div>";
    }
    const prog = st.progreso
      ? `<div class="kb-prog"><div class="kb-barra"><span style="width:${st.progreso.total ? Math.round(100 * st.progreso.hechos / st.progreso.total) : 0}%"></span></div>` +
        `<p class="kb-nota">${esc(fmt("kb.indexando", st.progreso))}${st.progreso.documento ? " · " + esc(fmt("kb.indexando_doc", { doc: st.progreso.documento })) : ""}</p></div>` : "";
    const msg = st.msg ? `<p class="kb-msg${st.msg.mal ? " mal" : ""}">${esc(st.msg.txt)}</p>` : "";
    const res = st.resultados === null ? "" : (st.resultados.length
      ? `<ol class="kb-res">${st.resultados.map((x) => `<li><span class="kb-score">${Number(x.score).toFixed(3)}</span> <strong>${esc(x.titulo)}</strong> <span class="kb-org">${esc(corto(x.origen))}</span><pre class="kb-txt">${esc(x.texto.slice(0, 600))}${x.texto.length > 600 ? "…" : ""}</pre></li>`).join("")}</ol>`
      : `<p class="kb-nota">${esc(t("kb.probar.nada"))}</p>`);
    cont.innerHTML =
      `<div class="kb-det-cab"><div><h3>${esc(d.nombre)}</h3><p class="kb-nota">${esc(metaBase(d))} · ${esc(d.embed_modelo)}</p></div>` +
      `<div class="kb-det-acc">` +
      `<button type="button" class="boton${d.id === st.activa ? "-txt" : ""} peq" id="kb-usar">${esc(t(d.id === st.activa ? "kb.en_uso" : "kb.usar_chat"))}</button>` +
      (d.pendientes ? `<button type="button" class="boton-txt peq" id="kb-indexar"${ocupado ? " disabled" : ""}>${esc(t("kb.indexar"))}</button>` : "") +
      `<button type="button" class="boton-txt peq" id="btn-kb-reindexar"${ocupado || !d.documentos ? " disabled" : ""}>${esc(t("kb.reindexar"))}</button>` +
      `<button type="button" class="boton-txt peq mal" id="kb-borrar"${ocupado ? " disabled" : ""}>${esc(t("kb.borrar"))}</button></div></div>` +
      prog + msg +
      `<h4>${esc(t("kb.docs"))}</h4>${docs}` +
      `<h4>${esc(t("kb.anadir"))}</h4><div class="kb-tabs" role="tablist">${tabs}</div><div class="kb-form">${form}` +
      `<div class="kb-fila"><button type="button" class="boton" id="btn-kb-anadir"${ocupado ? " disabled" : ""}><svg><use href="#i-mas"/></svg><span>${esc(t("kb.anadir_btn"))}</span></button></div></div>` +
      `<h4>${esc(t("kb.probar"))}</h4><form class="kb-ruta" id="kb-probar"><input id="kb-probar-q" type="text" placeholder="${esc(t("kb.probar.ph"))}"><button type="submit" class="boton-txt">${esc(t("kb.probar.btn"))}</button></form>${res}`;
  }

  const aviso = (txt, mal = false) => { st.msg = { txt, mal }; pintarDetalle(); };

  async function crear(ev) {
    ev.preventDefault();
    const nombre = $("#kb-nueva-nombre").value.trim();
    if (!nombre) return;
    try {
      const b = await A().api("/kb", { method: "POST", body: { nombre } });
      $("#kb-nueva-nombre").value = "";
      await cargar();
      st.sel = b.id; st.msg = null; st.resultados = null;
      if (!st.activa) activar(b.id);
      pintarLista();
      await cargarDetalle();
    } catch (e) { st.msg = { mal: true, txt: e.message }; pintarDetalle(); }
  }

  const leerB64 = (f) => new Promise((ok, mal) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(",", 2)[1] || "");
    r.onerror = () => mal(r.error);
    r.readAsDataURL(f);
  });

  async function anadir() {
    const id = st.sel;
    const peticiones = [];
    if (st.tab === "pegar") {
      const contenido = $("#kb-pegar-txt").value;
      if (!contenido.trim()) return;
      peticiones.push({ contenido, titulo: $("#kb-pegar-titulo").value.trim() || null });
    } else if (st.tab === "archivos") {
      const files = [...($("#kb-archivos").files || [])];
      if (!files.length) { $("#kb-archivos").click(); return; }
      for (const f of files) {
        if (f.size > MAX_ARCHIVO) { peticiones.push({ _omitido: `${f.name}: > 5 MB` }); continue; }
        peticiones.push({ nombre: f.name, contenido_b64: await leerB64(f) });
      }
    } else {
      const ruta = $("#kb-ruta").value.trim();
      if (!ruta) { $("#kb-ruta").focus(); return; }
      peticiones.push({ ruta, semilla: st.tab === "flipper" });
    }
    let n = 0;
    const omitidos = [];
    for (const p of peticiones) {
      if (p._omitido) { omitidos.push(p._omitido); continue; }
      try {
        const r = await A().api(`/kb/${id}/documentos`, { method: "POST", body: p });
        n += r.documentos.length;
        omitidos.push(...r.omitidos.map((o) => `${corto(o.origen)}: ${o.motivo}`));
      } catch (e) { omitidos.push(e.message); }
    }
    const txt = [n ? fmt("kb.anadidos", { n }) : "", omitidos.length ? fmt("kb.omitidos", { n: omitidos.length, motivo: omitidos.slice(0, 3).join(" · ") }) : ""].filter(Boolean).join(" ");
    st.msg = { txt, mal: !n };
    await cargar(); pintarLista(); await cargarDetalle();
    if (n) await indexar(false, txt);
  }

  /* API-072: progreso por SSE. */
  async function indexar(todo, prefijo = "") {
    const id = st.sel;
    st.progreso = { hechos: 0, total: 0, documento: "" };
    st.msg = prefijo ? { txt: prefijo } : null;
    pintarDetalle();
    let fin = null, err = null;
    try {
      await A().sse(`/kb/${id}/indexar`, { todo }, (ev, d) => {
        if (ev === "inicio") { st.progreso.total = d.fragmentos; }
        else if (ev === "progreso") { Object.assign(st.progreso, d); }
        else if (ev === "fin") { fin = d; }
        else if (ev === "error") { err = d; }
        pintarDetalle();
      });
    } catch (e) { err = { mensaje: e.message }; }
    st.progreso = null;
    if (err) st.msg = { mal: true, txt: err.codigo === "MODELO_FALTANTE" ? `${err.mensaje}` : err.mensaje };
    else if (fin) st.msg = { txt: [prefijo, fin.documentos ? fmt("kb.indexado_ok", { docs: fin.documentos, frag: fin.fragmentos }) : t("kb.nada_pendiente")].filter(Boolean).join(" ") };
    await cargar(); pintarLista(); await cargarDetalle();
  }

  async function probar(ev) {
    ev.preventDefault();
    const q = $("#kb-probar-q").value.trim();
    if (!q) return;
    try {
      const r = await A().api(`/kb/${st.sel}/buscar`, { method: "POST", body: { query: q, k: 5 } });
      st.resultados = r.fragmentos;
      st.msg = null;
    } catch (e) { st.resultados = null; st.msg = { mal: true, txt: e.message }; }
    pintarDetalle();
    $("#kb-probar-q").value = q;
  }

  async function borrarBase() {
    const d = st.detalle;
    if (!d || !confirm(fmt("kb.borrar_conf", { nombre: d.nombre }))) return;
    try {
      await A().api(`/kb/${d.id}`, { method: "DELETE" });
      if (st.activa === d.id) st.activa = null;
      if (st.ultima === d.id) st.ultima = null;
      st.sel = null;
      await cargar();
      st.sel = st.bases[0]?.id || null;
      pintarLista(); await cargarDetalle();
    } catch (e) { aviso(e.message, true); }
  }

  async function borrarDoc(docId) {
    try {
      await A().api(`/kb/${st.sel}/documentos/${docId}`, { method: "DELETE" });
      await cargar(); pintarLista(); await cargarDetalle();
    } catch (e) { aviso(e.message, true); }
  }

  async function elegirCarpeta() {
    try {
      const r = await A().api("/sistema/elegir-carpeta", { method: "POST", body: { inicial: $("#kb-ruta").value.trim() || null } });
      if (r?.ruta) $("#kb-ruta").value = r.ruta;
    } catch (e) { aviso(e.message, true); }
  }

  // ---------------------------------------------------------------- eventos
  function enlazar() {
    $("#btn-kb").addEventListener("click", () => abrir());
    $("#kb-cerrar").addEventListener("click", cerrar);
    $("#scr-050").addEventListener("click", (e) => { if (e.target.id === "scr-050") cerrar(); });
    $("#kb-nueva").addEventListener("submit", crear);
    $("#kb-k").addEventListener("change", (e) => {       // doc 24 rev. 18: top-k del chat (5–6 recomendado)
      st.k = parseInt(e.target.value, 10);
      A().api("/ajustes", { method: "PUT", body: { "kb.k": e.target.value } }).catch((er) => aviso(er.message, true));
    });
    $("#btn-kb-usar").addEventListener("click", alternarUso);
    $("#btn-kb-elegir").addEventListener("click", abrirPop);
    $("#kb-gestionar").addEventListener("click", () => abrir(st.activa));
    $("#kb-pop-lista").addEventListener("click", (e) => {
      const b = e.target.closest("[data-kb]");
      if (!b) return;
      activar(b.dataset.kb ? parseInt(b.dataset.kb, 10) : null);
      cerrarPop();
    });
    document.addEventListener("click", (e) => {
      if (!$("#pop-kb").hidden && !e.target.closest(".kb-ancla")) cerrarPop();
    });
    $("#kb-lista").addEventListener("click", async (e) => {
      const b = e.target.closest("[data-sel]");
      if (!b || st.progreso) return;
      st.sel = parseInt(b.dataset.sel, 10); st.msg = null; st.resultados = null;
      pintarLista(); await cargarDetalle();
    });
    $("#kb-det").addEventListener("click", (e) => {
      const tab = e.target.closest("[data-tab]");
      if (tab) { st.tab = tab.dataset.tab; pintarDetalle(); return; }
      const bd = e.target.closest("[data-borrar-doc]");
      if (bd) { borrarDoc(parseInt(bd.dataset.borrarDoc, 10)); return; }
      const id = e.target.closest("button")?.id;
      if (id === "kb-usar") activar(st.activa === st.sel ? null : st.sel);
      else if (id === "kb-indexar") indexar(false);
      else if (id === "btn-kb-reindexar") indexar(true);
      else if (id === "kb-borrar") borrarBase();
      else if (id === "btn-kb-anadir") anadir();
      else if (id === "kb-archivos-btn") $("#kb-archivos").click();
      else if (id === "kb-ruta-elegir") elegirCarpeta();
      if (id === "kb-usar") pintarDetalle();
    });
    $("#kb-det").addEventListener("change", (e) => {
      if (e.target.id === "kb-archivos") $("#kb-archivos-n").textContent = [...e.target.files].map((f) => f.name).join(", ");
    });
    $("#kb-det").addEventListener("submit", (e) => { if (e.target.id === "kb-probar") probar(e); });
  }

  window.ForjaKB = { activaId: () => (base(st.activa) ? st.activa : null), pintarChip, pintarFuentes, abrir, cerrar, cargar };

  function init() {
    if (!window.ForjaApp?.t || !document.querySelector("#kb-grupo")) { setTimeout(init, 50); return; }
    enlazar();
    cargar();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
