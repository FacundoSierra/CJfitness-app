// editar_rutinas.js — Modal de edición de rutinas del admin
// Taxonomía: Bloque → Categoría → Ejercicio (con label = "Nombre — Material")

let ejerciciosPorBloque = {};

// ── HELPERS (compartidos con calendario_rutinas.js pero independientes) ───────

function buildSeriesOptions(selected) {
  let opts = '<option value="">Series</option>';
  for (let i = 1; i <= 10; i++) {
    opts += `<option value="${i}" ${selected == i ? 'selected' : ''}>${i}</option>`;
  }
  return opts;
}

function buildRepsOptions(selected, placeholder) {
  let opts = `<option value="">${placeholder || 'Reps'}</option>`;
  for (let i = 1; i <= 25; i++) {
    opts += `<option value="${i}" ${selected == i ? 'selected' : ''}>${i}</option>`;
  }
  return opts;
}

function buildRpeOptions(selected, placeholder) {
  let opts = `<option value="">${placeholder || 'RPE'}</option>`;
  for (let i = 1; i <= 10; i++) {
    opts += `<option value="${i}" ${selected == i ? 'selected' : ''}>${i}</option>`;
  }
  return opts;
}

function buildCargaOptions(selected) {
  const selNum = parseFloat(selected);
  let opts = '<option value="">Carga</option>';
  for (let i = 0; i <= 800; i++) {
    const val = i / 4;
    const sel = (!isNaN(selNum) && selNum === val) ? 'selected' : '';
    opts += `<option value="${val}" ${sel}>${val} kg</option>`;
  }
  return opts;
}

function toggleVariarSeries(btn) {
  const entry = btn.closest('.ejercicio-entry');
  const tabla = entry.querySelector('.series-tabla');
  const isActive = btn.classList.contains('active');
  if (isActive) {
    btn.classList.remove('active', 'btn-primary');
    btn.classList.add('btn-outline-primary');
    tabla.style.display = 'none';
  } else {
    btn.classList.remove('btn-outline-primary');
    btn.classList.add('active', 'btn-primary');
    actualizarFilasSeries(entry.querySelector('.series-select'));
    tabla.style.display = 'block';
  }
}

function actualizarFilasSeries(seriesSelect) {
  const entry = seriesSelect.closest('.ejercicio-entry');
  if (!entry.querySelector('.variar-btn').classList.contains('active')) return;

  const n = parseInt(seriesSelect.value) || 0;
  const tbody = entry.querySelector('.series-tbody');
  const repsGlobal  = entry.querySelector('.reps-select').value;
  const rpeGlobal   = entry.querySelector('.rpe-select').value;
  const cargaGlobal = entry.querySelector('.carga-input').value;

  // Conservar valores ya introducidos
  const existentes = Array.from(tbody.querySelectorAll('tr')).map(tr => ({
    reps:  tr.querySelector('.reps-serie').value,
    rpe:   tr.querySelector('.rpe-serie').value,
    carga: tr.querySelector('.carga-serie').value,
  }));

  tbody.innerHTML = '';

  for (let i = 0; i < n; i++) {
    const prev  = existentes[i] || {};
    const reps  = prev.reps  || repsGlobal;
    const rpe   = prev.rpe   || rpeGlobal;
    const carga = (prev.carga !== undefined && prev.carga !== '') ? prev.carga : cargaGlobal;

    tbody.insertAdjacentHTML('beforeend', `
      <tr>
        <td style="padding:3px var(--space-3); color:var(--color-primary); font-weight:700; font-size:var(--text-sm);">S${i + 1}</td>
        <td style="padding:3px var(--space-3);">
          <select class="form-select form-select-sm reps-serie" style="width:86px;">
            ${buildRepsOptions(reps, '-')}
          </select>
        </td>
        <td style="padding:3px var(--space-3);">
          <select class="form-select form-select-sm rpe-serie" style="width:86px;">
            ${buildRpeOptions(rpe, '-')}
          </select>
        </td>
        <td style="padding:3px var(--space-3);">
          <select class="form-select form-select-sm carga-serie" style="width:110px;">
            ${buildCargaOptions(carga)}
          </select>
        </td>
      </tr>
    `);
  }
}

