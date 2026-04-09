// editar_rutinas.js — Modal de edición de rutinas del admin
// Taxonomía: Bloque → Categoría → Ejercicio (con label = "Nombre — Material")

let ejerciciosPorBloque = {};

async function fetchEjercicios() {
  try {
    const res = await fetch("/api_ejercicios");
    ejerciciosPorBloque = await res.json();
  } catch (err) {
    console.error("Error cargando ejercicios:", err);
  }
}

function buscarRutinaPorFecha(fecha) {
  for (const semana of rutinasPorFecha) {
    for (const rutina of semana.rutinas) {
      if (rutina.fecha === fecha) return rutina;
    }
  }
  return null;
}

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

    // Build bloque type options (from taxonomy keys)
    const bloqueOpts = Object.keys(ejerciciosPorBloque)
      .map(b => `<option value="${b}" ${b === bloqueNombre ? 'selected' : ''}>${b}</option>`)
      .join('');

    let ejerciciosHTML = "";
    if (bloque.ejercicios && bloque.ejercicios.length > 0) {
      bloque.ejercicios.forEach(e => {
        const bloqueEj  = e.categoria || bloqueNombre;
        const catValue  = e.subcategoria || "";
        const ejNombre  = e.ejercicio?.nombre || e.nombre_manual || "";

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
            const val   = ej.label || ej;
            const sel   = (label === ejNombre || ej.nombre === ejNombre) ? 'selected' : '';
            return `<option value="${val}" ${sel}>${label}</option>`;
          }).join('');

        // Series display using series_json if available
        let seriesDisplay = '';
        if (e.series_json) {
          try {
            const sd = JSON.parse(e.series_json);
            if (sd.variar) {
              seriesDisplay = sd.series_data
                .map((s, i) => {
                  let p = `S${i+1}: ${s.reps||'?'}r`;
                  if (s.carga) p += ` ${s.carga}`;
                  if (s.rpe)   p += ` RPE${s.rpe}`;
                  return p;
                }).join(' / ');
            } else {
              seriesDisplay = `${sd.series||'?'}×${sd.reps||'?'}`;
              if (sd.carga) seriesDisplay += ` ${sd.carga}`;
              if (sd.rpe)   seriesDisplay += ` RPE${sd.rpe}`;
            }
          } catch(ex) {}
        }
        if (!seriesDisplay) seriesDisplay = e.series_reps || '';

        ejerciciosHTML += `
          <div class="ejercicio-entry" style="border:1px solid var(--color-border); border-radius:var(--radius-md); padding:var(--space-3); margin-bottom:var(--space-2); background:var(--color-bg);">
            <div style="display:grid; grid-template-columns:1fr 1fr 2fr auto; gap:var(--space-2); align-items:end; margin-bottom:var(--space-2);">
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
            <div style="font-size:var(--text-xs); color:var(--color-text-muted); padding:var(--space-1) var(--space-2); background:var(--color-surface); border-radius:var(--radius-sm);">
              <i class="bi bi-arrow-repeat me-1"></i>${seriesDisplay || '—'}
            </div>
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

// ── Cascade: bloque → categorías
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

// ── Cascade: categoría → ejercicios
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

// ── Sync bloque tipo → bloque-select-ej de todos los ejercicios del contenedor
function sincronizarBloqueEjercicios(tipoSelect) {
  const container = tipoSelect.closest('.bloque-container');
  const nuevoBloque = tipoSelect.value;
  container.querySelectorAll('.bloque-select-ej').forEach(sel => {
    sel.value = nuevoBloque;
    actualizarCatsEditar(sel);
  });
}

// ── Añadir ejercicio nuevo en edición
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
    <div class="ejercicio-entry" style="border:1px solid var(--color-border); border-radius:var(--radius-md); padding:var(--space-3); margin-bottom:var(--space-2); background:var(--color-bg);">
      <div style="display:grid; grid-template-columns:1fr 1fr 2fr auto; gap:var(--space-2); align-items:end;">
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
    </div>`);
}

// ── Añadir bloque nuevo en edición
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

document.addEventListener("DOMContentLoaded", fetchEjercicios);
