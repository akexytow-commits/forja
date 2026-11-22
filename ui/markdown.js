/* Markdown mínimo y seguro (escapa todo HTML). Sin dependencias: la app funciona offline.
   Soporta: bloques ``` (también sin cerrar, durante el streaming), `código`, **negrita**, *cursiva*,
   encabezados, listas, citas y enlaces (mostrados como texto: la ventana no debe navegar fuera). */
(function () {
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  function inline(s) {
    const partes = s.split(/(`[^`\n]+`)/g);
    return partes.map((p) => {
      if (p.length > 1 && p.startsWith("`") && p.endsWith("`")) return `<code>${esc(p.slice(1, -1))}</code>`;
      let t = esc(p);
      t = t.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
      t = t.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, "$1<em>$2</em>");
      t = t.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, '<span class="enlace" title="$2">$1</span>');
      return t;
    }).join("");
  }

  function bloquesTexto(src) {
    const lineas = src.split("\n");
    const out = [];
    let lista = null; // {tipo:'ul'|'ol', items:[]}
    let parrafo = [];
    const cerrarParrafo = () => { if (parrafo.length) { out.push(`<p>${inline(parrafo.join("\n")).replace(/\n/g, "<br>")}</p>`); parrafo = []; } };
    const cerrarLista = () => { if (lista) { out.push(`<${lista.tipo}>${lista.items.map((i) => `<li>${inline(i)}</li>`).join("")}</${lista.tipo}>`); lista = null; } };
    for (const l of lineas) {
      let m;
      if (!l.trim()) { cerrarParrafo(); cerrarLista(); continue; }
      if ((m = l.match(/^(#{1,4})\s+(.*)$/))) { cerrarParrafo(); cerrarLista(); const n = Math.min(m[1].length + 2, 6); out.push(`<h${n}>${inline(m[2])}</h${n}>`); continue; }
      if ((m = l.match(/^\s*[-*+]\s+(.*)$/))) { cerrarParrafo(); if (!lista || lista.tipo !== "ul") { cerrarLista(); lista = { tipo: "ul", items: [] }; } lista.items.push(m[1]); continue; }
      if ((m = l.match(/^\s*\d+[.)]\s+(.*)$/))) { cerrarParrafo(); if (!lista || lista.tipo !== "ol") { cerrarLista(); lista = { tipo: "ol", items: [] }; } lista.items.push(m[1]); continue; }
      if ((m = l.match(/^>\s?(.*)$/))) { cerrarParrafo(); cerrarLista(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); continue; }
      if (/^\s*(---|\*\*\*)\s*$/.test(l)) { cerrarParrafo(); cerrarLista(); out.push("<hr>"); continue; }
      if (lista) { lista.items[lista.items.length - 1] += " " + l.trim(); continue; }
      parrafo.push(l);
    }
    cerrarParrafo(); cerrarLista();
    return out.join("");
  }

  /* SC2 — resaltado mínimo de sintaxis (sin dependencias). Los colores salen de variables CSS --tk-*, que
     cambian con ui.codigo_tema (acorde / oscuro / alto-contraste). Comentarios según el lenguaje. */
  const HASH = /^(py|python|sh|bash|zsh|shell|ps1|powershell|pwsh|yaml|yml|toml|ini|conf|rb|ruby|perl|r|makefile|dockerfile|nmap)$/i;
  const SLASH = /^(c|h|cpp|c\+\+|cc|hpp|cs|csharp|java|js|javascript|ts|typescript|jsx|tsx|go|rust|rs|kotlin|kt|swift|php|scala|dart|json5|fam)$/i;
  const DASH = /^(sql|lua|haskell|hs)$/i;
  const KW = new Set(("if else elif for while do return def class import from as with try except finally raise " +
    "in not and or is None True False null true false function const let var new this self async await yield " +
    "lambda pass break continue switch case default struct enum typedef static void int char float double long " +
    "unsigned bool include define public private protected fn mut impl use pub package func go defer select " +
    "echo then fi done esac local export param foreach begin end SELECT FROM WHERE INSERT UPDATE DELETE JOIN").split(" "));

  function resaltar(codigo, lang) {
    const l = (lang || "").toLowerCase();
    const com = HASH.test(l) ? /#[^\n]*/ : SLASH.test(l) ? /\/\/[^\n]*|\/\*[\s\S]*?\*\// : DASH.test(l) ? /--[^\n]*/ : /(?!)/;
    const str = /"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`/;
    const num = /\b0x[0-9a-fA-F]+\b|\b\d+(?:\.\d+)?\b/;
    const id = /[A-Za-z_]\w*/;
    const re = new RegExp([com, str, num, id].map((r) => `(${r.source})`).join("|"), "g");
    let out = "", ultimo = 0, m;
    while ((m = re.exec(codigo)) !== null) {
      out += esc(codigo.slice(ultimo, m.index));
      const [txt, c, str, num, id] = m;
      if (c) out += `<span class="tk-c">${esc(txt)}</span>`;
      else if (str) out += `<span class="tk-s">${esc(txt)}</span>`;
      else if (num) out += `<span class="tk-n">${esc(txt)}</span>`;
      else if (id && KW.has(id)) out += `<span class="tk-k">${esc(txt)}</span>`;
      else out += esc(txt);
      ultimo = re.lastIndex;
    }
    return out + esc(codigo.slice(ultimo));
  }

  /* Nombre de archivo sugerido para un bloque: la ruta que el modelo pone justo antes (p. ej. `src/main.py`). */
  function nombreSugerido(previo) {
    const lineas = previo.replace(/\s+$/, "").split("\n");
    const ultima = lineas[lineas.length - 1] || "";
    const re = /(?:^|[\s`*(])((?:[\w.-]+\/)*[\w-][\w.-]*\.[A-Za-z][A-Za-z0-9]{0,7})(?=$|[\s`*):,])/g;
    let m, nombre = "";
    while ((m = re.exec(ultima)) !== null) nombre = m[1];
    return nombre;
  }

  /* etiquetaGuardar (opcional): añade "Guardar" (BTN-031) a cada bloque ya cerrado. */
  function render(src, etiquetaCopiar, etiquetaGuardar) {
    const out = [];
    const re = /```([\w+#.-]*)[^\n]*\n([\s\S]*?)(?:```|$)/g;
    let ultimo = 0, m;
    while ((m = re.exec(src)) !== null) {
      if (m.index > ultimo) out.push(bloquesTexto(src.slice(ultimo, m.index)));
      const lang = m[1] || "código";
      const codigo = m[2].replace(/\n$/, "");
      const cerrado = /```\s*$/.test(m[0]) && m[0].length > 6;
      const guardar = etiquetaGuardar && cerrado
        ? `<button class="code-guardar" type="button" data-nombre="${esc(nombreSugerido(src.slice(0, m.index)))}" data-lang="${esc(m[1] || "")}">${esc(etiquetaGuardar)}</button>`
        : "";
      out.push(
        `<div class="code"><div class="code-head"><span class="code-lang">${esc(lang)}</span>` +
        `<span class="code-acc">${guardar}<button class="code-copiar" type="button">${esc(etiquetaCopiar)}</button></span></div>` +
        `<pre><code>${resaltar(codigo, m[1])}</code></pre></div>`
      );
      ultimo = re.lastIndex;
      if (m[0].length === 0) break;
    }
    if (ultimo < src.length) out.push(bloquesTexto(src.slice(ultimo)));
    return out.join("");
  }

  /* Los modelos de código sin thinking razonan en <plan>…</plan> con esfuerzo extra (04-...md). */
  function separarPlan(src) {
    const m = src.match(/^\s*<plan>([\s\S]*?)(<\/plan>|$)/);
    if (!m) return { plan: "", resto: src, planAbierto: false };
    return { plan: m[1].trim(), resto: src.slice(m[0].length).replace(/^\s+/, ""), planAbierto: m[2] !== "</plan>" };
  }

  window.ForjaMD = { render, separarPlan, esc, nombreSugerido, resaltar };
})();