function serializarEjercicios() {
  document.querySelectorAll('.ejercicio-entry').forEach(entry => {
    const hidden = entry.querySelector('.series-json-input');
    if (!hidden) return;

    const variar = entry.querySelector('.variar-btn').classList.contains('active');
    const series = parseInt(entry.querySelector('.series-select').value) || 0;

    let data;
    if (!variar) {
      data = {
        series,
        reps:  entry.querySelector('.reps-select').value,
        rpe:   entry.querySelector('.rpe-select').value,
        carga: entry.querySelector('.carga-input').value,
        variar: false
      };
    } else {
      const rows = Array.from(entry.querySelectorAll('.series-tbody tr'));
      data = {
        series,
        variar: true,
        series_data: rows.map(tr => ({
          reps:  tr.querySelector('.reps-serie').value,
          rpe:   tr.querySelector('.rpe-serie').value,
          carga: tr.querySelector('.carga-serie').value
        }))
      };
    }

    hidden.value = JSON.stringify(data);
  });
}

// ── FETCH ─────────────────────────────────────────────────────────────────────

async function fetchEjercicios() {
  try {
    const res = await fetch("/api_ejercicios");
    ejerciciosPorBloque = await res.json();
  } catch (err) {
    console.error("Error cargando ejercicios:", err);
  }
}

// ── BUSCAR RUTINA ─────────────────────────────────────────────────────────────

function buscarRutinaPorFecha(fecha) {
  for (const semana of rutinasPorFecha) {
    for (const rutina of semana.rutinas) {
      if (rutina.fecha === fecha) return rutina;
    }
  }
  return null;
}

// ── ABRIR MODAL EDICIÓN ───────────────────────────────────────────────────────

