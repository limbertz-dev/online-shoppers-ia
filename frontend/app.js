// Cliente web (frontend independiente) del servicio de IA Online Shoppers.
// Se comunica con el backend por API REST y envía el JWT en cada petición.
const API = (window.CONFIG && window.CONFIG.API_URL) || 'http://localhost:8000';

// ---------------------------------------------------------------- sesión (JWT)
const sesion = {
  get token() { try { return sessionStorage.getItem('token'); } catch { return null; } },
  get usuario() { try { return JSON.parse(sessionStorage.getItem('usuario') || 'null'); } catch { return null; } },
  guardar(t) { try { sessionStorage.setItem('token', t.access_token); sessionStorage.setItem('usuario', JSON.stringify({ usuario: t.usuario, rol: t.rol })); } catch {} },
  cerrar() { try { sessionStorage.removeItem('token'); sessionStorage.removeItem('usuario'); } catch {} },
  usuarioActual(u) { try { sessionStorage.setItem('usuario', JSON.stringify(u)); } catch {} },
};

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
// El formulario se muestra en 4 grupos: qué vio, cómo navegó, cuándo entró y quién es el visitante
const GRUPOS = [
  { id: 'vio', t: 'Qué páginas vio', i: 'i-ojo', d: 'Páginas visitadas de cada tipo y segundos que pasó en ellas.' },
  { id: 'nav', t: 'Cómo navegó', i: 'i-ruta', d: 'Métricas de Google Analytics de las páginas que recorrió.' },
  { id: 'cuando', t: 'Cuándo entró', i: 'i-calendario', d: 'Mes, día de la semana y cercanía a una fecha especial.' },
  { id: 'quien', t: 'Quién es el visitante', i: 'i-persona', d: 'Tipo de visitante y datos técnicos (códigos).' },
];
const CAMPOS = [
  { g: 'vio', n: 'paginas_administrativas', l: 'Páginas administrativas', d: 'cantidad visitada', t: 'int' },
  { g: 'vio', n: 'tiempo_administrativas', l: 'Tiempo administrativas', d: 'segundos', t: 'float' },
  { g: 'vio', n: 'paginas_informativas', l: 'Páginas informativas', d: 'cantidad visitada', t: 'int' },
  { g: 'vio', n: 'tiempo_informativas', l: 'Tiempo informativas', d: 'segundos', t: 'float' },
  { g: 'vio', n: 'paginas_producto', l: 'Páginas de productos', d: 'cantidad visitada', t: 'int' },
  { g: 'vio', n: 'tiempo_producto', l: 'Tiempo en productos', d: 'segundos', t: 'float' },
  { g: 'nav', n: 'tasa_rebote', l: 'Tasa de rebote', d: '0 a 1', t: 'float', max: 1 },
  { g: 'nav', n: 'tasa_salida', l: 'Tasa de salida', d: '0 a 1', t: 'float', max: 1 },
  { g: 'nav', n: 'valor_pagina', l: 'Valor de página', d: 'valor promedio', t: 'float' },
  { g: 'cuando', n: 'mes', l: 'Mes', d: 'mes de la visita', t: 'sel', o: MESES },
  { g: 'cuando', n: 'fin_de_semana', l: 'Fin de semana', d: '¿sábado o domingo?', t: 'sel', o: ['false', 'true'] },
  { g: 'cuando', n: 'dia_especial', l: 'Cercanía a fecha especial', d: '0 a 1', t: 'float', max: 1 },
  { g: 'quien', n: 'tipo_visitante', l: 'Tipo de visitante', d: 'nuevo o recurrente', t: 'sel', o: ['Recurrente', 'Nuevo', 'Otro'] },
  { g: 'quien', n: 'sistema_operativo', l: 'Sistema operativo', d: 'código 1–8', t: 'int', min: 1 },
  { g: 'quien', n: 'navegador', l: 'Navegador', d: 'código 1–13', t: 'int', min: 1 },
  { g: 'quien', n: 'region', l: 'Región', d: 'código 1–9', t: 'int', min: 1 },
  { g: 'quien', n: 'tipo_trafico', l: 'Tipo de tráfico', d: 'código 1–20', t: 'int', min: 1 },
];
const EJEMPLOS = {
  compra: { paginas_administrativas: 3, tiempo_administrativas: 85, paginas_informativas: 0, tiempo_informativas: 0,
    paginas_producto: 40, tiempo_producto: 1500, tasa_rebote: 0.005, tasa_salida: 0.02, valor_pagina: 25.5,
    dia_especial: 0, mes: 'Nov', tipo_visitante: 'Recurrente', fin_de_semana: 'false', sistema_operativo: 2,
    navegador: 2, region: 1, tipo_trafico: 2 },
  nocompra: { paginas_administrativas: 0, tiempo_administrativas: 0, paginas_informativas: 0, tiempo_informativas: 0,
    paginas_producto: 8, tiempo_producto: 180, tasa_rebote: 0.03, tasa_salida: 0.06, valor_pagina: 0,
    dia_especial: 0, mes: 'May', tipo_visitante: 'Recurrente', fin_de_semana: 'false', sistema_operativo: 2,
    navegador: 2, region: 3, tipo_trafico: 1 },
};

