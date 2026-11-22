/* FORJA — Rama 8: Estudio de Apariencia (MOD-100, SCR-040, doc 20, FR-073).
   BTN-095 presets · BTN-096 color y acento (con contraste comprobado) · BTN-097 tipografía y densidad ·
   BTN-098 fondo/imagen · BTN-099 vista previa en vivo y aplicar. Acento por modo (opcional) y la única
   animación (desactivable). Mientras está abierto, toda la app se repinta en vivo; Cancelar lo deshace y Aplicar
   lo guarda en ui.* (PUT /ajustes, que vuelve a validar el contraste). */
(function () {
  "use strict";

  const A = () => window.ForjaApp;
  const $ = (sel, raiz = document) => raiz.querySelector(sel);
  const CLAVES = ["ui.tema", "ui.acento", "ui.base", "ui.fondo", "ui.acento_por_modo", "ui.tipografia",
    "ui.densidad", "ui.animacion", "ui.preset"];
  const MODOS = ["scripts", "seguridad", "tareas"];
  const st = { cat: null, e: null, guardado: null, previa: null, seq: 0, modoMaqueta: "scripts", t: null };
  const json = (v, def) => { if (v && typeof v === "object") return v; try { return v ? JSON.parse(v) : def; } catch { return def; } };
  const t = (k, v) => (v ? A().fmt(k, v) : A().t(k));
  const esc = (x) => A().esc(String(x ?? ""));

  // Estado editable (las claves JSON se guardan como texto, igual que en settings).
  function estadoDe(aj) {
    const e = {};
    for (const k of CLAVES) e[k] = aj[k] ?? "";
    e["ui.tema"] ||= "oscuro"; e["ui.acento"] ||= "naranja-forja"; e["ui.tipografia"] ||= "sistema";
    e["ui.densidad"] ||= "comoda"; e["ui.animacion"] ||= "1"; e["ui.fondo"] ||= '{"tipo":"liso"}';
    e["ui.acento_por_modo"] ||= "{}";
    return e;
  }
  const comoTexto = (v) => (v && typeof v === "object" ? JSON.stringify(v) : v || "");

  // ------------------------------------------------------------------ construir la pantalla
  function construir() {
    const cat = st.cat;
    const raiz = $("#scr-040");
    const acentos = Object.entries(cat.acentos).map(([k, v]) =>
      `<button type="button" role="radio" class="sw" data-acento="${k}" style="--sw:${v.oscuro}" title="${esc(t("estudio.acento." + k))}" aria-label="${esc(t("estudio.acento." + k))}"></button>`).join("");
    const presets = cat.presets.map((p) => {
      const pal = muestras(p.ajustes);
      return `<button type="button" class="es-preset" data-preset="${p.id}">` +
        `<span class="es-muestra" style="--m-bg:${pal.bg};--m-sf:${pal.surface};--m-tx:${pal.texto};--m-ac:${pal.acento}"><i></i><i></i><i></i></span>` +
        `<strong>${esc(p.nombre)}</strong><span>${esc(p.descripcion)}</span></button>`;
    }).join("");
    const seg = (id, ops, pref) => `<div class="seg seg-envuelve" id="${id}" role="radiogroup">` +
      ops.map((o) => `<button type="button" role="radio" data-v="${o}">${esc(t(`${pref}.${o}`))}</button>`).join("") + "</div>";
    raiz.innerHTML = `
      <div class="estudio" role="dialog" aria-modal="true" aria-labelledby="es-titulo">
        <header class="es-cab">
          <div><h2 id="es-titulo">${esc(t("estudio.titulo"))}</h2><p class="nota">${esc(t("estudio.sub"))}</p></div>
          <div class="es-cab-acc">
            <span class="es-estado" id="es-estado" aria-live="polite"></span>
            <button class="boton-txt" type="button" id="es-cancelar">${esc(t("estudio.cancelar"))}</button>
            <button class="boton" type="button" id="es-aplicar">${esc(t("estudio.aplicar"))}</button>
          </div>
        </header>
        <div class="es-cuerpo">
          <div class="es-controles">
            <section><h3>${esc(t("estudio.sec.presets"))}</h3><div class="es-presets">${presets}</div></section>
            <section><h3>${esc(t("estudio.sec.color"))}</h3>
              <div class="campo"><span class="etq">${esc(t("estudio.tema"))}</span>${seg("es-tema", cat.temas, "estudio.tema")}</div>
              <div class="campo"><span class="etq">${esc(t("estudio.acento"))}</span>
                <div class="es-acentos" id="es-acentos" role="radiogroup">${acentos}
                  <label class="es-propio" title="${esc(t("estudio.acento_propio"))}"><input type="color" id="es-acento-hex" value="#8f64e0"><span>${esc(t("estudio.propio"))}</span></label>
                </div></div>
              <div class="campo"><span class="etq">${esc(t("estudio.base"))}</span>${seg("es-base-modo", ["tema", "propios"], "estudio.base")}
                <div class="es-base" id="es-base">
                  ${["bg", "surface", "texto"].map((k) => `<label><input type="color" data-base="${k}"><span>${esc(t("estudio.base." + k))}</span></label>`).join("")}
                </div></div>
              <div class="es-contraste" id="es-contraste" aria-live="polite"></div>
            </section>
            <section><h3>${esc(t("estudio.sec.tipo"))}</h3>
              <div class="campo"><span class="etq">${esc(t("estudio.fuente"))}</span>
                <div class="seg seg-envuelve es-fuentes" id="es-fuente" role="radiogroup">${cat.fuentes.map((f) =>
                  `<button type="button" role="radio" data-v="${f}" data-muestra-fuente="${f}">${esc(t("estudio.fuente." + f))}</button>`).join("")}</div></div>
              <div class="campo"><span class="etq">${esc(t("estudio.densidad"))}</span>${seg("es-densidad", ["comoda", "compacta"], "estudio.densidad")}</div>
            </section>
            <section><h3>${esc(t("estudio.sec.fondo"))}</h3>
              ${seg("es-fondo", ["liso", "degradado", "imagen"], "estudio.fondo")}
              <div class="es-imagen" id="es-imagen">
                <button class="boton-txt peq" type="button" id="es-elegir-img">${esc(t("estudio.fondo.elegir"))}</button>
                <input type="file" id="es-img" accept="image/png,image/jpeg,image/webp,image/gif" hidden>
                <label class="es-op"><span>${esc(t("estudio.fondo.opacidad"))}</span>
                  <input type="range" id="es-op" min="${cat.opacidad.min * 100}" max="${cat.opacidad.max * 100}" step="1"><b id="es-op-v"></b></label>
                <p class="nota" id="es-img-nota"></p>
              </div>
            </section>
            <section><h3>${esc(t("estudio.sec.modo"))}</h3><p class="nota">${esc(t("estudio.modo.ayuda"))}</p>
              <div class="es-modos">${MODOS.map((m) => `<label class="es-modo"><input type="checkbox" data-modo-on="${m}">` +
                `<span>${esc(t("modo." + m))}</span><input type="color" data-modo-color="${m}" value="#d9483b"></label>`).join("")}</div>
            </section>
            <section><h3>${esc(t("estudio.sec.anim"))}</h3>
              <label class="check"><input type="checkbox" id="es-anim"><span>${esc(t("estudio.anim"))}</span></label>
            </section>
          </div>
          <div class="es-previa" aria-label="${esc(t("estudio.previa"))}">
            <div class="es-previa-cab"><span>${esc(t("estudio.previa"))}</span><span class="nota">${esc(t("estudio.previa_ayuda"))}</span></div>
            <div class="es-maqueta" id="es-maqueta"></div>
          </div>
        </div>
      </div>`;
    enlazar();
  }

  /* Colores para las muestras de los presets (sin pedirle nada al backend). */
  function muestras(aj) {
    const base = json(aj["ui.base"], null) || st.cat.bases[aj["ui.tema"] === "claro" ? "claro" : aj["ui.tema"] === "contraste" ? "contraste" : "oscuro"];
    const acento = st.cat.acentos[aj["ui.acento"]]?.[aj["ui.tema"] === "claro" ? "claro" : "oscuro"] || aj["ui.acento"];
    return { bg: base.bg, surface: base.surface, texto: base.texto, acento };
  }

  // La maqueta: los DOS selectores, las pestañas de modo y una conversación de ejemplo (doc 20).
  function maqueta() {
    const app = A();
    const codigo = window.ForjaMD.render("Aquí tienes el script:\n```python\nimport os  # lista los .py\nfor f in os.listdir('.'):\n    if f.endswith('.py'):\n        print(f, 42)\n```\nLo puedes **Comprobar** antes de usarlo.", app.t("code.copiar"));
    $("#es-maqueta").innerHTML = `
      <div class="mq-top">
        <span class="mq-marca"><svg><use href="#i-yunque"/></svg>FORJA</span>
        ${MODOS.map((m) => `<button type="button" class="mq-modo" data-mq-modo="${m}" aria-selected="${m === st.modoMaqueta}">${esc(app.t("modo." + m))}</button>`).join("")}
      </div>
      <div class="mq-chat">
        <div class="mq-user">${esc(t("estudio.mq.pregunta"))}</div>
        <div class="mq-ia cuerpo">${codigo}</div>
        <p class="mq-sec">${esc(t("estudio.mq.secundario"))}</p>
      </div>
      <div class="mq-dock">
        <div class="mq-comp"><span>${esc(app.t("compositor.placeholder"))}</span><b class="mq-enviar"><svg><use href="#i-enviar"/></svg></b></div>
        <div class="mq-sel">
          <span class="etq">${esc(app.t("tier.etiqueta"))}</span>
          <div class="seg"><button type="button" role="radio" aria-checked="true">${esc(app.t("tier.pequeno"))}</button><button type="button" role="radio" aria-checked="false">${esc(app.t("tier.grande"))}</button><button type="button" role="radio" aria-checked="false" disabled>${esc(app.t("tier.nube"))}</button></div>
          <span class="etq">${esc(app.t("esfuerzo.etiqueta"))}</span>
          <div class="seg"><button type="button" role="radio" aria-checked="false">${esc(app.t("esfuerzo.bajo"))}</button><button type="button" role="radio" aria-checked="true">${esc(app.t("esfuerzo.medio"))}</button><button type="button" role="radio" aria-checked="false">${esc(app.t("esfuerzo.extra"))}</button></div>
        </div>
      </div>`;
    $("#es-maqueta").querySelectorAll("[data-mq-modo]").forEach((b) => b.addEventListener("click", () => {
      st.modoMaqueta = b.dataset.mqModo; maqueta(); pintarMaquetaModo();
    }));
    pintarMaquetaModo();
  }
  /* El acento por modo se ve en la maqueta al pulsar su pestaña (sin cambiar el modo real). */
  function pintarMaquetaModo() {
    const el = $("#es-maqueta");
    if (el && st.previa) A().pintarPaleta(el, st.modoMaqueta, { ...st.previa, propios: false });
  }

  // ------------------------------------------------------------------ estado → controles
  const marcar = (id, v) => document.querySelectorAll(`#${id} [data-v]`).forEach((b) => b.setAttribute("aria-checked", String(b.dataset.v === v)));
  function pintarControles() {
    const e = st.e;
    marcar("es-tema", e["ui.tema"]);
    const hex = /^#/.test(e["ui.acento"]);
    document.querySelectorAll("#es-acentos [data-acento]").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.acento === e["ui.acento"])));
    $(".es-propio").classList.toggle("activo", hex);
    if (hex) $("#es-acento-hex").value = e["ui.acento"];
    const base = json(e["ui.base"], null);
    marcar("es-base-modo", base ? "propios" : "tema");
    $("#es-base").hidden = !base;
    const b = base || st.previa?.variables && { bg: st.previa.variables["--bg"], surface: st.previa.variables["--surface"], texto: st.previa.variables["--text-strong"] } || st.cat.bases.oscuro;
    document.querySelectorAll("#es-base [data-base]").forEach((i) => { i.value = b[i.dataset.base] || "#000000"; });
    marcar("es-fuente", e["ui.tipografia"]);
    marcar("es-densidad", e["ui.densidad"]);
    const f = json(e["ui.fondo"], { tipo: "liso" });
    marcar("es-fondo", f.tipo);
    $("#es-imagen").hidden = f.tipo !== "imagen";
    const op = Math.round((f.opacidad ?? 0.2) * 100);
    $("#es-op").value = op; $("#es-op-v").textContent = `${op} %`;
    $("#es-img-nota").textContent = f.archivo ? t("estudio.fondo.cargada") : t("estudio.fondo.ninguna");
    const pm = json(e["ui.acento_por_modo"], {}) || {};
    for (const m of MODOS) {
      $(`[data-modo-on="${m}"]`).checked = !!pm[m];
      const c = $(`[data-modo-color="${m}"]`);
      c.disabled = !pm[m];
      if (pm[m] && /^#/.test(pm[m])) c.value = pm[m];
    }
    $("#es-anim").checked = e["ui.animacion"] !== "0";
    document.querySelectorAll(".es-preset").forEach((p) => p.classList.toggle("activo", p.dataset.preset === e["ui.preset"]));
  }

  function pintarContraste() {
    const p = st.previa;
    const cont = $("#es-contraste");
    if (!p) { cont.innerHTML = ""; return; }
    const filas = p.contrastes.map((c) =>
      `<li class="${c.ok ? "ok" : "mal"}"><span>${esc(t("estudio.par." + c.par.replace("/", "_")))}${c.donde ? ` · ${esc(A().t("modo." + c.donde))}` : ""}</span>` +
      `<b>${c.ratio.toFixed(2)}:1</b><small>${esc(t("estudio.minimo", { n: c.minimo }))}</small><i>${c.ok ? "✓" : "✗"}</i></li>`).join("");
    const malos = p.problemas.length;
    cont.innerHTML = `<p class="es-contraste-cab ${malos ? "mal" : "ok"}">${esc(malos ? t("estudio.contraste_mal", { n: malos }) : t("estudio.contraste_ok"))}</p><ul>${filas}</ul>`;
    $("#es-aplicar").disabled = malos > 0;
    $("#es-aplicar").title = malos ? t("estudio.no_aplicar") : "";
  }

  // ------------------------------------------------------------------ vista previa en vivo (BTN-099)
  function cambiar(parcial, { preset = false } = {}) {
    Object.assign(st.e, parcial);
    if (!preset && !("ui.preset" in parcial)) st.e["ui.preset"] = "";
    pintarControles();
    clearTimeout(st.t);
    st.t = setTimeout(previa, 60);          // los selectores de color mandan muchos eventos seguidos
  }
  async function previa() {
    const app = A();
    const seq = ++st.seq;
    const todo = { ...app.ajustes, ...st.e };
    app.aplicarApariencia(todo);           // toda la app (y la maqueta) se repinta al momento
    let p = null;
    try { p = await app.calcularPaleta(todo); } catch (x) { $("#es-estado").textContent = x.message; }
    if (seq !== st.seq) return;
    st.previa = p;
    pintarContraste();
    pintarControles();
    pintarMaquetaModo();
  }

  async function aplicar() {
    const app = A();
    const cuerpo = {};
    for (const k of CLAVES) cuerpo[k] = comoTexto(st.e[k]);
    const b = $("#es-aplicar");
    b.disabled = true;
    try {
      const r = await app.api("/ajustes", { method: "PUT", body: cuerpo });
      app.ajustes = r.ajustes;
      window.ForjaApp.ajustes = r.ajustes;
      st.guardado = estadoDe(r.ajustes);
      app.aplicarApariencia(r.ajustes);
      $("#es-estado").textContent = t("estudio.aplicado");
      $("#es-estado").className = "es-estado ok";
      setTimeout(cerrar, 500);
    } catch (x) {
      $("#es-estado").textContent = x.message;
      $("#es-estado").className = "es-estado mal";
      b.disabled = false;
    }
  }

  function cancelar() {
    A().aplicarApariencia(A().ajustes);      // deshace la vista previa
    cerrar();
  }
  function cerrar() { $("#scr-040").hidden = true; document.removeEventListener("keydown", teclas); }
  const teclas = (ev) => { if (ev.key === "Escape") cancelar(); };

  // ------------------------------------------------------------------ eventos
  function enlazar() {
    $("#es-cancelar").addEventListener("click", cancelar);
    $("#es-aplicar").addEventListener("click", aplicar);
    document.querySelectorAll(".es-preset").forEach((b) => b.addEventListener("click", () => {     // BTN-095
      const p = st.cat.presets.find((x) => x.id === b.dataset.preset);
      const aj = Object.fromEntries(Object.entries(p.ajustes).map(([k, v]) => [k, comoTexto(v)]));
      cambiar({ ...aj, "ui.preset": p.id }, { preset: true });
    }));
    const segs = { "es-tema": "ui.tema", "es-fuente": "ui.tipografia", "es-densidad": "ui.densidad" };
    for (const [id, k] of Object.entries(segs)) {
      document.querySelectorAll(`#${id} [data-v]`).forEach((b) => b.addEventListener("click", () => cambiar({ [k]: b.dataset.v })));
    }
    // BTN-096 color y acento
    document.querySelectorAll("#es-acentos [data-acento]").forEach((b) => b.addEventListener("click", () => cambiar({ "ui.acento": b.dataset.acento })));
    $("#es-acento-hex").addEventListener("input", (ev) => cambiar({ "ui.acento": ev.target.value }));
    document.querySelectorAll("#es-base-modo [data-v]").forEach((b) => b.addEventListener("click", () => {
      if (b.dataset.v === "tema") return cambiar({ "ui.base": "" });
      const v = st.previa?.variables || {};
      cambiar({ "ui.base": JSON.stringify({ bg: v["--bg"] || "#0d0d0e", surface: v["--surface"] || "#151517", texto: v["--text-strong"] || "#f1f1ee" }) });
    }));
    document.querySelectorAll("#es-base [data-base]").forEach((i) => i.addEventListener("input", () => {
      const b = json(st.e["ui.base"], {}) || {};
      b[i.dataset.base] = i.value;
      cambiar({ "ui.base": JSON.stringify(b) });
    }));
    // BTN-098 fondo
    const fondo = () => json(st.e["ui.fondo"], { tipo: "liso" });
    document.querySelectorAll("#es-fondo [data-v]").forEach((b) => b.addEventListener("click", () => {
      const f = fondo();
      if (b.dataset.v === "imagen" && !f.archivo) { cambiar({ "ui.fondo": JSON.stringify({ ...f, tipo: "liso" }) }); $("#es-imagen").hidden = false; marcar("es-fondo", "imagen"); $("#es-img").click(); return; }
      cambiar({ "ui.fondo": JSON.stringify({ ...f, tipo: b.dataset.v }) });
    }));
    $("#es-elegir-img").addEventListener("click", () => $("#es-img").click());
    $("#es-img").addEventListener("change", async (ev) => {
      const archivo = ev.target.files?.[0];
      ev.target.value = "";
      if (!archivo) return;
      $("#es-img-nota").textContent = t("estudio.fondo.subiendo");
      try {
        const r = await fetch("/apariencia/fondo", { method: "POST", headers: { "X-Forja-Token": window.FORJA_TOKEN }, body: archivo });
        const d = await r.json();
        if (!r.ok) throw new Error(d.error?.mensaje || r.status);
        cambiar({ "ui.fondo": JSON.stringify({ tipo: "imagen", archivo: d.archivo, opacidad: (fondo().opacidad ?? 0.2) }) });
      } catch (x) { $("#es-img-nota").textContent = x.message; }
    });
    $("#es-op").addEventListener("input", (ev) => {
      const f = fondo();
      $("#es-op-v").textContent = `${ev.target.value} %`;
      if (f.archivo) cambiar({ "ui.fondo": JSON.stringify({ ...f, opacidad: Number(ev.target.value) / 100 }) });
    });
    // Acento por modo (opcional)
    const porModo = () => {
      const pm = {};
      for (const m of MODOS) if ($(`[data-modo-on="${m}"]`).checked) pm[m] = $(`[data-modo-color="${m}"]`).value;
      cambiar({ "ui.acento_por_modo": JSON.stringify(pm) });
    };
    document.querySelectorAll("[data-modo-on], [data-modo-color]").forEach((i) => i.addEventListener("input", porModo));
    $("#es-anim").addEventListener("change", (ev) => cambiar({ "ui.animacion": ev.target.checked ? "1" : "0" }));
  }

  async function abrir() {
    const app = A();
    if (!st.cat) {
      st.cat = await app.api("/apariencia");
      construir();
    }
    const { ajustes } = await app.api("/ajustes");
    app.ajustes = ajustes;
    window.ForjaApp.ajustes = ajustes;
    st.guardado = estadoDe(ajustes);
    st.e = { ...st.guardado };
    st.modoMaqueta = app.st.modo === "tareas" || app.st.modo === "seguridad" ? app.st.modo : "scripts";
    $("#es-estado").textContent = ""; $("#es-estado").className = "es-estado";
    $("#scr-040").hidden = false;
    maqueta();
    pintarControles();
    await previa();
    document.addEventListener("keydown", teclas);
    $("#es-cancelar").focus();
  }

  window.ForjaEstudio = { abrir, cerrar, estado: () => st.e, previa: () => st.previa };
})();