function abrirModalEdicion(fecha) {
  const rutina = buscarRutinaPorFecha(fecha);
  if (!rutina) { alert("No se encontró la rutina para editar."); return; }

  document.getElementById("editarFechaTexto").innerText = fecha;
  document.getElementById("fechaEditarHidden").value = fecha;
  const container = document.getElementById("bloquesEditarContainer");
  container.innerHTML = "";

  if (!rutina.bloques || rutina.bloques.length === 0) {
    agregarBloqueEditar(null, 1);
    return;
  }

  rutina.bloques.forEach((bloque, idx) => {
    const bloqueIndex = idx + 1;
    const bloqueNombre = bloque.nombre_bloque || bloque.categoria || "";

    const bloqueOpts = Object.keys(ejerciciosPorBloque)
      .map(b => `<option value="${b}" ${b === bloqueNombre ? 'selected' : ''}>${b}</option>`)
      .join('');

    let ejerciciosHTML = "";
    if (bloque.ejercicios && bloque.ejercicios.length > 0) {
      bloque.ejercicios.forEach(e => {
        const bloqueEj = e.categoria || bloqueNombre;
        const catValue = e.subcategoria || "";
        const ejNombre = e.nombre_manual || "";

        // Parse series_json para pre-poblar los controles
        let sd = null;
        if (e.series_json) {
          try { sd = JSON.parse(e.series_json); } catch(ex) {}
        }

        // Build bloque options for this exercise
        const bloqueEjOpts = Object.keys(ejerciciosPorBloque)
          .map(b => `<option value="${b}" ${b === bloqueEj ? 'selected' : ''}>${b}</option>`)
          .join('');

        // Build category options
        const cats = bloqueEj && ejerciciosPorBloque[bloqueEj]
          ? Object.keys(ejerciciosPorBloque[bloqueEj])
          : [];
        const catOpts = cats
          .map(c => `<option value="${c}" ${c === catValue ? 'selected' : ''}>${c}</option>`)
          .join('');

        // Build exercise options — match by nombre or label
        const ejList = (bloqueEj && catValue && ejerciciosPorBloque[bloqueEj]?.[catValue]) || [];
        const ejOpts = ejList
          .map(ej => {
            const label = ej.label || ej;
            const sel   = (label === ejNombre || ej.nombre === ejNombre) ? 'selected' : '';
            return `<option value="${label}" ${sel}>${label}</option>`;
          }).join('');

        // Variable series rows HTML (si sd.variar)
        let seriesFilasHTML = '';
        if (sd && sd.variar && sd.series_data) {
          sd.series_data.forEach((s, i) => {
            seriesFilasHTML += `
              <tr>
                <td style="padding:3px var(--space-3); color:var(--color-primary); font-weight:700; font-size:var(--text-sm);">S${i+1}</td>
                <td style="padding:3px var(--space-3);">
                  <select class="form-select form-select-sm reps-serie" style="width:86px;">${buildRepsOptions(s.reps||'', '-')}</select>
                </td>
                <td style="padding:3px var(--space-3);">
                  <select class="form-select form-select-sm rpe-serie" style="width:86px;">${buildRpeOptions(s.rpe||'', '-')}</select>
                </td>
                <td style="padding:3px var(--space-3);">
                  <select class="form-select form-select-sm carga-serie" style="width:110px;">${buildCargaOptions(s.carga||'')}</select>
                </td>
              </tr>`;
          });
        }

        const variarActivo = sd && sd.variar;
        const variarClass  = variarActivo ? 'active btn-primary' : 'btn-outline-primary';
        const tablaDisplay = variarActivo ? 'block' : 'none';

        ejerciciosHTML += `
          <div class="ejercicio-entry" style="border:1px solid var(--color-border-dark); border-radius:var(--radius-md); padding:var(--space-4); margin-bottom:var(--space-3); background:var(--color-bg-alt);">
            <!-- Fila 1: Ejercicio -->
            <div style="display:grid; grid-template-columns:1fr 1fr 2fr auto; gap:var(--space-3); margin-bottom:var(--space-3); align-items:end;">
              <div>
                <label style="font-size:10px; font-weight:600; color:var(--color-text-muted); display:block; margin-bottom:3px;">Bloque</label>
                <select class="form-select form-select-sm bloque-select-ej" name="bloque_ej_${bloqueIndex}[]"
                        onchange="actualizarCatsEditar(this)">
                  <option value="">—</option>
                  ${bloqueEjOpts}
                </select>
              </div>
              <div>
                <label style="font-size:10px; font-weight:600; color:var(--color-text-muted); display:block; margin-bottom:3px;">Categoría</label>
                <select class="form-select form-select-sm cat-select-ej" name="categoria_ej_${bloqueIndex}[]"
                        onchange="actualizarEjsEditar(this)">
                  <option value="">—</option>
                  ${catOpts}
                </select>
              </div>
              <div>
                <label style="font-size:10px; font-weight:600; color:var(--color-text-muted); display:block; margin-bottom:3px;">Ejercicio</label>
                <select class="form-select form-select-sm ejercicio-select" name="ejercicio_${bloqueIndex}[]">
                  <option value="${ejNombre}">${ejNombre || '—'}</option>
                  ${ejOpts}
                </select>
              </div>
              <div style="padding-bottom:2px;">
                <button type="button" class="btn btn-sm btn-danger"
                        onclick="this.closest('.ejercicio-entry').remove()">
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </div>
            <!-- Fila 2: Volumen -->
            <div style="display:grid; grid-template-columns:90px 90px 90px 1fr auto; gap:var(--space-3); align-items:end;">
              <div>
                <label style="font-size:var(--text-xs); font-weight:600; color:var(--color-text-secondary); margin-bottom:4px; display:block;">Series</label>
                <select class="form-select series-select" onchange="actualizarFilasSeries(this)">
                  ${buildSeriesOptions(sd && !sd.variar ? sd.series : (sd && sd.variar ? sd.series_data.length : ''))}
                </select>
              </div>
              <div>
                <label style="font-size:var(--text-xs); font-weight:600; color:var(--color-text-secondary); margin-bottom:4px; display:block;">Reps</label>
                <select class="form-select reps-select">
                  ${buildRepsOptions(sd && !sd.variar ? sd.reps : '')}
                </select>
              </div>
              <div>
                <label style="font-size:var(--text-xs); font-weight:600; color:var(--color-text-secondary); margin-bottom:4px; display:block;">RPE</label>
                <select class="form-select rpe-select">
                  ${buildRpeOptions(sd && !sd.variar ? sd.rpe : '')}
                </select>
              </div>
              <div>
                <label style="font-size:var(--text-xs); font-weight:600; color:var(--color-text-secondary); margin-bottom:4px; display:block;">Carga</label>
                <select class="form-select carga-input">
                  ${buildCargaOptions(sd && !sd.variar ? sd.carga : '')}
                </select>
              </div>
              <div style="padding-bottom:2px;">
                <button type="button" class="btn btn-sm btn-outline-primary variar-btn ${variarClass}"
                        onclick="toggleVariarSeries(this)"
                        title="Activar variaciones por serie">
                  Variar Series
                </button>
              </div>
            </div>
            <!-- Tabla de series variables -->
            <div class="series-tabla" style="display:${tablaDisplay}; margin-top:var(--space-4); padding-top:var(--space-3); border-top:1px solid var(--color-border);">
              <p style="font-size:var(--text-xs); font-weight:600; color:var(--color-text-secondary); margin-bottom:var(--space-2);">Valores por serie:</p>
              <table style="width:auto; font-size:var(--text-sm); border-collapse:separate; border-spacing:0 6px;">
                <thead>
                  <tr style="color:var(--color-text-secondary); font-size:var(--text-xs); font-weight:600;">
                    <th style="padding:0 var(--space-3); width:60px;">Serie</th>
                    <th style="padding:0 var(--space-3); width:90px;">Reps</th>
                    <th style="padding:0 var(--space-3); width:90px;">RPE</th>
                    <th style="padding:0 var(--space-3); width:130px;">Carga</th>
                  </tr>
                </thead>
                <tbody class="series-tbody">${seriesFilasHTML}</tbody>
              </table>
            </div>
            <!-- Input oculto JSON -->
            <input type="hidden" class="series-json-input" name="series_json_${bloqueIndex}[]">
          </div>`;
      });
    }

    container.insertAdjacentHTML("beforeend", `
      <div class="bloque-container" style="border:1px solid var(--color-border); border-radius:var(--radius-md); padding:var(--space-4); margin-bottom:var(--space-3);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--space-3);">
          <strong style="font-size:var(--text-sm);">Bloque ${bloqueIndex}</strong>
          <button type="button" class="btn-close" onclick="this.closest('.bloque-container').remove()"></button>
        </div>
        <div style="margin-bottom:var(--space-3);">
          <label class="form-label" style="font-weight:600; font-size:var(--text-sm);">Tipo de Bloque:</label>
          <select class="form-select bloque-tipo-select" name="categoria_bloque_${bloqueIndex}" required style="max-width:220px;"
                  onchange="sincronizarBloqueEjercicios(this)">
            <option value="">Selecciona tipo</option>
            ${bloqueOpts}
          </select>
        </div>
        <div class="ejercicios">${ejerciciosHTML}</div>
        <button type="button" class="btn btn-sm btn-secondary" style="margin-top:var(--space-2);"
                onclick="agregarEjercicioEditar(this, ${bloqueIndex})">
          <i class="bi bi-plus me-1"></i>Añadir Ejercicio
        </button>
      </div>`);
  });
}

