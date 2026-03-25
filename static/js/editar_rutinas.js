let ejerciciosPorCategoria = {};

async function fetchEjercicios() {
  try {
    const res = await fetch("/api_ejercicios");
    ejerciciosPorCategoria = await res.json();
  } catch (err) {
    console.error("Error cargando ejercicios desde la API:", err);
  }
}

function buscarRutinaPorFecha(fecha) {
  console.log("🔍 Buscando rutina para fecha:", fecha, "tipo:", typeof fecha);
  console.log("🔍 Rutinas disponibles:", rutinasPorFecha);
  
  for (const semana of rutinasPorFecha) {
    for (const rutina of semana.rutinas) {
      console.log("🔍 Comparando con rutina fecha:", rutina.fecha, "tipo:", typeof rutina.fecha);
      if (rutina.fecha === fecha) {
        console.log("✅ Rutina encontrada:", rutina);
        return rutina;
      }
    }
  }
  console.log("❌ No se encontró rutina para fecha:", fecha);
  return null;
}

function abrirModalEdicion(fecha) {
  console.log("🟡 Abriendo edición para:", fecha);
  console.log("🟡 Rutinas disponibles:", rutinasPorFecha);
  
  const rutina = buscarRutinaPorFecha(fecha);
  console.log("🟡 Rutina encontrada:", rutina);
  
  if (!rutina) {
    alert("No se encontró la rutina para editar.");
    return;
  }

  document.getElementById("editarFechaTexto").innerText = fecha;
  document.getElementById("fechaEditarHidden").value = fecha;
  const container = document.getElementById("bloquesEditarContainer");
  container.innerHTML = "";

  // Si no hay bloques, crear uno vacío
  if (!rutina.bloques || rutina.bloques.length === 0) {
    agregarBloqueEditar(null, 1);
    return;
  }

  rutina.bloques.forEach((bloque, idx) => {
    const bloqueIndex = idx + 1;
    let ejerciciosHTML = "";

    if (bloque.ejercicios && bloque.ejercicios.length > 0) {
      bloque.ejercicios.forEach((e, i) => {
        // Preselecciona la categoría y subcategoría (si existen)
        const catValue = e.categoria || "";
        const subcatValue = e.subcategoria || "";
        const ejercicioValue = e.ejercicio?.nombre || e.nombre_manual || "";
        const seriesValue = e.series_reps || "";
        const rpeValue = e.rpe || "";
        const cargaValue = e.carga || "";

        const categoriaOptions = Object.keys(ejerciciosPorCategoria)
          .map(cat => `<option value="${cat}" ${cat === catValue ? 'selected' : ''}>${cat}</option>`)
          .join("");

        const subcatKeys = catValue ? Object.keys(ejerciciosPorCategoria[catValue] || {}) : [];
        const subcategoriaOptions = subcatKeys
          .map(subcat => `<option value="${subcat}" ${subcat === subcatValue ? 'selected' : ''}>${subcat}</option>`)
          .join("");

        const ejercicioOptions = (catValue && subcatValue && ejerciciosPorCategoria[catValue]?.[subcatValue])
          ? ejerciciosPorCategoria[catValue][subcatValue]
              .map(ej => {
                const selected = (ej === ejercicioValue) ? 'selected' : '';
                return `<option value="${ej}" ${selected}>${ej}</option>`;
              }).join("")
          : `<option value="${ejercicioValue}" selected>${ejercicioValue}</option>`;

        ejerciciosHTML += `
          <div class="input-group mt-2 ejercicio-entry align-items-center">
            <select class="form-select categoria-select-ej" name="categoria_ej_${bloqueIndex}[]" style="max-width:120px;" onchange="actualizarSubcategoriasEjercicioEditar(this)">
              <option value="">Categoría</option>
              ${categoriaOptions}
            </select>
            <select class="form-select subcategoria-select-ej" name="subcategoria_ej_${bloqueIndex}[]" style="max-width:120px;" onchange="actualizarEjerciciosEjercicioEditar(this)">
              <option value="">Subcategoría</option>
              ${subcategoriaOptions}
            </select>
            <select class="form-select ejercicio-select" name="ejercicio_${bloqueIndex}[]" style="max-width:140px;">
              <option value="">Ejercicio</option>
              ${ejercicioOptions}
            </select>
            <input type="text" class="form-control" name="series_${bloqueIndex}[]" placeholder="Series/Reps" value="${seriesValue}">
            <input type="text" class="form-control" name="rpe_${bloqueIndex}[]" placeholder="RPE" value="${rpeValue}">
            <input type="text" class="form-control" name="carga_${bloqueIndex}[]" placeholder="Carga" value="${cargaValue}">

            <button type="button" class="btn btn-sm btn-danger" onclick="this.closest('.ejercicio-entry').remove()">❌</button>
          </div>
        `;
      });
    }

    container.insertAdjacentHTML("beforeend", `
      <div class="bloque-container border p-3 rounded mb-3">
        <div class="d-flex justify-content-between align-items-center">
          <strong>Bloque ${bloqueIndex}</strong>
          <button type="button" class="btn-close" onclick="this.closest('.bloque-container').remove()"></button>
        </div>
        
        <!-- Categoría del bloque -->
        <div class="mb-3">
          <label class="form-label fw-bold">Categoría del Bloque:</label>
          <select class="form-select" name="categoria_bloque_${bloqueIndex}" required>
            <option value="">Selecciona categoría</option>
            <option value="Calentamiento" ${bloque.categoria == 'Calentamiento' ? 'selected' : ''}>Calentamiento</option>
            <option value="Fuerza" ${bloque.categoria == 'Fuerza' ? 'selected' : ''}>Fuerza</option>
            <option value="Cardio" ${bloque.categoria == 'Cardio' ? 'selected' : ''}>Cardio</option>
            <option value="Flexibilidad" ${bloque.categoria == 'Flexibilidad' ? 'selected' : ''}>Flexibilidad</option>
            <option value="Recuperación" ${bloque.categoria == 'Recuperación' ? 'selected' : ''}>Recuperación</option>
            <option value="General" ${bloque.categoria == 'General' ? 'selected' : ''}>General</option>
          </select>
        </div>
        
        <div class="ejercicios mt-3">
          ${ejerciciosHTML}
        </div>
        <button type="button" class="btn btn-outline-secondary btn-sm mt-2" onclick="agregarEjercicioEditar(this, ${bloqueIndex})">➕ Añadir Ejercicio</button>
      </div>
    `);
  });
}

