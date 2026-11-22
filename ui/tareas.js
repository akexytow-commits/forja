/* FORJA — Modo Tareas (SCR-030 captura, SCR-031 plan por días). Rama 3.
   Patrones (17-patrones-planificador.md): P1 lenguaje natural con vista previa (Todoist), P2 fijar +
   reorganizar (Motion/Sunsama), P3 carga del día (Sunsama), P4 subtareas tipo outliner (Logseq).
   ST1 = tablero por columnas; ST2 = minutos y carga del día visibles. */
(() => {
  "use strict";

  const COLUMNAS = ["hoy", "manana", "pasado", "mas", "sin"];
  const DIAS_SEM = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
  const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

  const s = { listas: [], lista: null, tareas: [], hoy: null, cap: 480, editando: null, menu: null,
              organizando: null, arrastrando: null, borrarConfirm: null, cargado: false, ultimo: null };
  let F;   // window.ForjaApp: { api, t, fmt, esc, st, actualizarLinea }
  const $ = (q, r = document) => r.querySelector(q);

  // ---------------------------------------------------------------- fechas
  const isoDe = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const fechaDe = (iso) => { const [a, m, d] = iso.split("-").map(Number); return new Date(a, m - 1, d); };
  const sumar = (iso, n) => { const d = fechaDe(iso); d.setDate(d.getDate() + n); return isoDe(d); };
  const difDias = (a, b) => Math.round((fechaDe(a) - fechaDe(b)) / 86400000);
  const fechaCorta = (iso) => { const d = fechaDe(iso); return `${DIAS_SEM[d.getDay()].slice(0, 3)} ${d.getDate()} ${MESES[d.getMonth()]}`; };

  function columnaDe(t) {
    if (!t.dia_asignado) return "sin";
    const k = difDias(t.dia_asignado, s.hoy);
    if (k <= 0) return "hoy";       // incluye atrasadas
    if (k === 1) return "manana";
    if (k === 2) return "pasado";
    return "mas";
  }
  const diaDeColumna = (col) => ({ hoy: s.hoy, manana: sumar(s.hoy, 1), pasado: sumar(s.hoy, 2), mas: sumar(s.hoy, 3), sin: null }[col]);

  // ---------------------------------------------------------------- árbol (P4)
  function indices() {
    const porId = new Map(s.tareas.map((t) => [t.id, t]));
    const hijas = new Map();
    for (const t of s.tareas) {
      if (t.parent_id == null) continue;
      if (!hijas.has(t.parent_id)) hijas.set(t.parent_id, []);
      hijas.get(t.parent_id).push(t);
    }
    for (const l of hijas.values()) l.sort(ordenar);
    return { porId, hijas };
  }
  const ordenar = (a, b) => (a.dia_asignado || "9999").localeCompare(b.dia_asignado || "9999") || a.orden - b.orden || a.id - b.id;
  const minutos = (t) => t.estimacion_min || 30;

  // ---------------------------------------------------------------- carga
  async function cargar(listaId) {
    const { listas } = await F.api("/listas");
    s.listas = listas;
    const id = listaId ?? s.lista?.id ?? (Number(F.ajustes?.["tareas.lista"]) || null);
    const elegida = listas.find((l) => l.id === id) || listas[0];
    const v = await F.api(`/tareas?lista=${elegida.id}`);
    s.lista = v.lista; s.tareas = v.tareas; s.hoy = v.hoy; s.cap = v.capacidad_dia_min;
    s.cargado = true;
    pintar();
  }

  async function recargar() {
    const v = await F.api(`/tareas?lista=${s.lista.id}`);
    s.lista = v.lista; s.tareas = v.tareas; s.hoy = v.hoy; s.cap = v.capacidad_dia_min;
    const { listas } = await F.api("/listas");
    s.listas = listas;
    pintar();
  }

  function error(e) {
    const el = $("#tl-msg");
    el.textContent = e.message || String(e);
    el.className = "tl-msg mal";
    el.hidden = false;
  }
  function aviso(txt, clase = "") {
    const el = $("#tl-msg");
    el.textContent = txt; el.className = "tl-msg " + clase; el.hidden = !txt;
  }

  // ---------------------------------------------------------------- pintado
  function pintar() {
    pintarBarra();
    pintarTablero();
  }

  function pintarBarra() {
    const sel = $("#tl-lista");
    sel.innerHTML = s.listas.map((l) =>
      `<option value="${l.id}">${F.esc(l.nombre)}${l.pendientes ? ` (${l.pendientes})` : ""}</option>`).join("");
    sel.value = String(s.lista.id);
    $("#tl-cap").value = s.cap;
    const conDia = s.tareas.some((t) => t.estado !== "hecha" && t.dia_asignado);
    const b = $("#tl-organizar");
    if (!s.organizando) {
      b.querySelector("span").textContent = F.t(conDia ? "tareas.reorganizar" : "tareas.organizar");
      b.disabled = !s.tareas.some((t) => t.estado !== "hecha");
    }
    b.title = F.st.esfuerzo === "bajo" ? F.t("tareas.organizar.bajo") : F.fmt("tareas.organizar.ia", { esfuerzo: F.t("esfuerzo." + F.st.esfuerzo) });
    const res = $("#tl-resumen");
    res.textContent = s.lista.resumen || "";
    res.hidden = !s.lista.resumen;
  }

  function pintarTablero() {
    const tab = $("#tl-tablero");
    const { porId, hijas } = indices();
    const porCol = Object.fromEntries(COLUMNAS.map((c) => [c, []]));
    for (const t of s.tareas) porCol[columnaDe(t)].push(t);
    tab.innerHTML = "";
    for (const col of COLUMNAS) {
      const items = porCol[col].sort(ordenar);
      const ids = new Set(items.map((t) => t.id));
      const raices = items.filter((t) => t.parent_id == null || !ids.has(t.parent_id));
      const el = document.createElement("section");
      el.className = "tl-col";
      el.dataset.col = col;
      el.append(cabeceraColumna(col, items, hijas));
      const lista = document.createElement("div");
      lista.className = "tl-col-lista";
      lista.dataset.col = col;
      const pintarRama = (t, nivel) => {
        lista.append(tarjeta(t, nivel, porId, hijas, ids));
        for (const h of hijas.get(t.id) || []) if (ids.has(h.id)) pintarRama(h, nivel + 1);
      };
      for (const r of raices) pintarRama(r, 0);
      if (!items.length) {
        const v = document.createElement("p");
        v.className = "tl-vacio";
        v.textContent = F.t(`tareas.col.${col}.vacio`);
        lista.append(v);
      }
      prepararSoltar(lista);
      el.append(lista);
      tab.append(el);
    }
    if (s.editando) $(`.tl-card[data-id="${s.editando}"] .tl-ed-texto`)?.focus();
  }

  function cabeceraColumna(col, items, hijas) {
    const cab = document.createElement("header");
    cab.className = "tl-col-cab";
    let sub = "";
    if (col === "hoy" || col === "manana" || col === "pasado") sub = fechaCorta(diaDeColumna(col));
    else if (col === "mas") sub = F.t("tareas.col.mas.sub");
    const hojas = items.filter((t) => !hijas.has(t.id));
    const pend = hojas.filter((t) => t.estado !== "hecha").length;
    cab.innerHTML = `<div class="tl-col-tit"><h3>${F.esc(F.t("tareas.col." + col))}</h3>` +
      `<span class="tl-col-sub">${F.esc(sub)}</span><span class="tl-cuenta">${pend}</span></div>`;
    // P3 carga del día (barra por día con capacidad). "Más adelante" y "Sin asignar": solo el total.
    const total = hojas.reduce((a, t) => a + minutos(t), 0);
    const hecho = hojas.filter((t) => t.estado === "hecha").reduce((a, t) => a + minutos(t), 0);
    if (["hoy", "manana", "pasado"].includes(col)) {
      const pct = Math.min(100, (total / s.cap) * 100);
      const pctH = Math.min(100, (hecho / s.cap) * 100);
      const sobre = total > s.cap;
      const carga = document.createElement("div");
      carga.className = "tl-carga" + (sobre ? " sobre" : "");
      carga.title = sobre ? F.fmt("tareas.carga.sobre", { exceso: horas(total - s.cap) }) : F.t("tareas.carga.ayuda");
      carga.innerHTML = `<div class="tl-barra-carga"><span class="lleno" style="width:${pct}%"></span><span class="hecho" style="width:${pctH}%"></span></div>` +
        `<span class="tl-carga-txt">${horas(total)} / ${horas(s.cap)}${sobre ? ` · ${F.esc(F.t("tareas.carga.sobrecargado"))}` : ""}</span>`;
      cab.append(carga);
    } else if (total) {
      const tot = document.createElement("div");
      tot.className = "tl-carga";
      tot.innerHTML = `<span class="tl-carga-txt">${horas(total)} ${F.esc(F.t("tareas.carga.en_total"))}</span>`;
      cab.append(tot);
    }
    return cab;
  }

  function horas(min) {
    if (min < 60) return `${min} min`;
    const h = Math.floor(min / 60), m = min % 60;
    return m ? `${h} h ${m}` : `${h} h`;
  }

  function tarjeta(t, nivel, porId, hijas, idsCol) {
    const el = document.createElement("article");
    const esPadre = hijas.has(t.id);
    const hecha = t.estado === "hecha";
    el.className = `tl-card p${t.prioridad}` + (hecha ? " hecha" : "") + (esPadre ? " padre" : "") + (t.fijada ? " fijada" : "");
    el.dataset.id = t.id;
    el.style.setProperty("--nivel", nivel);
    el.tabIndex = 0;
    if (s.editando === t.id) { el.append(editor(t)); el.classList.add("editando"); return el; }
    el.draggable = true;

    const atrasada = !hecha && t.dia_asignado && difDias(t.dia_asignado, s.hoy) < 0;
    const padre = t.parent_id != null && !idsCol.has(t.parent_id) ? porId.get(t.parent_id) : null;
    const meta = [];
    if (t.prioridad <= 2 || t.prioridad >= 4) meta.push(`<span class="tl-prio p${t.prioridad}" title="${F.esc(F.t("tareas.prio." + t.prioridad))}">P${t.prioridad}</span>`);
    if (t.hora) meta.push(`<span class="tl-meta-i">${F.esc(t.hora)}</span>`);
    if (esPadre) {
      const hs = todasLasHojas(t.id, hijas);
      const hechas = hs.filter((h) => h.estado === "hecha").length;
      meta.push(`<span class="tl-meta-i">${hechas}/${hs.length} · ${horas(hs.reduce((a, h) => a + minutos(h), 0))}</span>`);
    } else meta.push(`<span class="tl-meta-i${t.estimacion_min ? "" : " estimada"}">${horas(minutos(t))}</span>`);
    if (atrasada) meta.push(`<span class="tl-atrasada">${F.esc(F.fmt("tareas.atrasada", { dia: fechaCorta(t.dia_asignado) }))}</span>`);
    if (columnaDe(t) === "mas" && t.dia_asignado) meta.push(`<span class="tl-meta-i">${F.esc(fechaCorta(t.dia_asignado))}</span>`);
    if (t.origen !== "usuario") meta.push(`<span class="tl-origen">${F.esc(F.t("tareas.origen." + t.origen))}</span>`);

    el.innerHTML =
      `<button class="tl-check" type="button" role="checkbox" aria-checked="${hecha}" title="${F.esc(F.t(hecha ? "tareas.desmarcar" : "tareas.marcar"))}"><svg><use href="#i-check"/></svg></button>` +
      `<div class="tl-cuerpo">` +
        (padre ? `<span class="tl-miga">↳ ${F.esc(padre.texto)}</span>` : "") +
        `<span class="tl-texto">${F.esc(t.texto)}</span>` +
        `<div class="tl-meta">${meta.join("")}</div>` +
      `</div>` +
      `<div class="tl-acciones">` +
        `<button class="tl-pin" type="button" aria-pressed="${!!t.fijada}" title="${F.esc(F.t(t.fijada ? "tareas.desfijar" : "tareas.fijar"))}"><svg><use href="#i-pin"/></svg></button>` +
        `<button class="tl-mas" type="button" title="${F.esc(F.t("tareas.acciones"))}" aria-haspopup="menu"><svg><use href="#i-puntos"/></svg></button>` +
      `</div>`;
    el.querySelector(".tl-check").addEventListener("click", () => patch(t.id, { estado: hecha ? "pendiente" : "hecha" }));
    el.querySelector(".tl-pin").addEventListener("click", () => patch(t.id, { fijada: t.fijada ? 0 : 1 }));
    el.querySelector(".tl-mas").addEventListener("click", (ev) => { ev.stopPropagation(); abrirMenu(t, ev.currentTarget); });
    el.querySelector(".tl-texto").addEventListener("dblclick", () => editar(t.id));
    el.addEventListener("keydown", (ev) => teclado(ev, t));
    el.addEventListener("dragstart", (ev) => {
      s.arrastrando = t.id;
      ev.dataTransfer.effectAllowed = "move";
      ev.dataTransfer.setData("text/plain", String(t.id));
      requestAnimationFrame(() => el.classList.add("arrastrando"));
    });
    el.addEventListener("dragend", () => { s.arrastrando = null; el.classList.remove("arrastrando"); limpiarMarcas(); });
    return el;
  }

  function todasLasHojas(id, hijas) {
    const out = [];
    for (const h of hijas.get(id) || []) {
      if (hijas.has(h.id)) out.push(...todasLasHojas(h.id, hijas));
      else out.push(h);
    }
    return out;
  }

  // ---------------------------------------------------------------- edición (BTN-054)
  function editor(t) {
    const f = document.createElement("form");
    f.className = "tl-editor";
    f.innerHTML =
      `<input class="tl-ed-texto" type="text" maxlength="500" value="${F.esc(t.texto)}" aria-label="${F.esc(F.t("tareas.ed.texto"))}">` +
      `<div class="tl-ed-fila">` +
        `<label>${F.esc(F.t("tareas.ed.prioridad"))}<select class="tl-ed-prio">${[1, 2, 3, 4, 5].map((p) => `<option value="${p}"${p === t.prioridad ? " selected" : ""} title="${F.esc(F.t("tareas.prio." + p))}">P${p} ${F.esc(F.t("tareas.prio." + p))}</option>`).join("")}</select></label>` +
        `<label>${F.esc(F.t("tareas.ed.minutos"))}<input class="tl-ed-min" type="number" min="1" max="1440" step="5" value="${t.estimacion_min ?? ""}" placeholder="30"></label>` +
        `<label>${F.esc(F.t("tareas.ed.dia"))}<input class="tl-ed-dia" type="date" value="${t.dia_asignado ?? ""}"></label>` +
        `<label>${F.esc(F.t("tareas.ed.hora"))}<input class="tl-ed-hora" type="time" value="${t.hora ?? ""}"></label>` +
      `</div>` +
      `<div class="tl-ed-pie"><button class="boton-txt" type="button" data-cancelar>${F.esc(F.t("tareas.ed.cancelar"))}</button>` +
      `<button class="boton" type="submit">${F.esc(F.t("tareas.ed.guardar"))}</button></div>`;
    f.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const cambios = {
        texto: $(".tl-ed-texto", f).value,
        prioridad: Number($(".tl-ed-prio", f).value),
        estimacion_min: $(".tl-ed-min", f).value === "" ? null : Number($(".tl-ed-min", f).value),
        hora: $(".tl-ed-hora", f).value,
      };
      const dia = $(".tl-ed-dia", f).value || null;
      if (dia !== (t.dia_asignado ?? null)) cambios.dia_asignado = dia;
      s.editando = null;
      await patch(t.id, cambios);
    });
    f.querySelector("[data-cancelar]").addEventListener("click", () => { s.editando = null; pintarTablero(); });
    f.addEventListener("keydown", (ev) => { if (ev.key === "Escape") { s.editando = null; pintarTablero(); } ev.stopPropagation(); });
    return f;
  }

  function editar(id) { s.editando = id; cerrarMenu(); pintarTablero(); }

  // ---------------------------------------------------------------- acciones
  async function patch(id, cambios, { silencioso = false } = {}) {
    try {
      await F.api(`/tareas/${id}`, { method: "PATCH", body: cambios });
      await recargar();
      if (!silencioso) aviso("");
      return true;
    } catch (e) { error(e); await recargar().catch(() => {}); return false; }
  }

  function hermanoAnterior(t) {
    // P4 (Logseq): "anidar" = pasa a ser hija de la tarea visible justo encima con su mismo nivel.
    const cards = [...document.querySelectorAll(`.tl-col-lista[data-col="${columnaDe(t)}"] .tl-card`)];
    const i = cards.findIndex((c) => Number(c.dataset.id) === t.id);
    const nivel = Number(cards[i]?.style.getPropertyValue("--nivel") || 0);
    for (let k = i - 1; k >= 0; k--) {
      const n = Number(cards[k].style.getPropertyValue("--nivel") || 0);
      if (n === nivel) return Number(cards[k].dataset.id);
      if (n < nivel) return null;
    }
    return null;
  }

  async function anidar(t) {
    const padre = hermanoAnterior(t);
    if (!padre) { aviso(F.t("tareas.anidar.sin_anterior")); return; }
    await patch(t.id, { parent_id: padre });
    enfocar(t.id);
  }
  async function desanidar(t) {
    if (t.parent_id == null) return;
    const padre = s.tareas.find((x) => x.id === t.parent_id);
    await patch(t.id, { parent_id: padre?.parent_id ?? null });
    enfocar(t.id);
  }
  async function mover(t, delta) {
    const delDia = s.tareas.filter((x) => (x.dia_asignado ?? null) === (t.dia_asignado ?? null)).sort(ordenar);
    const i = delDia.findIndex((x) => x.id === t.id);
    const j = Math.max(0, Math.min(delDia.length - 1, i + delta));
    if (i === j) return;
    await patch(t.id, { orden: j, dia_asignado: t.dia_asignado, fijada: t.fijada });
    enfocar(t.id);
  }
  async function aColumna(t, col) {
    await patch(t.id, { dia_asignado: diaDeColumna(col) });
  }
  async function borrar(t) {
    const hijas = s.tareas.filter((x) => x.parent_id === t.id).length;
    if (hijas && s.borrarConfirm !== t.id) { s.borrarConfirm = t.id; aviso(F.fmt("tareas.borrar.confirmar", { n: hijas }), "aviso"); return; }
    s.borrarConfirm = null;
    try { await F.api(`/tareas/${t.id}`, { method: "DELETE" }); aviso(""); } catch (e) { error(e); }
    await recargar();
  }
  async function subtarea(t) {
    const texto = await pedirTexto(F.t("tareas.subtarea.prompt"));
    if (!texto) return;
    try { await F.api("/tareas", { method: "POST", body: { lista_id: s.lista.id, texto, parent_id: t.id } }); }
    catch (e) { error(e); }
    await recargar();
  }

  function enfocar(id) { requestAnimationFrame(() => $(`.tl-card[data-id="${id}"]`)?.focus()); }

  function teclado(ev, t) {
    if (ev.target.closest(".tl-editor")) return;
    if (ev.altKey && ev.key === "ArrowRight") { ev.preventDefault(); anidar(t); }
    else if (ev.altKey && ev.key === "ArrowLeft") { ev.preventDefault(); desanidar(t); }
    else if (ev.altKey && ev.key === "ArrowUp") { ev.preventDefault(); mover(t, -1); }
    else if (ev.altKey && ev.key === "ArrowDown") { ev.preventDefault(); mover(t, 1); }
    else if (ev.key === "Enter" && ev.target === ev.currentTarget) { ev.preventDefault(); editar(t.id); }
    else if (ev.key === " " && ev.target === ev.currentTarget) { ev.preventDefault(); patch(t.id, { estado: t.estado === "hecha" ? "pendiente" : "hecha" }).then(() => enfocar(t.id)); }
    else if (ev.key === "Delete" && ev.target === ev.currentTarget) { ev.preventDefault(); borrar(t); }
    else if (ev.key.toLowerCase() === "f" && !ev.ctrlKey && ev.target === ev.currentTarget) { ev.preventDefault(); patch(t.id, { fijada: t.fijada ? 0 : 1 }).then(() => enfocar(t.id)); }
  }

  // ---------------------------------------------------------------- menú contextual
  function abrirMenu(t, ancla) {
    cerrarMenu();
    const m = document.createElement("div");
    m.className = "tl-menu";
    m.setAttribute("role", "menu");
    const col = columnaDe(t);
    const items = [
      ["editar", () => editar(t.id), "Enter"],
      ["subtarea", () => subtarea(t)],
      ["anidar", () => anidar(t), "Alt →"],
      ...(t.parent_id != null ? [["desanidar", () => desanidar(t), "Alt ←"]] : []),
      ["subir", () => mover(t, -1), "Alt ↑"],
      ["bajar", () => mover(t, 1), "Alt ↓"],
      "sep",
      ...COLUMNAS.filter((c) => c !== col).map((c) => [`mover.${c}`, () => aColumna(t, c)]),
      "sep",
      [t.fijada ? "desfijar" : "fijar", () => patch(t.id, { fijada: t.fijada ? 0 : 1 }), "F"],
      ["borrar", () => borrar(t), "Supr", "peligro"],
    ];
    for (const it of items) {
      if (it === "sep") { m.append(Object.assign(document.createElement("hr"), {})); continue; }
      const [k, fn, atajo, clase] = it;
      const b = document.createElement("button");
      b.type = "button"; b.setAttribute("role", "menuitem");
      if (clase) b.className = clase;
      b.innerHTML = `<span>${F.esc(F.t("tareas.menu." + k))}</span>${atajo ? `<kbd>${F.esc(atajo)}</kbd>` : ""}`;
      b.addEventListener("click", () => { cerrarMenu(); fn(); });
      m.append(b);
    }
    document.body.append(m);
    const r = ancla.getBoundingClientRect();
    const alto = m.offsetHeight, ancho = m.offsetWidth;
    m.style.top = `${Math.max(8, Math.min(window.innerHeight - alto - 8, r.bottom + 4))}px`;
    m.style.left = `${Math.max(8, Math.min(window.innerWidth - ancho - 8, r.right - ancho))}px`;
    s.menu = m;
    m.querySelector("button")?.focus();
    m.addEventListener("keydown", (ev) => {
      const bs = [...m.querySelectorAll("button")];
      const i = bs.indexOf(document.activeElement);
      if (ev.key === "Escape") { cerrarMenu(); ancla.focus(); }
      else if (ev.key === "ArrowDown") { ev.preventDefault(); bs[(i + 1) % bs.length].focus(); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); bs[(i - 1 + bs.length) % bs.length].focus(); }
    });
  }
  function cerrarMenu() { s.menu?.remove(); s.menu = null; }

  // ---------------------------------------------------------------- arrastrar y soltar (BTN-051/052)
  function prepararSoltar(lista) {
    lista.addEventListener("dragover", (ev) => {
      if (s.arrastrando == null) return;
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "move";
      limpiarMarcas();
      lista.classList.add("soltar");
      const antes = tarjetaBajo(lista, ev.clientY);
      if (antes) antes.classList.add("marca-antes");
      else lista.classList.add("marca-final");
    });
    lista.addEventListener("dragleave", (ev) => { if (!lista.contains(ev.relatedTarget)) limpiarMarcas(); });
    lista.addEventListener("drop", async (ev) => {
      ev.preventDefault();
      const id = s.arrastrando ?? Number(ev.dataTransfer.getData("text/plain"));
      const antes = tarjetaBajo(lista, ev.clientY);
      limpiarMarcas();
      if (!id) return;
      const t = s.tareas.find((x) => x.id === id);
      const col = lista.dataset.col;
      let dia = diaDeColumna(col);
      const ref = antes ? s.tareas.find((x) => x.id === Number(antes.dataset.id)) : null;
      if (col === "mas") dia = ref?.dia_asignado ?? (columnaDe(t) === "mas" ? t.dia_asignado : dia);
      if (col === "hoy" && ref?.dia_asignado && difDias(ref.dia_asignado, s.hoy) < 0) dia = s.hoy;
      // Índice dentro del día (mismo criterio que el backend: orden de las tareas de ese día).
      const delDia = s.tareas.filter((x) => (x.dia_asignado ?? null) === dia && x.id !== id).sort(ordenar);
      const orden = ref && (ref.dia_asignado ?? null) === dia ? delDia.findIndex((x) => x.id === ref.id) : delDia.length;
      const cambios = { orden: Math.max(0, orden), dia_asignado: dia };
      if ((t.dia_asignado ?? null) === dia) cambios.fijada = t.fijada;  // reordenar sin cambiar de día no fija
      await patch(id, cambios);
    });
  }
  function tarjetaBajo(lista, y) {
    for (const c of lista.querySelectorAll(".tl-card:not(.arrastrando)")) {
      const r = c.getBoundingClientRect();
      if (y < r.top + r.height / 2) return c;
    }
    return null;
  }
  function limpiarMarcas() {
    document.querySelectorAll(".marca-antes").forEach((c) => c.classList.remove("marca-antes"));
    document.querySelectorAll(".tl-col-lista.soltar, .tl-col-lista.marca-final").forEach((c) => c.classList.remove("soltar", "marca-final"));
  }

  // ---------------------------------------------------------------- captura (SCR-030, P1)
  let previaTimer = null, previaSeq = 0;
  function previa() {
    clearTimeout(previaTimer);
    previaTimer = setTimeout(async () => {
      const texto = $("#tl-entrada").value;
      const cont = $("#tl-previa");
      const seq = ++previaSeq;
      if (!texto.trim()) { cont.innerHTML = ""; cont.hidden = true; return; }
      try {
        const { lineas } = await F.api("/tareas/interpretar", { method: "POST", body: { texto } });
        if (seq !== previaSeq) return;
        cont.hidden = false;
        cont.innerHTML = lineas.slice(0, 8).map((l) => {
          const chips = [];
          if (l.dia_asignado) chips.push(`<span class="ch fecha">${F.esc(nombreDia(l.dia_asignado))}</span>`);
          if (l.hora) chips.push(`<span class="ch">${F.esc(l.hora)}</span>`);
          if (l.prioridad !== 3) chips.push(`<span class="ch prio p${l.prioridad}">P${l.prioridad}</span>`);
          if (l.estimacion_min) chips.push(`<span class="ch">${horas(l.estimacion_min)}</span>`);
          if (l.ambigua && !l.dia_asignado) chips.push(`<span class="ch ia" title="${F.esc(F.t("tareas.previa.ia"))}">${F.esc(F.t("tareas.previa.ia_corto"))}</span>`);
          return `<div class="tl-previa-l"><span class="t">${F.esc(l.texto)}</span>${chips.join("")}</div>`;
        }).join("") + (lineas.length > 8 ? `<div class="tl-previa-l mas">+${lineas.length - 8}</div>` : "");
      } catch { /* la vista previa es opcional */ }
    }, 220);
  }
  function nombreDia(iso) {
    const k = difDias(iso, s.hoy);
    if (k === 0) return F.t("tareas.col.hoy");
    if (k === 1) return F.t("tareas.col.manana");
    if (k === 2) return F.t("tareas.col.pasado");
    return fechaCorta(iso);
  }

  async function anadir() {
    const ta = $("#tl-entrada");
    const texto = ta.value;
    if (!texto.trim()) { ta.focus(); return; }
    const b = $("#tl-anadir");
    b.disabled = true;
    try {
      const { creadas } = await F.api("/tareas", { method: "POST", body: { lista_id: s.lista.id, texto } });
      ta.value = ""; autoAltura(); previa();
      const fechadas = creadas.filter((c) => c.dia_asignado).length;
      aviso(F.fmt(fechadas ? "tareas.anadidas_fecha" : "tareas.anadidas", { n: creadas.length, f: fechadas }), "ok");
      await recargar();
    } catch (e) { error(e); }
    b.disabled = false;
    ta.focus();
  }
  function autoAltura() {
    const ta = $("#tl-entrada");
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }

  // ---------------------------------------------------------------- organizar (BTN-055/056)
  async function organizar() {
    if (s.organizando) return;
    const b = $("#tl-organizar");
    const t0 = Date.now();
    const ia = F.st.esfuerzo !== "bajo";
    s.organizando = setInterval(() => {
      b.querySelector("span").textContent = `${F.t("tareas.organizando")} ${Math.round((Date.now() - t0) / 1000)} s`;
    }, 500);
    b.disabled = true;
    b.classList.add("trabajando");
    aviso(ia ? F.fmt("tareas.organizando.ia", { modelo: F.etiquetaPara("tareas", F.st.tier) || F.st.tier }) : F.t("tareas.organizando.reglas"));
    try {
      const r = await F.api("/tareas/organizar", { method: "POST", body: { lista_id: s.lista.id, esfuerzo: F.st.esfuerzo, tier: F.st.tier } });
      s.lista = r.lista; s.tareas = r.tareas; s.hoy = r.hoy; s.cap = r.capacidad_dia_min;
      const quien = r.origen === "ia" ? F.fmt("tareas.hecho.ia", { modelo: r.modelo }) : F.t("tareas.hecho.reglas");
      aviso([F.fmt("tareas.hecho", { quien, movidas: r.movidas, respetadas: r.respetadas }), ...r.avisos].join(" "), r.avisos.length ? "aviso" : "ok");
    } catch (e) { error(e); }
    clearInterval(s.organizando);
    s.organizando = null;
    b.classList.remove("trabajando");
    const { listas } = await F.api("/listas").catch(() => ({ listas: s.listas }));
    s.listas = listas;
    pintar();
    F.refrescarSalud?.();
  }

  // ---------------------------------------------------------------- listas (BTN-057)
  function pedirTexto(etiqueta, valor = "") {
    // Diálogo propio (pywebview/WebView2 no garantiza window.prompt).
    return new Promise((res) => {
      const o = $("#tl-dialogo");
      $("#tl-dialogo-etq").textContent = etiqueta;
      const inp = $("#tl-dialogo-txt");
      inp.value = valor;
      o.hidden = false;
      inp.focus(); inp.select();
      const fin = (v) => { o.hidden = true; f.removeEventListener("submit", ok); cancel.removeEventListener("click", no); res(v); };
      const f = $("#tl-dialogo-form"), cancel = $("#tl-dialogo-cancelar");
      const ok = (ev) => { ev.preventDefault(); fin(inp.value.trim() || null); };
      const no = () => fin(null);
      f.addEventListener("submit", ok);
      cancel.addEventListener("click", no);
      o.onkeydown = (ev) => { if (ev.key === "Escape") no(); };
    });
  }

  async function nuevaLista() {
    const nombre = await pedirTexto(F.t("tareas.lista.nueva_prompt"));
    if (!nombre) return;
    try { const l = await F.api("/listas", { method: "POST", body: { nombre } }); await cargar(l.id); }
    catch (e) { error(e); }
  }
  function menuLista(ancla) {
    cerrarMenu();
    const m = document.createElement("div");
    m.className = "tl-menu";
    const ops = [
      ["renombrar", async () => {
        const nombre = await pedirTexto(F.t("tareas.lista.renombrar_prompt"), s.lista.nombre);
        if (!nombre) return;
        try { await F.api(`/listas/${s.lista.id}`, { method: "PATCH", body: { nombre } }); await cargar(s.lista.id); } catch (e) { error(e); }
      }],
      ["borrar", async () => {
        if (s.borrarConfirm !== "lista") { s.borrarConfirm = "lista"; aviso(F.fmt("tareas.lista.borrar_confirmar", { nombre: s.lista.nombre }), "aviso"); return; }
        s.borrarConfirm = null;
        try { await F.api(`/listas/${s.lista.id}`, { method: "DELETE" }); s.lista = null; aviso(""); await cargar(); } catch (e) { error(e); }
      }, "peligro"],
    ];
    for (const [k, fn, clase] of ops) {
      const b = document.createElement("button");
      b.type = "button"; if (clase) b.className = clase;
      b.innerHTML = `<span>${F.esc(F.t("tareas.lista." + k))}</span>`;
      b.addEventListener("click", () => { cerrarMenu(); fn(); });
      m.append(b);
    }
    document.body.append(m);
    const r = ancla.getBoundingClientRect();
    m.style.top = `${r.bottom + 4}px`;
    m.style.left = `${Math.max(8, Math.min(window.innerWidth - m.offsetWidth - 8, r.left))}px`;
    s.menu = m;
    m.querySelector("button").focus();
    m.addEventListener("keydown", (ev) => { if (ev.key === "Escape") { cerrarMenu(); ancla.focus(); } });
  }

  // ---------------------------------------------------------------- arranque
  let enlazado = false;
  function enlazar() {
    if (enlazado) return;
    enlazado = true;
    $("#tl-lista").addEventListener("change", (ev) => { aviso(""); cargar(Number(ev.target.value)).catch(error); });
    $("#tl-nueva").addEventListener("click", nuevaLista);
    $("#tl-lista-mas").addEventListener("click", (ev) => { ev.stopPropagation(); menuLista(ev.currentTarget); });
    $("#tl-organizar").addEventListener("click", organizar);
    $("#tl-anadir").addEventListener("click", anadir);
    const ta = $("#tl-entrada");
    ta.addEventListener("input", () => { autoAltura(); previa(); });
    ta.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && (ev.ctrlKey || !ev.shiftKey) && !ev.isComposing) { ev.preventDefault(); anadir(); }
      else if (ev.key === "Tab") {  // P4: sangría con Tab en la captura (outliner)
        ev.preventDefault();
        const { selectionStart: a, value: v } = ta;
        const ini = v.lastIndexOf("\n", a - 1) + 1;
        if (ev.shiftKey) { if (v.startsWith("  ", ini)) { ta.value = v.slice(0, ini) + v.slice(ini + 2); ta.selectionStart = ta.selectionEnd = Math.max(ini, a - 2); } }
        else { ta.value = v.slice(0, ini) + "  " + v.slice(ini); ta.selectionStart = ta.selectionEnd = a + 2; }
        previa();
      }
    });
    $("#tl-cap").addEventListener("change", async (ev) => {
      const v = Math.max(30, Math.min(1440, Number(ev.target.value) || 480));
      try { await F.api("/ajustes", { method: "PUT", body: { "plan.capacidad_dia_min": String(v) } }); s.cap = v; pintar(); }
      catch (e) { error(e); }
    });
    document.addEventListener("click", (ev) => { if (s.menu && !s.menu.contains(ev.target)) cerrarMenu(); });
    window.addEventListener("resize", cerrarMenu);
  }

  window.ForjaTareas = {
    async mostrar() {
      F = window.ForjaApp;
      enlazar();
      try { await cargar(); } catch (e) { error(e); }
    },
    alCambiarSelector() { if (s.cargado) pintarBarra(); },
  };
})();
