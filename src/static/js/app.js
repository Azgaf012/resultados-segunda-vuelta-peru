"use strict";

const fmtMiles = new Intl.NumberFormat("es-PE");
let cacheRegiones = [];

function fmtPct(valor) {
  return `${Number(valor).toFixed(3)}%`;
}

function fmtPct1(valor) {
  return `${Number(valor).toFixed(1)}%`;
}

function fmtFecha(iso) {
  if (!iso) return "sin datos";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-PE", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

async function obtenerJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Error ${resp.status} al consultar ${url}`);
  return resp.json();
}

function urlEstatica(ruta) {
  return `/static/${ruta}`;
}

// Colores identificativos por agrupación (según su logo).
const PARTIDOS = {
  8: { color: "#ed7d31", rgb: "237, 125, 49" }, // Fuerza Popular · naranja
  10: { color: "#22a05a", rgb: "34, 160, 90" }, // Juntos por el Perú · verde
};
const PARTIDO_DEFECTO = { color: "#64748b", rgb: "100, 116, 139" };

function colorPartido(codigo) {
  return PARTIDOS[codigo] || PARTIDO_DEFECTO;
}

function renderMetrics(contenedor, totales) {
  if (!totales) {
    contenedor.innerHTML = "";
    return;
  }
  const items = [
    { label: "Actas contabilizadas", valor: `${Number(totales.actas_contabilizadas).toFixed(3)}%` },
    { label: "Participación", valor: `${Number(totales.participacion).toFixed(3)}%` },
    { label: "Votos válidos", valor: fmtMiles.format(totales.votos_validos) },
    { label: "Votos emitidos", valor: fmtMiles.format(totales.votos_emitidos) },
  ];
  contenedor.innerHTML = items
    .map(
      (m) => `
      <div class="metric">
        <div class="metric__label">${m.label}</div>
        <div class="metric__value">${m.valor}</div>
      </div>`
    )
    .join("");
}

// Tarjeta detallada de candidato (sección general).
function renderCandidatosGeneral(contenedor, participantes) {
  if (!participantes || participantes.length === 0) {
    contenedor.innerHTML =
      '<p class="placeholder">Aún no hay datos para este ámbito.</p>';
    return;
  }
  const maxPct = Math.max(...participantes.map((p) => p.pct_validos), 1);
  contenedor.innerHTML = participantes
    .map((p, i) => {
      const lider = i === 0 ? "lider" : "";
      const color = colorPartido(p.codigo).color;
      return `
      <div class="candidato ${lider}">
        <img class="candidato__foto" src="${urlEstatica(p.foto)}"
             alt="${p.candidato}" onerror="this.style.visibility='hidden'" />
        <div class="candidato__info">
          <div class="candidato__top">
            <div class="candidato__nombre">
              ${p.candidato}
              <span class="candidato__partido">
                <img class="candidato__logo" src="${urlEstatica(p.logo)}"
                     alt="" onerror="this.style.display='none'" />
                ${p.agrupacion}
              </span>
            </div>
            <div class="candidato__pct" style="color:${color}">${fmtPct(p.pct_validos)}</div>
          </div>
          <div class="barra">
            <div class="barra__fill" style="width:0;background:${color}"></div>
          </div>
          <div class="candidato__votos">${fmtMiles.format(p.votos)} votos válidos</div>
        </div>
      </div>`;
    })
    .join("");

  requestAnimationFrame(() => {
    const fills = contenedor.querySelectorAll(".barra__fill");
    participantes.forEach((p, i) => {
      if (fills[i]) fills[i].style.width = `${(p.pct_validos / maxPct) * 100}%`;
    });
  });
}

// Resumen agregado por regiones.
function renderResumen(data) {
  const cont = document.getElementById("resumen");
  if (!data || !data.candidatos || data.candidatos.length === 0) {
    cont.innerHTML =
      '<p class="placeholder">Aún no hay datos de regiones.</p>';
    return;
  }

  // Barra comparativa de regiones ganadas.
  const total = data.total_regiones || 1;
  const segmentos = data.candidatos
    .map((c) => {
      const color = colorPartido(c.codigo).color;
      const ancho = (c.regiones_ganadas / total) * 100;
      return `<div class="reparto__seg" style="width:${ancho}%;background:${color}"
                   title="${c.agrupacion}: ${c.regiones_ganadas}"></div>`;
    })
    .join("");

  // Tarjetas por candidato (sin foto, con color y logo).
  const tarjetas = data.candidatos
    .map((c, i) => {
      const color = colorPartido(c.codigo).color;
      const clase = i === 0 ? "resumen-cand--top" : "";
      const bastion = c.bastion
        ? `${c.bastion.nombre} · ${fmtPct1(c.bastion.pct)}`
        : "—";
      return `
      <div class="resumen-cand ${clase}" style="--cp:${color}">
        <div class="resumen-cand__cab">
          <img class="resumen-cand__logo" src="${urlEstatica(c.logo)}"
               alt="" onerror="this.style.display='none'" />
          <span class="resumen-cand__partido">${c.agrupacion}</span>
        </div>
        <div class="resumen-cand__num" style="color:${color}">
          ${c.regiones_ganadas}
          <span class="resumen-cand__num-sub">/ ${total} regiones</span>
        </div>
        <div class="resumen-cand__filas">
          <div class="resumen-cand__fila">
            <span>Votos (regional)</span>
            <strong>${fmtMiles.format(c.votos)}</strong>
          </div>
          <div class="resumen-cand__fila">
            <span>% del total</span>
            <strong style="color:${color}">${fmtPct1(c.pct_votos)}</strong>
          </div>
          <div class="resumen-cand__fila">
            <span>Bastión</span>
            <strong>${bastion}</strong>
          </div>
        </div>
      </div>`;
    })
    .join("");

  // Datos globales destacados.
  const dato = (label, valor, sub, color) => `
    <div class="resumen-dato">
      <div class="resumen-dato__label">${label}</div>
      <div class="resumen-dato__valor"${color ? ` style="color:${color}"` : ""}>${valor}</div>
      <div class="resumen-dato__sub">${sub || ""}</div>
    </div>`;

  const extras = [];
  if (data.mas_holgada) {
    extras.push(
      dato(
        "Mayor ventaja",
        data.mas_holgada.nombre,
        `${data.mas_holgada.agrupacion} · +${fmtPct1(data.mas_holgada.diferencia)}`,
        colorPartido(data.mas_holgada.codigo).color
      )
    );
  }
  if (data.mas_ajustada) {
    extras.push(
      dato(
        "Más reñida",
        data.mas_ajustada.nombre,
        `${data.mas_ajustada.agrupacion} · +${fmtPct1(data.mas_ajustada.diferencia)}`,
        colorPartido(data.mas_ajustada.codigo).color
      )
    );
  }
  extras.push(
    dato(
      "Ventaja promedio",
      `+${fmtPct1(data.ventaja_promedio)}`,
      "del ganador por región"
    )
  );
  if (data.mayor_participacion) {
    extras.push(
      dato(
        "Mayor participación",
        data.mayor_participacion.nombre,
        `${fmtPct1(data.mayor_participacion.participacion)} de asistencia`
      )
    );
  }

  cont.innerHTML = `
    <div class="reparto" title="Reparto de regiones">${segmentos}</div>
    <div class="resumen-cands">${tarjetas}</div>
    <div class="resumen-datos">${extras.join("")}</div>`;
}

// Tarjeta compacta de una región para el grid.
function tarjetaRegion(region) {
  const p = region.participantes || [];
  if (p.length === 0) {
    return `
      <div class="region">
        <div class="region__head"><span class="region__nombre">${region.nombre}</span></div>
        <p class="placeholder">Sin datos</p>
      </div>`;
  }
  const lider = p[0];
  const cgan = colorPartido(lider.codigo);
  const actas = region.totales
    ? `${Number(region.totales.actas_contabilizadas).toFixed(0)}%`
    : "";

  // Donut con la proporción de votos válidos entre los participantes.
  const totalPct = p.reduce((s, c) => s + c.pct_validos, 0) || 1;
  let acc = 0;
  const segmentos = p
    .map((c) => {
      const ini = (acc / totalPct) * 360;
      acc += c.pct_validos;
      const fin = (acc / totalPct) * 360;
      return `${colorPartido(c.codigo).color} ${ini}deg ${fin}deg`;
    })
    .join(", ");

  const leyenda = p
    .map((c, i) => {
      const color = colorPartido(c.codigo).color;
      const claseLider = i === 0 ? "region-cand--lider" : "";
      return `
      <span class="region-cand ${claseLider}" style="color:${color}">
        ${fmtPct1(c.pct_validos)}
      </span>`;
    })
    .join("");

  return `
    <div class="region" data-ubigeo="${region.ubigeo}"
         style="--cp:${cgan.color}; background:
           linear-gradient(160deg, rgba(${cgan.rgb}, 0.16), rgba(${cgan.rgb}, 0.04));
           border-color: rgba(${cgan.rgb}, 0.55)">
      <div class="region__head">
        <span class="region__nombre">${region.nombre}</span>
        <span class="region__actas" title="Porcentaje de actas contabilizadas">${actas}</span>
      </div>
      <div class="region__cuerpo">
        <div class="donut" style="background: conic-gradient(${segmentos})">
          <div class="donut__centro"></div>
        </div>
        <div class="region__leyenda">${leyenda}</div>
      </div>
    </div>`;
}

function tooltipRegion(region) {
  const t = region.totales;
  const filasCand = (region.participantes || [])
    .map((c) => {
      const color = colorPartido(c.codigo).color;
      return `
      <div class="tt-cand">
        <span class="tt-cand__punto" style="background:${color}"></span>
        <img class="tt-cand__logo" src="${urlEstatica(c.logo)}"
             alt="" onerror="this.style.display='none'" />
        <span class="tt-cand__nombre">${c.agrupacion}</span>
        <span class="tt-cand__pct" style="color:${color}">${fmtPct1(c.pct_validos)}</span>
        <span class="tt-cand__votos">${fmtMiles.format(c.votos)}</span>
      </div>`;
    })
    .join("");

  const datos = t
    ? `
      <div class="tt-datos">
        <div><span>Actas contabilizadas</span><strong>${fmtPct1(t.actas_contabilizadas)}</strong></div>
        <div><span>Participación</span><strong>${fmtPct1(t.participacion)}</strong></div>
        <div><span>Votos válidos</span><strong>${fmtMiles.format(t.votos_validos)}</strong></div>
        <div><span>Votos emitidos</span><strong>${fmtMiles.format(t.votos_emitidos)}</strong></div>
        <div><span>Actas (procesadas/total)</span><strong>${fmtMiles.format(t.contabilizadas)} / ${fmtMiles.format(t.total_actas)}</strong></div>
      </div>`
    : '<p class="placeholder">Sin datos de actas.</p>';

  const fecha = t ? `<div class="tt-fecha">Actualizado: ${fmtFecha(t.fecha_actualizacion)}</div>` : "";

  return `
    <div class="tt-titulo">${region.nombre}</div>
    <div class="tt-cands">${filasCand}</div>
    ${datos}
    ${fecha}`;
}

const tooltipEl = (() => {
  const el = document.createElement("div");
  el.id = "region-tooltip";
  el.className = "region-tooltip";
  el.style.display = "none";
  document.body.appendChild(el);
  return el;
})();

function posicionarTooltip(ev) {
  const margen = 14;
  const { innerWidth: w, innerHeight: h } = window;
  const r = tooltipEl.getBoundingClientRect();
  let x = ev.clientX + margen;
  let y = ev.clientY + margen;
  if (x + r.width > w - 8) x = ev.clientX - r.width - margen;
  if (y + r.height > h - 8) y = ev.clientY - r.height - margen;
  tooltipEl.style.left = `${Math.max(8, x)}px`;
  tooltipEl.style.top = `${Math.max(8, y)}px`;
}

function conectarTooltips(grid) {
  grid.addEventListener("mouseover", (ev) => {
    const tarjeta = ev.target.closest(".region");
    if (!tarjeta || !grid.contains(tarjeta)) return;
    const region = cacheRegiones.find((r) => r.ubigeo === tarjeta.dataset.ubigeo);
    if (!region) return;
    tooltipEl.innerHTML = tooltipRegion(region);
    tooltipEl.style.display = "block";
    posicionarTooltip(ev);
  });
  grid.addEventListener("mousemove", (ev) => {
    if (tooltipEl.style.display === "block") posicionarTooltip(ev);
  });
  grid.addEventListener("mouseout", (ev) => {
    const sigue = ev.relatedTarget && ev.relatedTarget.closest(".region");
    if (!sigue) tooltipEl.style.display = "none";
  });
}

// --- Modal de detalle por región (clic/tap en una tarjeta) ---
const modalEl = (() => {
  const el = document.createElement("div");
  el.id = "region-modal";
  el.className = "modal";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-modal", "true");
  el.hidden = true;
  el.innerHTML = `
    <div class="modal__overlay" data-cerrar></div>
    <div class="modal__caja" role="document">
      <button class="modal__cerrar" type="button" aria-label="Cerrar" data-cerrar>×</button>
      <div class="modal__contenido"></div>
    </div>`;
  document.body.appendChild(el);
  return el;
})();

function abrirModalRegion(region) {
  modalEl.querySelector(".modal__contenido").innerHTML = tooltipRegion(region);
  modalEl.hidden = false;
  document.body.classList.add("modal-abierto");
}

function abrirModalInfo() {
  modalEl.querySelector(".modal__contenido").innerHTML = `
    <div class="tt-titulo">Acerca de esta página</div>
    <div class="info-bloque">
      <p>
        Visualización <strong>no oficial</strong> de los resultados de la segunda
        vuelta presidencial del Perú.
      </p>
      <h4>¿De dónde salen los datos?</h4>
      <p>
        Se obtienen automáticamente de la <strong>API pública de la ONPE</strong>
        (Oficina Nacional de Procesos Electorales), la misma fuente que alimenta
        su portal oficial de resultados.
      </p>
      <h4>¿Cada cuánto se actualizan?</h4>
      <p>
        La página consulta a la ONPE de forma periódica y se refresca sola cada
        minuto. La hora de la última actualización se muestra en la parte superior.
      </p>
      <h4>¿Qué significan los porcentajes?</h4>
      <ul>
        <li>
          El <strong>porcentaje junto al nombre de la región</strong> es el avance
          de actas contabilizadas en ese ámbito.
        </li>
        <li>
          Los porcentajes de cada agrupación son sobre <strong>votos válidos</strong>.
        </li>
        <li>
          Toca o pasa el cursor por una región para ver su detalle (votos,
          participación y actas).
        </li>
      </ul>
      <p class="info-aviso">
        Los resultados son preliminares y pueden variar. Para información oficial
        visita el portal de la ONPE.
      </p>
    </div>`;
  modalEl.hidden = false;
  document.body.classList.add("modal-abierto");
}

function cerrarModal() {
  modalEl.hidden = true;
  document.body.classList.remove("modal-abierto");
}

function conectarModalRegiones(grid) {
  grid.addEventListener("click", (ev) => {
    const tarjeta = ev.target.closest(".region");
    if (!tarjeta || !grid.contains(tarjeta)) return;
    const region = cacheRegiones.find((r) => r.ubigeo === tarjeta.dataset.ubigeo);
    if (!region) return;
    // En móvil no hay hover: ocultamos cualquier tooltip residual.
    tooltipEl.style.display = "none";
    abrirModalRegion(region);
  });
  modalEl.addEventListener("click", (ev) => {
    if (ev.target.hasAttribute("data-cerrar")) cerrarModal();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !modalEl.hidden) cerrarModal();
  });
}

function renderGridRegiones(regiones, filtro = "") {
  const grid = document.getElementById("grid-regiones");
  const texto = filtro.trim().toLowerCase();
  const visibles = texto
    ? regiones.filter((r) => r.nombre.toLowerCase().includes(texto))
    : regiones;

  if (!visibles.length) {
    grid.innerHTML = '<p class="placeholder">Sin regiones que coincidan.</p>';
    return;
  }
  grid.innerHTML = visibles.map(tarjetaRegion).join("");
}

async function cargarGeneral() {
  const data = await obtenerJSON("/api/general");
  renderMetrics(document.getElementById("metrics-general"), data.totales);
  renderCandidatosGeneral(
    document.getElementById("candidatos-general"),
    data.participantes
  );

  const fecha = data.totales ? data.totales.fecha_actualizacion : null;
  document.getElementById("actualizado").textContent =
    "Actualizado: " + fmtFecha(fecha);
}

async function cargarRegiones() {
  cacheRegiones = await obtenerJSON("/api/regiones");
  const filtro = document.getElementById("buscar-region").value;
  renderGridRegiones(cacheRegiones, filtro);
}

async function cargarResumen() {
  const data = await obtenerJSON("/api/resumen");
  renderResumen(data);
}

async function refrescarTodo() {
  try {
    await Promise.all([cargarGeneral(), cargarResumen(), cargarRegiones()]);
  } catch (err) {
    document.getElementById("actualizado").textContent =
      "Error al cargar datos";
    console.error(err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document
    .getElementById("buscar-region")
    .addEventListener("input", (e) =>
      renderGridRegiones(cacheRegiones, e.target.value)
    );

  conectarTooltips(document.getElementById("grid-regiones"));
  conectarModalRegiones(document.getElementById("grid-regiones"));

  const btnInfo = document.getElementById("btn-info");
  if (btnInfo) btnInfo.addEventListener("click", abrirModalInfo);
  const btnInfoFooter = document.getElementById("btn-info-footer");
  if (btnInfoFooter) btnInfoFooter.addEventListener("click", abrirModalInfo);

  refrescarTodo();
  // Auto-refresco cada 60 s.
  setInterval(refrescarTodo, 60000);
});
