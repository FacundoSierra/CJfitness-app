let ejerciciosPorCategoria = {};

async function fetchEjercicios() {
  const res = await fetch("/api_ejercicios");
  const data = await res.json();
  ejerciciosPorCategoria = data;
}

function abrirModalAsignacion(fecha) {
  document.getElementById("modalFecha").innerText = fecha;
  document.getElementById("inputFecha").value = fecha;
  document.getElementById("contenedorBloques").innerHTML = '';
  agregarBloque();

  const modal = new bootstrap.Modal(document.getElementById("modalAsignarRutina"));
  modal.show();
}

// ── HELPERS ──────────────────────────────────────────────────────────────────

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

// ── BLOQUE ────────────────────────────────────────────────────────────────────

function agregarBloque() {
  const index = document.querySelectorAll(".bloque-container").length + 1;

  const bloqueHTML = `
    <div class="bloque-container" style="border:1px solid var(--color-border); border-radius:var(--radius-md); padding:var(--space-4); margin-bottom:var(--space-3);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--space-3);">
        <strong style="font-size:var(--text-sm);">Bloque ${index}</strong>
        <button type="button" class="btn-close" onclick="this.closest('.bloque-container').remove()"></button>
      </div>

      <div style="margin-bottom:var(--space-3);">
        <label class="form-label" style="font-weight:600; font-size:var(--text-sm);">Categoría del Bloque:</label>
        <select class="form-select" name="categoria_bloque_${index}" required style="max-width:220px;">
          <option value="">Selecciona categoría</option>
          <option value="Calentamiento">Calentamiento</option>
          <option value="Fuerza">Fuerza</option>
          <option value="Cardio">Cardio</option>
          <option value="Flexibilidad">Flexibilidad</option>
          <option value="Recuperación">Recuperación</option>
          <option value="General">General</option>
        </select>
      </div>

      <div class="ejercicios"></div>
      <button type="button" class="btn btn-sm btn-secondary" onclick="agregarEjercicio(this, ${index})" style="margin-top:var(--space-2);">
        <i class="bi bi-plus me-1"></i>Añadir Ejercicio
      </button>
    </div>
  `;

  document.getElementById("contenedorBloques").insertAdjacentHTML("beforeend", bloqueHTML);
}

// ── EJERCICIO ROW ─────────────────────────────────────────────────────────────

function agregarEjercicio(btn, bloqueIndex) {
  const bloque = btn.closest('.bloque-container');
  const ejercicios = bloque.querySelector(".ejercicios");

  const catOpts = Object.keys(ejerciciosPorCategoria)
    .map(cat => `<option value="${cat}">${cat}</option>`).join('');

  const html = `
    <div class="ejercicio-entry" style="border:1px solid var(--color-border-dark); border-radius:var(--radius-md); padding:var(--space-3); margin-bottom:var(--space-2); background:var(--color-bg-alt);">

      <!-- Fila principal -->
      <div style="display:flex; flex-wrap:wrap; gap:var(--space-2); align-items:center;">

        <!-- Categoría → Subcategoría → Ejercicio -->
        <select class="form-select categoria-select-ej" name="categoria_ej_${bloqueIndex}[]"
                style="width:110px; font-size:var(--text-sm);"
                onchange="actualizarSubcategoriasEjercicio(this)">
          <option value="">Categoría</option>
          ${catOpts}
        </select>

        <select class="form-select subcategoria-select-ej" name="subcategoria_ej_${bloqueIndex}[]"
                style="width:120px; font-size:var(--text-sm);"
                onchange="actualizarEjerciciosEjercicio(this)">
          <option value="">Subcategoría</option>
        </select>

        <select class="form-select ejercicio-select" name="ejercicio_${bloqueIndex}[]"
                style="width:150px; font-size:var(--text-sm);">
          <option value="">Ejercicio</option>
        </select>

        <span style="border-left:1px solid var(--color-border); height:28px; margin:0 var(--space-1);"></span>

        <!-- Series (1-10) -->
        <select class="form-select series-select"
                style="width:80px; font-size:var(--text-sm);"
                onchange="actualizarFilasSeries(this)">
          ${buildSeriesOptions('')}
        </select>

        <!-- Reps (1-25) -->
        <select class="form-select reps-select"
                style="width:72px; font-size:var(--text-sm);">
          ${buildRepsOptions('')}
        </select>

        <!-- RPE (1-10) -->
        <select class="form-select rpe-select"
                style="width:72px; font-size:var(--text-sm);">
          ${buildRpeOptions('')}
        </select>

        <!-- Carga (texto libre) -->
        <input type="text" class="form-control carga-input"
               placeholder="Carga (ej: 80kg)"
               style="width:100px; font-size:var(--text-sm);">

        <!-- Botón variar -->
        <button type="button" class="btn btn-sm btn-outline-primary variar-btn"
                onclick="toggleVariarSeries(this)"
                title="Activar variaciones por serie"
                style="font-size:var(--text-xs);">
          ⚡ Variar
        </button>

        <!-- Eliminar -->
        <button type="button" class="btn btn-sm btn-danger"
                onclick="this.closest('.ejercicio-entry').remove()"
                style="margin-left:auto;">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>

      <!-- Tabla de series variables (oculta por defecto) -->
      <div class="series-tabla" style="display:none; margin-top:var(--space-3);">
        <table style="width:auto; font-size:var(--text-sm); border-collapse:separate; border-spacing:0 4px;">
          <thead>
            <tr style="color:var(--color-text-secondary);">
              <th style="padding:0 var(--space-2); width:50px;">Serie</th>
              <th style="padding:0 var(--space-2); width:72px;">Reps</th>
              <th style="padding:0 var(--space-2); width:72px;">RPE</th>
              <th style="padding:0 var(--space-2); width:110px;">Carga</th>
            </tr>
          </thead>
          <tbody class="series-tbody"></tbody>
        </table>
      </div>

      <!-- Input oculto que lleva el JSON al servidor -->
      <input type="hidden" class="series-json-input" name="series_json_${bloqueIndex}[]">
    </div>
  `;

  ejercicios.insertAdjacentHTML("beforeend", html);
}

