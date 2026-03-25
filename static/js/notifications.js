/**
 * Sistema de Notificaciones Mejorado para Fitness App
 * Proporciona notificaciones elegantes y personalizables
 */

class NotificationSystem {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Crear contenedor de notificaciones si no existe
        if (!document.getElementById('notification-container')) {
            this.container = document.createElement('div');
            this.container.id = 'notification-container';
            this.container.className = 'notification-container';
            document.body.appendChild(this.container);
        } else {
            this.container = document.getElementById('notification-container');
        }

        // Agregar estilos CSS
        this.addStyles();
    }

    addStyles() {
        if (!document.getElementById('notification-styles')) {
            const style = document.createElement('style');
            style.id = 'notification-styles';
            style.textContent = `
                .notification-container {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 9999;
                    max-width: 400px;
                }

                .notification {
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    margin-bottom: 10px;
                    padding: 16px 20px;
                    border-left: 4px solid #007bff;
                    transform: translateX(100%);
                    transition: all 0.3s ease;
                    opacity: 0;
                }

                .notification.show {
                    transform: translateX(0);
                    opacity: 1;
                }

                .notification.success {
                    border-left-color: #28a745;
                }

                .notification.error {
                    border-left-color: #dc3545;
                }

                .notification.warning {
                    border-left-color: #ffc107;
                }

                .notification.info {
                    border-left-color: #17a2b8;
                }

                .notification-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 8px;
                }

                .notification-title {
                    font-weight: 600;
                    font-size: 14px;
                    color: #333;
                }

                .notification-close {
                    background: none;
                    border: none;
                    font-size: 18px;
                    cursor: pointer;
                    color: #999;
                    padding: 0;
                    width: 20px;
                    height: 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }

                .notification-close:hover {
                    color: #666;
                }

                .notification-message {
                    font-size: 13px;
                    color: #666;
                    line-height: 1.4;
                }

                .notification-progress {
                    height: 3px;
                    background: #e9ecef;
                    border-radius: 2px;
                    margin-top: 12px;
                    overflow: hidden;
                }

                .notification-progress-bar {
                    height: 100%;
                    background: #007bff;
                    width: 100%;
                    transition: width linear;
                }

                .notification.success .notification-progress-bar {
                    background: #28a745;
                }

                .notification.error .notification-progress-bar {
                    background: #dc3545;
                }

                .notification.warning .notification-progress-bar {
                    background: #ffc107;
                }

                .notification.info .notification-progress-bar {
                    background: #17a2b8;
                }
            `;
            document.head.appendChild(style);
        }
    }

    show(message, type = 'info', title = null, duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        
        const icon = this.getIcon(type);
        const defaultTitle = this.getDefaultTitle(type);
        
        notification.innerHTML = `
            <div class="notification-header">
                <div class="notification-title">
                    ${icon} ${title || defaultTitle}
                </div>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">
                    ×
                </button>
            </div>
            <div class="notification-message">${message}</div>
            <div class="notification-progress">
                <div class="notification-progress-bar"></div>
            </div>
        `;

        this.container.appendChild(notification);

        // Animar entrada
        setTimeout(() => {
            notification.classList.add('show');
        }, 100);

        // Auto-remover después del tiempo especificado
        if (duration > 0) {
            setTimeout(() => {
                this.hide(notification);
            }, duration);

            // Barra de progreso
            const progressBar = notification.querySelector('.notification-progress-bar');
            if (progressBar) {
                progressBar.style.transition = `width ${duration}ms linear`;
                setTimeout(() => {
                    progressBar.style.width = '0%';
                }, 100);
            }
        }

        return notification;
    }

    hide(notification) {
        if (notification && notification.parentElement) {
            notification.style.transform = 'translateX(100%)';
            notification.style.opacity = '0';
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, 300);
        }
    }

    getIcon(type) {
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };
        return icons[type] || icons.info;
    }

    getDefaultTitle(type) {
        const titles = {
            success: 'Éxito',
            error: 'Error',
            warning: 'Advertencia',
            info: 'Información'
        };
        return titles[type] || titles.info;
    }

    // Métodos de conveniencia
    success(message, title = null, duration = 5000) {
        return this.show(message, 'success', title, duration);
    }

    error(message, title = null, duration = 7000) {
        return this.show(message, 'error', title, duration);
    }

    warning(message, title = null, duration = 6000) {
        return this.show(message, 'warning', title, duration);
    }

    info(message, title = null, duration = 5000) {
        return this.show(message, 'info', title, duration);
    }
}

// Inicializar sistema de notificaciones
const notifications = new NotificationSystem();

// Función global para compatibilidad
window.showNotification = (message, type, title, duration) => {
    return notifications.show(message, type, title, duration);
};

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NotificationSystem;
}