// Función para añadir ejercicio en editar (igual que en asignar)
function agregarEjercicioEditar(btn, bloqueIndex) {
  const bloque = btn.closest('.bloque-container');
  const ejercicios = bloque.querySelector(".ejercicios");

  const nuevoEjercicio = `
    <div class="input-group mt-2 ejercicio-entry align-items-center">
      <select class="form-select categoria-select-ej" name="categoria_ej_${bloqueIndex}[]" style="max-width:120px;" onchange="actualizarSubcategoriasEjercicioEditar(this)">
        <option value="">Categoría</option>
        ${Object.keys(ejerciciosPorCategoria).map(cat => `<option value="${cat}">${cat}</option>`).join('')}
      </select>
      <select class="form-select subcategoria-select-ej" name="subcategoria_ej_${bloqueIndex}[]" style="max-width:120px;" onchange="actualizarEjerciciosEjercicioEditar(this)">
        <option value="">Subcategoría</option>
      </select>
      <select class="form-select ejercicio-select" name="ejercicio_${bloqueIndex}[]" style="max-width:140px;">
        <option value="">Ejercicio</option>
      </select>
      <input type="text" class="form-control" name="series_${bloqueIndex}[]" placeholder="Series/Reps">
      <input type="text" class="form-control" name="rpe_${bloqueIndex}[]" placeholder="RPE">
      <input type="text" class="form-control" name="carga_${bloqueIndex}[]" placeholder="Carga">

      <button type="button" class="btn btn-sm btn-danger" onclick="this.closest('.ejercicio-entry').remove()">❌</button>
    </div>
  `;

  ejercicios.insertAdjacentHTML("beforeend", nuevoEjercicio);
}

// Actualiza subcategorías al cambiar categoría
function actualizarSubcategoriasEjercicioEditar(select) {
  const categoria = select.value;
  const ejercicioEntry = select.closest('.ejercicio-entry');
  const subcategoriaSelect = ejercicioEntry.querySelector('.subcategoria-select-ej');
  subcategoriaSelect.innerHTML = '<option value="">Subcategoría</option>';

  if (categoria && ejerciciosPorCategoria[categoria]) {
    Object.keys(ejerciciosPorCategoria[categoria]).forEach(sub => {
      subcategoriaSelect.innerHTML += `<option value="${sub}">${sub}</option>`;
    });
  }
  actualizarEjerciciosEjercicioEditar(subcategoriaSelect);
}

// Actualiza ejercicios al cambiar subcategoría
function actualizarEjerciciosEjercicioEditar(select) {
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

// Función para agregar bloque en editar
function agregarBloqueEditar(btn, bloqueIndex) {
  const container = document.getElementById("bloquesEditarContainer");
  const nuevoBloqueIndex = document.querySelectorAll(".bloque-container").length + 1;

  const bloqueHTML = `
    <div class="bloque-container border p-3 rounded mb-3">
      <div class="d-flex justify-content-between align-items-center">
        <strong>Bloque ${nuevoBloqueIndex}</strong>
        <button type="button" class="btn-close" onclick="this.closest('.bloque-container').remove()"></button>
      </div>
      
      <!-- Categoría del bloque -->
      <div class="mb-3">
        <label class="form-label fw-bold">Categoría del Bloque:</label>
        <select class="form-select" name="categoria_bloque_${nuevoBloqueIndex}" required>
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
      <button type="button" class="btn btn-sm btn-outline-secondary mt-2" onclick="agregarEjercicioEditar(this, ${nuevoBloqueIndex})">➕ Añadir Ejercicio</button>
    </div>
  `;

  container.insertAdjacentHTML("beforeend", bloqueHTML);
}

document.addEventListener("DOMContentLoaded", fetchEjercicios);

