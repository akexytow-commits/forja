/* FORJA — Rama 5 en el chat de Scripts/Firmware (MOD-020):
   SCR-011 Proyectos (SC1 = desplegable) · BTN-031 Guardar a archivo (ST-040) · BTN-032 Plantillas ·
   BTN-034 Nuevo proyecto · BTN-035 Abrir carpeta · BTN-036 Asociar hilo · BTN-060 Exportar conversación. */
(() => {
  "use strict";

  const A = () => window.ForjaApp;
  const $ = (s, r = document) => r.querySelector(s);
  const t = (k) => A().t(k);
  const fmt = (k, v) => A().fmt(k, v);
  const esc = (s) => A().esc(String(s ?? ""));
  const EXT = { python: "py", py: "py", bash: "sh", sh: "sh", shell: "sh", zsh: "sh", powershell: "ps1", ps1: "ps1",
    pwsh: "ps1", c: "c", cpp: "cpp", "c++": "cpp", h: "h", javascript: "js", js: "js", typescript: "ts", ts: "ts",
    json: "json", yaml: "yaml", yml: "yml", toml: "toml", ini: "ini", html: "html", css: "css", sql: "sql", rust: "rs",
    go: "go", java: "java", lua: "lua", markdown: "md", md: "md", batch: "bat", bat: "bat", cmd: "cmd", xml: "xml" };

  const st = { proyectos: [], plantillas: [], hilo: null, dg: null, dpAlCrear: null, carpetaTocada: false, selectorNativo: false };

  // ---------------------------------------------------------------- utilidades
  let tToast = null;
  function toast(html, ms = 5000) {
    const el = $("#toast");
    el.innerHTML = html;
    el.hidden = false;
    clearTimeout(tToast);
    tToast = setTimeout(() => { el.hidden = true; }, ms);
  }
  function errorToast(e) { toast(`<span class="mal">${esc(e.message || e)}</span>`); }

  const fijo = () => document.documentElement.dataset.proyectos === "fijo";
  function cerrarPops(excepto) {
    for (const [btn, pop] of [["#btn-proyecto", "#pop-proyectos"], ["#btn-plantillas", "#pop-plantillas"]]) {
      if (pop === excepto) continue;
      if (pop === "#pop-proyectos" && fijo()) continue;     // SC1 = fijo: el panel no se cierra
      $(pop).hidden = true;
      $(btn).setAttribute("aria-expanded", "false");
    }
  }
  function alternarPop(btn, pop, pintar) {
    const abrir = $(pop).hidden;
    cerrarPops(pop);
    $(pop).hidden = !abrir;
    $(btn).setAttribute("aria-expanded", String(abrir));
    if (abrir) pintar();
  }

  const proyectoDe = (id) => st.proyectos.find((p) => p.id === id) || null;
  const esScripts = () => A().st.modo === "scripts";

  async function cargarProyectos() {
    try {
      const r = await A().api("/proyectos");
      st.proyectos = r.proyectos;
      st.selectorNativo = r.selector_nativo;
    } catch { st.proyectos = []; }
  }

  // ---------------------------------------------------------------- barra del chat
  function pintarBarra() {
    const scripts = esScripts();
    $("#btn-proyecto").parentElement.hidden = !scripts;
    $("#btn-plantillas").parentElement.hidden = !scripts;
    const p = proyectoDe(st.hilo?.project_id);
    $("#btn-proyecto-txt").textContent = p ? p.nombre : t("proy.ninguno");
    $("#btn-proyecto").classList.toggle("con", !!p);
    $("#btn-proyecto").title = p ? p.carpeta : t("proy.titulo");
    $("#btn-exportar").disabled = !st.hilo;
  }

  function alCambiarHilo(hilo) {
    st.hilo = hilo;
    pintarBarra();
    if (fijo()) pintarProyectos();          // el panel fijo marca el proyecto del hilo abierto
  }

  // ---------------------------------------------------------------- SCR-011 desplegable
  function pintarProyectos() {
    const ul = $("#proy-lista");
    ul.innerHTML = "";
    if (!st.proyectos.length) ul.innerHTML = `<li class="pop-vacio">${esc(t("proy.vacio"))}</li>`;
    for (const p of st.proyectos) {
      const asociado = st.hilo?.project_id === p.id;
      const li = document.createElement("li");
      li.className = "proy" + (asociado ? " activo" : "");
      li.innerHTML = `<div class="proy-txt"><strong></strong><span class="proy-ruta"></span><span class="proy-meta"></span></div>` +
        `<div class="proy-acc">` +
        (asociado ? `<button type="button" class="boton-txt peq" data-a="quitar">${esc(t("proy.desasociar"))}</button>`
          : `<button type="button" class="boton-txt peq" data-a="asociar">${esc(t("proy.asociar"))}</button>`) +
        `<button type="button" class="icono-btn peq" data-a="abrir" title="${esc(t("proy.abrir"))}" aria-label="${esc(t("proy.abrir"))}"><svg><use href="#i-carpeta"/></svg></button></div>`;
      li.querySelector("strong").textContent = p.nombre;
      li.querySelector(".proy-ruta").textContent = p.carpeta;
      li.querySelector(".proy-meta").textContent = fmt("proy.hilos", { n: p.n_hilos }) + (p.existe ? "" : ` · ${t("proy.no_existe")}`);
      li.querySelector("[data-a=abrir]").addEventListener("click", () => abrirCarpeta(p.id));
      li.querySelector("[data-a=asociar], [data-a=quitar]").addEventListener("click", () => asociar(asociado ? null : p.id));
      ul.append(li);
    }
    $("#proy-nota").textContent = t("proy.nota");
  }

  async function abrirCarpeta(id) {           // BTN-035
    try { await A().api(`/proyectos/${id}/abrir`, { method: "POST" }); }
    catch (e) { errorToast(e); }
  }

  /* BTN-036. Si el hilo aún no existe (se crea con el primer mensaje), se crea ya, vacío y asociado. */
  async function asociar(pid) {
    const app = A();
    try {
      let id = app.st.hilo[app.clave()];
      if (id == null) {
        if (pid == null) return;
        id = (await app.api("/conversaciones", { method: "POST", body: { modo: "scripts", project_id: pid } })).id;
        app.st.hilo[app.clave()] = id;
      } else {
        await app.api(`/conversaciones/${id}`, { method: "PATCH", body: { project_id: pid } });
      }
      await cargarProyectos();
      await app.recargarHilos();
      if (pid != null) toast(esc(fmt("proy.asociado_ok", { nombre: proyectoDe(pid)?.nombre || "" })), 3000);
      if (!$("#pop-proyectos").hidden) pintarProyectos();
    } catch (e) { errorToast(e); }
  }

  /* SC1 (doc 13): "desplegable" = popover desde la barra del chat; "fijo" = el mismo panel, siempre visible
     a la izquierda del chat de Scripts. Se cambia en vivo desde Ajustes, sin recargar. */
  function aplicarModo() {
    const pop = $("#pop-proyectos");
    const vista = document.querySelector('.vista[data-vista="scripts"]');
    let panel = $("#proy-fijo");
    if (fijo()) {
      if (!panel) {
        panel = document.createElement("aside");
        panel.id = "proy-fijo";
        panel.className = "proy-fijo";
        panel.setAttribute("aria-label", t("proy.titulo"));
      }
      if (panel.parentElement !== vista) vista.prepend(panel);
      if (pop.parentElement !== panel) panel.append(pop);
      pop.hidden = false;
      $("#btn-proyecto").setAttribute("aria-expanded", "true");
      cargarProyectos().then(pintarProyectos);
    } else {
      const ancla = $("#btn-proyecto").parentElement;
      if (pop.parentElement !== ancla) { ancla.append(pop); pop.hidden = true; $("#btn-proyecto").setAttribute("aria-expanded", "false"); }
      panel?.remove();
    }
  }

  // ---------------------------------------------------------------- BTN-034 nuevo proyecto
  async function abrirNuevoProyecto(alCrear) {
    st.dpAlCrear = alCrear || null;
    st.carpetaTocada = false;
    $("#dp-nombre").value = "";
    $("#dp-carpeta").value = "";
    $("#dp-desc").value = "";
    $("#dp-msg").hidden = true;
    $("#dp-elegir").hidden = false;
    await sugerirCarpeta();
    $("#dlg-proyecto").hidden = false;
    $("#dp-nombre").focus();
  }

  let tSug = null;
  async function sugerirCarpeta() {
    if (st.carpetaTocada) return;
    try {
      const r = await A().api(`/proyectos/sugerencia?nombre=${encodeURIComponent($("#dp-nombre").value.trim() || "proyecto")}`);
      if (!st.carpetaTocada) $("#dp-carpeta").value = r.carpeta;
    } catch { /* sin sugerencia */ }
  }

  async function elegirCarpeta() {
    try {
      const r = await A().api("/sistema/elegir-carpeta", { method: "POST", body: { inicial: $("#dp-carpeta").value.trim() || null } });
      if (r.carpeta) {
        st.carpetaTocada = true;
        $("#dp-carpeta").value = r.carpeta;
      }
    } catch (e) {
      if (e.codigo === "SIN_SELECTOR") {
        $("#dp-elegir").hidden = true;
        const m = $("#dp-msg"); m.textContent = t("proy.sin_selector"); m.className = "nota"; m.hidden = false;
        $("#dp-carpeta").focus();
      } else errorToast(e);
    }
  }

  async function crearProyecto(ev) {
    ev.preventDefault();
    const m = $("#dp-msg");
    try {
      const p = await A().api("/proyectos", { method: "POST", body: {
        nombre: $("#dp-nombre").value.trim(), carpeta: $("#dp-carpeta").value.trim() || null, descripcion: $("#dp-desc").value.trim() } });
      $("#dlg-proyecto").hidden = true;
      await cargarProyectos();
      const cb = st.dpAlCrear;
      st.dpAlCrear = null;
      if (cb) await cb(p);
      else pintarProyectos();
    } catch (e) {
      m.textContent = e.message; m.className = "nota mal"; m.hidden = false;
    }
  }

  // ---------------------------------------------------------------- BTN-031 guardar a archivo (ST-040)
  async function guardarBloque(btn) {
    const codigo = btn.closest(".code").querySelector("code").textContent;
    const lang = (btn.dataset.lang || "").toLowerCase();
    const nombre = btn.dataset.nombre || `script.${EXT[lang] || "txt"}`;
    await cargarProyectos();
    st.dg = { codigo: codigo.endsWith("\n") ? codigo : codigo + "\n", sobrescribir: false };
    let ultimo = null;
    try { ultimo = Number(localStorage.getItem("forja.ultimoProyecto")) || null; } catch { /* sin almacenamiento */ }
    pintarSelectProyectos(st.hilo?.project_id ?? ultimo);
    $("#dg-nombre").value = nombre;
    $("#dg-msg").hidden = true;
    $("#dg-bytes").textContent = fmt("guardar.bytes", { n: new TextEncoder().encode(st.dg.codigo).length.toLocaleString("es-ES") });
    pintarDestino();
    $("#dlg-guardar").hidden = false;
    $("#dg-nombre").focus();
    const punto = nombre.lastIndexOf(".");
    $("#dg-nombre").setSelectionRange(nombre.lastIndexOf("/") + 1, punto > 0 ? punto : nombre.length);
  }

  function pintarSelectProyectos(preferido) {
    const sel = $("#dg-proyecto");
    sel.innerHTML = st.proyectos.map((p) => `<option value="${p.id}">${esc(p.nombre)}</option>`).join("");
    if (st.proyectos.some((p) => p.id === preferido)) sel.value = String(preferido);
    sel.disabled = !st.proyectos.length;
  }

  function pintarDestino() {
    const p = proyectoDe(Number($("#dg-proyecto").value));
    const ok = $("#dg-ok");
    st.dg.sobrescribir = false;
    ok.textContent = t("guardar.confirmar");
    ok.classList.remove("peligro");
    $("#dg-msg").hidden = true;
    if (!p) {
      $("#dg-ruta").textContent = t("guardar.sin_proyectos");
      ok.disabled = true;
      return;
    }
    ok.disabled = !$("#dg-nombre").value.trim();
    const rel = $("#dg-nombre").value.trim().replace(/\//g, "\\");
    $("#dg-ruta").innerHTML = `<h4>${esc(t("guardar.destino"))}</h4><code class="ruta"></code>`;
    $("#dg-ruta code").textContent = `${p.carpeta}\\${rel}`;
  }

  async function confirmarGuardar(ev) {
    ev.preventDefault();
    const pid = Number($("#dg-proyecto").value);
    const nombre = $("#dg-nombre").value.trim();
    if (!pid || !nombre) return;
    const m = $("#dg-msg");
    try {
      // La confirmación es este diálogo: confirmado=true solo sale de aquí (ST-040 propuesta → confirmada).
      const r = await A().api(`/proyectos/${pid}/guardar-archivo`, { method: "POST",
        body: { nombre, contenido: st.dg.codigo, confirmado: true, sobrescribir: st.dg.sobrescribir } });
      $("#dlg-guardar").hidden = true;
      try { localStorage.setItem("forja.ultimoProyecto", String(pid)); } catch { /* sin almacenamiento */ }
      toast(`${esc(fmt("guardar.ok", { ruta: r.relativa }))} <button type="button" class="tel-btn" data-abrir-proy="${pid}">${esc(t("proy.abrir"))}</button>`);
      if (st.hilo && st.hilo.project_id == null) await asociar(pid);   // el hilo pasa a ser de ese proyecto
      else await cargarProyectos();
    } catch (e) {
      if (e.codigo === "SOBRESCRIBIR") {
        st.dg.sobrescribir = true;
        m.textContent = fmt("guardar.existe", { ruta: nombre });
        m.className = "nota aviso"; m.hidden = false;
        $("#dg-ok").textContent = t("guardar.sobrescribir");
        $("#dg-ok").classList.add("peligro");
      } else {
        m.textContent = e.message; m.className = "nota mal"; m.hidden = false;
      }
    }
  }

  // ---------------------------------------------------------------- BTN-032 plantillas
  async function pintarPlantillas() {
    try { st.plantillas = (await A().api("/plantillas")).plantillas; } catch { st.plantillas = []; }
    const ul = $("#plant-lista");
    ul.innerHTML = st.plantillas.length ? "" : `<li class="pop-vacio">${esc(t("plant.vacio"))}</li>`;
    for (const p of st.plantillas) {
      const li = document.createElement("li");
      li.innerHTML = `<button type="button" class="plant"><strong></strong><span></span></button>`;
      li.querySelector("strong").textContent = p.nombre + (p.origen === "usuario" ? ` · ${t("plant.tuya")}` : "");
      li.querySelector("span").textContent = p.descripcion;
      li.querySelector("button").addEventListener("click", () => insertarPlantilla(p));
      ul.append(li);
    }
  }

  function insertarPlantilla(p) {
    cerrarPops();
    const ta = A().entrada();
    const previo = ta.value.trim();
    ta.value = previo ? `${previo}\n\n${p.contenido}` : p.contenido;
    A().autoAltura();
    ta.focus();
    // Selecciona el hueco "<describe aquí…>" para escribir encima.
    const i = ta.value.indexOf("<describe aquí");
    if (i >= 0) ta.setSelectionRange(i, ta.value.indexOf(">", i) + 1);
    ta.scrollTop = 0;
  }

  // ---------------------------------------------------------------- BTN-060 exportar conversación
  async function exportar() {
    const app = A();
    const id = app.st.hilo[app.clave()];
    if (id == null) { toast(esc(t("export.vacio")), 3000); return; }
    try {
      const r = await app.api("/export", { method: "POST", body: { tipo: "conversacion", id } });
      toast(`${esc(fmt("export.ok", { nombre: r.nombre }))} <button type="button" class="tel-btn" data-abrir-export="1">${esc(t("export.abrir"))}</button>`, 8000);
    } catch (e) { errorToast(e); }
  }

  // ---------------------------------------------------------------- arranque
  function init() {
    $("#btn-exportar").title = t("export.conversacion");
    $("#btn-exportar").setAttribute("aria-label", t("export.conversacion"));
    $("#btn-proyecto").addEventListener("click", () => {
      if (fijo()) { $("#proy-lista button")?.focus(); return; }        // ya está a la vista
      alternarPop("#btn-proyecto", "#pop-proyectos", async () => { await cargarProyectos(); pintarProyectos(); });
    });
    $("#btn-plantillas").addEventListener("click", () => alternarPop("#btn-plantillas", "#pop-plantillas", pintarPlantillas));
    $("#btn-exportar").addEventListener("click", exportar);
    $("#proy-nuevo").addEventListener("click", () => { cerrarPops(); abrirNuevoProyecto(async (p) => { await asociar(p.id); }); });
    $("#plant-carpeta").addEventListener("click", () => { cerrarPops(); A().api("/plantillas/abrir-carpeta", { method: "POST" }).catch(errorToast); });
    // Nuevo proyecto
    $("#dlg-proyecto-form").addEventListener("submit", crearProyecto);
    $("#dp-cancelar").addEventListener("click", () => { $("#dlg-proyecto").hidden = true; st.dpAlCrear = null; });
    $("#dp-elegir").addEventListener("click", elegirCarpeta);
    $("#dp-nombre").addEventListener("input", () => { clearTimeout(tSug); tSug = setTimeout(sugerirCarpeta, 200); });
    $("#dp-carpeta").addEventListener("input", () => { st.carpetaTocada = true; });
    // Guardar a archivo
    $("#dlg-guardar-form").addEventListener("submit", confirmarGuardar);
    $("#dg-cancelar").addEventListener("click", () => { $("#dlg-guardar").hidden = true; });
    $("#dg-nombre").addEventListener("input", pintarDestino);
    $("#dg-proyecto").addEventListener("change", pintarDestino);
    $("#dg-nuevo-proy").addEventListener("click", () => abrirNuevoProyecto(async (p) => {
      pintarSelectProyectos(p.id); pintarDestino(); $("#dg-nombre").focus();
    }));
    // Toast: abrir carpeta
    $("#toast").addEventListener("click", (e) => {
      const b = e.target.closest("[data-abrir-proy]");
      if (b) abrirCarpeta(Number(b.dataset.abrirProy));
      if (e.target.closest("[data-abrir-export]")) A().api("/export/abrir-carpeta?tipo=conversaciones", { method: "POST" }).catch(errorToast);
    });
    document.addEventListener("click", (e) => { if (!e.target.closest(".pop-ancla, .proy-fijo")) cerrarPops(); });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      cerrarPops();
      if (!$("#dlg-proyecto").hidden) { $("#dlg-proyecto").hidden = true; st.dpAlCrear = null; }
      else if (!$("#dlg-guardar").hidden) $("#dlg-guardar").hidden = true;
    });
    cargarProyectos().then(pintarBarra);
    aplicarModo();
  }

  window.ForjaProyectos = { init, alCambiarHilo, guardarBloque, toast, pintarBarra, aplicarModo };
})();
