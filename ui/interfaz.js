/* FORJA — Rama 6: Personalización de interfaces (13-protocolo-personalizacion.md).

   Una clave ui.* por cada pregunta PREGUNTAR del Protocolo. Este módulo:
   - aplica las elecciones en vivo (atributos data-* en <html> + repintado de cada pantalla), sin reiniciar;
   - construye la pestaña «Interfaces» de Ajustes (SCR-007) a partir de la tabla PANTALLAS, para re-pulir
     cualquier pantalla más tarde sin perder lo guardado (todo vive en settings).
   Lo FIJADO del doc 13 (dos selectores siempre visibles, gate obligatorio, explicación del escalado…) no
   depende de estas claves: solo cambia la forma. */
(function () {
  "use strict";

  // Pantalla → preguntas. `attr` = atributo data-* de <html> que lee el CSS (rama6.css) y los módulos.
  const PANTALLAS = [
    { id: "shell", claves: [
      { k: "ui.pestanas", attr: "pestanas", def: "icono+texto", ops: ["icono+texto", "texto", "icono"] },          // S1
      { k: "ui.esfuerzo_control", attr: "esfuerzo", def: "segmentos", ops: ["segmentos", "deslizador"] },          // S2
      { k: "ui.mostrar_modelo", attr: "modelo", def: "tier+tooltip", ops: ["tier+tooltip", "tier+modelo"] },     // S3
    ] },
    { id: "scripts", claves: [
      { k: "ui.proyectos", attr: "proyectos", def: "desplegable", ops: ["desplegable", "fijo"] },                 // SC1
      { k: "ui.codigo_tema", attr: "codigo", def: "acorde", ops: ["acorde", "oscuro", "alto-contraste"] },        // SC2
    ] },
    { id: "seguridad", claves: [
      { k: "ui.gate", attr: "gate", def: "pantalla_completa", ops: ["pantalla_completa", "asistente"] },          // SG1
      { k: "ui.hallazgos", attr: "hallazgos", def: "tabla", ops: ["tabla", "tarjetas"] },                         // SG2
      { k: "ui.informe_plantilla", attr: "informe", def: "hackerone", ops: ["hackerone", "bugcrowd", "breve", "personalizada"] }, // SG3
    ] },
    { id: "tareas", claves: [
      { k: "ui.tareas_vista", attr: "tareasVista", def: "tablero", ops: ["tablero", "lista"] },                  // ST1
      { k: "ui.tareas_carga", attr: "tareasCarga", def: "1", ops: ["1", "0"] },                                   // ST2
    ] },
    { id: "avisos", claves: [
      { k: "ui.aviso_escalado", attr: "aviso", def: "modal-nube+banner-justo", ops: ["modal-nube+banner-justo", "modal", "banner"] }, // SE1
      { k: "ui.ajustes", attr: "ajustes", def: "pestanas", ops: ["pestanas", "pagina"] },                         // SA1
    ] },
  ];
  const CLAVES = PANTALLAS.flatMap((p) => p.claves);
  const idSeg = (k) => "aj-if-" + k.slice(3).replace(/[^a-z0-9]/gi, "-");

  const A = () => window.ForjaApp;
  const $ = (sel) => document.querySelector(sel);

  /* Aplica las claves de interfaz: data-* en <html> y repintado de lo que no es solo CSS. */
  function aplicar(a) {
    const r = document.documentElement;
    for (const c of CLAVES) {
      const v = a[c.k];
      r.dataset[c.attr] = c.ops.includes(v) ? v : c.def;
    }
    window.ForjaProyectos?.aplicarModo?.();           // SC1: mueve el panel (desplegable ↔ fijo)
    window.ForjaSeguridad?.alCambiarInterfaz?.();     // SG1/SG2
  }

  /* Pestaña «Interfaces» de Ajustes, generada desde PANTALLAS. */
  let construido = false;
  function construir(onCambio) {
    if (construido) return;
    construido = true;
    const t = A().t;
    const cont = $("#aj-interfaz");
    for (const p of PANTALLAS) {
      const g = document.createElement("fieldset");
      g.className = "aj-grupo";
      g.innerHTML = `<legend>${A().esc(t("if." + p.id))}</legend>`;
      for (const c of p.claves) {
        const campo = document.createElement("div");
        campo.className = "campo";
        const nombre = c.k.slice(3);
        campo.innerHTML = `<span class="etq">${A().esc(t("if." + nombre))}</span>` +
          `<div class="seg seg-envuelve" id="${idSeg(c.k)}" role="radiogroup" aria-label="${A().esc(t("if." + nombre))}">` +
          c.ops.map((o) => `<button type="button" role="radio" data-v="${o}" title="${A().esc(t(`if.${nombre}.${o}.ayuda`))}">${A().esc(t(`if.${nombre}.${o}`))}</button>`).join("") +
          `</div>`;
        g.append(campo);
        if (c.k === "ui.informe_plantilla") g.append(bloqueInforme());
      }
      cont.append(g);
    }
    cont.querySelectorAll(".seg [data-v]").forEach((b) => b.addEventListener("click", () => {
      const seg = b.parentElement;
      seg.querySelectorAll("[data-v]").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
      if (seg.id === idSeg("ui.informe_plantilla")) pintarInforme();
      onCambio();
    }));
  }

  // SG3 "editable": la estructura propia del informe, partiendo de la plantilla elegida.
  let plantillas = null;
  function bloqueInforme() {
    const t = A().t;
    const d = document.createElement("div");
    d.className = "campo aj-informe";
    d.innerHTML = `<label for="aj-if-estructura">${A().esc(t("if.informe_estructura"))}</label>` +
      `<textarea id="aj-if-estructura" rows="7" spellcheck="false" maxlength="4000"></textarea>` +
      `<div class="aj-informe-pie"><span class="nota" id="aj-if-estructura-nota"></span>` +
      `<button type="button" class="boton-txt peq" id="aj-if-partir">${A().esc(t("if.informe_partir"))}</button></div>` +
      `<pre class="aj-informe-previa" id="aj-if-previa"></pre>`;
    d.querySelector("#aj-if-partir").addEventListener("click", () => {
      $("#aj-if-estructura").value = plantillas?.plantillas?.hackerone?.estructura || "";
    });
    return d;
  }
  function pintarInforme() {
    const elegida = leerSeg("ui.informe_plantilla");
    const propia = elegida === "personalizada";
    $("#aj-if-estructura").closest(".aj-informe").classList.toggle("propia", propia);
    $("#aj-if-estructura").hidden = !propia;
    $("#aj-if-partir").hidden = !propia;
    $("#aj-if-estructura-nota").textContent = A().t(propia ? "if.informe_propia_nota" : "if.informe_serie_nota");
    $("#aj-if-previa").hidden = propia;
    $("#aj-if-previa").textContent = plantillas?.plantillas?.[elegida]?.estructura || "";
  }

  const leerSeg = (k) => document.querySelector(`#${idSeg(k)} [aria-checked=true]`)?.dataset.v
    || CLAVES.find((c) => c.k === k).def;

  /* Rellena la pestaña con lo guardado. */
  async function pintar(ajustes) {
    for (const c of CLAVES) {
      const v = c.ops.includes(ajustes[c.k]) ? ajustes[c.k] : c.def;
      document.querySelectorAll(`#${idSeg(c.k)} [data-v]`).forEach((b) => b.setAttribute("aria-checked", String(b.dataset.v === v)));
    }
    $("#aj-if-estructura").value = ajustes["ui.informe_estructura"] || "";
    try { plantillas = await A().api("/seguridad/plantillas-informe"); } catch { plantillas = null; }
    pintarInforme();
  }

  /* Lo que hay elegido ahora en la pestaña (para la vista previa y para Guardar). */
  function leer() {
    const out = {};
    for (const c of CLAVES) out[c.k] = leerSeg(c.k);
    out["ui.informe_estructura"] = $("#aj-if-estructura")?.value.trim() || "";
    return out;
  }

  window.ForjaInterfaz = { aplicar, construir, pintar, leer, PANTALLAS, CLAVES };
})();
