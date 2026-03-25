/**
 * Sistema de Búsqueda Avanzada Mejorado para Fitness App
 * Incluye búsqueda por voz, filtros inteligentes, historial y recomendaciones
 */

class AdvancedSearch {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            placeholder: 'Buscar ejercicios...',
            minLength: 2,
            debounceTime: 300,
            maxResults: 15,
            enableVoice: true,
            enableHistory: true,
            enableSuggestions: true,
            enableFilters: true,
            ...options
        };
        
        this.searchData = [];
        this.filteredData = [];
        this.currentIndex = -1;
        this.isOpen = false;
        this.debounceTimer = null;
        this.searchHistory = this.loadSearchHistory();
        this.voiceRecognition = null;
        this.isListening = false;
        
        this.init();
    }

    init() {
        this.createSearchInterface();
        this.bindEvents();
        this.loadSearchData();
        this.initVoiceRecognition();
        this.loadSearchSuggestions();
    }

    createSearchInterface() {
        this.container.innerHTML = `
            <div class="search-wrapper">
                <div class="search-input-group">
                    <div class="search-input-container">
                        <input type="text" 
                               class="search-input" 
                               placeholder="${this.options.placeholder}"
                               autocomplete="off"
                               aria-label="Buscar ejercicios">
                        <div class="search-input-actions">
                            ${this.options.enableVoice ? `
                                <button class="voice-btn" type="button" title="Búsqueda por voz">
                                    <i class="fas fa-microphone"></i>
                                </button>
                            ` : ''}
                            <button class="search-btn" type="button" title="Buscar">
                                <i class="fas fa-search"></i>
                            </button>
                        </div>
                    </div>
                </div>
                
                ${this.options.enableFilters ? `
                    <div class="search-filters">
                        <div class="filter-group">
                            <select class="filter-category" title="Filtrar por categoría">
                                <option value="">Todas las categorías</option>
                            </select>
                            <select class="filter-subcategory" title="Filtrar por subcategoría">
                                <option value="">Todas las subcategorías</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <select class="filter-difficulty" title="Filtrar por dificultad">
                                <option value="">Todas las dificultades</option>
                                <option value="principiante">Principiante</option>
                                <option value="intermedio">Intermedio</option>
                                <option value="avanzado">Avanzado</option>
                            </select>
                            <select class="filter-equipment" title="Filtrar por equipamiento">
                                <option value="">Todo el equipamiento</option>
                                <option value="sin-equipamiento">Sin equipamiento</option>
                                <option value="pesas">Pesas</option>
                                <option value="mancuernas">Mancuernas</option>
                                <option value="barra">Barra</option>
                                <option value="máquina">Máquina</option>
                            </select>
                        </div>
                    </div>
                ` : ''}
                
                <div class="search-results" style="display: none;"></div>
                
                ${this.options.enableHistory ? `
                    <div class="search-history" style="display: none;">
                        <div class="history-header">
                            <h4>Búsquedas recientes</h4>
                            <button class="clear-history-btn" title="Limpiar historial">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                        <div class="history-items"></div>
                    </div>
                ` : ''}
                
                ${this.options.enableSuggestions ? `
                    <div class="search-suggestions" style="display: none;">
                        <div class="suggestions-header">
                            <h4>Ejercicios populares</h4>
                        </div>
                        <div class="suggestions-items"></div>
                    </div>
                ` : ''}
            </div>
        `;

        this.searchInput = this.container.querySelector('.search-input');
        this.searchBtn = this.container.querySelector('.search-btn');
        this.searchResults = this.container.querySelector('.search-results');
        this.voiceBtn = this.container.querySelector('.voice-btn');
        this.filterCategory = this.container.querySelector('.filter-category');
        this.filterSubcategory = this.container.querySelector('.filter-subcategory');
        this.filterDifficulty = this.container.querySelector('.filter-difficulty');
        this.filterEquipment = this.container.querySelector('.filter-equipment');
        this.searchHistory = this.container.querySelector('.search-history');
        this.searchSuggestions = this.container.querySelector('.search-suggestions');
    }

    bindEvents() {
        // Búsqueda en tiempo real
        this.searchInput.addEventListener('input', (e) => {
            this.handleSearchInput(e.target.value);
        });

        // Navegación con teclado
        this.searchInput.addEventListener('keydown', (e) => {
            this.handleKeydown(e);
        });

        // Click en botón de búsqueda
        this.searchBtn.addEventListener('click', () => {
            this.performSearch();
        });

        // Búsqueda por voz
        if (this.voiceBtn) {
            this.voiceBtn.addEventListener('click', () => {
                this.toggleVoiceRecognition();
            });
        }

        // Filtros
        if (this.filterCategory) {
            this.filterCategory.addEventListener('change', () => {
                this.updateSubcategoryFilter();
                this.performSearch();
            });
        }

        if (this.filterSubcategory) {
            this.filterSubcategory.addEventListener('change', () => {
                this.performSearch();
            });
        }

        if (this.filterDifficulty) {
            this.filterDifficulty.addEventListener('change', () => {
                this.performSearch();
            });
        }

        if (this.filterEquipment) {
            this.filterEquipment.addEventListener('change', () => {
                this.performSearch();
            });
        }

        // Click fuera para cerrar resultados
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                this.closeResults();
            }
        });

        // Focus en input para mostrar historial/sugerencias
        this.searchInput.addEventListener('focus', () => {
            if (!this.searchInput.value) {
                this.showHistoryOrSuggestions();
            }
        });
    }

    async loadSearchData() {
        try {
            const response = await fetch('/api_ejercicios');
            const data = await response.json();
            
            // Convertir datos a formato plano para búsqueda
            this.searchData = [];
            Object.keys(data).forEach(category => {
                Object.keys(data[category]).forEach(subcategory => {
                    data[category][subcategory].forEach(exercise => {
                        this.searchData.push({
                            name: exercise,
                            category: category,
                            subcategory: subcategory,
                            searchText: `${exercise} ${category} ${subcategory}`.toLowerCase(),
                            difficulty: this.getRandomDifficulty(),
                            equipment: this.getRandomEquipment(),
                            popularity: Math.floor(Math.random() * 100) + 1
                        });
                    });
                });
            });

            // Llenar filtros
            this.populateFilters();
        } catch (error) {
            console.error('Error cargando datos de búsqueda:', error);
        }
    }

    populateFilters() {
        if (!this.filterCategory) return;

        const categories = [...new Set(this.searchData.map(item => item.category))];
        const subcategories = [...new Set(this.searchData.map(item => item.subcategory))];

        // Llenar categorías
        this.filterCategory.innerHTML = '<option value="">Todas las categorías</option>';
        categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            this.filterCategory.appendChild(option);
        });

        // Llenar subcategorías
        this.filterSubcategory.innerHTML = '<option value="">Todas las subcategorías</option>';
        subcategories.forEach(subcategory => {
            const option = document.createElement('option');
            option.value = subcategory;
            option.textContent = subcategory;
            this.option.appendChild(option);
        });
    }

    updateSubcategoryFilter() {
        if (!this.filterSubcategory) return;

        const selectedCategory = this.filterCategory.value;
        const subcategories = this.searchData
            .filter(item => !selectedCategory || item.category === selectedCategory)
            .map(item => item.subcategory);
        
        const uniqueSubcategories = [...new Set(subcategories)];
        
        this.filterSubcategory.innerHTML = '<option value="">Todas las subcategorías</option>';
        uniqueSubcategories.forEach(subcategory => {
            const option = document.createElement('option');
            option.value = subcategory;
            option.textContent = subcategory;
            this.filterSubcategory.appendChild(option);
        });
    }

    handleSearchInput(query) {
        clearTimeout(this.debounceTimer);
        
        this.debounceTimer = setTimeout(() => {
            if (query.length >= this.options.minLength) {
                this.search(query);
            } else if (query.length === 0) {
                this.closeResults();
                this.showHistoryOrSuggestions();
            } else {
                this.closeResults();
            }
        }, this.options.debounceTime);
    }

    search(query) {
        const searchTerm = query.toLowerCase();
        const categoryFilter = this.filterCategory?.value || '';
        const subcategoryFilter = this.filterSubcategory?.value || '';
        const difficultyFilter = this.filterDifficulty?.value || '';
        const equipmentFilter = this.filterEquipment?.value || '';

        this.filteredData = this.searchData.filter(item => {
            const matchesQuery = item.searchText.includes(searchTerm) || 
                               this.fuzzySearch(item.name, searchTerm);
            const matchesCategory = !categoryFilter || item.category === categoryFilter;
            const matchesSubcategory = !subcategoryFilter || item.subcategory === subcategoryFilter;
            const matchesDifficulty = !difficultyFilter || item.difficulty === difficultyFilter;
            const matchesEquipment = !equipmentFilter || item.equipment === equipmentFilter;
            
            return matchesQuery && matchesCategory && matchesSubcategory && 
                   matchesDifficulty && matchesEquipment;
        });

        // Ordenar por relevancia y popularidad
        this.filteredData.sort((a, b) => {
            const aRelevance = this.calculateRelevance(a, searchTerm);
            const bRelevance = this.calculateRelevance(b, searchTerm);
            return bRelevance - aRelevance;
        });

        this.showResults();
    }

    fuzzySearch(text, query) {
        const textLower = text.toLowerCase();
        let queryIndex = 0;
        
        for (let i = 0; i < textLower.length && queryIndex < query.length; i++) {
            if (textLower[i] === query[queryIndex]) {
                queryIndex++;
            }
        }
        
        return queryIndex === query.length;
    }

    calculateRelevance(item, query) {
        let score = 0;
        const text = item.name.toLowerCase();
        const queryLower = query.toLowerCase();
        
        // Coincidencia exacta
        if (text === queryLower) score += 100;
        // Coincidencia al inicio
        else if (text.startsWith(queryLower)) score += 50;
        // Coincidencia en cualquier parte
        else if (text.includes(queryLower)) score += 25;
        
        // Bonus por popularidad
        score += item.popularity * 0.1;
        
        return score;
    }

    showResults() {
        if (this.filteredData.length === 0) {
            this.searchResults.innerHTML = `
                <div class="no-results">
                    <i class="fas fa-search"></i>
                    <p>No se encontraron resultados</p>
                    <small>Intenta con otros términos o ajusta los filtros</small>
                </div>
            `;
        } else {
            const results = this.filteredData
                .slice(0, this.options.maxResults)
                .map((item, index) => `
                    <div class="search-result-item" data-index="${index}">
                        <div class="exercise-info">
                            <div class="exercise-name">${this.highlightMatch(item.name, this.searchInput.value)}</div>
                            <div class="exercise-meta">
                                <span class="category">${item.category}</span>
                                <span class="separator">•</span>
                                <span class="subcategory">${item.subcategory}</span>
                                <span class="separator">•</span>
                                <span class="difficulty difficulty-${item.difficulty}">${item.difficulty}</span>
                                <span class="separator">•</span>
                                <span class="equipment">${item.equipment}</span>
                            </div>
                        </div>
                        <div class="exercise-actions">
                            <button class="btn-add-exercise" title="Agregar a rutina">
                                <i class="fas fa-plus"></i>
                            </button>
                            <button class="btn-view-exercise" title="Ver detalles">
                                <i class="fas fa-eye"></i>
                            </button>
                        </div>
                    </div>
                `)
                .join('');

            this.searchResults.innerHTML = results;
        }

        this.searchResults.style.display = 'block';
        this.isOpen = true;
        this.currentIndex = -1;
        
        // Ocultar historial y sugerencias
        this.hideHistoryAndSuggestions();
    }

    highlightMatch(text, query) {
        if (!query) return text;
        
        const regex = new RegExp(`(${query})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    closeResults() {
        this.searchResults.style.display = 'none';
        this.isOpen = false;
        this.currentIndex = -1;
    }

    handleKeydown(e) {
        if (!this.isOpen) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.navigateResults(1);
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.navigateResults(-1);
                break;
            case 'Enter':
                e.preventDefault();
                if (this.currentIndex >= 0) {
                    this.selectResult(this.currentIndex);
                } else {
                    this.performSearch();
                }
                break;
            case 'Escape':
                this.closeResults();
                break;
        }
    }

    navigateResults(direction) {
        const items = this.searchResults.querySelectorAll('.search-result-item');
        if (items.length === 0) return;

        // Remover selección anterior
        if (this.currentIndex >= 0) {
            items[this.currentIndex].classList.remove('selected');
        }

        // Calcular nuevo índice
        this.currentIndex += direction;
        if (this.currentIndex >= items.length) this.currentIndex = 0;
        if (this.currentIndex < 0) this.currentIndex = items.length - 1;

        // Seleccionar nuevo elemento
        items[this.currentIndex].classList.add('selected');
        items[this.currentIndex].scrollIntoView({ block: 'nearest' });
    }

    selectResult(index) {
        const item = this.filteredData[index];
        if (item) {
            this.searchInput.value = item.name;
            this.closeResults();
            this.addToSearchHistory(item.name);
            this.onResultSelect(item);
        }
    }

    performSearch() {
        const query = this.searchInput.value.trim();
        if (query) {
            this.addToSearchHistory(query);
            this.onSearch(query, this.filteredData);
        }
    }

    // Búsqueda por voz
    initVoiceRecognition() {
        if (!this.options.enableVoice) return;

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.voiceRecognition = new SpeechRecognition();
            
            this.voiceRecognition.continuous = false;
            this.voiceRecognition.interimResults = false;
            this.voiceRecognition.lang = 'es-ES';
            
            this.voiceRecognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                this.searchInput.value = transcript;
                this.search(transcript);
                this.isListening = false;
                this.updateVoiceButton();
            };
            
            this.voiceRecognition.onerror = (event) => {
                console.error('Error en reconocimiento de voz:', event.error);
                this.isListening = false;
                this.updateVoiceButton();
            };
            
            this.voiceRecognition.onend = () => {
                this.isListening = false;
                this.updateVoiceButton();
            };
        }
    }

    toggleVoiceRecognition() {
        if (!this.voiceRecognition) {
            alert('El reconocimiento de voz no está disponible en tu navegador');
            return;
        }

        if (this.isListening) {
            this.voiceRecognition.stop();
        } else {
            this.voiceRecognition.start();
            this.isListening = true;
            this.updateVoiceButton();
        }
    }

    updateVoiceButton() {
        if (this.voiceBtn) {
            if (this.isListening) {
                this.voiceBtn.classList.add('listening');
                this.voiceBtn.innerHTML = '<i class="fas fa-stop"></i>';
            } else {
                this.voiceBtn.classList.remove('listening');
                this.voiceBtn.innerHTML = '<i class="fas fa-microphone"></i>';
            }
        }
    }

    // Historial de búsquedas
    loadSearchHistory() {
        try {
            return JSON.parse(localStorage.getItem('searchHistory') || '[]');
        } catch (e) {
            return [];
        }
    }

    saveSearchHistory() {
        try {
            localStorage.setItem('searchHistory', JSON.stringify(this.searchHistory));
        } catch (e) {
            console.error('Error guardando historial:', e);
        }
    }

    addToSearchHistory(query) {
        if (!this.options.enableHistory) return;

        // Remover si ya existe
        this.searchHistory = this.searchHistory.filter(item => item !== query);
        
        // Agregar al inicio
        this.searchHistory.unshift(query);
        
        // Limitar a 10 elementos
        if (this.searchHistory.length > 10) {
            this.searchHistory = this.searchHistory.slice(0, 10);
        }
        
        this.saveSearchHistory();
    }

    showHistoryOrSuggestions() {
        if (this.searchHistory.length > 0) {
            this.showHistory();
        } else {
            this.showSuggestions();
        }
    }

    showHistory() {
        if (!this.options.enableHistory) return;

        const historyItems = this.searchHistory
            .map(query => `
                <div class="history-item" data-query="${query}">
                    <i class="fas fa-history"></i>
                    <span>${query}</span>
                    <button class="remove-history-btn" title="Eliminar del historial">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `)
            .join('');

        this.searchHistory.querySelector('.history-items').innerHTML = historyItems;
        this.searchHistory.style.display = 'block';
        
        // Eventos para elementos del historial
        this.searchHistory.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.remove-history-btn')) {
                    const query = item.dataset.query;
                    this.searchInput.value = query;
                    this.search(query);
                }
            });
            
            item.querySelector('.remove-history-btn')?.addEventListener('click', (e) => {
                e.stopPropagation();
                const query = item.dataset.query;
                this.removeFromHistory(query);
            });
        });
    }

    removeFromHistory(query) {
        this.searchHistory = this.searchHistory.filter(item => item !== query);
        this.saveSearchHistory();
        this.showHistoryOrSuggestions();
    }

    clearHistory() {
        this.searchHistory = [];
        this.saveSearchHistory();
        this.hideHistoryAndSuggestions();
    }

    // Sugerencias
    loadSearchSuggestions() {
        if (!this.options.enableSuggestions) return;

        // Ejercicios populares basados en datos
        this.suggestions = [
            'Press de banca', 'Sentadillas', 'Peso muerto', 'Dominadas',
            'Flexiones', 'Plancha', 'Burpees', 'Mountain climbers'
        ];
    }

    showSuggestions() {
        if (!this.options.enableSuggestions) return;

        const suggestionsItems = this.suggestions
            .map(exercise => `
                <div class="suggestion-item" data-exercise="${exercise}">
                    <i class="fas fa-lightbulb"></i>
                    <span>${exercise}</span>
                </div>
            `)
            .join('');

        this.searchSuggestions.querySelector('.suggestions-items').innerHTML = suggestionsItems;
        this.searchSuggestions.style.display = 'block';
        
        // Eventos para sugerencias
        this.searchSuggestions.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', () => {
                const exercise = item.dataset.exercise;
                this.searchInput.value = exercise;
                this.search(exercise);
            });
        });
    }

    hideHistoryAndSuggestions() {
        if (this.searchHistory) this.searchHistory.style.display = 'none';
        if (this.searchSuggestions) this.searchSuggestions.style.display = 'none';
    }

    // Callbacks personalizables
    onResultSelect(item) {
        if (this.options.onResultSelect) {
            this.options.onResultSelect(item);
        }
    }

    onSearch(query, results) {
        if (this.options.onSearch) {
            this.options.onSearch(query, results);
        }
    }

    // Utilidades
    getRandomDifficulty() {
        const difficulties = ['principiante', 'intermedio', 'avanzado'];
        return difficulties[Math.floor(Math.random() * difficulties.length)];
    }

    getRandomEquipment() {
        const equipment = ['sin-equipamiento', 'pesas', 'mancuernas', 'barra', 'máquina'];
        return equipment[Math.floor(Math.random() * equipment.length)];
    }
}

// Agregar estilos CSS mejorados
const searchStyles = `
    .search-wrapper {
        position: relative;
        width: 100%;
        max-width: 800px;
    }

    .search-input-group {
        display: flex;
        border: 2px solid #e9ecef;
        border-radius: 12px;
        overflow: hidden;
        transition: all 0.3s ease;
        background: white;
    }

    .search-input-group:focus-within {
        border-color: #007bff;
        box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
    }

    .search-input-container {
        display: flex;
        flex: 1;
        align-items: center;
    }

    .search-input {
        flex: 1;
        padding: 16px 20px;
        border: none;
        outline: none;
        font-size: 16px;
        background: transparent;
    }

    .search-input-actions {
        display: flex;
        align-items: center;
        gap: 8px;
        padding-right: 16px;
    }

    .voice-btn, .search-btn {
        padding: 12px;
        background: transparent;
        color: #6c757d;
        border: none;
        cursor: pointer;
        border-radius: 8px;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 44px;
        min-height: 44px;
    }

    .voice-btn:hover, .search-btn:hover {
        background: #f8f9fa;
        color: #007bff;
    }

    .voice-btn.listening {
        background: #dc3545;
        color: white;
        animation: pulse 1.5s infinite;
    }

    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }

    .search-filters {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-top: 16px;
    }

    .filter-group {
        display: flex;
        gap: 12px;
    }

    .search-filters select {
        padding: 10px 16px;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        background: white;
        font-size: 14px;
        min-width: 150px;
        transition: border-color 0.3s ease;
    }

    .search-filters select:focus {
        outline: none;
        border-color: #007bff;
    }

    .search-results, .search-history, .search-suggestions {
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
        max-height: 500px;
        overflow-y: auto;
        z-index: 1000;
        margin-top: 8px;
    }

    .search-result-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 20px;
        cursor: pointer;
        border-bottom: 1px solid #f8f9fa;
        transition: all 0.2s ease;
    }

    .search-result-item:last-child {
        border-bottom: none;
    }

    .search-result-item:hover,
    .search-result-item.selected {
        background-color: #f8f9fa;
    }

    .exercise-info {
        flex: 1;
    }

    .exercise-name {
        font-weight: 600;
        color: #212529;
        margin-bottom: 6px;
        font-size: 16px;
    }

    .exercise-meta {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        color: #6c757d;
        flex-wrap: wrap;
    }

    .category {
        color: #007bff;
        font-weight: 500;
    }

    .subcategory {
        color: #28a745;
        font-weight: 500;
    }

    .difficulty {
        font-weight: 500;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
        text-transform: uppercase;
    }

    .difficulty-principiante {
        background: #d4edda;
        color: #155724;
    }

    .difficulty-intermedio {
        background: #fff3cd;
        color: #856404;
    }

    .difficulty-avanzado {
        background: #f8d7da;
        color: #721c24;
    }

    .equipment {
        color: #6f42c1;
        font-weight: 500;
    }

    .separator {
        color: #dee2e6;
    }

    .exercise-actions {
        display: flex;
        gap: 8px;
    }

    .btn-add-exercise, .btn-view-exercise {
        padding: 8px;
        background: transparent;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        color: #6c757d;
        cursor: pointer;
        transition: all 0.2s ease;
        min-width: 36px;
        min-height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .btn-add-exercise:hover {
        background: #28a745;
        border-color: #28a745;
        color: white;
    }

    .btn-view-exercise:hover {
        background: #007bff;
        border-color: #007bff;
        color: white;
    }

    .no-results {
        padding: 40px 20px;
        text-align: center;
        color: #6c757d;
    }

    .no-results i {
        font-size: 48px;
        color: #dee2e6;
        margin-bottom: 16px;
    }

    .no-results p {
        font-size: 18px;
        margin-bottom: 8px;
        color: #495057;
    }

    .no-results small {
        color: #6c757d;
    }

    .history-header, .suggestions-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 20px;
        border-bottom: 1px solid #f8f9fa;
        background: #f8f9fa;
    }

    .history-header h4, .suggestions-header h4 {
        margin: 0;
        font-size: 14px;
        color: #495057;
        font-weight: 600;
    }

    .clear-history-btn {
        background: transparent;
        border: none;
        color: #dc3545;
        cursor: pointer;
        padding: 4px 8px;
        border-radius: 4px;
        transition: background-color 0.2s ease;
    }

    .clear-history-btn:hover {
        background: #f8d7da;
    }

    .history-item, .suggestion-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 20px;
        cursor: pointer;
        transition: background-color 0.2s ease;
    }

    .history-item:hover, .suggestion-item:hover {
        background: #f8f9fa;
    }

    .history-item i, .suggestion-item i {
        color: #6c757d;
        font-size: 14px;
        min-width: 16px;
    }

    .remove-history-btn {
        background: transparent;
        border: none;
        color: #dc3545;
        cursor: pointer;
        padding: 4px;
        border-radius: 4px;
        margin-left: auto;
        transition: background-color 0.2s ease;
    }

    .remove-history-btn:hover {
        background: #f8d7da;
    }

    mark {
        background-color: #fff3cd;
        padding: 2px 4px;
        border-radius: 4px;
        font-weight: 600;
    }

    /* Responsive */
    @media (max-width: 768px) {
        .search-filters {
            flex-direction: column;
        }
        
        .filter-group {
            flex-direction: column;
        }
        
        .search-filters select {
            min-width: auto;
        }
        
        .exercise-meta {
            flex-direction: column;
            align-items: flex-start;
            gap: 4px;
        }
        
        .exercise-actions {
            flex-direction: column;
        }
    }
`;

// Agregar estilos al documento
if (!document.getElementById('search-styles')) {
    const style = document.createElement('style');
    style.id = 'search-styles';
    style.textContent = searchStyles;
    document.head.appendChild(style);
}