const $ = (s) => document.querySelector(s);
const fmt = (v, d = 3) => Number(v).toFixed(d);
const pct = (v) => (Number(v) * 100).toFixed(1) + ' %';
const fecha = (s) => new Date(s).toLocaleString('es-BO');
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function aviso(msg, ok = false) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast show' + (ok ? ' ok' : '');
  clearTimeout(aviso.t);
  aviso.t = setTimeout(() => (t.className = 'toast'), 4500);
}

async function api(ruta, opciones = {}) {
  const headers = { ...(opciones.headers || {}) };
  if (sesion.token) headers.Authorization = `Bearer ${sesion.token}`;
  const r = await fetch(API + ruta, { ...opciones, headers });
  if (r.status === 401 && ruta !== '/auth/login') {
    sesion.cerrar();
    mostrarLogin();
    throw new Error('La sesión venció o el token no es válido. Inicie sesión de nuevo.');
  }
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) {
    let d = datos.detail;
    if (Array.isArray(d)) d = d.map((e) => `${e.loc.slice(-1)[0]}: ${e.msg}`).join(' · ');
    throw new Error(d || `Error ${r.status}`);
  }
  return datos;
}

async function ocupado(boton, texto, fn) {
  const original = boton.innerHTML;
  boton.disabled = true;
  boton.innerHTML = `<span class="spinner"></span>${texto}`;
  try { await fn(); } catch (e) { aviso(e.message); } finally { boton.disabled = false; boton.innerHTML = original; }
}

// ---------------------------------------------------------------- pestañas
document.querySelectorAll('.tab').forEach((b) => b.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach((x) => x.classList.toggle('active', x === b));
  document.querySelectorAll('.panel').forEach((p) => p.classList.toggle('active', p.id === b.dataset.tab));
  if (b.dataset.tab === 'historial') cargarHistorial();
  if (b.dataset.tab === 'metricas') cargarMetricas();
}));

// ---------------------------------------------------------------- predecir
function campoHtml(c) {
  const control = c.t === 'sel'
    ? `<select id="f-${c.n}" name="${c.n}">${c.o.map((o) => `<option value="${o}">${o === 'true' ? 'Sí' : o === 'false' ? 'No' : o}</option>`).join('')}</select>`
    : `<input id="f-${c.n}" name="${c.n}" type="number" required min="${c.min ?? 0}" ${c.max ? `max="${c.max}"` : ''} step="${c.t === 'int' ? 1 : 'any'}">`;
  return `<div class="field"><label for="f-${c.n}">${c.l}</label>${control}<small>${c.n} · ${c.d}</small></div>`;
}
function construirFormulario() {
  $('#form-pred').innerHTML = GRUPOS.map((g) => `
    <fieldset class="grupo g-${g.id}">
      <legend><svg><use href="#${g.i}"/></svg>${g.t}</legend>
      <p class="desc">${g.d}</p>
      <div class="campos">${CAMPOS.filter((c) => c.g === g.id).map(campoHtml).join('')}</div>
    </fieldset>`).join('');
  llenar(EJEMPLOS.compra);
}
function llenar(ej) { Object.entries(ej).forEach(([k, v]) => ($('#f-' + k).value = v)); }

function leerFormulario() {
  const datos = {};
  CAMPOS.forEach((c) => {
    const v = $('#f-' + c.n).value;
    datos[c.n] = c.t === 'int' ? parseInt(v, 10) : c.t === 'float' ? parseFloat(v) : c.n === 'fin_de_semana' ? v === 'true' : v;
  });
  return datos;
}