// ── Cascade: bloque → categorías ─────────────────────────────────────────────

function actualizarCatsEditar(select) {
  const bloque  = select.value;
  const entry   = select.closest('.ejercicio-entry');
  const catSel  = entry.querySelector('.cat-select-ej');
  const ejSel   = entry.querySelector('.ejercicio-select');
  catSel.innerHTML = '<option value="">Categoría</option>';
  ejSel.innerHTML  = '<option value="">Ejercicio</option>';
  if (bloque && ejerciciosPorBloque[bloque]) {
    Object.keys(ejerciciosPorBloque[bloque]).forEach(c => {
      catSel.innerHTML += `<option value="${c}">${c}</option>`;
    });
  }
}

// ── Cascade: categoría → ejercicios ──────────────────────────────────────────

function actualizarEjsEditar(select) {
  const entry    = select.closest('.ejercicio-entry');
  const bloque   = entry.querySelector('.bloque-select-ej').value;
  const cat      = select.value;
  const ejSel    = entry.querySelector('.ejercicio-select');
  ejSel.innerHTML = '<option value="">Ejercicio</option>';
  const lista = ejerciciosPorBloque[bloque]?.[cat] || [];
  lista.forEach(ej => {
    const label = ej.label || ej;
    ejSel.innerHTML += `<option value="${label}">${label}</option>`;
  });
}