// ── CASCADING SELECTS ─────────────────────────────────────────────────────────

function actualizarSubcategoriasEjercicio(select) {
  const categoria = select.value;
  const entry = select.closest('.ejercicio-entry');
  const subSelect = entry.querySelector('.subcategoria-select-ej');
  subSelect.innerHTML = '<option value="">Subcategoría</option>';

  if (categoria && ejerciciosPorCategoria[categoria]) {
    Object.keys(ejerciciosPorCategoria[categoria]).forEach(sub => {
      subSelect.innerHTML += `<option value="${sub}">${sub}</option>`;
    });
  }
  actualizarEjerciciosEjercicio(subSelect);
}

function actualizarEjerciciosEjercicio(select) {
  const entry = select.closest('.ejercicio-entry');
  const categoria = entry.querySelector('.categoria-select-ej').value;
  const subcategoria = select.value;
  const ejSelect = entry.querySelector('.ejercicio-select');
  ejSelect.innerHTML = '<option value="">Ejercicio</option>';

  if (
    categoria &&
    subcategoria &&
    ejerciciosPorCategoria[categoria] &&
    ejerciciosPorCategoria[categoria][subcategoria]
  ) {
    ejerciciosPorCategoria[categoria][subcategoria].forEach(ej => {
      ejSelect.innerHTML += `<option value="${ej}">${ej}</option>`;
    });
  }
}

// ── MODO VARIAR ───────────────────────────────────────────────────────────────

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
  const repsGlobal = entry.querySelector('.reps-select').value;
  const rpeGlobal = entry.querySelector('.rpe-select').value;
  const cargaGlobal = entry.querySelector('.carga-input').value;

  // Conservar valores ya introducidos
  const existentes = Array.from(tbody.querySelectorAll('tr')).map(tr => ({
    reps: tr.querySelector('.reps-serie').value,
    rpe:  tr.querySelector('.rpe-serie').value,
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
        <td style="padding:2px var(--space-2); color:var(--color-text-secondary); font-weight:600;">S${i + 1}</td>
        <td style="padding:2px var(--space-2);">
          <select class="form-select form-select-sm reps-serie" style="width:68px;">
            ${buildRepsOptions(reps, '-')}
          </select>
        </td>
        <td style="padding:2px var(--space-2);">
          <select class="form-select form-select-sm rpe-serie" style="width:68px;">
            ${buildRpeOptions(rpe, '-')}
          </select>
        </td>
        <td style="padding:2px var(--space-2);">
          <input type="text" class="form-control form-control-sm carga-serie"
                 style="width:90px;" value="${carga}" placeholder="Carga">
        </td>
      </tr>
    `);
  }
}

// ── SERIALIZACIÓN AL ENVIAR ───────────────────────────────────────────────────

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

// ── INIT ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", function () {
  fetchEjercicios();

  const form = document.getElementById('formAsignarRutina');
  if (form) {
    form.addEventListener('submit', serializarEjercicios);
  }
});