$('#ej-compra').onclick = () => llenar(EJEMPLOS.compra);
$('#ej-nocompra').onclick = () => llenar(EJEMPLOS.nocompra);
$('#form-pred').addEventListener('submit', (e) => {
  e.preventDefault();
  ocupado($('#btn-predecir'), 'Prediciendo…', async () => {
    const r = await api('/predict', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(leerFormulario()) });
    const caja = $('#resultado');
    caja.className = 'result ' + (r.compra ? 'si' : 'no');
    caja.innerHTML = `
      <span class="result-icon"><svg><use href="#i-bolsa"/></svg><span class="marca">${r.compra ? '✓' : '✕'}</span></span>
      <p class="muted">Resultado del modelo</p>
      <div class="big">${r.compra ? 'Comprará' : 'No comprará'}</div>
      <p class="muted">Probabilidad de compra: <b>${pct(r.probabilidad)}</b></p>
      <div class="bar"><span style="width:${r.probabilidad * 100}%"></span><i style="left:${r.umbral * 100}%" title="umbral"></i></div>
      <p class="muted" style="font-size:.78rem">La línea marca el umbral de decisión (${pct(r.umbral)}).</p>
      <dl class="kv"><dt>Id</dt><dd>#${r.id}</dd><dt>Modelo</dt><dd>v${r.modelo_version}</dd><dt>Fecha</dt><dd>${fecha(r.fecha)}</dd></dl>`;
  });
});

// ---------------------------------------------------------------- historial
const hist = { limit: 10, offset: 0, total: 0 };
async function cargarHistorial() {
  try {
    const r = await api(`/predictions?limit=${hist.limit}&offset=${hist.offset}`);
    hist.total = r.total;
    $('#tabla-hist').innerHTML = `<tr><th>Id</th><th>Fecha</th><th>Resultado</th><th>Prob.</th><th>Modelo</th>
      <th>Mes</th><th>Visitante</th><th>Valor página</th><th>Tasa salida</th><th>Datos enviados</th></tr>` +
      (r.items.length ? r.items.map((p) => `<tr>
        <td class="num">#${p.id}</td><td>${fecha(p.fecha)}</td>
        <td><span class="tag ${p.compra ? 'si' : 'no'}">${p.compra ? 'Compra' : 'No compra'}</span></td>
        <td class="num">${pct(p.probabilidad)}</td><td>v${p.modelo_version}</td>
        <td>${esc(p.entrada.mes)}</td><td>${esc(p.entrada.tipo_visitante)}</td>
        <td class="num">${fmt(p.entrada.valor_pagina, 2)}</td><td class="num">${fmt(p.entrada.tasa_salida, 3)}</td>
        <td><details><summary>ver JSON</summary><pre>${esc(JSON.stringify(p.entrada, null, 1))}</pre></details></td>
      </tr>`).join('') : '<tr><td colspan="10" class="muted">Todavía no hay predicciones.</td></tr>');
    const hasta = Math.min(hist.offset + hist.limit, hist.total);
    $('#hist-info').textContent = hist.total ? `${hist.offset + 1}–${hasta} de ${hist.total}` : '';
    $('#hist-prev').disabled = hist.offset === 0;
    $('#hist-next').disabled = hasta >= hist.total;
  } catch (e) { aviso(e.message); }
}
$('#btn-hist').onclick = () => { hist.offset = 0; cargarHistorial(); };
$('#hist-prev').onclick = () => { hist.offset = Math.max(0, hist.offset - hist.limit); cargarHistorial(); };
$('#hist-next').onclick = () => { hist.offset += hist.limit; cargarHistorial(); };

