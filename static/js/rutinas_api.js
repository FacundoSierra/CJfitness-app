let ejerciciosPorCategoria = {};

async function fetchEjercicios() {
    try {
        const response = await fetch("/api_ejercicios");
        if (!response.ok) throw new Error("Error al cargar los ejercicios");
        const data = await response.json();
        ejerciciosPorCategoria = data;
    } catch (error) {
        console.error("Error cargando ejercicios:", error);
    }
}

function agregarBloque(dia) {
    const contenedor = document.getElementById(`bloques-${dia}`);
    const bloqueIndex = contenedor.children.length + 1;

    const bloqueHTML = `
    <div class="bloque-container">
        <div class="d-flex justify-content-between align-items-center">
            <h5>Bloque ${bloqueIndex}</h5>
            <button type="button" class="btn btn-sm btn-danger" onclick="this.closest('.bloque-container').remove()">Eliminar bloque</button>
        </div>

        <div class="row mb-3">
            <div class="col-md-4">
                <label class="form-label">Categoría</label>
                <select class="form-select categoria-select" 
                        name="bloque_${dia}_${bloqueIndex}_categoria"
                        onchange="actualizarSubcategorias(this)">
                    <option value="">Selecciona una categoría</option>
                    ${Object.keys(ejerciciosPorCategoria).map(cat => `<option value="${cat}">${cat}</option>`).join('')}
                </select>
            </div>
            <div class="col-md-4">
                <label class="form-label">Subcategoría</label>
                <select class="form-select subcategoria-select" 
                        name="bloque_${dia}_${bloqueIndex}_subcategoria"
                        onchange="actualizarEjercicios(this)">
                    <option value="">Selecciona una subcategoría</option>
                </select>
            </div>
        </div>

        <div class="ejercicios">
            ${crearEjercicioHTML(dia, bloqueIndex)}
        </div>
        <button type="button" class="btn btn-outline-secondary btn-sm mt-2" onclick="agregarEjercicio(this)">➕ Añadir Ejercicio</button>
    </div>`;

    contenedor.insertAdjacentHTML('beforeend', bloqueHTML);
}

function crearEjercicioHTML(dia, bloqueIndex) {
    return `
    <div class="ejercicio-entry input-group mt-2">
        <select class="form-select me-2 ejercicio-select" name="ejercicio_${dia}_${bloqueIndex}[]">
            <option value="">Selecciona un ejercicio</option>
        </select>
        <input type="text" class="form-control me-2" name="series_${dia}_${bloqueIndex}[]" placeholder="Series/Rep/Descanso">
        <input type="text" class="form-control me-2" name="rpe_${dia}_${bloqueIndex}[]" placeholder="RPE">
        <input type="text" class="form-control me-2" name="carga_${dia}_${bloqueIndex}[]" placeholder="Carga">
        <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('.ejercicio-entry').remove()">❌</button>
    </div>`;
}

function agregarEjercicio(btn) {
    const bloque = btn.closest('.bloque-container');
    const bloqueIndex = Array.from(bloque.parentNode.children).indexOf(bloque) + 1;
    const dia = bloque.parentNode.id.replace('bloques-', '');

    bloque.querySelector('.ejercicios').insertAdjacentHTML('beforeend', crearEjercicioHTML(dia, bloqueIndex));
    actualizarEjercicios(bloque.querySelector('.subcategoria-select'));
}

function actualizarSubcategorias(selectCategoria) {
    const categoria = selectCategoria.value;
    const bloque = selectCategoria.closest('.bloque-container');
    const subcategoriaSelect = bloque.querySelector('.subcategoria-select');
    subcategoriaSelect.innerHTML = '<option value="">Selecciona una subcategoría</option>';

    if (categoria && ejerciciosPorCategoria[categoria]) {
        Object.keys(ejerciciosPorCategoria[categoria]).forEach(sub => {
            const option = document.createElement('option');
            option.value = sub;
            option.textContent = sub;
            subcategoriaSelect.appendChild(option);
        });
    }

    actualizarEjercicios(subcategoriaSelect);
}

function actualizarEjercicios(selectSubcategoria) {
    const subcategoria = selectSubcategoria.value;
    const bloque = selectSubcategoria.closest('.bloque-container');
    const categoria = bloque.querySelector('.categoria-select').value;
    const selectsEjercicios = bloque.querySelectorAll('.ejercicio-select');

    selectsEjercicios.forEach(sel => {
        sel.innerHTML = '<option value="">Selecciona un ejercicio</option>';
        if (categoria && subcategoria && ejerciciosPorCategoria[categoria] && ejerciciosPorCategoria[categoria][subcategoria]) {
            ejerciciosPorCategoria[categoria][subcategoria].forEach(ej => {
                const option = document.createElement('option');
                option.value = ej;
                option.textContent = ej;
                sel.appendChild(option);
            });
        }
    });
}

document.addEventListener("DOMContentLoaded", fetchEjercicios);


