/* FORJA — Academia de Seguridad (MOD-090) y Laboratorio Linux + Copiloto (MOD-091), Rama 4b.
   SCR-024 rutas + gate de laboratorio (BTN-087) · SCR-025 lección guiada · SCR-026 progreso y herramientas ·
   SCR-027 laboratorio Linux. Los guardarraíles viven en el backend; la UI solo los refleja. */
(() => {
  "use strict";

  const s = { vista: "rutas", rutas: [], abierta: null, rutaDet: {}, lab: null, sid: null, sec: null,
              gen: null, perfil: null, herr: [], det: null, prop: null, copi: { gen: null }, labForm: false };
  let F;
  const $ = (q, r = document) => r.querySelector(q);
  const T = (k, v) => (v ? F.fmt(k, v) : F.t(k));
  const E = (x) => F.esc(x ?? "");
  const errorTxt = (e) => (e && e.message) || String(e);
  const ajuste = (k, d) => (F.ajustes[k] ?? d);
  const activa = () => ajuste("seguridad.actividad", "trabajo") === "aprender";

  function msg(el, texto, clase = "") {
    if (typeof el === "string") el = $(el);
    if (!el) return;
    el.textContent = texto || "";
    el.className = "sg-msg " + clase;
    el.hidden = !texto;
  }

  async function sse(path, body, onEvento, signal) {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Forja-Token": window.FORJA_TOKEN },
      body: JSON.stringify(body), signal });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error?.mensaje || `HTTP ${r.status}`); }
    const lector = r.body.getReader(), dec = new TextDecoder();
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

  async function guardarAjuste(clave, valor) {
    const r = await F.api("/ajustes", { method: "PUT", body: { [clave]: valor } });
    F.ajustes = r.ajustes; window.ForjaApp.ajustes = r.ajustes;
  }
  const modeloTxt = () => (F.st.tier === "nube" ? "Claude" : F.etiquetaPara("seguridad", F.st.tier));
  const cuerpoIA = () => ({ tier: F.st.tier, esfuerzo: F.st.esfuerzo });

  // ---------------------------------------------------------------- barra: actividad + enfoque (FR-035)
  function pintarBarra() {
    for (const b of document.querySelectorAll("#ac-actividad button")) b.setAttribute("aria-checked", String(b.dataset.v === ajuste("seguridad.actividad", "trabajo")));
    for (const b of document.querySelectorAll("#ac-enfoque button")) b.setAttribute("aria-checked", String(b.dataset.v === ajuste("seguridad.enfoque", "ofensivo")));
    $("#ac-nav").hidden = !activa();
    for (const b of document.querySelectorAll(".ac-nav-b")) {
      b.setAttribute("aria-selected", String(b.dataset.vista === s.vista));
      if (b.dataset.vista === "leccion") b.disabled = !s.sid;
    }
  }

  // ---------------------------------------------------------------- SCR-024 rutas + gate de laboratorio
  async function cargarRutas() {
    const r = await F.api("/academia/rutas");
    s.rutas = r.rutas; s.lab = r.laboratorio;
    if (s.abierta) s.rutaDet[s.abierta] = await F.api(`/academia/rutas/${s.abierta}`);
  }

  function pintarGateLab() {
    const caja = $("#ac-lab-gate");
    if (s.lab && !s.labForm) {
      caja.className = "ac-lab-gate ok";
      caja.innerHTML = `<svg><use href="#i-escudo"/></svg><div><strong>${E(T("aca.lab.declarado"))}</strong>` +
        `<p>${E(s.lab.descripcion)} · <span class="ac-chip">${E(T("aca.entorno." + s.lab.entorno))}</span></p></div>` +
        `<button type="button" class="boton-txt peq" data-cambiar>${E(T("aca.lab.cambiar"))}</button>` +
        `<button type="button" class="boton-txt peq" data-revocar>${E(T("aca.lab.revocar"))}</button>`;
      $("[data-cambiar]", caja).addEventListener("click", () => { s.labForm = true; pintarGateLab(); });
      $("[data-revocar]", caja).addEventListener("click", async () => {
        await F.api("/academia/laboratorio", { method: "DELETE" }); s.lab = null; pintarGateLab();
      });
      return;
    }
    caja.className = "ac-lab-gate";
    caja.innerHTML = `<svg><use href="#i-candado"/></svg><form class="ac-lab-form" autocomplete="off">` +
      `<strong>${E(T("aca.lab.titulo"))}</strong><p>${E(T("aca.lab.sub"))}</p>` +
      `<div class="ac-lab-fila"><select name="entorno">${["htb", "thm", "local", "ctf", "otro"].map((x) => `<option value="${x}">${E(T("aca.entorno." + x))}</option>`).join("")}</select>` +
      `<input type="text" name="desc" maxlength="300" placeholder="${E(T("aca.lab.desc_ph"))}"></div>` +
      `<label class="sg-declaro"><input type="checkbox" name="declaro"><span>${E(T("aca.lab.declaro"))}</span></label>` +
      `<div class="ac-lab-fila fin"><p class="sg-msg" hidden></p>` +
      (s.lab ? `<button type="button" class="boton-txt peq" data-cancelar>${E(T("tareas.ed.cancelar"))}</button>` : "") +
      `<button type="submit" class="boton peq" disabled>${E(T("aca.lab.declarar"))}</button></div></form>`;
    const f = $("form", caja);
    const valida = () => { $("[type=submit]", f).disabled = !(f.desc.value.trim() && f.declaro.checked); };
    f.desc.addEventListener("input", valida); f.declaro.addEventListener("change", valida);
    $("[data-cancelar]", f)?.addEventListener("click", () => { s.labForm = false; pintarGateLab(); });
    f.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try {
        s.lab = (await F.api("/academia/laboratorio", { method: "POST", body: { entorno: f.entorno.value, descripcion: f.desc.value, declaracion: f.declaro.checked } })).laboratorio;
        s.labForm = false; pintarGateLab();
        if (s.vista === "leccion") pintarLeccion();
      } catch (x) { msg($(".sg-msg", f), errorTxt(x), "mal"); }
    });
  }

  const DIF = { fundamental: 1, facil: 2, medio: 3, dificil: 4 };
  function pintarRutas() {
    pintarGateLab();
    const cont = $("#ac-rutas");
    cont.innerHTML = "";
    for (const tipo of ["skill", "rol"]) {
      const grupo = s.rutas.filter((r) => r.tipo === tipo);
      if (!grupo.length) continue;
      const h = document.createElement("h3");
      h.className = "ac-h3"; h.textContent = T("aca.tipo." + tipo);
      cont.append(h);
      for (const r of grupo) cont.append(tarjetaRuta(r));
    }
  }

  function tarjetaRuta(r) {
    const div = document.createElement("div");
    div.className = "ac-ruta" + (s.abierta === r.id ? " abierta" : "") + (r.terminada ? " hecha" : "");
    div.innerHTML = `<button type="button" class="ac-ruta-cab">` +
      `<div class="ac-ruta-txt"><strong>${E(r.nombre)}</strong><p>${E(r.descripcion)}</p></div>` +
      `<div class="ac-ruta-meta"><span class="ac-chip ${r.enfoque}">${E(T("aca.enf." + r.enfoque))}</span>` +
      `<span>${E(T("aca.ruta.meta", { m: r.modulos, s: r.secciones }))}</span>` +
      (r.enrolado ? `<div class="ac-barra-prog"><i style="width:${r.porcentaje}%"></i></div><span>${r.porcentaje}%</span>` : "") +
      `</div></button>`;
    $(".ac-ruta-cab", div).addEventListener("click", async () => {
      s.abierta = s.abierta === r.id ? null : r.id;
      if (s.abierta) s.rutaDet[r.id] = await F.api(`/academia/rutas/${r.id}`);
      pintarRutas();
    });
    const det = s.abierta === r.id ? s.rutaDet[r.id] : null;
    if (det) {
      const cuerpo = document.createElement("div");
      cuerpo.className = "ac-ruta-cuerpo";
      if (!det.enrolado) {
        const b = document.createElement("button");
        b.type = "button"; b.className = "boton"; b.textContent = T("aca.ruta.enrolar");
        b.addEventListener("click", async () => { s.rutaDet[r.id] = await F.api("/academia/enrolar", { method: "POST", body: { path_id: r.id } }); await cargarRutas(); pintarRutas(); });
        cuerpo.append(b);
      }
      for (const m of det.modulos_detalle) {
        const mod = document.createElement("div");
        mod.className = "ac-modulo";
        mod.innerHTML = `<div class="ac-mod-cab"><strong>${E(m.nombre)}</strong><span class="ac-dif d${DIF[m.dificultad]}">${E(T("aca.dif." + m.dificultad))}</span></div>`;
        const ul = document.createElement("ul");
        for (const sec of m.secciones) {
          const li = document.createElement("li");
          li.innerHTML = `<button type="button" ${det.enrolado ? "" : "disabled"}><span class="ac-est e-${sec.estado}"></span>` +
            `<span class="tit">${E(sec.titulo)}</span><span class="ac-tipo">${E(T("aca.stipo." + sec.tipo))}</span>` +
            (sec.estado === "completada" ? `<span class="ac-xp">+${sec.xp} XP</span>` : "") + `</button>`;
          $("button", li).addEventListener("click", () => abrirSeccion(sec.id));
          ul.append(li);
        }
        mod.append(ul);
        cuerpo.append(mod);
      }
      div.append(cuerpo);
    }
    return div;
  }

  // ---------------------------------------------------------------- SCR-025 lección guiada
  async function abrirSeccion(id) {
    if (s.gen) s.gen.abort();
    s.sid = id;
    s.sec = await F.api(`/academia/leccion/${id}`);
    guardarAjuste("academia.seccion", String(id)).catch(() => {});
    await cambiarVista("leccion");
  }

  function pintarLeccion() {
    const main = $("#ac-lec-main");
    const x = s.sec;
    if (!x) { main.innerHTML = `<p class="sg-vacio">${E(T("aca.lec.ninguna"))}</p>`; return; }
    const bloqueada = x.requiere_lab && !s.lab;
    const generando = !!s.gen;
    main.innerHTML =
      `<div class="ac-miga">${E(x.ruta)} › ${E(x.modulo)}</div>` +
      `<h2 class="ac-lec-h2">${E(x.titulo)}</h2>` +
      `<div class="ac-chips"><span class="ac-chip">${E(T("aca.stipo." + x.tipo))}</span><span class="ac-dif d${DIF[x.dificultad]}">${E(T("aca.dif." + x.dificultad))}</span>` +
      `<span class="ac-chip est-${x.estado}">${E(T("aca.est." + (x.estado || "sin_enrolar")))}</span>${x.estado === "completada" ? `<span class="ac-xp">+${x.xp} XP</span>` : ""}</div>` +
      (bloqueada ? `<div class="ac-aviso"><svg><use href="#i-candado"/></svg><span>${E(T("aca.lec.requiere_lab"))}</span><button type="button" class="boton-txt peq" data-ir-lab>${E(T("aca.lec.declarar"))}</button></div>` : "") +
      `<div class="ac-lec-acc"><button type="button" class="boton" data-generar ${bloqueada || !x.enrolado ? "disabled" : ""}><svg><use href="#i-chispa"/></svg><span>${E(T(generando ? "seg.inf.detener" : x.leccion_md ? "aca.lec.regenerar" : "aca.lec.empezar"))}</span></button>` +
      (x.requiere_lab ? `<button type="button" class="boton-txt" data-abrir-lab ${bloqueada ? "disabled" : ""}>${E(T("aca.lec.abrir_linux"))}</button>` : "") +
      `<p class="sg-msg" id="ac-lec-msg" hidden></p></div>` +
      `<div class="cuerpo ac-lec-md" id="ac-lec-md">${x.leccion_md ? window.ForjaMD.render(x.leccion_md) : `<p class="ac-guia">${E(x.contenido_guia || "")}</p>`}</div>` +
      (x.pregunta ? `<div class="ac-pregunta"><h4>${E(T("aca.lec.pregunta"))}</h4><p>${E(x.pregunta)}</p>` +
        `<form class="ac-resp" autocomplete="off"><input type="text" name="r" maxlength="2000" ${x.acertada ? "disabled" : ""} placeholder="${E(T(x.acertada ? "aca.lec.acertada" : "aca.lec.resp_ph"))}">` +
        `<button type="submit" class="boton-txt" ${x.acertada || bloqueada ? "disabled" : ""}>${E(T("aca.lec.comprobar"))}</button></form><p class="sg-msg" id="ac-resp-msg" hidden></p></div>` : "") +
      `<div class="ac-pistas"><div class="ac-pistas-cab"><h4>${E(T("aca.lec.pistas"))}</h4>` +
        `<button type="button" class="boton-txt peq" data-pista ${bloqueada || !x.enrolado || x.estado === "completada" ? "disabled" : ""}>${E(T("aca.lec.pedir_pista", { n: x.pistas_usadas || 0 }))}</button></div>` +
        (x.pistas.length ? `<ol>${x.pistas.map((p) => `<li class="cuerpo">${window.ForjaMD.render(p)}</li>`).join("")}</ol>` : `<p class="ac-ayuda">${E(T("aca.lec.pistas_ayuda"))}</p>`) +
        `<p class="sg-msg" id="ac-pista-msg" hidden></p></div>` +
      `<div class="ac-lec-pie"><button type="button" class="boton-txt peq" data-ant ${x.anterior ? "" : "disabled"}>← ${E(T("aca.lec.anterior"))}</button>` +
        `<button type="button" class="boton" data-completar ${x.estado === "completada" || !x.enrolado || (x.pregunta && !x.acertada) ? "disabled" : ""}>${E(T(x.estado === "completada" ? "aca.lec.completada" : "aca.lec.completar"))}</button>` +
        `<button type="button" class="boton-txt peq" data-sig ${x.siguiente ? "" : "disabled"}>${E(T("aca.lec.siguiente"))} →</button></div>` +
      `<p class="sg-msg" id="ac-comp-msg" hidden></p>`;

    $("[data-ir-lab]", main)?.addEventListener("click", () => cambiarVista("rutas"));
    $("[data-generar]", main).addEventListener("click", generar);
    $("[data-abrir-lab]", main)?.addEventListener("click", () => abrirLinux(null, $("#ac-lec-msg")));
    $("[data-pista]", main).addEventListener("click", pedirPista);
    $(".ac-resp", main)?.addEventListener("submit", comprobar);
    $("[data-ant]", main).addEventListener("click", () => abrirSeccion(x.anterior));
    $("[data-sig]", main).addEventListener("click", () => abrirSeccion(x.siguiente));
    $("[data-completar]", main).addEventListener("click", completar);
  }

  async function generar() {
    if (s.gen) { s.gen.abort(); return; }
    const ctrl = new AbortController();
    s.gen = ctrl;
    pintarLeccion();
    const md = $("#ac-lec-md");
    let texto = "";
    md.innerHTML = "";
    msg("#ac-lec-msg", T("aca.lec.preparando", { modelo: modeloTxt() }));
    try {
      await sse(`/academia/leccion/${s.sid}/generar`, cuerpoIA(), (ev, d) => {
        if (ev === "token") { texto += d.texto; md.innerHTML = window.ForjaMD.render(texto); }
        else if (ev === "thinking") msg("#ac-lec-msg", T("seg.inf.pensando"));
        else if (ev === "error") { s.err = d.mensaje; }
        else if (ev === "fin") { s.sec = d.seccion; s.err = null; }
      }, ctrl.signal);
    } catch (x) { s.err = x.name === "AbortError" ? T("seg.inf.detenido") : errorTxt(x); }
    s.gen = null;
    pintarLeccion();
    if (s.err) { msg("#ac-lec-msg", s.err, "mal"); s.err = null; }
    F.refrescarSalud();
  }

  async function pedirPista(ev) {
    const b = ev.currentTarget;
    b.disabled = true;
    msg("#ac-pista-msg", T("aca.lec.pensando_pista", { modelo: modeloTxt() }));
    try {
      await F.api("/academia/pista", { method: "POST", body: { seccion_id: s.sid, ...cuerpoIA() } });
      s.sec = await F.api(`/academia/leccion/${s.sid}`);
      pintarLeccion();
    } catch (x) { msg("#ac-pista-msg", errorTxt(x), "mal"); b.disabled = false; }
  }

  async function comprobar(ev) {
    ev.preventDefault();
    const f = ev.currentTarget;
    const resp = f.r.value;
    if (!resp.trim()) return;
    $("[type=submit]", f).disabled = true;
    msg("#ac-resp-msg", T("aca.lec.comprobando"));
    try {
      const r = await F.api("/academia/comprobar", { method: "POST", body: { seccion_id: s.sid, respuesta: resp, ...cuerpoIA() } });
      if (r.correcta) { s.sec = await F.api(`/academia/leccion/${s.sid}`); pintarLeccion(); msg("#ac-resp-msg", r.feedback, "ok"); }
      else { msg("#ac-resp-msg", r.feedback, "aviso"); $("[type=submit]", f).disabled = false; }
    } catch (x) { msg("#ac-resp-msg", errorTxt(x), "mal"); $("[type=submit]", f).disabled = false; }
  }

  async function completar() {
    try {
      const r = await F.api("/academia/progreso", { method: "POST", body: { seccion_id: s.sid } });
      s.sec = r.seccion; s.perfil = r.perfil;
      pintarLeccion();
      msg("#ac-comp-msg", T("aca.lec.xp_ganado", { xp: r.xp_ganado, total: r.perfil.xp, rango: r.perfil.rango }), "ok");
      if (s.abierta) s.rutaDet[s.abierta] = await F.api(`/academia/rutas/${s.abierta}`);
    } catch (x) { msg("#ac-comp-msg", errorTxt(x), "mal"); }
  }

  // ---------------------------------------------------------------- SCR-026 progreso + árbol de herramientas
  async function pintarProgreso() {
    const cont = $("#ac-progreso");
    try {
      [s.perfil, s.herr] = await Promise.all([F.api("/academia/perfil"), F.api("/academia/herramientas").then((r) => r.herramientas)]);
    } catch (x) { cont.innerHTML = `<p class="sg-msg mal">${E(errorTxt(x))}</p>`; return; }
    const p = s.perfil;
    const pct = p.siguiente ? Math.round((p.xp / p.siguiente.xp) * 100) : 100;
    const enf = ajuste("seguridad.enfoque", "ofensivo");
    const grupos = {};
    for (const h of s.herr) (grupos[h.categoria || "Otros"] ||= []).push(h);
    cont.innerHTML =
      `<div class="ac-stats">` +
        `<div class="ac-stat"><span>${E(T("aca.prog.xp"))}</span><strong>${p.xp}</strong></div>` +
        `<div class="ac-stat"><span>${E(T("aca.prog.rango"))}</span><strong>${E(p.rango)}</strong>` +
          `<div class="ac-barra-prog"><i style="width:${pct}%"></i></div><small>${E(p.siguiente ? T("aca.prog.faltan", { n: p.siguiente.faltan, r: p.siguiente.rango }) : T("aca.prog.max"))}</small></div>` +
        `<div class="ac-stat"><span>${E(T("aca.prog.racha"))}</span><strong>${p.racha} ${E(T(p.racha === 1 ? "aca.prog.dia" : "aca.prog.dias"))}</strong></div>` +
        `<div class="ac-stat"><span>${E(T("aca.prog.lecciones"))}</span><strong>${p.lecciones_completadas}</strong></div>` +
      `</div>` +
      `<h3 class="ac-h3">${E(T("aca.prog.rutas"))}</h3>` +
      (p.rutas_en_curso.length || p.rutas_completadas.length
        ? `<ul class="ac-lista-rutas">${p.rutas_completadas.map((n) => `<li class="hecha"><svg><use href="#i-check"/></svg>${E(n)}</li>`).join("")}` +
          `${p.rutas_en_curso.map((r) => `<li><span>${E(r.nombre)}</span><div class="ac-barra-prog"><i style="width:${r.porcentaje}%"></i></div><small>${r.porcentaje}%</small></li>`).join("")}</ul>`
        : `<p class="ac-ayuda">${E(T("aca.prog.sin_rutas"))}</p>`) +
      `<h3 class="ac-h3">${E(T("aca.prog.arbol"))}</h3><p class="ac-ayuda">${E(T("aca.prog.arbol_ayuda"))}</p>` +
      `<div class="ac-arbol">${Object.entries(grupos).map(([cat, hs]) => `<div class="ac-rama"><h4>${E(cat)}</h4><ul>` +
        hs.map((h) => `<li class="${h.aprendida ? "aprendida" : ""} ${h.enfoque !== "ambos" && h.enfoque !== enf ? "otro-enfoque" : ""}">` +
          `<div class="ac-herr-cab"><span class="ac-est e-${h.aprendida ? "completada" : "pendiente"}"></span><strong>${E(h.nombre)}</strong><span class="ac-chip ${h.enfoque}">${E(T("aca.enf." + h.enfoque))}</span></div>` +
          `<p>${E(h.para_que)}</p>` +
          (h.seccion ? `<button type="button" class="ac-enlace" data-sec="${h.seccion_id}">${E(h.ruta)} › ${E(h.seccion)}</button>` : "") + `</li>`).join("") +
        `</ul></div>`).join("")}</div>`;
    cont.querySelectorAll("[data-sec]").forEach((b) => b.addEventListener("click", async () => {
      try { await abrirSeccion(Number(b.dataset.sec)); } catch (x) { /* sección no enrolada: se abre igualmente en modo lectura */ }
    }));
  }

  // ---------------------------------------------------------------- SCR-027 Laboratorio Linux
  async function pintarLab(redetectar = true) {
    const cont = $("#ac-lab");
    if (redetectar || !s.det) {
      cont.innerHTML = `<p class="ac-ayuda">${E(T("aca.labl.detectando"))}</p>`;
      try { s.det = await F.api("/academia/lab/detectar"); } catch (x) { cont.innerHTML = `<p class="sg-msg mal">${E(errorTxt(x))}</p>`; return; }
    }
    const d = s.det;
    const sec = s.sec;
    cont.innerHTML =
      `<h2 class="ac-lec-h2">${E(T("aca.labl.titulo"))}</h2><p class="ac-ayuda">${E(T("aca.labl.sub", { ram: Math.round((d.ram_total_mb || 0) / 1024), disco: Math.round((d.disco_libre_mb || 0) / 1024) }))}</p>` +
      `<div class="ac-backends">${d.backends.map((b) => `<div class="ac-backend ${d.activo === b.id ? "activo" : ""}">` +
        `<div class="ac-backend-cab"><strong>${E(T("aca.backend." + b.id))}</strong>` +
          (b.recomendado ? `<span class="ac-chip ok">${E(T("aca.labl.recomendado"))}</span>` : "") +
          (b.pesado ? `<span class="ac-chip aviso">${E(T("aca.labl.pesado"))}</span>` : "") +
          (b.disponible ? `<span class="ac-chip">${E(T("aca.labl.listo"))}</span>` : "") + `</div>` +
        `<p>${E(b.nota)}</p>` +
        (b.id === "attackbox" ? `<div class="ac-lab-fila"><input type="text" data-url value="${E(b.url || "")}" placeholder="https://…"><button type="button" class="boton-txt peq" data-guardar-url>${E(T("seg.f.guardar"))}</button></div>` : "") +
        `<div class="ac-lab-fila fin">` +
          (b.instalable && !b.disponible ? `<button type="button" class="boton-txt peq" data-config="${b.id}">${E(T("aca.labl.configurar"))}</button>` : "") +
          (d.activo === b.id ? `<span class="ac-activo">${E(T("aca.labl.activo"))}</span>` : `<button type="button" class="boton-txt peq" data-activar="${b.id}">${E(T("aca.labl.usar"))}</button>`) +
        `</div></div>`).join("")}</div>` +
      `<div id="ac-propuesta"></div>` +
      `<div class="ac-lab-ej"><h3 class="ac-h3">${E(T("aca.labl.ejercicio"))}</h3>` +
        (sec ? `<p><strong>${E(sec.titulo)}</strong> · ${E(sec.ruta)}</p><div class="ac-lab-fila">` +
          `<button type="button" class="boton" data-abrir ${s.lab ? "" : "disabled"}>${E(T("aca.lec.abrir_linux"))}</button>` +
          `<button type="button" class="boton-txt" data-contexto ${s.lab ? "" : "disabled"}>${E(T("aca.labl.contexto"))}</button>` +
          `<button type="button" class="boton-txt" data-carpeta ${s.lab ? "" : "disabled"}>${E(T("aca.labl.carpeta"))}</button></div>` +
          (s.lab ? "" : `<p class="sg-msg aviso">${E(T("aca.lec.requiere_lab"))}</p>`)
          : `<p class="ac-ayuda">${E(T("aca.labl.sin_ejercicio"))}</p>`) +
        `<p class="sg-msg" id="ac-lab-msg" hidden></p>` +
        `<button type="button" class="boton-txt peq" data-redetectar>${E(T("aca.labl.redetectar"))}</button></div>`;
    cont.querySelectorAll("[data-activar]").forEach((b) => b.addEventListener("click", async () => {
      await guardarAjuste("lab.backend", b.dataset.activar); s.det.activo = b.dataset.activar; pintarLab(false);
    }));
    cont.querySelectorAll("[data-config]").forEach((b) => b.addEventListener("click", () => proponer(b.dataset.config)));
    $("[data-guardar-url]", cont)?.addEventListener("click", async () => {
      try { await F.api("/academia/lab/configurar", { method: "POST", body: { backend: "attackbox", url: $("[data-url]", cont).value } }); msg("#ac-lab-msg", T("seg.inf.guardado"), "ok"); s.det = null; pintarLab(); }
      catch (x) { msg("#ac-lab-msg", errorTxt(x), "mal"); }
    });
    $("[data-abrir]", cont)?.addEventListener("click", () => abrirLinux(null, $("#ac-lab-msg")));
    $("[data-contexto]", cont)?.addEventListener("click", async () => {
      try { const r = await F.api("/academia/lab/contexto", { method: "POST", body: { seccion_id: s.sid } }); msgHtml($("#ac-lab-msg"), T("aca.labl.contexto_ok"), r.readme); }
      catch (x) { msg("#ac-lab-msg", errorTxt(x), "mal"); }
    });
    $("[data-carpeta]", cont)?.addEventListener("click", () => F.api("/academia/lab/carpeta", { method: "POST", body: { seccion_id: s.sid } }).catch((x) => msg("#ac-lab-msg", errorTxt(x), "mal")));
    $("[data-redetectar]", cont).addEventListener("click", () => pintarLab(true));
    if (s.prop) pintarPropuesta();
  }

  function msgHtml(el, texto, ruta) {
    el.className = "sg-msg ok"; el.hidden = false;
    el.innerHTML = `${E(texto)} <code>${E(ruta)}</code>`;
  }

  // ST-040: propuesta → esperando_usuario → (aprobada → ejecutando) | rechazada. Nada se instala sin el OK.
  async function proponer(backend) {
    try { s.prop = await F.api("/academia/lab/configurar", { method: "POST", body: { backend } }); pintarPropuesta(); }
    catch (x) { msg("#ac-lab-msg", errorTxt(x), "mal"); }
  }
  function pintarPropuesta() {
    const p = s.prop, caja = $("#ac-propuesta");
    if (!p || !caja) return;
    caja.innerHTML = `<div class="ac-propuesta"><h4>${E(T("aca.labl.propuesta", { b: T("aca.backend." + p.backend) }))}</h4><p>${E(p.explicacion)}</p>` +
      `<pre class="ac-cmd">${p.comandos.map(E).join("\n")}</pre>` +
      (p.mensaje ? `<p class="sg-msg ok">${E(p.mensaje)}</p>` :
        `<label class="sg-declaro"><input type="checkbox" data-ok><span>${E(T("aca.labl.confirmo"))}</span></label>` +
        `<div class="ac-lab-fila fin"><button type="button" class="boton-txt peq" data-rechazar>${E(T("aca.labl.rechazar"))}</button>` +
        `<button type="button" class="boton peq" data-ejecutar disabled>${E(T("aca.labl.ejecutar"))}</button></div>`) + `</div>`;
    $("[data-ok]", caja)?.addEventListener("change", (ev) => { $("[data-ejecutar]", caja).disabled = !ev.target.checked; });
    $("[data-rechazar]", caja)?.addEventListener("click", () => { s.prop = null; caja.innerHTML = ""; });
    $("[data-ejecutar]", caja)?.addEventListener("click", async () => {
      try { s.prop = await F.api("/academia/lab/configurar", { method: "POST", body: { backend: p.backend, confirmado: true, distro: p.distro } }); pintarPropuesta(); }
      catch (x) { msg("#ac-lab-msg", errorTxt(x), "mal"); }
    });
  }

  async function abrirLinux(backend, el) {
    if (!s.sid) return;
    msg(el, T("aca.labl.abriendo"));
    try {
      const r = await F.api("/academia/lab/abrir", { method: "POST", body: { seccion_id: s.sid, backend } });
      msgHtml(el, T(r.backend === "attackbox" ? "aca.labl.abierto_ab" : r.backend === "wsl" ? "aca.labl.abierto_wsl" : "aca.labl.abierto_vb"), r.readme);
    } catch (x) { msg(el, errorTxt(x), "mal"); }
  }

  // ---------------------------------------------------------------- Copiloto (FR-075/076)
  function colocarCopi() {
    const destino = s.vista === "lab" ? $("#ac-lado-lab") : $("#ac-lado-leccion");
    const copi = $("#ac-copi");
    if (copi.parentElement !== destino) destino.append(copi);
    $("#ac-copi-ctx").textContent = s.sec ? s.sec.titulo : T("aca.copi.libre");
  }

  async function cargarCopi() {
    const caja = $("#ac-copi-msgs");
    if (!s.lab) { caja.innerHTML = `<p class="ac-ayuda">${E(T("aca.copi.bloqueado"))}</p>`; bloquearCopi(true); return; }
    bloquearCopi(false);
    try {
      const { mensajes } = await F.api(`/academia/mensajes${s.sid ? `?seccion=${s.sid}` : ""}`);
      const visibles = mensajes.filter((m) => !m.contenido.startsWith("[Pista "));
      caja.innerHTML = visibles.length ? "" : `<p class="ac-ayuda">${E(T("aca.copi.vacio"))}</p>`;
      for (const m of visibles) caja.append(burbuja(m.rol, m.contenido));
      caja.scrollTop = caja.scrollHeight;
    } catch (x) { msg("#ac-copi-msg", errorTxt(x), "mal"); }
  }
  function bloquearCopi(b) {
    for (const id of ["#ac-copi-sig", "#ac-copi-exp", "#ac-copi-enviar", "#ac-copi-txt"]) $(id).disabled = b;
  }
  function burbuja(rol, texto) {
    const d = document.createElement("div");
    d.className = "ac-burbuja " + rol;
    if (rol === "user") d.textContent = texto; else { d.classList.add("cuerpo"); d.innerHTML = window.ForjaMD.render(texto); }
    return d;
  }

  async function copiloto(accion) {
    if (s.copi.gen) { s.copi.gen.abort(); return; }
    const ta = $("#ac-copi-txt");
    const texto = ta.value.trim();
    if (accion !== "siguiente" && !texto) { msg("#ac-copi-msg", T(accion === "explicar" ? "aca.copi.pega" : "aca.copi.escribe"), "aviso"); return; }
    const caja = $("#ac-copi-msgs");
    caja.querySelector(".ac-ayuda")?.remove();
    caja.append(burbuja("user", accion === "siguiente" ? `[${T("aca.copi.siguiente")}]${texto ? " " + texto : ""}` : accion === "explicar" ? `[${T("aca.copi.explicar")}]\n${texto}` : texto));
    const ia = burbuja("assistant", "");
    caja.append(ia);
    ta.value = "";
    const ctrl = new AbortController();
    s.copi.gen = ctrl;
    $("#ac-copi-enviar use").setAttribute("href", "#i-parar");
    msg("#ac-copi-msg", T("aca.copi.pensando", { modelo: modeloTxt() }));
    let out = "";
    try {
      await sse(`/academia/copiloto/${accion}`, { seccion_id: s.sid, texto, ...cuerpoIA() }, (ev, d) => {
        if (ev === "token") { out += d.texto; ia.innerHTML = window.ForjaMD.render(out); caja.scrollTop = caja.scrollHeight; }
        else if (ev === "error") { ia.remove(); msg("#ac-copi-msg", d.mensaje + (d.reconduccion ? " " + d.reconduccion : ""), "mal"); }
        else if (ev === "fin") msg("#ac-copi-msg", "");
      }, ctrl.signal);
    } catch (x) { msg("#ac-copi-msg", x.name === "AbortError" ? T("seg.inf.detenido") : errorTxt(x), x.name === "AbortError" ? "aviso" : "mal"); }
    s.copi.gen = null;
    $("#ac-copi-enviar use").setAttribute("href", "#i-enviar");
    F.refrescarSalud();
  }

  // ---------------------------------------------------------------- vistas
  async function cambiarVista(v) {
    s.vista = v;
    document.querySelectorAll(".ac-vista").forEach((n) => { n.hidden = n.dataset.vista !== v; });
    $("#ac-copi").hidden = !(v === "leccion" || v === "lab");
    pintarBarra();
    try {
      if (v === "rutas") { await cargarRutas(); pintarRutas(); }
      if (v === "leccion") { if (!s.lab) s.lab = (await F.api("/academia/laboratorio")).laboratorio; pintarLeccion(); }
      if (v === "progreso") await pintarProgreso();
      if (v === "lab") { if (!s.lab) s.lab = (await F.api("/academia/laboratorio")).laboratorio; await pintarLab(!s.det); }
    } catch (x) { console.error(x); }
    if (v === "leccion" || v === "lab") { colocarCopi(); cargarCopi(); }
    F.actualizarLinea();
  }

  let enlazado = false;
  function enlazar(alCambiarActividad) {
    if (enlazado) return;
    enlazado = true;
    document.querySelectorAll("#ac-actividad button").forEach((b) => b.addEventListener("click", async () => {
      if (F.st.gen || b.dataset.v === ajuste("seguridad.actividad", "trabajo")) return;
      await guardarAjuste("seguridad.actividad", b.dataset.v);
      alCambiarActividad();
    }));
    document.querySelectorAll("#ac-enfoque button").forEach((b) => b.addEventListener("click", async () => {
      if (b.dataset.v === ajuste("seguridad.enfoque", "ofensivo")) return;
      await guardarAjuste("seguridad.enfoque", b.dataset.v);   // auditado (L-A4)
      s.abierta = null;
      pintarBarra();
      if (activa()) cambiarVista(s.vista === "leccion" || s.vista === "lab" ? s.vista : s.vista);
    }));
    document.querySelectorAll(".ac-nav-b").forEach((b) => b.addEventListener("click", () => cambiarVista(b.dataset.vista)));
    $("#ac-copi-sig").addEventListener("click", () => copiloto("siguiente"));
    $("#ac-copi-exp").addEventListener("click", () => copiloto("explicar"));
    $("#ac-copi-enviar").addEventListener("click", () => copiloto("chat"));
    $("#ac-copi-txt").addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); copiloto("chat"); } });
  }

  window.ForjaAcademia = {
    activa,
    pintarBarra: () => { if (F) pintarBarra(); },
    async mostrar(alCambiarActividad) {
      F = window.ForjaApp;
      enlazar(alCambiarActividad);
      pintarBarra();
      if (!activa()) return;
      const ult = parseInt(ajuste("academia.seccion", ""), 10);
      if (!s.sid && Number.isFinite(ult)) {
        try { s.sid = ult; s.sec = await F.api(`/academia/leccion/${ult}`); } catch { s.sid = null; s.sec = null; }
      }
      await cambiarVista(s.vista);
    },
    alCambiarSelector() { /* el tier/esfuerzo se leen al vuelo en cada petición */ },
    linea() {
      const et = modeloTxt() || "";
      return s.lab ? F.fmt("aca.linea", { modelo: et }) : F.t("aca.linea.sin_lab");
    },
  };
})();
