/**
 * utils_fitness.js — helpers compartidos entre templates de rutinas y progresos.
 * Incluir con: <script src="{{ url_for('static', filename='js/utils_fitness.js') }}"></script>
 */

/**
 * Parsea un token de serie con formato "S1: 10r 80 kg RPE7"
 * Devuelve { num, reps, carga, rpe }
 */
function parseSerieStr(parte) {
    if (!parte || !parte.trim()) return { num: '?', reps: '', carga: '', rpe: '' };
    const num   = parte.includes(':') ? parte.split(':')[0].trim() : '?';
    const after = (parte.includes(':') ? parte.split(':')[1] : parte).trim();
    const toks  = after.split(' ');
    const reps  = (toks[0] || '').replace(/r$/i, '');
    const kgIdx = toks.indexOf('kg');
    const carga = kgIdx > 0 ? toks[kgIdx - 1] : '';
    const rpeIdx = toks.findIndex(t => t.toUpperCase().startsWith('RPE'));
    const rpe   = rpeIdx >= 0 ? toks[rpeIdx].replace(/^RPE/i, '') : '';
    return { num, reps, carga, rpe };
}

/**
 * Genera opciones <option> para selector de carga (0–100 kg en pasos de 0.5).
 * @param {string|number} selected - valor actualmente seleccionado
 */
function buildCargaOpts(selected) {
    let html = '<option value="">— kg</option>';
    for (let i = 0; i <= 200; i++) {
        const v = i / 2;
        const sel = String(selected) === String(v) ? 'selected' : '';
        html += `<option value="${v}" ${sel}>${v} kg</option>`;
    }
    return html;
}
