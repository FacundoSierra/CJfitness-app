/**
 * Sistema de Estadísticas en Tiem Real para Dashboard
 * Muestra métricas importantes de la aplicación
 */

class DashboardStats {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            refreshInterval: 30000, // 30 segundos
            showCharts: true,
            ...options
        };
        
        this.stats = {};
        this.charts = {};
        this.refreshTimer = null;
        
        this.init();
    }

    init() {
        this.createStatsInterface();
        this.loadInitialStats();
        this.startAutoRefresh();
    }

    createStatsInterface() {
        this.container.innerHTML = `
            <div class="row g-4">
                <!-- Tarjetas de estadísticas principales -->
                <div class="col-xl-3 col-md-6">
                    <div class="stat-card users-card">
                        <div class="stat-icon">
                            <i class="bi bi-people-fill"></i>
                        </div>
                        <div class="stat-content">
                            <h3 class="stat-number" id="total-users">-</h3>
                            <p class="stat-label">Usuarios Totales</p>
                            <div class="stat-change" id="users-change">
                                <span class="change-value">+0%</span>
                                <span class="change-period">este mes</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="col-xl-3 col-md-6">
                    <div class="stat-card exercises-card">
                        <div class="stat-icon">
                            <i class="bi bi-dumbbell-fill"></i>
                        </div>
                        <div class="stat-content">
                            <h3 class="stat-number" id="total-exercises">-</h3>
                            <p class="stat-label">Ejercicios</p>
                            <div class="stat-change" id="exercises-change">
                                <span class="change-value">+0%</span>
                                <span class="change-period">este mes</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="col-xl-3 col-md-6">
                    <div class="stat-card routines-card">
                        <div class="stat-icon">
                            <i class="bi bi-calendar-check-fill"></i>
                        </div>
                        <div class="stat-content">
                            <h3 class="stat-number" id="total-routines">-</h3>
                            <p class="stat-label">Rutinas Activas</p>
                            <div class="stat-change" id="routines-change">
                                <span class="change-value">+0%</span>
                                <span class="change-period">esta semana</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="col-xl-3 col-md-6">
                    <div class="stat-card payments-card">
                        <div class="stat-icon">
                            <i class="bi bi-credit-card-fill"></i>
                        </div>
                        <div class="stat-content">
                            <h3 class="stat-number" id="total-payments">-</h3>
                            <p class="stat-label">Pagos del Mes</p>
                            <div class="stat-change" id="payments-change">
                                <span class="change-value">+0%</span>
                                <span class="change-period">vs mes anterior</span>
                            </div>
                            <div class="stat-details" id="payments-details">
                                <small class="text-muted">€0 ingresos</small>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos y métricas detalladas -->
                <div class="col-xl-8">
                    <div class="chart-container">
                        <h5>Actividad de Usuarios</h5>
                        <canvas id="users-activity-chart"></canvas>
                    </div>
                </div>

                <div class="col-xl-4">
                    <div class="metrics-container">
                        <h5>Métricas Rápidas</h5>
                        <div class="metric-item">
                            <span class="metric-label">Usuarios Nuevos Hoy</span>
                            <span class="metric-value" id="new-users-today">-</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Ejercicios Más Populares</span>
                            <span class="metric-value" id="popular-exercises">-</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Rutinas Completadas</span>
                            <span class="metric-value" id="completed-routines">-</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-value" id="monthly-revenue">-</span>
                            <span class="metric-label">Ingresos del Mes</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-value" id="pending-payments">-</span>
                            <span class="metric-label">Pagos Pendientes</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.addStyles();
    }

    addStyles() {
        if (!document.getElementById('dashboard-stats-styles')) {
            const style = document.createElement('style');
            style.id = 'dashboard-stats-styles';
            style.textContent = `
                .stat-card {
                    background: white;
                    border-radius: 12px;
                    padding: 24px;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                    border-left: 4px solid #007bff;
                }

                .stat-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
                }

                .stat-card.users-card { border-left-color: #28a745; }
                .stat-card.exercises-card { border-left-color: #ffc107; }
                .stat-card.routines-card { border-left-color: #17a2b8; }
                .stat-card.payments-card { border-left-color: #dc3545; }

                .stat-icon {
                    float: left;
                    margin-right: 16px;
                    font-size: 2.5rem;
                    color: #007bff;
                }

                .stat-card.users-card .stat-icon { color: #28a745; }
                .stat-card.exercises-card .stat-icon { color: #ffc107; }
                .stat-card.routines-card .stat-icon { color: #17a2b8; }
                .stat-card.payments-card .stat-icon { color: #dc3545; }

                .stat-content {
                    overflow: hidden;
                }

                .stat-number {
                    font-size: 2rem;
                    font-weight: 700;
                    margin: 0;
                    color: #333;
                }

                .stat-label {
                    margin: 4px 0;
                    color: #666;
                    font-size: 0.9rem;
                }

                .stat-change {
                    font-size: 0.8rem;
                    margin-top: 8px;
                }

                .stat-details {
                    font-size: 0.75rem;
                    margin-top: 4px;
                }

                .change-value {
                    color: #28a745;
                    font-weight: 600;
                }

                .change-period {
                    color: #999;
                    margin-left: 4px;
                }

                .chart-container, .metrics-container {
                    background: white;
                    border-radius: 12px;
                    padding: 24px;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                    height: 300px;
                }

                .metrics-container h5, .chart-container h5 {
                    margin-bottom: 20px;
                    color: #333;
                    font-weight: 600;
                }

                .metric-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 0;
                    border-bottom: 1px solid #f0f0f0;
                }

                .metric-item:last-child {
                    border-bottom: none;
                }

                .metric-label {
                    color: #666;
                    font-size: 0.9rem;
                }

                .metric-value {
                    font-weight: 600;
                    color: #333;
                }

                .loading {
                    opacity: 0.6;
                }

                .pulse {
                    animation: pulse 1.5s infinite;
                }

                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.5; }
                    100% { opacity: 1; }
                }

                .loading-spinner {
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background: rgba(255, 255, 255, 0.9);
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                    z-index: 10;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    font-weight: 600;
                    color: #007bff;
                }

                .loading-spinner .spin {
                    animation: spin 1s linear infinite;
                }

                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }

                .stat-card.loading {
                    opacity: 0.6;
                    pointer-events: none;
                }
            `;
            document.head.appendChild(style);
        }
    }

    async loadInitialStats() {
        try {
            // Mostrar indicador de carga
            this.showLoading(true);
            
            await this.fetchStats();
            this.updateUI();
            
            if (this.options.showCharts) {
                this.createCharts();
            }
            
            // Mostrar mensaje de éxito
            this.showSuccess('Estadísticas actualizadas correctamente');
            
        } catch (error) {
            console.error('Error cargando estadísticas:', error);
            this.showError('Error cargando estadísticas');
        } finally {
            // Ocultar indicador de carga
            this.showLoading(false);
        }
    }

    showLoading(show) {
        const container = this.container;
        if (show) {
            container.classList.add('loading');
            // Agregar spinner si no existe
            if (!container.querySelector('.loading-spinner')) {
                const spinner = document.createElement('div');
                spinner.className = 'loading-spinner';
                spinner.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> Cargando estadísticas...';
                container.appendChild(spinner);
            }
        } else {
            container.classList.remove('loading');
            const spinner = container.querySelector('.loading-spinner');
            if (spinner) {
                spinner.remove();
            }
        }
    }

    async fetchStats() {
        try {
            // Obtener estadísticas reales de la API
            const response = await fetch('/api/stats/dashboard');
            if (!response.ok) {
                throw new Error('Error obteniendo estadísticas');
            }
            
            const data = await response.json();
            
            // Actualizar estadísticas con datos reales
            this.stats = {
                users: {
                    total: data.usuarios.total,
                    change: data.usuarios.cambio_mes,
                    newToday: data.usuarios.nuevos_hoy
                },
                exercises: {
                    total: data.ejercicios.total,
                    change: data.ejercicios.cambio_mes,
                    popular: data.ejercicios.mas_popular
                },
                routines: {
                    total: data.rutinas.total,
                    change: data.rutinas.cambio_semana,
                    completed: data.rutinas.esta_semana
                },
                payments: {
                    total: data.pagos.total_mes,
                    change: data.pagos.cambio_mes,
                    monthly: data.pagos.ingresos_mes,
                    pending: data.pagos.pendientes,
                    pagados: data.pagos.pagados_mes
                },
                activity: {
                    labels: data.actividad.labels,
                    data: data.actividad.data
                }
            };
            
            // Log de éxito
            console.log('✅ Estadísticas cargadas correctamente:', this.stats);
            
        } catch (error) {
            console.error('❌ Error cargando estadísticas:', error);
            
            // Fallback a datos básicos si hay error
            this.stats = {
                users: { total: 0, change: 0, newToday: 0 },
                exercises: { total: 0, change: 0, popular: 'N/A' },
                routines: { total: 0, change: 0, completed: 0 },
                payments: { total: 0, change: 0, monthly: 0 },
                activity: { labels: ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'], data: [0, 0, 0, 0, 0, 0, 0] }
            };
            
            // Mostrar error al usuario
            this.showError('Error cargando estadísticas. Mostrando datos básicos.');
        }
    }

    updateUI() {
        // Actualizar números principales
        document.getElementById('total-users').textContent = this.stats.users.total;
        document.getElementById('total-exercises').textContent = this.stats.exercises.total;
        document.getElementById('total-routines').textContent = this.stats.routines.total;
        document.getElementById('total-payments').textContent = `€${this.stats.payments.total}`;

        // Actualizar cambios
        document.getElementById('users-change').querySelector('.change-value').textContent = 
            `+${this.stats.users.change}%`;
        document.getElementById('exercises-change').querySelector('.change-value').textContent = 
            `+${this.stats.exercises.change}%`;
        document.getElementById('routines-change').querySelector('.change-value').textContent = 
            `+${this.stats.routines.change}%`;
        document.getElementById('payments-change').querySelector('.change-value').textContent = 
            `+${this.stats.payments.change}%`;

        // Actualizar métricas rápidas
        document.getElementById('new-users-today').textContent = this.stats.users.newToday;
        document.getElementById('popular-exercises').textContent = this.stats.exercises.popular;
        document.getElementById('completed-routines').textContent = this.stats.routines.completed;
        document.getElementById('monthly-revenue').textContent = `€${this.stats.payments.monthly}`;
        document.getElementById('pending-payments').textContent = this.stats.payments.pending;
        
        // Actualizar detalles de pagos
        const paymentsDetails = document.getElementById('payments-details');
        if (paymentsDetails) {
            paymentsDetails.innerHTML = `
                <small class="text-muted">
                    €${this.stats.payments.monthly} ingresos | ${this.stats.payments.pagados} pagados
                </small>
            `;
        }
    }

    createCharts() {
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js no está disponible');
            return;
        }

        const ctx = document.getElementById('users-activity-chart');
        if (ctx) {
            this.charts.activity = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: this.stats.activity.labels,
                    datasets: [{
                        label: 'Usuarios Activos',
                        data: this.stats.activity.data,
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            }
                        }
                    }
                }
            });
        }
    }

    startAutoRefresh() {
        this.refreshTimer = setInterval(() => {
            this.refreshStats();
        }, this.options.refreshInterval);
    }

    async refreshStats() {
        try {
            await this.fetchStats();
            this.updateUI();
            
            // Actualizar gráficos si existen
            if (this.charts.activity) {
                this.charts.activity.data.datasets[0].data = this.stats.activity.data;
                this.charts.activity.update('none');
            }
        } catch (error) {
            console.error('Error actualizando estadísticas:', error);
        }
    }

    showError(message) {
        // Mostrar error usando el sistema de notificaciones si está disponible
        if (window.notifications) {
            window.notifications.error(message, 'Error en Dashboard');
        } else {
            console.error(message);
            // Fallback: mostrar alerta básica
            alert(`Error en Dashboard: ${message}`);
        }
    }

    showSuccess(message) {
        // Mostrar éxito usando el sistema de notificaciones si está disponible
        if (window.notifications) {
            window.notifications.success(message, 'Dashboard');
        } else {
            console.log(message);
        }
    }

    destroy() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        
        // Destruir gráficos
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
    }
}

// Función global para inicializar
window.initDashboardStats = (containerId, options) => {
    return new DashboardStats(containerId, options);
};