// ── Sync bloque tipo → bloque-select-ej de todos los ejercicios ───────────────

function sincronizarBloqueEjercicios(tipoSelect) {
  const container   = tipoSelect.closest('.bloque-container');
  const nuevoBloque = tipoSelect.value;
  container.querySelectorAll('.bloque-select-ej').forEach(sel => {
    sel.value = nuevoBloque;
    actualizarCatsEditar(sel);
  });
}

// ── Añadir ejercicio nuevo en edición ─────────────────────────────────────────

function agregarEjercicioEditar(btn, bloqueIndex) {
  const container = btn.closest('.bloque-container');
  const ejercicios = container.querySelector('.ejercicios');
  const bloqueSeleccionado = container.querySelector(`[name="categoria_bloque_${bloqueIndex}"]`)?.value || '';

  const bloqueOpts = Object.keys(ejerciciosPorBloque)
    .map(b => `<option value="${b}" ${b === bloqueSeleccionado ? 'selected' : ''}>${b}</option>`)
    .join('');

  const cats = bloqueSeleccionado && ejerciciosPorBloque[bloqueSeleccionado]
    ? Object.keys(ejerciciosPorBloque[bloqueSeleccionado]).map(c => `<option value="${c}">${c}</option>`).join('')
    : '';

  ejercicios.insertAdjacentHTML("beforeend", `
    <div class="ejercicio-entry" style="border:1px solid var(--color-border-dark); border-radius:var(--radius-md); padding:var(--space-4); margin-bottom:var(--space-3); background:var(--color-bg-alt);">
      <!-- Fila 1: Ejercicio -->
      <div style="display:grid; grid-template-columns:1fr 1fr 2fr auto; gap:var(--space-3); margin-bottom:var(--space-3); align-items:end;">
        <div>
          <label style="font-size:10px; font-weight:600; color:var(--color-text-muted); display:block; margin-bottom:3px;">Bloque</label>
          <select class="form-select form-select-sm bloque-select-ej" name="bloque_ej_${bloqueIndex}[]"
                  onchange="actualizarCatsEditar(this)">
            <option value="">—</option>
            ${bloqueOpts}
          </select>
        </div>
        <div>
          <label style="font-size:10px; font-weight:600; color:var(--color-text-muted); display:block; margin-bottom:3px;">Categoría</label>
          <select class="form-select form-select-sm cat-select-ej" name="categoria_ej_${bloqueIndex}[]"
                  onchange="actualizarEjsEditar(this)">
            <option value="">—</option>
            ${cats}
          </select>
        </div>
        <div>
          <label style="font-size:10px; font-weight:600; color:var(--color-text-muted); display:block; margin-bottom:3px;">Ejercicio</label>
          <select class="form-select form-select-sm ejercicio-select" name="ejercicio_${bloqueIndex}[]">
            <option value="">—</option>
          </select>
        </div>
        <div style="padding-bottom:2px;">
          <button type="button" class="btn btn-sm btn-danger"
                  onclick="this.closest('.ejercicio-entry').remove()">
            <i class="bi bi-trash"></i>
          </button>
        </div>
      </div>
      <!-- Fila 2: Volumen -->
      <div style="display:grid; grid-template-columns:90px 90px 90px 1fr auto; gap:var(--space-3); align-items:end;">
        <div>
          <label style="font-size:var(--text-xs); font-weight:600; color:var(--color-text-secondary); margin-bottom:4px; display:block;">Series</label>
          <select class="form-select series-select" onchange="actualizarFilasSeries(this)">
            ${buildSeriesOptions('')}
          </select>
        </div>
        <div>
          <label style="font-size:var(--text-xs); font-weight:600; color:var(--color-text-secondary); margin-bottom:4px; display:block;">Reps</label>
          <select class="form-select reps-select">
            ${buildRepsOptions('')}
          </select>
        </div>
        <div>
          <label style="font-size:var(--text-xs); font-weight:600; color:var(--color-text-secondary); margin-bottom:4px; display:block;">RPE</label>
          <select class="form-select rpe-select">
            ${buildRpeOptions('')}
          </select>
        </div>
        <div>
          <label style="font-size:var(--text-xs); font-weight:600; color:var(--color-text-secondary); margin-bottom:4px; display:block;">Carga</label>
          <select class="form-select carga-input">
            ${buildCargaOptions('')}
          </select>
        </div>
        <div style="padding-bottom:2px;">
          <button type="button" class="btn btn-sm btn-outline-primary variar-btn"
                  onclick="toggleVariarSeries(this)"
                  title="Activar variaciones por serie">
            Variar Series
          </button>
        </div>
      </div>
      <!-- Tabla de series variables (oculta por defecto) -->
      <div class="series-tabla" style="display:none; margin-top:var(--space-4); padding-top:var(--space-3); border-top:1px solid var(--color-border);">
        <p style="font-size:var(--text-xs); font-weight:600; color:var(--color-text-secondary); margin-bottom:var(--space-2);">Valores por serie:</p>
        <table style="width:auto; font-size:var(--text-sm); border-collapse:separate; border-spacing:0 6px;">
          <thead>
            <tr style="color:var(--color-text-secondary); font-size:var(--text-xs); font-weight:600;">
              <th style="padding:0 var(--space-3); width:60px;">Serie</th>
              <th style="padding:0 var(--space-3); width:90px;">Reps</th>
              <th style="padding:0 var(--space-3); width:90px;">RPE</th>
              <th style="padding:0 var(--space-3); width:130px;">Carga</th>
            </tr>
          </thead>
          <tbody class="series-tbody"></tbody>
        </table>
      </div>
      <!-- Input oculto JSON -->
      <input type="hidden" class="series-json-input" name="series_json_${bloqueIndex}[]">
    </div>`);
}