// ---------------------------------------------------------------- métricas
function matriz(cm) {
  return `<div class="cm">
    <div></div><div class="h">Predijo: no compra</div><div class="h">Predijo: compra</div>
    <div class="h">Real: no compra</div><div class="ok">${cm.tn}<small>verdaderos negativos</small></div><div class="bad">${cm.fp}<small>falsos positivos</small></div>
    <div class="h">Real: compra</div><div class="bad">${cm.fn}<small>falsos negativos</small></div><div class="ok">${cm.tp}<small>verdaderos positivos</small></div>
  </div>`;
}
async function cargarMetricas() {
  try {
    const [m, versiones] = await Promise.all([api('/metrics').catch(() => null), api('/metrics/history')]);
    if (!m) {
      $('#met-info').textContent = 'No hay un modelo activo. Suba datos y reentrene.';
      $('#met-cards').innerHTML = ''; $('#met-cm').innerHTML = '';
    } else {
      $('#met-info').innerHTML = `Modelo <b>v${m.version}</b> · ${esc(m.algoritmo)} · umbral ${fmt(m.umbral, 2)} ·
        ${m.filas_entrenamiento.toLocaleString('es-BO')} filas de entrenamiento / ${m.filas_prueba.toLocaleString('es-BO')} de prueba · ${fecha(m.fecha)}`;
      const k = m.metricas;
      $('#met-cards').innerHTML = [
        ['Recall (compra)', k.recall, 'main', 'requisito ≥ 70 %'], ['F2', k.f2, 'main', 'métrica principal'],
        ['Precision', k.precision, '', ''], ['F1', k.f1, '', ''], ['ROC-AUC', k.roc_auc, '', ''],
      ].map(([n, v, c, s]) => `<div class="card ${c}"><span>${n}</span><b>${pct(v)}</b><span>${s}</span></div>`).join('');
      $('#met-cm').innerHTML = matriz(m.matriz_confusion);
    }
    $('#tabla-versiones').innerHTML = `<tr><th>Versión</th><th>Estado</th><th>Recall</th><th>Precision</th><th>F2</th><th>ROC-AUC</th><th>Umbral</th><th>Filas</th><th>Fecha</th></tr>` +
      (versiones.length ? versiones.map((v) => `<tr><td>v${v.version}</td>
        <td>${v.activo ? '<span class="tag si">Activo</span>' : '<span class="muted">inactivo</span>'}</td>
        <td class="num">${fmt(v.metricas.recall)}</td><td class="num">${fmt(v.metricas.precision)}</td>
        <td class="num">${fmt(v.metricas.f2)}</td><td class="num">${fmt(v.metricas.roc_auc)}</td>
        <td class="num">${fmt(v.umbral, 2)}</td><td class="num">${v.filas_entrenamiento + v.filas_prueba}</td><td>${fecha(v.fecha)}</td></tr>`).join('')
        : '<tr><td colspan="9" class="muted">Sin versiones.</td></tr>');
  } catch (e) { aviso(e.message); }
}
$('#btn-met').onclick = cargarMetricas;

// ---------------------------------------------------------------- datos (CSV)
const drop = $('#drop');
let subirAlElegir = false;
$('#archivo').addEventListener('change', () => {
  const f = $('#archivo').files[0];
  $('#drop-text').innerHTML = f ? `<b>${esc(f.name)}</b> (${(f.size / 1024).toFixed(0)} KB)` : 'Haga clic o arrastre aquí un archivo <b>.csv</b>';
  if (f && subirAlElegir) $('#form-csv').requestSubmit();
  subirAlElegir = false;
});
['dragover', 'dragenter'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove('over')));
drop.addEventListener('drop', (e) => {
  e.preventDefault();
  $('#archivo').files = e.dataTransfer.files;
  $('#archivo').dispatchEvent(new Event('change'));
});
$('#form-csv').addEventListener('submit', (e) => {
  e.preventDefault();
  if (!$('#archivo').files[0]) {
    subirAlElegir = true;
    $('#archivo').click();
    return;
  }
  ocupado($('#btn-csv'), 'Subiendo y limpiando…', async () => {
    const fd = new FormData();
    fd.append('archivo', $('#archivo').files[0]);
    const r = await api(`/training-data?reemplazar=${$('#reemplazar').checked}`, { method: 'POST', body: fd });
    $('#csv-res').innerHTML = `<div class="summary">
      ${[['Filas recibidas', r.filas_recibidas], ['Filas inválidas', r.filas_invalidas], ['Nulos imputados', r.nulos_imputados],
         ['Duplicados eliminados', r.duplicados_eliminados], ['Filas guardadas', r.filas_validas],
         ['Total en la BD', r.total_datos_entrenamiento]]
        .map(([n, v], i) => `<div class="card ${i >= 4 ? 'main' : ''}"><span>${n}</span><b>${v.toLocaleString('es-BO')}</b></div>`).join('')}
      </div><div class="note ok">Lote #${r.lote_id} guardado${r.reemplazo ? ' (datos anteriores reemplazados)' : ''}. Ahora puede reentrenar el modelo.</div>`;
    aviso('CSV cargado correctamente', true);
  });
});

