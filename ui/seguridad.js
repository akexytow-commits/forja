/* FORJA — Modo Seguridad (MOD-030): SCR-020 gate a pantalla completa (SG1), SCR-021 análisis de recon,
   SCR-023 hallazgos en tabla (SG2), SCR-022 redactor de informe estilo HackerOne (SG3) y chat por engagement.
   Los guardarraíles viven en el backend (ADR-0005); la UI solo los refleja. */
(() => {
  "use strict";

  const TABS = ["chat", "analisis", "hallazgos", "informe"];
  const SEV = ["critica", "alta", "media", "baja", "info"];
  const s = { lista: [], eng: null, tab: "chat", editando: null, findings: [], abierto: null, nuevoManual: false,
              analizando: null, informe: { fid: null, enfoques: ["", ""], gen: null, previa: false },
              borrarConfirm: null };
  let F;
  const $ = (q, r = document) => r.querySelector(q);
  const T = (k, v) => (v ? F.fmt(k, v) : F.t(k));
  const E = (x) => F.esc(x ?? "");

  // ---------------------------------------------------------------- utilidades
  function msg(sel, texto, clase = "") {
    const el = $(sel);
    if (!el) return;
    el.textContent = texto || "";
    el.className = "sg-msg " + clase;
    el.hidden = !texto;
  }
  const errorTxt = (e) => (e && e.message) || String(e);
  const sevChip = (sv) => `<span class="sg-sev ${sv || "nd"}">${E(sv ? T("seg.sev." + sv) : "—")}</span>`;
  const estadoChip = (est) => `<span class="sg-est ${est}">${E(T("seg.estado_f." + est))}</span>`;

  async function sseLocal(path, body, onEvento, signal) {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Forja-Token": window.FORJA_TOKEN },
      body: JSON.stringify(body), signal });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error?.mensaje || `HTTP ${r.status}`);
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
        const bloque = buf.slice(0, i); buf = buf.slice(i + 2);
        let ev = null, dat = null;
        for (const l of bloque.split("\n")) {
          if (l.startsWith("event: ")) ev = l.slice(7);
          else if (l.startsWith("data: ")) dat = JSON.parse(l.slice(6));
        }
        if (ev) onEvento(ev, dat);
      }
    }
  }

  // ---------------------------------------------------------------- vistas
  const aprendiendo = () => !!window.ForjaAcademia?.activa();

  function pintar() {
    const dentro = !!s.eng;
    const aca = aprendiendo();
    $("#ac-raiz").hidden = !aca;
    $("#sg-gate").hidden = aca || dentro;
    $("#sg-trabajo").hidden = aca || !dentro;
    if (!aca) { if (dentro) pintarTrabajo(); else pintarGate(); }
    window.ForjaAcademia?.pintarBarra();
    F.colocarChat();
    F.actualizarCompositor();
    F.actualizarLinea();
  }

  // ---------------------------------------------------------------- SCR-020 gate (pantalla completa)
  async function cargarLista() {
    s.lista = (await F.api("/engagements")).engagements;
  }

  function pintarGate() {
    const ed = s.editando ? s.lista.find((e) => e.id === s.editando) : null;
    $("#sg-gate-h3").textContent = T(ed ? "seg.gate.revisar" : "seg.gate.nuevo");
    $("#sg-cancelar-ed").hidden = !ed;
    const ul = $("#sg-lista");
    ul.innerHTML = s.lista.length ? "" : `<li class="sg-vacio">${E(T("seg.gate.sin_engagements"))}</li>`;
    for (const e of s.lista) {
      const li = document.createElement("li");
      li.className = "sg-item" + (e.id === s.editando ? " activo" : "");
      const chips = e.alcance_items.slice(0, 4).map((a) => `<code>${E(a)}</code>`).join("") +
        (e.alcance_items.length > 4 ? `<span class="sg-mas">+${e.alcance_items.length - 4}</span>` : "");
      li.innerHTML =
        `<div class="sg-item-cab"><strong>${E(e.nombre)}</strong>` +
        `<span class="sg-badge ${e.operable ? "ok" : e.estado}">${E(T("seg.estado." + (e.operable ? "autorizado" : e.estado)))}</span></div>` +
        `<div class="sg-chips">${chips}</div>` +
        `<div class="sg-item-pie"><span>${E(T("seg.gate.hallazgos", { n: e.hallazgos, v: e.validados }))}</span>` +
        `<span class="sg-item-acc">` +
          `<button type="button" class="boton-txt peq" data-borrar>${E(T(s.borrarConfirm === e.id ? "seg.gate.borrar_conf" : "seg.gate.borrar"))}</button>` +
          (e.operable
            ? `<button type="button" class="boton-txt peq" data-revisar>${E(T("seg.gate.editar"))}</button><button type="button" class="boton peq" data-entrar>${E(T("seg.gate.entrar_corto"))}</button>`
            : `<button type="button" class="boton peq" data-revisar>${E(T("seg.gate.revisar_corto"))}</button>`) +
        `</span></div>`;
      li.querySelector("[data-revisar]").addEventListener("click", () => editar(e));
      li.querySelector("[data-entrar]")?.addEventListener("click", () => entrar(e.id));
      li.querySelector("[data-borrar]").addEventListener("click", async () => {
        if (s.borrarConfirm !== e.id) { s.borrarConfirm = e.id; pintarGate(); return; }
        s.borrarConfirm = null;
        try { await F.api(`/engagements/${e.id}`, { method: "DELETE" }); } catch (x) { msg("#sg-gate-msg", errorTxt(x), "mal"); }
        if (s.editando === e.id) limpiarForm();
        await cargarLista(); pintarGate();
      });
      ul.append(li);
    }
    validarForm();
  }

  // ---------------------------------------------------------------- SG1: gate como asistente por pasos
  const asistente = () => document.documentElement.dataset.gate === "asistente";
  const alcanceItems = () => $("#sg-alcance").value.split(/\n|,|;/).map((x) => x.trim()).filter((x) => x && !x.startsWith("#"));
  const paso1Ok = () => !!($("#sg-nombre").value.trim() && $("#sg-alcance").value.trim());

  function pintarPasos() {
    const form = $("#sg-gate-form");
    const a = asistente();
    if (!a || !s.paso) s.paso = 1;
    form.dataset.paso = s.paso;
    $("#sg-pasos").hidden = !a;
    form.querySelectorAll("[data-paso]").forEach((el) => {
      el.hidden = a ? Number(el.dataset.paso) !== s.paso : el.hasAttribute("data-solo-asistente");
    });
    form.querySelectorAll("#sg-pasos li").forEach((li) => {
      const n = Number(li.dataset.n);
      li.classList.toggle("hecho", n < s.paso);
      if (n === s.paso) li.setAttribute("aria-current", "step"); else li.removeAttribute("aria-current");
    });
    $("#sg-atras").hidden = !a || s.paso === 1;
    $("#sg-siguiente").hidden = !a || s.paso === 3;
    $("#sg-siguiente").disabled = s.paso === 1 && !paso1Ok();
    $("#sg-entrar").hidden = a && s.paso !== 3;
    if (a && s.paso === 3) {
      $("#sg-resumen").innerHTML = `<h4>${E($("#sg-nombre").value.trim())}</h4>` +
        `<div class="sg-chips">${alcanceItems().slice(0, 12).map((x) => `<code>${E(x)}</code>`).join("")}</div>`;
    }
  }
  function irPaso(n) {
    if (n > 1 && !paso1Ok()) n = 1;
    s.paso = Math.max(1, Math.min(3, n));
    pintarPasos();
    const foco = { 1: "#sg-nombre", 2: "#sg-siguiente", 3: "#sg-declaro" }[s.paso];
    requestAnimationFrame(() => $(foco)?.focus());
  }

  function editar(e) {
    s.editando = e.id;
    s.paso = 1;
    $("#sg-nombre").value = e.nombre;
    $("#sg-alcance").value = e.alcance;
    $("#sg-notas").value = e.notas || "";
    $("#sg-declaro").checked = false;
    msg("#sg-gate-msg", e.operable ? "" : T("seg.gate.reconfirmar"), e.operable ? "" : "aviso");
    pintarGate();
    $("#sg-alcance").focus();
  }
  function limpiarForm() {
    s.editando = null;
    s.paso = 1;
    for (const id of ["#sg-nombre", "#sg-alcance", "#sg-notas"]) $(id).value = "";
    $("#sg-declaro").checked = false;
    msg("#sg-gate-msg", "");
    pintarGate();
  }
  function validarForm() {
    const ok = $("#sg-nombre").value.trim() && $("#sg-alcance").value.trim() && $("#sg-declaro").checked;
    $("#sg-entrar").disabled = !ok;
    $("#sg-alcance-previa").innerHTML = alcanceItems().slice(0, 12).map((x) => `<code>${E(x)}</code>`).join("");
    pintarPasos();
  }

  async function enviarGate() {
    const b = $("#sg-entrar");
    b.disabled = true;
    const datos = { nombre: $("#sg-nombre").value, alcance: $("#sg-alcance").value, notas: $("#sg-notas").value };
    try {
      let e;
      if (s.editando) e = await F.api(`/engagements/${s.editando}`, { method: "PATCH", body: datos });
      else e = await F.api("/engagements", { method: "POST", body: datos });
      // BTN-038: la declaración del checkbox viaja explícita; el backend la exige.
      if (!e.operable) e = await F.api(`/engagements/${e.id}`, { method: "PATCH", body: { autorizacion_confirmada: 1, declaracion: true } });
      await entrar(e.id);
      limpiarForm();
    } catch (x) {
      msg("#sg-gate-msg", errorTxt(x), "mal");
      await cargarLista(); pintarGate();
    }
    validarForm();
  }

  async function entrar(id) {
    try {
      s.eng = await F.api(`/engagements/${id}/entrar`, { method: "POST" });   // BTN-039, auditado
      s.tab = "chat";
      s.findings = []; s.abierto = null; s.informe = { fid: null, enfoques: ["", ""], gen: null, previa: false };
      await cargarFindings();
      pintar();
      await F.cargarHilos();
      F.pintarVacio();
    } catch (x) { msg("#sg-gate-msg", errorTxt(x), "mal"); }
  }

  async function salir() {
    if (F.st.gen) return;
    s.eng = null;
    await cargarLista();
    pintar();
  }

  // ---------------------------------------------------------------- trabajo (engagement operando)
  async function cargarFindings() {
    if (!s.eng) return;
    s.findings = (await F.api(`/engagements/${s.eng.id}/findings`)).findings;
  }

  function pintarTrabajo() {
    const e = s.eng;
    $("#sg-eng-nombre").textContent = e.nombre;
    $("#sg-eng-alcance").innerHTML = e.alcance_items.map((a) => `<code>${E(a)}</code>`).join("");
    document.querySelectorAll(".sg-tab").forEach((b) => {
      const on = b.dataset.tab === s.tab;
      b.setAttribute("aria-selected", String(on));
      if (b.dataset.tab === "hallazgos") b.querySelector(".n").textContent = s.findings.length || "";
    });
    document.querySelectorAll(".sg-panel").forEach((p) => { p.hidden = p.dataset.tab !== s.tab; });
    if (s.tab === "analisis") pintarAnalisis();
    if (s.tab === "hallazgos") pintarHallazgos();
    if (s.tab === "informe") pintarInforme();
  }

  function cambiarTab(tab) {
    if (s.tab === tab) return;
    s.tab = tab;
    pintarTrabajo();
    F.colocarChat();
    F.actualizarCompositor();
    F.actualizarLinea();
  }

  // ---------------------------------------------------------------- SCR-021 análisis
  function pintarAnalisis() {
    const ta = $("#sg-recon");
    $("#sg-recon-n").textContent = T("seg.analisis.caracteres", { n: ta.value.length.toLocaleString("es-ES") });
    $("#sg-analizar").disabled = !!s.analizando || !ta.value.trim();
  }

  async function analizar() {
    const datos = $("#sg-recon").value;
    if (!datos.trim() || s.analizando) return;
    const b = $("#sg-analizar");
    const t0 = Date.now();
    b.classList.add("trabajando");
    s.analizando = setInterval(() => { b.querySelector("span").textContent = `${T("seg.analisis.analizando")} ${Math.round((Date.now() - t0) / 1000)} s`; }, 500);
    pintarAnalisis();
    msg("#sg-analisis-msg", T("seg.analisis.espera", { modelo: F.st.tier === "nube" ? "Claude" : F.etiquetaPara("seguridad", F.st.tier) }));
    $("#sg-resultado").innerHTML = "";
    try {
      const r = await F.api(`/engagements/${s.eng.id}/analizar`, { method: "POST", body: { datos_recon: datos, tier: F.st.tier, esfuerzo: F.st.esfuerzo } });
      await cargarFindings();
      msg("#sg-analisis-msg", T(r.hallazgos.length ? "seg.analisis.hecho" : "seg.analisis.nada", { n: r.hallazgos.length, modelo: r.modelo }) +
        (r.recortado ? " " + T("seg.analisis.recortado", { n: r.caracteres_analizados.toLocaleString("es-ES") }) : ""), r.recortado ? "aviso" : "ok");
      $("#sg-resultado").innerHTML =
        (r.resumen ? `<p class="sg-resumen">${E(r.resumen)}</p>` : "") +
        (r.hallazgos.length ? `<ul class="sg-nuevos">${r.hallazgos.map((h) => `<li>${sevChip(h.severidad_estim)} <strong>${E(h.titulo)}</strong> <span class="sg-clase">${E(h.clase)}</span><p>${E(h.donde_enfocar)}</p></li>`).join("")}</ul>` +
          `<button type="button" class="boton-txt" id="sg-ver-hallazgos">${E(T("seg.analisis.ver"))}</button>` : "");
      $("#sg-ver-hallazgos")?.addEventListener("click", () => cambiarTab("hallazgos"));
      pintarTrabajo();
    } catch (x) { msg("#sg-analisis-msg", errorTxt(x), "mal"); }
    clearInterval(s.analizando); s.analizando = null;
    b.classList.remove("trabajando");
    b.querySelector("span").textContent = T("seg.analisis.analizar");
    pintarAnalisis();
    F.refrescarSalud();
  }

  function importar(ev) {
    const f = ev.target.files[0];
    ev.target.value = "";
    if (!f) return;
    if (f.size > 2_000_000) { msg("#sg-analisis-msg", T("seg.analisis.grande"), "mal"); return; }
    const lector = new FileReader();
    lector.onload = () => {
      const ta = $("#sg-recon");
      ta.value = (ta.value.trim() ? ta.value + "\n\n" : "") + `# ${f.name}\n` + lector.result;
      msg("#sg-analisis-msg", T("seg.analisis.importado", { nombre: f.name }), "ok");
      pintarAnalisis();
    };
    lector.readAsText(f);
  }

  // ---------------------------------------------------------------- SCR-023 hallazgos (tabla, SG2)
  function pintarHallazgos() {
    const cuerpo = $("#sg-tabla tbody");
    cuerpo.innerHTML = "";
    $("#sg-tabla").hidden = !s.findings.length;
    $("#sg-hallazgos-vacio").hidden = !!s.findings.length;
    $("#sg-manual").hidden = !s.nuevoManual;
    for (const f of s.findings) {
      const tr = document.createElement("tr");
      tr.className = "sg-fila sev-" + (f.severidad_estim || "nd") + (s.abierto === f.id ? " abierta" : "");   // sev-*: SG2 tarjetas
      tr.tabIndex = 0;
      tr.innerHTML = `<td>${sevChip(f.severidad_estim)}</td><td class="tit">${E(f.titulo)}</td><td>${E(f.clase || "—")}</td>` +
        `<td>${estadoChip(f.estado)}</td><td class="org">${E(T("seg.origen." + f.origen))}</td>`;
      const alternar = () => { s.abierto = s.abierto === f.id ? null : f.id; pintarHallazgos(); };
      tr.addEventListener("click", alternar);
      tr.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); alternar(); } });
      cuerpo.append(tr);
      if (s.abierto === f.id) cuerpo.append(detalle(f));
    }
  }

  function detalle(f) {
    const tr = document.createElement("tr");
    tr.className = "sg-detalle";
    const validado = f.estado !== "idea";
    tr.innerHTML = `<td colspan="5"><div class="sg-det">` +
      `<div class="sg-det-col"><h4>${E(T("seg.f.donde"))}</h4><p>${E(f.donde_enfocar || "—")}</p>` +
      `<h4>${E(T("seg.f.como"))}</h4><p>${E(f.como_verificar || "—")}</p></div>` +
      `<div class="sg-det-col"><label><h4>${E(T("seg.f.evidencia"))}</h4>` +
      `<textarea class="sg-evidencia" rows="5" spellcheck="false" placeholder="${E(T("seg.f.evidencia_ph"))}">${E(f.evidencia_usuario || "")}</textarea></label>` +
      `<div class="sg-det-acc">` +
        `<button type="button" class="boton-txt peq peligro" data-borrar>${E(T(s.borrarConfirm === "f" + f.id ? "seg.gate.borrar_conf" : "seg.gate.borrar"))}</button>` +
        `<span class="sep"></span>` +
        `<button type="button" class="boton-txt peq" data-guardar>${E(T("seg.f.guardar"))}</button>` +
        (validado ? `<button type="button" class="boton-txt peq" data-idea>${E(T("seg.f.a_idea"))}</button>`
                  : `<button type="button" class="boton peq" data-validar>${E(T("seg.f.validar"))}</button>`) +
        (validado ? `<button type="button" class="boton peq" data-informe>${E(T("seg.f.informe"))}</button>` : "") +
      `</div><p class="sg-msg" hidden></p></div></div></td>`;
    const ev = () => $(".sg-evidencia", tr).value;
    const m = (txt, c) => { const p = $(".sg-msg", tr); p.textContent = txt; p.className = "sg-msg " + c; p.hidden = !txt; };
    const guardar = async (extra) => {
      try {
        const nuevo = await F.api(`/findings/${f.id}`, { method: "POST", body: { evidencia_usuario: ev(), ...extra } });
        Object.assign(f, nuevo);
        pintarHallazgos(); pintarTrabajo();
        return true;
      } catch (x) { m(errorTxt(x), "mal"); return false; }
    };
    $("[data-guardar]", tr).addEventListener("click", () => guardar({}));
    $("[data-validar]", tr)?.addEventListener("click", () => guardar({ estado: "validado_por_usuario" }));
    $("[data-idea]", tr)?.addEventListener("click", () => guardar({ estado: "idea" }));
    $("[data-informe]", tr)?.addEventListener("click", async () => { if (await guardar({})) { s.informe.fid = f.id; cambiarTab("informe"); } });
    $("[data-borrar]", tr).addEventListener("click", async () => {
      if (s.borrarConfirm !== "f" + f.id) { s.borrarConfirm = "f" + f.id; pintarHallazgos(); return; }
      s.borrarConfirm = null;
      try { await F.api(`/findings/${f.id}`, { method: "DELETE" }); } catch (x) { m(errorTxt(x), "mal"); return; }
      s.abierto = null; await cargarFindings(); pintarTrabajo();
    });
    return tr;
  }

  async function crearManual(ev) {
    ev.preventDefault();
    const f = ev.target;
    try {
      const nuevo = await F.api(`/engagements/${s.eng.id}/findings`, { method: "POST", body: {
        titulo: f.titulo.value, clase: f.clase.value, severidad_estim: f.sev.value || null,
        donde_enfocar: f.donde.value, evidencia_usuario: f.evidencia.value } });
      f.reset(); s.nuevoManual = false; s.abierto = nuevo.id;
      msg("#sg-manual-msg", "");
      await cargarFindings(); pintarTrabajo();
    } catch (x) { msg("#sg-manual-msg", errorTxt(x), "mal"); }
  }

  // ---------------------------------------------------------------- SCR-022 informe (HackerOne, SG3)
  function pintarInforme() {
    if (!s.plantillasPedidas) { s.plantillasPedidas = true; cargarPlantillas(); }
    const validados = s.findings.filter((f) => f.estado !== "idea");
    const sel = $("#sg-inf-sel");
    if (!validados.some((f) => f.id === s.informe.fid)) s.informe.fid = validados[0]?.id ?? null;
    sel.innerHTML = validados.map((f) => `<option value="${f.id}">${E(f.titulo)} · ${E(T("seg.estado_f." + f.estado))}</option>`).join("");
    sel.value = s.informe.fid ?? "";
    $("#sg-inf-vacio").hidden = !!validados.length;
    $("#sg-inf-cuerpo").hidden = !validados.length;
    const f = validados.find((x) => x.id === s.informe.fid);
    if (!f) return;
    $("#sg-inf-evidencia").textContent = f.evidencia_usuario || "—";
    const cont = $("#sg-enfoques");
    cont.innerHTML = "";
    s.informe.enfoques.forEach((txt, i) => {
      const l = document.createElement("label");
      l.innerHTML = `<span>${E(T("seg.inf.enfoque", { n: i + 1 }))}</span><textarea rows="3" spellcheck="false" placeholder="${E(T("seg.inf.enfoque_ph"))}"></textarea>`;
      const ta = $("textarea", l);
      ta.value = txt;
      ta.addEventListener("input", () => { s.informe.enfoques[i] = ta.value; });
      cont.append(l);
    });
    const md = $("#sg-inf-md");
    if (!s.informe.gen && md.dataset.fid !== String(f.id)) { md.value = f.informe_md || ""; md.dataset.fid = f.id; }
    $("#sg-inf-previa").hidden = !s.informe.previa;
    md.hidden = s.informe.previa;
    if (s.informe.previa) $("#sg-inf-previa").innerHTML = window.ForjaMD.render(md.value || "");
    $("#sg-inf-toggle").textContent = T(s.informe.previa ? "seg.inf.editar" : "seg.inf.previa");
    const generando = !!s.informe.gen;
    $("#sg-inf-generar span").textContent = T(generando ? "seg.inf.detener" : (md.value ? "seg.inf.regenerar" : "seg.inf.generar"));
    for (const id of ["#sg-inf-guardar", "#sg-inf-exportar", "#sg-inf-copiar", "#sg-inf-reportado"]) $(id).disabled = generando || !md.value.trim();
    $("#sg-inf-reportado").hidden = f.estado === "reportado";
    md.readOnly = generando;
  }

  // API-055: la plantilla se elige también aquí; es el mismo ajuste (ui.informe_plantilla) que en Ajustes.
  async function cargarPlantillas() {
    try { s.plantillas = await F.api("/seguridad/plantillas-informe"); } catch { s.plantillas = null; }
    pintarPlantillas();
  }
  function pintarPlantillas() {
    const sel = $("#sg-inf-plantilla");
    const p = s.plantillas;
    sel.closest("label").hidden = !p;
    if (!p) return;
    const orden = ["hackerone", "bugcrowd", "breve", "personalizada"].filter((k) => p.plantillas[k]);
    sel.innerHTML = orden.map((k) => `<option value="${k}">${E(T("if.informe_plantilla." + k))}</option>`).join("");
    sel.value = p.activa.id;
    const nota = $("#sg-inf-plantilla-nota");
    const propiaVacia = p.activa.id === "personalizada" && !p.plantillas.personalizada.estructura;
    nota.hidden = !propiaVacia;
    nota.textContent = propiaVacia ? T("seg.inf.plantilla_vacia") : "";
    sel.title = p.activa.estructura;
  }
  async function cambiarPlantilla(id) {
    try {
      await F.api("/ajustes", { method: "PUT", body: { "ui.informe_plantilla": id } });
      F.ajustes["ui.informe_plantilla"] = id;
    } catch (x) { msg("#sg-inf-msg", errorTxt(x), "mal"); }
    await cargarPlantillas();
  }

  async function generarInforme() {
    if (s.informe.gen) { s.informe.gen.abort(); return; }
    const fid = s.informe.fid;
    const md = $("#sg-inf-md");
    const ctrl = new AbortController();
    s.informe.gen = ctrl;
    s.informe.previa = false;
    md.value = "";
    pintarInforme();
    msg("#sg-inf-msg", T("seg.inf.redactando", { modelo: F.st.tier === "nube" ? "Claude" : F.etiquetaPara("seguridad", F.st.tier) }));
    try {
      await sseLocal(`/findings/${fid}/informe`, { enfoques: s.informe.enfoques, tier: F.st.tier, esfuerzo: F.st.esfuerzo }, (ev, d) => {
        if (ev === "token") { md.value += d.texto; md.scrollTop = md.scrollHeight; }
        else if (ev === "thinking") msg("#sg-inf-msg", T("seg.inf.pensando"));
        else if (ev === "error") msg("#sg-inf-msg", d.mensaje, "mal");
        else if (ev === "fin") {
          const i = s.findings.findIndex((x) => x.id === fid);
          if (i >= 0) s.findings[i] = d.finding;
          md.value = d.finding.informe_md || md.value;   // el texto guardado manda (sin razonamiento previo)
          msg("#sg-inf-msg", T("seg.inf.listo"), "ok");
        }
      }, ctrl.signal);
    } catch (x) {
      msg("#sg-inf-msg", x.name === "AbortError" ? T("seg.inf.detenido") : errorTxt(x), x.name === "AbortError" ? "aviso" : "mal");
    }
    s.informe.gen = null;
    md.dataset.fid = fid;
    pintarInforme();
    F.refrescarSalud();
  }

  async function guardarInforme(extra = {}) {
    try {
      const f = await F.api(`/findings/${s.informe.fid}`, { method: "POST", body: { informe_md: $("#sg-inf-md").value, ...extra } });
      const i = s.findings.findIndex((x) => x.id === f.id);
      if (i >= 0) s.findings[i] = f;
      msg("#sg-inf-msg", T(extra.estado ? "seg.inf.reportado_ok" : "seg.inf.guardado"), "ok");
      pintarInforme();
      return true;
    } catch (x) { msg("#sg-inf-msg", errorTxt(x), "mal"); return false; }
  }

  async function exportarInforme() {
    if (!(await guardarInforme())) return;
    try {
      const r = await F.api("/export", { method: "POST", body: { tipo: "informe", id: s.informe.fid } });
      const el = $("#sg-inf-msg");
      el.className = "sg-msg ok"; el.hidden = false;
      el.innerHTML = `${E(T("seg.inf.exportado"))} <code>${E(r.ruta)}</code> <button type="button" class="boton-txt peq" id="sg-abrir-carpeta">${E(T("seg.inf.abrir_carpeta"))}</button>`;
      $("#sg-abrir-carpeta").addEventListener("click", () => F.api("/export/abrir-carpeta", { method: "POST" }).catch(() => {}));
    } catch (x) { msg("#sg-inf-msg", errorTxt(x), "mal"); }
  }

  // ---------------------------------------------------------------- enlaces
  let enlazado = false;
  function enlazar() {
    if (enlazado) return;
    enlazado = true;
    for (const id of ["#sg-nombre", "#sg-alcance", "#sg-notas"]) $(id).addEventListener("input", validarForm);
    $("#sg-declaro").addEventListener("change", validarForm);
    $("#sg-gate-form").addEventListener("submit", (ev) => {
      ev.preventDefault();
      if (asistente() && s.paso < 3) { if (s.paso > 1 || paso1Ok()) irPaso(s.paso + 1); return; }   // Enter = Siguiente
      enviarGate();
    });
    $("#sg-siguiente").addEventListener("click", () => irPaso(s.paso + 1));
    $("#sg-atras").addEventListener("click", () => irPaso(s.paso - 1));
    $("#sg-pasos").addEventListener("click", (ev) => {
      const li = ev.target.closest("li");
      if (li && Number(li.dataset.n) < s.paso) irPaso(Number(li.dataset.n));     // volver a un paso hecho
    });
    $("#sg-cancelar-ed").addEventListener("click", limpiarForm);
    $("#sg-salir").addEventListener("click", salir);
    $("#sg-editar-alcance").addEventListener("click", async () => {
      if (F.st.gen) return;
      const e = s.eng;
      s.eng = null;
      await cargarLista();
      pintar();
      editar(s.lista.find((x) => x.id === e.id) || e);
    });
    document.querySelectorAll(".sg-tab").forEach((b) => b.addEventListener("click", () => cambiarTab(b.dataset.tab)));
    $("#sg-recon").addEventListener("input", pintarAnalisis);
    $("#sg-analizar").addEventListener("click", analizar);
    $("#sg-importar").addEventListener("click", () => $("#sg-archivo").click());
    $("#sg-archivo").addEventListener("change", importar);
    $("#sg-nuevo-manual").addEventListener("click", () => { s.nuevoManual = !s.nuevoManual; pintarHallazgos(); if (s.nuevoManual) $("#sg-manual [name=titulo]").focus(); });
    $("#sg-manual").addEventListener("submit", crearManual);
    $("#sg-manual-cancelar").addEventListener("click", () => { s.nuevoManual = false; pintarHallazgos(); });
    $("#sg-inf-plantilla").addEventListener("change", (ev) => cambiarPlantilla(ev.target.value));
    $("#sg-inf-sel").addEventListener("change", (ev) => { s.informe.fid = Number(ev.target.value); $("#sg-inf-md").dataset.fid = ""; msg("#sg-inf-msg", ""); pintarInforme(); });
    $("#sg-inf-mas").addEventListener("click", () => { if (s.informe.enfoques.length < 4) { s.informe.enfoques.push(""); pintarInforme(); } });
    $("#sg-inf-generar").addEventListener("click", generarInforme);
    $("#sg-inf-guardar").addEventListener("click", () => guardarInforme());
    $("#sg-inf-reportado").addEventListener("click", () => guardarInforme({ estado: "reportado" }));
    $("#sg-inf-exportar").addEventListener("click", exportarInforme);
    $("#sg-inf-copiar").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText($("#sg-inf-md").value); msg("#sg-inf-msg", T("seg.inf.copiado"), "ok"); }
      catch { $("#sg-inf-md").select(); document.execCommand("copy"); msg("#sg-inf-msg", T("seg.inf.copiado"), "ok"); }
    });
    $("#sg-inf-toggle").addEventListener("click", () => { s.informe.previa = !s.informe.previa; pintarInforme(); });
    $("#sg-inf-md").addEventListener("input", () => pintarInforme());
  }

  window.ForjaSeguridad = {
    async mostrar() {
      F = window.ForjaApp;
      enlazar();
      // Actividad «Aprender» (Rama 4b): la Academia sustituye al gate/engagement en esta vista.
      await window.ForjaAcademia?.mostrar(() => window.ForjaSeguridad.mostrar());
      if (aprendiendo()) { pintar(); return; }
      try { await cargarLista(); } catch (x) { msg("#sg-gate-msg", errorTxt(x), "mal"); }
      if (s.eng) {   // vuelve al mismo engagement en esta sesión (sigue auditado al haber entrado)
        const actual = s.lista.find((e) => e.id === s.eng.id);
        if (!actual?.operable) s.eng = null; else s.eng = actual;
      }
      pintar();
      if (s.eng && F.st.hilosDe !== `seg:${s.eng.id}`) { await F.cargarHilos(); }
    },
    engagementId: () => (aprendiendo() ? null : s.eng?.id ?? null),
    chatActivo: () => !aprendiendo() && !!s.eng && s.tab === "chat",
    aprendiendo,
    contenedorChat: () => $("#sg-chat"),
    alCambiarSelector() { if (s.eng && s.tab === "analisis") pintarAnalisis(); },
    // Rama 6: el gate (SG1) y los hallazgos (SG2) se repintan al cambiar la interfaz en Ajustes.
    alCambiarInterfaz() {
      if (!enlazado) return;
      pintarPasos();
      if (s.eng && s.tab === "hallazgos") pintarHallazgos();
      if (s.plantillasPedidas) cargarPlantillas();          // SG3 cambiado en Ajustes → el redactor lo refleja
    },
  };
})();