// ── Añadir bloque nuevo en edición ────────────────────────────────────────────

function agregarBloqueEditar(btn, forcedIndex) {
  const container = document.getElementById("bloquesEditarContainer");
  const newIndex  = forcedIndex || (document.querySelectorAll('.bloque-container').length + 1);
  const bloqueOpts = Object.keys(ejerciciosPorBloque)
    .map(b => `<option value="${b}">${b}</option>`).join('');

  container.insertAdjacentHTML("beforeend", `
    <div class="bloque-container" style="border:1px solid var(--color-border); border-radius:var(--radius-md); padding:var(--space-4); margin-bottom:var(--space-3);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--space-3);">
        <strong style="font-size:var(--text-sm);">Bloque ${newIndex}</strong>
        <button type="button" class="btn-close" onclick="this.closest('.bloque-container').remove()"></button>
      </div>
      <div style="margin-bottom:var(--space-3);">
        <label class="form-label" style="font-weight:600; font-size:var(--text-sm);">Tipo de Bloque:</label>
        <select class="form-select bloque-tipo-select" name="categoria_bloque_${newIndex}" required style="max-width:220px;"
                onchange="sincronizarBloqueEjercicios(this)">
          <option value="">Selecciona tipo</option>
          ${bloqueOpts}
        </select>
      </div>
      <div class="ejercicios"></div>
      <button type="button" class="btn btn-sm btn-secondary" style="margin-top:var(--space-2);"
              onclick="agregarEjercicioEditar(this, ${newIndex})">
        <i class="bi bi-plus me-1"></i>Añadir Ejercicio
      </button>
    </div>`);
}

// ── INIT ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", function () {
  fetchEjercicios();
  const form = document.getElementById('formEditarRutina');
  if (form) form.addEventListener('submit', serializarEjercicios);
});