// ---------------------------------------------------------------- reentrenar
$('#btn-retrain').onclick = () => ocupado($('#btn-retrain'), 'Entrenando… (unos segundos)', async () => {
  const r = await api('/retrain', { method: 'POST' });
  const a = r.modelo_anterior;
  const filas = ['recall', 'precision', 'f1', 'f2', 'roc_auc'].map((k) => {
    const nuevo = r.metricas[k], viejo = a ? a[k] : null;
    const dif = viejo === null ? '' : nuevo - viejo;
    const cls = dif === '' || Math.abs(dif) < 1e-4 ? '' : dif > 0 ? 'up' : 'down';
    return `<tr><td>${k.toUpperCase().replace('_', '-')}</td><td class="num">${viejo === null ? '—' : fmt(viejo)}</td>
      <td class="num">${fmt(nuevo)}</td><td class="num ${cls}">${dif === '' ? '' : (dif >= 0 ? '+' : '') + fmt(dif)}</td></tr>`;
  }).join('');
  $('#retrain-res').innerHTML = `
    <div class="note ${r.activado ? 'ok' : 'bad'}">Versión v${r.version} (${esc(r.algoritmo)}) · ${esc(r.motivo)}</div>
    <h3>Comparación con el modelo anterior${a ? ` (v${a.version})` : ''}</h3>
    <div class="table-wrap compare"><table><tr><th>Métrica</th><th class="num">Anterior</th><th class="num">Nuevo</th><th class="num">Diferencia</th></tr>${filas}</table></div>
    <p class="muted">Umbral ${fmt(r.umbral, 2)} · ${r.filas_entrenamiento.toLocaleString('es-BO')} filas de entrenamiento y
      ${r.filas_prueba.toLocaleString('es-BO')} de prueba.</p>
    <h3>Matriz de confusión</h3><div style="max-width:340px">${matriz(r.matriz_confusion)}</div>`;
  aviso('Modelo reentrenado', true);
});

// ---------------------------------------------------------------- login / logout
function mostrarLogin() {
  $('#login').hidden = false; $('#app').hidden = true;
  $('#cabecera').hidden = true; $('#pie').hidden = true;
  $('#usuario-actual').hidden = true; $('#btn-salir').hidden = true;
  $('#l-usuario').focus();
}
function mostrarApp() {
  const u = sesion.usuario;
  $('#login').hidden = true; $('#app').hidden = false;
  $('#cabecera').hidden = false; $('#pie').hidden = false;
  $('#usuario-actual').innerHTML = `<b>${esc(u.usuario)}</b> · ${esc(u.rol)}`;
  $('#usuario-actual').hidden = false; $('#btn-salir').hidden = false;
  // Autorización en la interfaz: el analista no ve carga de datos ni reentrenamiento (el backend igual lo valida)
  document.querySelectorAll('.solo-admin').forEach((t) => (t.hidden = u.rol !== 'admin'));
  const inicial = document.querySelector(`.tab[data-tab="${location.hash.slice(1)}"]:not([hidden])`)
    || document.querySelector('.tab[data-tab="predecir"]');
  inicial.click();
}
$('#form-login').addEventListener('submit', (e) => {
  e.preventDefault();
  ocupado($('#btn-login'), 'Ingresando…', async () => {
    const cuerpo = new URLSearchParams({ username: $('#l-usuario').value, password: $('#l-password').value });
    const t = await api('/auth/login', { method: 'POST', body: cuerpo });
    sesion.guardar(t);
    $('#l-password').value = '';
    mostrarApp();
  });
});
$('#btn-salir').onclick = () => { sesion.cerrar(); mostrarLogin(); };

construirFormulario();
api('/health').catch(() => aviso('El servicio de IA no responde. Verifique que el backend esté encendido.'));
if (sesion.token) {
  api('/auth/me').then((u) => { sesion.usuarioActual(u); mostrarApp(); }).catch(() => mostrarLogin());
} else {
  mostrarLogin();
}
