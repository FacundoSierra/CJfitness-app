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

function agregarBloque() {
  const index = document.querySelectorAll(".bloque-container").length + 1;

  const bloqueHTML = `
    <div class="bloque-container border p-3 rounded mb-3">
      <div class="d-flex justify-content-between align-items-center">
        <strong>Bloque ${index}</strong>
        <button type="button" class="btn-close" onclick="this.closest('.bloque-container').remove()"></button>
      </div>
      
      <!-- Categoría del bloque -->
      <div class="mb-3">
        <label class="form-label fw-bold">Categoría del Bloque:</label>
        <select class="form-select" name="categoria_bloque_${index}" required>
          <option value="">Selecciona categoría</option>
          <option value="Calentamiento">Calentamiento</option>
          <option value="Fuerza">Fuerza</option>
          <option value="Cardio">Cardio</option>
          <option value="Flexibilidad">Flexibilidad</option>
          <option value="Recuperación">Recuperación</option>
          <option value="General">General</option>
        </select>
      </div>
      
      <div class="ejercicios mt-3"></div>
      <button type="button" class="btn btn-sm btn-outline-secondary mt-2" onclick="agregarEjercicio(this, ${index})">➕ Añadir Ejercicio</button>
    </div>
  `;

  document.getElementById("contenedorBloques").insertAdjacentHTML("beforeend", bloqueHTML);
}

function agregarEjercicio(btn, bloqueIndex) {
  const bloque = btn.closest('.bloque-container');
  const ejercicios = bloque.querySelector(".ejercicios");

  const nuevoEjercicio = `
    <div class="input-group mt-2 ejercicio-entry align-items-center">
      <select class="form-select categoria-select-ej" name="categoria_ej_${bloqueIndex}[]" style="max-width:120px;" onchange="actualizarSubcategoriasEjercicio(this)">
        <option value="">Categoría</option>
        ${Object.keys(ejerciciosPorCategoria).map(cat => `<option value="${cat}">${cat}</option>`).join('')}
      </select>
      <select class="form-select subcategoria-select-ej" name="subcategoria_ej_${bloqueIndex}[]" style="max-width:120px;" onchange="actualizarEjerciciosEjercicio(this)">
        <option value="">Subcategoría</option>
      </select>
      <select class="form-select ejercicio-select" name="ejercicio_${bloqueIndex}[]" style="max-width:140px;">
        <option value="">Ejercicio</option>
      </select>
      <input type="number" class="form-control" name="series_${bloqueIndex}[]" placeholder="Series/Reps" min="0" max="25" step="any">
      <input type="number" class="form-control" name="rpe_${bloqueIndex}[]" placeholder="RPE" min="0" max="25" step="any">
      <input type="number" class="form-control" name="carga_${bloqueIndex}[]" placeholder="Carga" min="0" max="25" step="any">

      <button type="button" class="btn btn-sm btn-danger" onclick="this.closest('.ejercicio-entry').remove()">❌</button>
    </div>
  `;

  ejercicios.insertAdjacentHTML("beforeend", nuevoEjercicio);
}

// Nuevas funciones para selects individuales
function actualizarSubcategoriasEjercicio(select) {
  const categoria = select.value;
  const ejercicioEntry = select.closest('.ejercicio-entry');
  const subcategoriaSelect = ejercicioEntry.querySelector('.subcategoria-select-ej');
  subcategoriaSelect.innerHTML = '<option value="">Subcategoría</option>';

  if (categoria && ejerciciosPorCategoria[categoria]) {
    Object.keys(ejerciciosPorCategoria[categoria]).forEach(sub => {
      subcategoriaSelect.innerHTML += `<option value="${sub}">${sub}</option>`;
    });
  }
  actualizarEjerciciosEjercicio(subcategoriaSelect);
}

function actualizarEjerciciosEjercicio(select) {
  const ejercicioEntry = select.closest('.ejercicio-entry');
  const categoria = ejercicioEntry.querySelector('.categoria-select-ej').value;
  const subcategoria = select.value;
  const ejercicioSelect = ejercicioEntry.querySelector('.ejercicio-select');
  ejercicioSelect.innerHTML = '<option value="">Ejercicio</option>';

  if (
    categoria &&
    subcategoria &&
    ejerciciosPorCategoria[categoria] &&
    ejerciciosPorCategoria[categoria][subcategoria]
  ) {
    ejerciciosPorCategoria[categoria][subcategoria].forEach(ej => {
      ejercicioSelect.innerHTML += `<option value="${ej}">${ej}</option>`;
    });
  }
}

// Cargar ejercicios al inicio
document.addEventListener("DOMContentLoaded", fetchEjercicios);
