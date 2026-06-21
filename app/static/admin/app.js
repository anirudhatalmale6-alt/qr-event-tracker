/* ========================================
   QR Tracker - Panel de Administracion
   Aplicacion JavaScript principal
   ======================================== */

const App = (function () {
    'use strict';

    /* ========== STATE ========== */
    let state = {
        currentSection: 'dashboard',
        currentReportTab: 'escaneos',
        currentSubReport: 'scans-per-campaign',
        apiKey: localStorage.getItem('qrtracker_api_key') || '',
        baseUrl: localStorage.getItem('qrtracker_base_url') || window.location.origin,
        companies: [],
        campaigns: [],
        qrCodes: [],
        locations: [],
        charts: {}
    };

    /* ========== SPANISH LABELS ========== */
    const MONTHS_ES = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ];
    const DAYS_ES = ['Domingo', 'Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado'];
    const DAYS_SHORT_ES = ['Dom', 'Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab'];

    const SECTION_TITLES = {
        dashboard: 'Dashboard',
        empresas: 'Empresas',
        campanas: 'Campanas',
        'qr-codes': 'Codigos QR',
        ubicaciones: 'Ubicaciones',
        reportes: 'Reportes',
        configuracion: 'Configuracion'
    };

    /* ========== HELPERS ========== */

    function formatDate(dateStr) {
        if (!dateStr) return '-';
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        const day = String(d.getDate()).padStart(2, '0');
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const year = d.getFullYear();
        return day + '/' + month + '/' + year;
    }

    function formatDateTime(dateStr) {
        if (!dateStr) return '-';
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return formatDate(dateStr) + ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    }

    function formatNumber(n) {
        if (n == null) return '0';
        return Number(n).toLocaleString('es-ES');
    }

    function formatCurrency(n) {
        if (n == null) return '$0.00';
        return '$' + Number(n).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function debounce(fn, delay) {
        let timer;
        return function () {
            const args = arguments;
            const ctx = this;
            clearTimeout(timer);
            timer = setTimeout(function () { fn.apply(ctx, args); }, delay);
        };
    }

    function statusBadge(status) {
        const isActive = status === true || status === 'active' || status === 'activo' || status === 1;
        const label = isActive ? 'Activo' : 'Inactivo';
        const cls = isActive ? 'badge-active' : 'badge-inactive';
        return '<span class="badge ' + cls + '">' + label + '</span>';
    }

    function getDefaultDates() {
        const today = new Date();
        const thirtyAgo = new Date(today);
        thirtyAgo.setDate(today.getDate() - 30);
        return {
            from: thirtyAgo.toISOString().split('T')[0],
            to: today.toISOString().split('T')[0]
        };
    }

    /* ========== API HELPER ========== */

    async function api(method, path, body) {
        const url = state.baseUrl.replace(/\/$/, '') + path;
        const headers = {
            'Content-Type': 'application/json'
        };
        if (state.apiKey) {
            headers['X-API-Key'] = state.apiKey;
        }
        const opts = { method: method, headers: headers };
        if (body && method !== 'GET') {
            opts.body = JSON.stringify(body);
        }
        const resp = await fetch(url, opts);
        if (!resp.ok) {
            let errMsg = 'Error ' + resp.status;
            try {
                const errBody = await resp.json();
                errMsg = errBody.detail || errBody.message || errMsg;
            } catch (_) { /* ignore */ }
            throw new Error(errMsg);
        }
        const ct = resp.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
            return resp.json();
        }
        return resp;
    }

    async function apiBlobUrl(method, path, body) {
        const url = state.baseUrl.replace(/\/$/, '') + path;
        const headers = { 'Content-Type': 'application/json' };
        if (state.apiKey) {
            headers['X-API-Key'] = state.apiKey;
        }
        const opts = { method: method, headers: headers };
        if (body && method !== 'GET') {
            opts.body = JSON.stringify(body);
        }
        const resp = await fetch(url, opts);
        if (!resp.ok) throw new Error('Error generando QR: ' + resp.status);
        const blob = await resp.blob();
        return URL.createObjectURL(blob);
    }

    /* ========== TOAST NOTIFICATIONS ========== */

    function showToast(message, type) {
        type = type || 'info';
        const container = document.getElementById('toastContainer');
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        const toast = document.createElement('div');
        toast.className = 'toast toast-' + type;
        toast.innerHTML = '<i class="fas ' + (icons[type] || icons.info) + '"></i> ' + escapeHtml(message);
        toast.addEventListener('click', function () {
            toast.classList.add('removing');
            setTimeout(function () { toast.remove(); }, 300);
        });
        container.appendChild(toast);
        setTimeout(function () {
            if (toast.parentNode) {
                toast.classList.add('removing');
                setTimeout(function () { toast.remove(); }, 300);
            }
        }, 4000);
    }

    /* ========== MODAL ========== */

    function showModal(title, contentHtml) {
        document.getElementById('modalTitle').textContent = title;
        document.getElementById('modalBody').innerHTML = contentHtml;
        document.getElementById('modalOverlay').classList.add('active');
    }

    function closeModal() {
        document.getElementById('modalOverlay').classList.remove('active');
    }

    /* ========== LOADING ========== */

    function showLoading() {
        document.getElementById('loadingOverlay').classList.add('active');
    }

    function hideLoading() {
        document.getElementById('loadingOverlay').classList.remove('active');
    }

    /* ========== NAVIGATION ========== */

    function navigate(section) {
        state.currentSection = section;

        // Update sidebar
        document.querySelectorAll('.nav-item').forEach(function (el) {
            el.classList.toggle('active', el.dataset.section === section);
        });

        // Update page title
        document.getElementById('pageTitle').textContent = SECTION_TITLES[section] || section;

        // Show/hide sections
        document.querySelectorAll('.content-section').forEach(function (el) {
            el.classList.toggle('active', el.id === 'section-' + section);
        });

        // Close mobile sidebar
        document.getElementById('sidebar').classList.remove('open');
        document.getElementById('sidebarOverlay').classList.remove('active');

        // Load section data
        loadSectionData(section);
    }

    function loadSectionData(section) {
        switch (section) {
            case 'dashboard':
                loadDashboard();
                break;
            case 'empresas':
                loadCompanies();
                break;
            case 'campanas':
                loadCampaignFilters();
                loadCampaigns();
                break;
            case 'qr-codes':
                loadQrFilters();
                loadQrCodes();
                break;
            case 'ubicaciones':
                loadLocations();
                break;
            case 'reportes':
                loadReportFilters();
                break;
            case 'configuracion':
                loadSettings();
                break;
        }
    }

    /* ========== CHART HELPERS ========== */

    function destroyChart(key) {
        if (state.charts[key]) {
            state.charts[key].destroy();
            delete state.charts[key];
        }
    }

    function chartColors(count) {
        const palette = [
            '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
            '#06b6d4', '#ec4899', '#14b8a6', '#f97316', '#6366f1',
            '#84cc16', '#e11d48', '#0ea5e9', '#a855f7', '#10b981'
        ];
        const result = [];
        for (var i = 0; i < count; i++) {
            result.push(palette[i % palette.length]);
        }
        return result;
    }

    /* ========== DASHBOARD ========== */

    async function loadDashboard() {
        try {
            // Fetch companies, campaigns, qr-codes for counts
            const [companies, campaigns, qrCodes] = await Promise.all([
                api('GET', '/api/v1/companies').catch(function () { return []; }),
                api('GET', '/api/v1/campaigns').catch(function () { return []; }),
                api('GET', '/api/v1/qr-codes').catch(function () { return []; })
            ]);

            state.companies = Array.isArray(companies) ? companies : (companies.data || companies.items || []);
            state.campaigns = Array.isArray(campaigns) ? campaigns : (campaigns.data || campaigns.items || []);
            state.qrCodes = Array.isArray(qrCodes) ? qrCodes : (qrCodes.data || qrCodes.items || []);

            // Update stat cards
            var activeCompanies = state.companies.filter(function (c) {
                return c.is_active !== false && c.status !== 'inactive';
            });
            var activeCampaigns = state.campaigns.filter(function (c) {
                return c.is_active !== false && c.status !== 'inactive';
            });
            var activeQr = state.qrCodes.filter(function (q) {
                return q.is_active !== false && q.status !== 'inactive';
            });

            document.getElementById('statCompanies').textContent = formatNumber(activeCompanies.length);
            document.getElementById('statCampaigns').textContent = formatNumber(activeCampaigns.length);
            document.getElementById('statQrCodes').textContent = formatNumber(activeQr.length);

            // Fetch reports for charts
            var dates = getDefaultDates();
            var params = '?date_from=' + dates.from + '&date_to=' + dates.to;

            var [trendData, topData, deviceData] = await Promise.all([
                api('GET', '/api/v1/reports/trend-analysis' + params).catch(function () { return { data: [] }; }),
                api('GET', '/api/v1/reports/top-campaigns' + params).catch(function () { return { data: [] }; }),
                api('GET', '/api/v1/reports/scans-by-device' + params).catch(function () { return { data: [] }; })
            ]);

            var trendItems = trendData.data || trendData.items || trendData || [];
            var topItems = topData.data || topData.items || topData || [];
            var deviceItems = deviceData.data || deviceData.items || deviceData || [];

            // Total scans today (sum from trend for today)
            var today = new Date().toISOString().split('T')[0];
            var todayScans = 0;
            if (Array.isArray(trendItems)) {
                trendItems.forEach(function (item) {
                    if (item.date === today || item.day === today) {
                        todayScans = item.scan_count || item.total_scans || item.scans || item.count || item.total || 0;
                    }
                });
            }
            document.getElementById('statTotalScans').textContent = formatNumber(todayScans);

            // Trend chart
            renderTrendChart(trendItems);

            // Top campaigns chart
            renderTopCampaignsChart(topItems);

            // Device chart
            renderDeviceChart(deviceItems);

            // Recent scans placeholder
            renderRecentScans(trendItems);

        } catch (err) {
            showToast('Error cargando dashboard: ' + err.message, 'error');
        }
    }

    function renderTrendChart(items) {
        if (!Array.isArray(items)) items = [];
        var labels = items.map(function (i) { return i.date || i.day || i.label || ''; });
        var values = items.map(function (i) { return i.total_scans || i.scan_count || i.scans || i.count || i.total || 0; });

        destroyChart('trend');
        var ctx = document.getElementById('chartTrend');
        if (!ctx) return;
        state.charts.trend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Escaneos',
                    data: values,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 2,
                    pointHoverRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
                    x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } }
                }
            }
        });
    }

    function renderTopCampaignsChart(items) {
        if (!Array.isArray(items)) items = [];
        var top5 = items.slice(0, 5);
        var labels = top5.map(function (i) { return i.campaign_name || i.name || i.label || ''; });
        var values = top5.map(function (i) { return i.total_scans || i.scan_count || i.scans || i.count || i.total || 0; });

        destroyChart('topCampaigns');
        var ctx = document.getElementById('chartTopCampaigns');
        if (!ctx) return;
        state.charts.topCampaigns = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Escaneos',
                    data: values,
                    backgroundColor: chartColors(5)
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { beginAtZero: true, grid: { color: '#f1f5f9' } },
                    y: { grid: { display: false } }
                }
            }
        });
    }

    function renderDeviceChart(items) {
        if (!Array.isArray(items)) items = [];
        var labels = items.map(function (i) { return i.device_type || i.device || i.type || i.label || ''; });
        var values = items.map(function (i) { return i.total_scans || i.scan_count || i.scans || i.count || i.total || 0; });

        destroyChart('devices');
        var ctx = document.getElementById('chartDevices');
        if (!ctx) return;
        state.charts.devices = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: chartColors(labels.length)
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }

    function renderRecentScans(trendItems) {
        var body = document.getElementById('recentScansBody');
        if (!trendItems || trendItems.length === 0) {
            body.innerHTML = '<tr><td colspan="4" class="text-center text-light">Sin datos recientes</td></tr>';
            return;
        }
        // Show latest entries (trend items as proxy)
        var rows = '';
        var recent = trendItems.slice(-20).reverse();
        recent.forEach(function (item) {
            rows += '<tr>' +
                '<td>' + escapeHtml(formatDate(item.date || item.day || '')) + '</td>' +
                '<td>' + escapeHtml(item.campaign_name || item.campaign || '-') + '</td>' +
                '<td>' + escapeHtml(item.location || '-') + '</td>' +
                '<td>' + escapeHtml(item.device || item.device_type || '-') + '</td>' +
                '</tr>';
        });
        body.innerHTML = rows || '<tr><td colspan="4" class="text-center text-light">Sin datos recientes</td></tr>';
    }

    /* ========== COMPANIES (EMPRESAS) ========== */

    async function loadCompanies() {
        try {
            var data = await api('GET', '/api/v1/companies');
            state.companies = Array.isArray(data) ? data : (data.data || data.items || []);
            renderCompaniesTable();
        } catch (err) {
            showToast('Error cargando empresas: ' + err.message, 'error');
        }
    }

    function renderCompaniesTable() {
        var body = document.getElementById('companiesBody');
        if (state.companies.length === 0) {
            body.innerHTML = '<tr><td colspan="5" class="text-center text-light">No hay empresas registradas</td></tr>';
            return;
        }
        var html = '';
        state.companies.forEach(function (c) {
            html += '<tr>' +
                '<td><strong>' + escapeHtml(c.name || c.nombre || '') + '</strong></td>' +
                '<td>' + escapeHtml(c.email || '') + '</td>' +
                '<td>' + escapeHtml(c.phone || c.telefono || '') + '</td>' +
                '<td>' + statusBadge(c.is_active != null ? c.is_active : c.status) + '</td>' +
                '<td class="action-btns">' +
                    '<button class="btn btn-icon btn-outline" title="Editar" onclick="App.openCompanyModal(' + c.id + ')"><i class="fas fa-edit"></i></button> ' +
                    '<button class="btn btn-icon btn-outline-danger" title="Eliminar" onclick="App.deleteCompany(' + c.id + ')"><i class="fas fa-trash"></i></button>' +
                '</td>' +
                '</tr>';
        });
        body.innerHTML = html;
    }

    function openCompanyModal(id) {
        var company = null;
        if (id) {
            company = state.companies.find(function (c) { return c.id === id; });
        }
        var title = company ? 'Editar Empresa' : 'Nueva Empresa';
        var html = '<form id="companyForm" onsubmit="App.saveCompany(event, ' + (id || 'null') + ')">' +
            '<div class="form-group">' +
                '<label for="companyName">Nombre</label>' +
                '<input type="text" class="form-input" id="companyName" required placeholder="Nombre de la empresa" value="' + escapeHtml((company && (company.name || company.nombre)) || '') + '">' +
            '</div>' +
            '<div class="form-row">' +
                '<div class="form-group">' +
                    '<label for="companyEmail">Email</label>' +
                    '<input type="email" class="form-input" id="companyEmail" placeholder="correo@empresa.com" value="' + escapeHtml((company && company.email) || '') + '">' +
                '</div>' +
                '<div class="form-group">' +
                    '<label for="companyPhone">Telefono</label>' +
                    '<input type="text" class="form-input" id="companyPhone" placeholder="+1 234 567 890" value="' + escapeHtml((company && (company.phone || company.telefono)) || '') + '">' +
                '</div>' +
            '</div>' +
            '<div class="form-group">' +
                '<label for="companyStatus">Estado</label>' +
                '<select class="form-select" id="companyStatus">' +
                    '<option value="true"' + ((!company || company.is_active !== false) ? ' selected' : '') + '>Activo</option>' +
                    '<option value="false"' + ((company && company.is_active === false) ? ' selected' : '') + '>Inactivo</option>' +
                '</select>' +
            '</div>' +
            '<div class="form-actions">' +
                '<button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Guardar</button>' +
                '<button type="button" class="btn btn-outline" onclick="App.closeModal()">Cancelar</button>' +
            '</div>' +
        '</form>';
        showModal(title, html);
    }

    async function saveCompany(event, id) {
        event.preventDefault();
        var payload = {
            name: document.getElementById('companyName').value.trim(),
            email: document.getElementById('companyEmail').value.trim(),
            phone: document.getElementById('companyPhone').value.trim(),
            is_active: document.getElementById('companyStatus').value === 'true'
        };
        try {
            if (id) {
                await api('PUT', '/api/v1/companies/' + id, payload);
                showToast('Empresa actualizada correctamente', 'success');
            } else {
                await api('POST', '/api/v1/companies', payload);
                showToast('Empresa creada correctamente', 'success');
            }
            closeModal();
            loadCompanies();
        } catch (err) {
            showToast('Error guardando empresa: ' + err.message, 'error');
        }
    }

    async function deleteCompany(id) {
        if (!confirm('Esta seguro de eliminar esta empresa? Esta accion no se puede deshacer.')) return;
        try {
            await api('DELETE', '/api/v1/companies/' + id);
            showToast('Empresa eliminada', 'success');
            loadCompanies();
        } catch (err) {
            showToast('Error eliminando empresa: ' + err.message, 'error');
        }
    }

    /* ========== CAMPAIGNS (CAMPANAS) ========== */

    async function loadCampaignFilters() {
        try {
            if (state.companies.length === 0) {
                var data = await api('GET', '/api/v1/companies');
                state.companies = Array.isArray(data) ? data : (data.data || data.items || []);
            }
            var select = document.getElementById('filterCampaignCompany');
            if (!select) return;
            var html = '<option value="">Todas las empresas</option>';
            state.companies.forEach(function (c) {
                html += '<option value="' + c.id + '">' + escapeHtml(c.name || c.nombre || '') + '</option>';
            });
            select.innerHTML = html;
        } catch (err) { /* silent */ }
    }

    async function loadCampaigns() {
        try {
            var path = '/api/v1/campaigns';
            var companyFilter = document.getElementById('filterCampaignCompany');
            if (companyFilter && companyFilter.value) {
                path += '?company_id=' + companyFilter.value;
            }
            var data = await api('GET', path);
            state.campaigns = Array.isArray(data) ? data : (data.data || data.items || []);
            renderCampaignsTable();
        } catch (err) {
            showToast('Error cargando campanas: ' + err.message, 'error');
        }
    }

    function renderCampaignsTable() {
        var body = document.getElementById('campaignsBody');
        if (state.campaigns.length === 0) {
            body.innerHTML = '<tr><td colspan="7" class="text-center text-light">No hay campanas registradas</td></tr>';
            return;
        }
        var html = '';
        state.campaigns.forEach(function (c) {
            var companyName = '';
            if (c.company_name) {
                companyName = c.company_name;
            } else if (c.company_id) {
                var comp = state.companies.find(function (co) { return co.id === c.company_id; });
                companyName = comp ? (comp.name || comp.nombre || '') : '';
            }
            html += '<tr>' +
                '<td><strong>' + escapeHtml(c.name || c.nombre || '') + '</strong></td>' +
                '<td>' + escapeHtml(companyName) + '</td>' +
                '<td>' + formatDate(c.start_date || c.fecha_inicio) + '</td>' +
                '<td>' + formatDate(c.end_date || c.fecha_fin) + '</td>' +
                '<td>' + formatCurrency(c.budget || c.presupuesto) + '</td>' +
                '<td>' + statusBadge(c.is_active != null ? c.is_active : c.status) + '</td>' +
                '<td class="action-btns">' +
                    '<button class="btn btn-icon btn-outline" title="Editar" onclick="App.openCampaignModal(' + c.id + ')"><i class="fas fa-edit"></i></button> ' +
                    '<button class="btn btn-icon btn-outline-danger" title="Eliminar" onclick="App.deleteCampaign(' + c.id + ')"><i class="fas fa-trash"></i></button>' +
                '</td>' +
                '</tr>';
        });
        body.innerHTML = html;
    }

    function openCampaignModal(id) {
        var campaign = null;
        if (id) {
            campaign = state.campaigns.find(function (c) { return c.id === id; });
        }
        var title = campaign ? 'Editar Campana' : 'Nueva Campana';
        var companyOptions = '<option value="">Seleccionar empresa</option>';
        state.companies.forEach(function (c) {
            var selected = (campaign && campaign.company_id === c.id) ? ' selected' : '';
            companyOptions += '<option value="' + c.id + '"' + selected + '>' + escapeHtml(c.name || c.nombre || '') + '</option>';
        });

        var html = '<form id="campaignForm" onsubmit="App.saveCampaign(event, ' + (id || 'null') + ')">' +
            '<div class="form-group">' +
                '<label for="campaignName">Nombre de la Campana</label>' +
                '<input type="text" class="form-input" id="campaignName" required placeholder="Nombre de la campana" value="' + escapeHtml((campaign && (campaign.name || campaign.nombre)) || '') + '">' +
            '</div>' +
            '<div class="form-group">' +
                '<label for="campaignCompany">Empresa</label>' +
                '<select class="form-select" id="campaignCompany" required>' + companyOptions + '</select>' +
            '</div>' +
            '<div class="form-row">' +
                '<div class="form-group">' +
                    '<label for="campaignStart">Fecha de Inicio</label>' +
                    '<input type="date" class="form-input" id="campaignStart" value="' + ((campaign && (campaign.start_date || campaign.fecha_inicio)) || '') + '">' +
                '</div>' +
                '<div class="form-group">' +
                    '<label for="campaignEnd">Fecha de Fin</label>' +
                    '<input type="date" class="form-input" id="campaignEnd" value="' + ((campaign && (campaign.end_date || campaign.fecha_fin)) || '') + '">' +
                '</div>' +
            '</div>' +
            '<div class="form-row">' +
                '<div class="form-group">' +
                    '<label for="campaignBudget">Presupuesto ($)</label>' +
                    '<input type="number" step="0.01" class="form-input" id="campaignBudget" placeholder="0.00" value="' + ((campaign && (campaign.budget || campaign.presupuesto)) || '') + '">' +
                '</div>' +
                '<div class="form-group">' +
                    '<label for="campaignStatus">Estado</label>' +
                    '<select class="form-select" id="campaignStatus">' +
                        '<option value="true"' + ((!campaign || campaign.is_active !== false) ? ' selected' : '') + '>Activo</option>' +
                        '<option value="false"' + ((campaign && campaign.is_active === false) ? ' selected' : '') + '>Inactivo</option>' +
                    '</select>' +
                '</div>' +
            '</div>' +
            '<div class="form-group">' +
                '<label for="campaignDesc">Descripcion</label>' +
                '<textarea class="form-textarea" id="campaignDesc" placeholder="Descripcion de la campana">' + escapeHtml((campaign && (campaign.description || campaign.descripcion)) || '') + '</textarea>' +
            '</div>' +
            '<div class="form-actions">' +
                '<button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Guardar</button>' +
                '<button type="button" class="btn btn-outline" onclick="App.closeModal()">Cancelar</button>' +
            '</div>' +
        '</form>';
        showModal(title, html);
    }

    async function saveCampaign(event, id) {
        event.preventDefault();
        var payload = {
            name: document.getElementById('campaignName').value.trim(),
            company_id: parseInt(document.getElementById('campaignCompany').value),
            start_date: document.getElementById('campaignStart').value || null,
            end_date: document.getElementById('campaignEnd').value || null,
            budget: parseFloat(document.getElementById('campaignBudget').value) || 0,
            is_active: document.getElementById('campaignStatus').value === 'true',
            description: document.getElementById('campaignDesc').value.trim()
        };
        try {
            if (id) {
                await api('PUT', '/api/v1/campaigns/' + id, payload);
                showToast('Campana actualizada correctamente', 'success');
            } else {
                await api('POST', '/api/v1/campaigns', payload);
                showToast('Campana creada correctamente', 'success');
            }
            closeModal();
            loadCampaigns();
        } catch (err) {
            showToast('Error guardando campana: ' + err.message, 'error');
        }
    }

    async function deleteCampaign(id) {
        if (!confirm('Esta seguro de eliminar esta campana? Esta accion no se puede deshacer.')) return;
        try {
            await api('DELETE', '/api/v1/campaigns/' + id);
            showToast('Campana eliminada', 'success');
            loadCampaigns();
        } catch (err) {
            showToast('Error eliminando campana: ' + err.message, 'error');
        }
    }

    /* ========== QR CODES (CODIGOS QR) ========== */

    async function loadQrFilters() {
        try {
            if (state.campaigns.length === 0) {
                var data = await api('GET', '/api/v1/campaigns');
                state.campaigns = Array.isArray(data) ? data : (data.data || data.items || []);
            }
            var select = document.getElementById('filterQrCampaign');
            if (!select) return;
            var html = '<option value="">Todas las campanas</option>';
            state.campaigns.forEach(function (c) {
                html += '<option value="' + c.id + '">' + escapeHtml(c.name || c.nombre || '') + '</option>';
            });
            select.innerHTML = html;
        } catch (err) { /* silent */ }
    }

    async function loadQrCodes() {
        try {
            var path = '/api/v1/qr-codes';
            var campaignFilter = document.getElementById('filterQrCampaign');
            if (campaignFilter && campaignFilter.value) {
                path += '?campaign_id=' + campaignFilter.value;
            }
            var data = await api('GET', path);
            state.qrCodes = Array.isArray(data) ? data : (data.data || data.items || []);
            renderQrCodesTable();
        } catch (err) {
            showToast('Error cargando codigos QR: ' + err.message, 'error');
        }
    }

    function renderQrCodesTable() {
        var body = document.getElementById('qrCodesBody');
        if (state.qrCodes.length === 0) {
            body.innerHTML = '<tr><td colspan="6" class="text-center text-light">No hay codigos QR registrados</td></tr>';
            return;
        }
        var html = '';
        state.qrCodes.forEach(function (q) {
            var campaignName = '';
            if (q.campaign_name) {
                campaignName = q.campaign_name;
            } else if (q.campaign_id) {
                var camp = state.campaigns.find(function (c) { return c.id === q.campaign_id; });
                campaignName = camp ? (camp.name || camp.nombre || '') : '';
            }
            html += '<tr>' +
                '<td><strong>' + escapeHtml(q.label || q.etiqueta || '') + '</strong></td>' +
                '<td>' + escapeHtml(campaignName) + '</td>' +
                '<td><span style="font-size:0.82rem;color:var(--text-light);">' + escapeHtml(q.target_url || q.url_destino || '') + '</span></td>' +
                '<td><code style="background:#f1f5f9;padding:2px 8px;border-radius:4px;font-size:0.82rem;">' + escapeHtml(q.code || q.codigo || '') + '</code></td>' +
                '<td>' + statusBadge(q.is_active != null ? q.is_active : q.status) + '</td>' +
                '<td class="action-btns">' +
                    '<button class="btn btn-icon btn-success" title="Generar QR" onclick="App.generateQr(' + q.id + ')"><i class="fas fa-qrcode"></i></button> ' +
                    '<button class="btn btn-icon btn-outline" title="Editar" onclick="App.openQrCodeModal(' + q.id + ')"><i class="fas fa-edit"></i></button> ' +
                    '<button class="btn btn-icon btn-outline-danger" title="Eliminar" onclick="App.deleteQrCode(' + q.id + ')"><i class="fas fa-trash"></i></button>' +
                '</td>' +
                '</tr>';
        });
        body.innerHTML = html;
    }

    function openQrCodeModal(id) {
        var qr = null;
        if (id) {
            qr = state.qrCodes.find(function (q) { return q.id === id; });
        }
        var title = qr ? 'Editar Codigo QR' : 'Nuevo Codigo QR';
        var campaignOptions = '<option value="">Seleccionar campana</option>';
        state.campaigns.forEach(function (c) {
            var selected = (qr && qr.campaign_id === c.id) ? ' selected' : '';
            campaignOptions += '<option value="' + c.id + '"' + selected + '>' + escapeHtml(c.name || c.nombre || '') + '</option>';
        });

        var html = '<form id="qrForm" onsubmit="App.saveQrCode(event, ' + (id || 'null') + ')">' +
            '<div class="form-group">' +
                '<label for="qrLabel">Etiqueta</label>' +
                '<input type="text" class="form-input" id="qrLabel" required placeholder="Nombre identificador del QR" value="' + escapeHtml((qr && (qr.label || qr.etiqueta)) || '') + '">' +
            '</div>' +
            '<div class="form-group">' +
                '<label for="qrCampaign">Campana</label>' +
                '<select class="form-select" id="qrCampaign" required>' + campaignOptions + '</select>' +
            '</div>' +
            '<div class="form-group">' +
                '<label for="qrTargetUrl">URL Destino</label>' +
                '<input type="url" class="form-input" id="qrTargetUrl" placeholder="https://ejemplo.com/landing" value="' + escapeHtml((qr && (qr.target_url || qr.url_destino)) || '') + '">' +
            '</div>' +
            '<div class="form-group">' +
                '<label for="qrStatus">Estado</label>' +
                '<select class="form-select" id="qrStatus">' +
                    '<option value="true"' + ((!qr || qr.is_active !== false) ? ' selected' : '') + '>Activo</option>' +
                    '<option value="false"' + ((qr && qr.is_active === false) ? ' selected' : '') + '>Inactivo</option>' +
                '</select>' +
            '</div>' +
            '<div class="form-actions">' +
                '<button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Guardar</button>' +
                '<button type="button" class="btn btn-outline" onclick="App.closeModal()">Cancelar</button>' +
            '</div>' +
        '</form>';
        showModal(title, html);
    }

    async function saveQrCode(event, id) {
        event.preventDefault();
        var payload = {
            label: document.getElementById('qrLabel').value.trim(),
            campaign_id: parseInt(document.getElementById('qrCampaign').value),
            target_url: document.getElementById('qrTargetUrl').value.trim(),
            is_active: document.getElementById('qrStatus').value === 'true'
        };
        try {
            if (id) {
                await api('PUT', '/api/v1/qr-codes/' + id, payload);
                showToast('Codigo QR actualizado correctamente', 'success');
            } else {
                await api('POST', '/api/v1/qr-codes', payload);
                showToast('Codigo QR creado correctamente', 'success');
            }
            closeModal();
            loadQrCodes();
        } catch (err) {
            showToast('Error guardando codigo QR: ' + err.message, 'error');
        }
    }

    async function deleteQrCode(id) {
        if (!confirm('Esta seguro de eliminar este codigo QR? Esta accion no se puede deshacer.')) return;
        try {
            await api('DELETE', '/api/v1/qr-codes/' + id);
            showToast('Codigo QR eliminado', 'success');
            loadQrCodes();
        } catch (err) {
            showToast('Error eliminando codigo QR: ' + err.message, 'error');
        }
    }

    async function generateQr(id) {
        try {
            showToast('Generando codigo QR...', 'info');
            var blobUrl = await apiBlobUrl('POST', '/api/v1/qr/generate', { qr_code_id: id });
            var html = '<div class="qr-preview">' +
                '<img src="' + blobUrl + '" alt="Codigo QR" id="qrImage">' +
                '<br>' +
                '<a href="' + blobUrl + '" download="qr-code-' + id + '.png" class="btn btn-primary">' +
                    '<i class="fas fa-download"></i> Descargar PNG' +
                '</a>' +
            '</div>';
            showModal('Codigo QR Generado', html);
        } catch (err) {
            showToast('Error generando QR: ' + err.message, 'error');
        }
    }

    /* ========== LOCATIONS (UBICACIONES) ========== */

    async function loadLocations() {
        try {
            var data = await api('GET', '/api/v1/locations');
            state.locations = Array.isArray(data) ? data : (data.data || data.items || []);
            renderLocationsTable();
        } catch (err) {
            showToast('Error cargando ubicaciones: ' + err.message, 'error');
        }
    }

    function renderLocationsTable() {
        var body = document.getElementById('locationsBody');
        if (state.locations.length === 0) {
            body.innerHTML = '<tr><td colspan="6" class="text-center text-light">No hay ubicaciones registradas</td></tr>';
            return;
        }
        var html = '';
        state.locations.forEach(function (loc) {
            html += '<tr>' +
                '<td><strong>' + escapeHtml(loc.name || loc.nombre || '') + '</strong></td>' +
                '<td>' + escapeHtml(loc.address || loc.direccion || '') + '</td>' +
                '<td>' + escapeHtml(loc.city || loc.ciudad || '') + '</td>' +
                '<td>' + escapeHtml(loc.region || '') + '</td>' +
                '<td>' + escapeHtml(loc.country || loc.pais || '') + '</td>' +
                '<td class="action-btns">' +
                    '<button class="btn btn-icon btn-outline" title="Editar" onclick="App.openLocationModal(' + loc.id + ')"><i class="fas fa-edit"></i></button> ' +
                    '<button class="btn btn-icon btn-outline-danger" title="Eliminar" onclick="App.deleteLocation(' + loc.id + ')"><i class="fas fa-trash"></i></button>' +
                '</td>' +
                '</tr>';
        });
        body.innerHTML = html;
    }

    function openLocationModal(id) {
        var loc = null;
        if (id) {
            loc = state.locations.find(function (l) { return l.id === id; });
        }
        var title = loc ? 'Editar Ubicacion' : 'Nueva Ubicacion';

        // Build QR assignment checkboxes
        var qrAssignHtml = '';
        if (state.qrCodes.length > 0) {
            qrAssignHtml = '<div class="form-group">' +
                '<label>Codigos QR Asignados</label>' +
                '<div style="max-height:120px;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius);padding:8px;">';
            var assignedIds = (loc && loc.qr_code_ids) || [];
            state.qrCodes.forEach(function (q) {
                var checked = assignedIds.indexOf(q.id) !== -1 ? ' checked' : '';
                qrAssignHtml += '<label style="display:block;padding:4px 0;cursor:pointer;">' +
                    '<input type="checkbox" class="loc-qr-check" value="' + q.id + '"' + checked + '> ' +
                    escapeHtml(q.label || q.etiqueta || q.code || '') +
                '</label>';
            });
            qrAssignHtml += '</div></div>';
        }

        var html = '<form id="locationForm" onsubmit="App.saveLocation(event, ' + (id || 'null') + ')">' +
            '<div class="form-group">' +
                '<label for="locName">Nombre</label>' +
                '<input type="text" class="form-input" id="locName" required placeholder="Nombre de la ubicacion" value="' + escapeHtml((loc && (loc.name || loc.nombre)) || '') + '">' +
            '</div>' +
            '<div class="form-group">' +
                '<label for="locAddress">Direccion</label>' +
                '<input type="text" class="form-input" id="locAddress" placeholder="Calle y numero" value="' + escapeHtml((loc && (loc.address || loc.direccion)) || '') + '">' +
            '</div>' +
            '<div class="form-row">' +
                '<div class="form-group">' +
                    '<label for="locCity">Ciudad</label>' +
                    '<input type="text" class="form-input" id="locCity" placeholder="Ciudad" value="' + escapeHtml((loc && (loc.city || loc.ciudad)) || '') + '">' +
                '</div>' +
                '<div class="form-group">' +
                    '<label for="locRegion">Region</label>' +
                    '<input type="text" class="form-input" id="locRegion" placeholder="Estado / Provincia" value="' + escapeHtml((loc && loc.region) || '') + '">' +
                '</div>' +
            '</div>' +
            '<div class="form-group">' +
                '<label for="locCountry">Pais</label>' +
                '<input type="text" class="form-input" id="locCountry" placeholder="Pais" value="' + escapeHtml((loc && (loc.country || loc.pais)) || '') + '">' +
            '</div>' +
            qrAssignHtml +
            '<div class="form-actions">' +
                '<button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Guardar</button>' +
                '<button type="button" class="btn btn-outline" onclick="App.closeModal()">Cancelar</button>' +
            '</div>' +
        '</form>';
        showModal(title, html);
    }

    async function saveLocation(event, id) {
        event.preventDefault();
        var qrChecks = document.querySelectorAll('.loc-qr-check:checked');
        var qrIds = [];
        qrChecks.forEach(function (cb) { qrIds.push(parseInt(cb.value)); });

        var payload = {
            name: document.getElementById('locName').value.trim(),
            address: document.getElementById('locAddress').value.trim(),
            city: document.getElementById('locCity').value.trim(),
            region: document.getElementById('locRegion').value.trim(),
            country: document.getElementById('locCountry').value.trim(),
            qr_code_ids: qrIds
        };
        try {
            if (id) {
                await api('PUT', '/api/v1/locations/' + id, payload);
                showToast('Ubicacion actualizada correctamente', 'success');
            } else {
                await api('POST', '/api/v1/locations', payload);
                showToast('Ubicacion creada correctamente', 'success');
            }
            closeModal();
            loadLocations();
        } catch (err) {
            showToast('Error guardando ubicacion: ' + err.message, 'error');
        }
    }

    async function deleteLocation(id) {
        if (!confirm('Esta seguro de eliminar esta ubicacion? Esta accion no se puede deshacer.')) return;
        try {
            await api('DELETE', '/api/v1/locations/' + id);
            showToast('Ubicacion eliminada', 'success');
            loadLocations();
        } catch (err) {
            showToast('Error eliminando ubicacion: ' + err.message, 'error');
        }
    }

    /* ========== REPORTS (REPORTES) ========== */

    async function loadReportFilters() {
        try {
            // Set default dates
            var dates = getDefaultDates();
            var fromInput = document.getElementById('reportDateFrom');
            var toInput = document.getElementById('reportDateTo');
            if (fromInput && !fromInput.value) fromInput.value = dates.from;
            if (toInput && !toInput.value) toInput.value = dates.to;

            // Load companies and campaigns for filters
            var [compData, campData] = await Promise.all([
                state.companies.length > 0 ? Promise.resolve(state.companies) : api('GET', '/api/v1/companies').catch(function () { return []; }),
                state.campaigns.length > 0 ? Promise.resolve(state.campaigns) : api('GET', '/api/v1/campaigns').catch(function () { return []; })
            ]);

            state.companies = Array.isArray(compData) ? compData : (compData.data || compData.items || []);
            state.campaigns = Array.isArray(campData) ? campData : (campData.data || campData.items || []);

            var compSelect = document.getElementById('reportCompanyFilter');
            if (compSelect) {
                var html = '<option value="">Todas</option>';
                state.companies.forEach(function (c) {
                    html += '<option value="' + c.id + '">' + escapeHtml(c.name || c.nombre || '') + '</option>';
                });
                compSelect.innerHTML = html;
            }

            var campSelect = document.getElementById('reportCampaignFilter');
            if (campSelect) {
                var html2 = '<option value="">Todas</option>';
                state.campaigns.forEach(function (c) {
                    html2 += '<option value="' + c.id + '">' + escapeHtml(c.name || c.nombre || '') + '</option>';
                });
                campSelect.innerHTML = html2;
            }
        } catch (err) { /* silent */ }
    }

    function getReportParams() {
        var params = [];
        var from = document.getElementById('reportDateFrom');
        var to = document.getElementById('reportDateTo');
        var comp = document.getElementById('reportCompanyFilter');
        var camp = document.getElementById('reportCampaignFilter');
        if (from && from.value) params.push('date_from=' + from.value);
        if (to && to.value) params.push('date_to=' + to.value);
        if (comp && comp.value) params.push('company_id=' + comp.value);
        if (camp && camp.value) params.push('campaign_id=' + camp.value);
        return params.length > 0 ? '?' + params.join('&') : '';
    }

    function switchReportTab(btn) {
        var tabName = btn.dataset.report;
        state.currentReportTab = tabName;

        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(function (b) {
            b.classList.toggle('active', b === btn);
        });

        // Show/hide panels
        document.querySelectorAll('.report-panel').forEach(function (p) {
            p.classList.toggle('active', p.id === 'report-' + tabName);
        });

        // Set default sub-report based on tab
        var defaults = {
            'escaneos': 'scans-per-campaign',
            'geografico': 'scans-by-geography',
            'dispositivos': 'scans-by-device',
            'campanas-report': 'top-campaigns',
            'usuarios': 'unique-vs-repeat'
        };
        state.currentSubReport = defaults[tabName] || 'scans-per-campaign';

        // Reset sub-tab active state
        var panel = document.getElementById('report-' + tabName);
        if (panel) {
            var subTabs = panel.querySelectorAll('.sub-tab');
            subTabs.forEach(function (st, idx) {
                st.classList.toggle('active', idx === 0);
            });
        }

        loadCurrentReport();
    }

    function switchSubReport(btn) {
        var subreport = btn.dataset.subreport;
        state.currentSubReport = subreport;

        // Update sub-tab UI within the same parent
        var parent = btn.parentElement;
        parent.querySelectorAll('.sub-tab').forEach(function (b) {
            b.classList.toggle('active', b === btn);
        });

        loadCurrentReport();
    }

    async function loadCurrentReport() {
        var reportType = state.currentSubReport;
        var params = getReportParams();

        try {
            var data = await api('GET', '/api/v1/reports/' + reportType + params);
            var items = data.data || data.items || data || [];
            if (!Array.isArray(items)) items = [];

            renderReportChart(reportType, items);
            renderReportTable(reportType, items);
        } catch (err) {
            showToast('Error cargando reporte: ' + err.message, 'error');
        }
    }

    function renderReportChart(reportType, items) {
        var chartConfigs = {
            'scans-per-campaign': { canvas: 'reportChartEscaneos', type: 'bar', labelKey: 'campaign_name', valueKey: 'scans' },
            'scans-per-company': { canvas: 'reportChartEscaneos', type: 'bar', labelKey: 'company_name', valueKey: 'scans' },
            'scans-by-hour': { canvas: 'reportChartEscaneos', type: 'bar', labelKey: 'hour', valueKey: 'scans' },
            'scans-by-day-of-week': { canvas: 'reportChartEscaneos', type: 'bar', labelKey: 'day', valueKey: 'scans' },
            'scans-per-location': { canvas: 'reportChartEscaneos', type: 'bar', labelKey: 'location_name', valueKey: 'scans' },
            'scans-by-device': { canvas: 'reportChartDevices', type: 'doughnut', labelKey: 'device_type', valueKey: 'scans' },
            'top-campaigns': { canvas: 'reportChartCampanas', type: 'bar', labelKey: 'campaign_name', valueKey: 'scans', indexAxis: 'y' },
            'campaign-comparison': { canvas: 'reportChartCampanas', type: 'bar', labelKey: 'campaign_name', valueKey: 'scans' },
            'campaign-roi': { canvas: 'reportChartCampanas', type: 'bar', labelKey: 'campaign_name', valueKey: 'roi' },
            'trend-analysis': { canvas: 'reportChartCampanas', type: 'line', labelKey: 'date', valueKey: 'scans' },
            'unique-vs-repeat': { canvas: 'reportChartUsuarios', type: 'bar', labelKey: 'campaign_name', valueKey: null },
            'user-demographics': { canvas: 'reportChartUsuarios', type: 'doughnut', labelKey: 'category', valueKey: 'count' }
        };

        var config = chartConfigs[reportType];
        if (!config) return;

        var chartKey = 'report_' + config.canvas;
        destroyChart(chartKey);

        var ctx = document.getElementById(config.canvas);
        if (!ctx) return;

        var labels = items.map(function (i) {
            var val = i[config.labelKey] || i.name || i.label || '';
            // Format hours
            if (config.labelKey === 'hour' && typeof val === 'number') {
                return String(val).padStart(2, '0') + ':00';
            }
            // Translate days
            if (config.labelKey === 'day' && typeof val === 'number') {
                return DAYS_ES[val] || val;
            }
            return val;
        });

        var datasets;
        if (reportType === 'unique-vs-repeat') {
            datasets = [
                {
                    label: 'Unicos',
                    data: items.map(function (i) { return i.unique_scans || i.unique_scanners || i.unique || i.unicos || 0; }),
                    backgroundColor: '#3b82f6'
                },
                {
                    label: 'Repetidos',
                    data: items.map(function (i) { return i.repeat_scans || i.repeat || i.repetidos || 0; }),
                    backgroundColor: '#f59e0b'
                }
            ];
        } else {
            var values = items.map(function (i) { return i[config.valueKey] || i.total_scans || i.total_scans || i.scan_count || i.scans || i.count || i.total || 0; });
            datasets = [{
                label: 'Valor',
                data: values,
                backgroundColor: config.type === 'line' ? 'rgba(59, 130, 246, 0.1)' : chartColors(values.length),
                borderColor: config.type === 'line' ? '#3b82f6' : undefined,
                fill: config.type === 'line',
                tension: config.type === 'line' ? 0.4 : undefined,
                pointRadius: config.type === 'line' ? 3 : undefined
            }];
        }

        var options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: reportType === 'unique-vs-repeat' || config.type === 'doughnut', position: 'bottom' }
            }
        };

        if (config.type !== 'doughnut' && config.type !== 'pie') {
            options.scales = {
                y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
                x: { grid: { display: false } }
            };
            if (config.indexAxis) {
                options.indexAxis = config.indexAxis;
            }
        }

        state.charts[chartKey] = new Chart(ctx, {
            type: config.type,
            data: { labels: labels, datasets: datasets },
            options: options
        });
    }

    function renderReportTable(reportType, items) {
        var tableConfigs = {
            'scans-per-campaign': {
                head: 'reportTableHeadEscaneos', body: 'reportTableBodyEscaneos',
                cols: [
                    { key: 'campaign_name', label: 'Campana' },
                    { key: 'scans', label: 'Escaneos', format: 'number' },
                    { key: 'percentage', label: 'Porcentaje', format: 'percent' }
                ]
            },
            'scans-per-company': {
                head: 'reportTableHeadEscaneos', body: 'reportTableBodyEscaneos',
                cols: [
                    { key: 'company_name', label: 'Empresa' },
                    { key: 'scans', label: 'Escaneos', format: 'number' },
                    { key: 'percentage', label: 'Porcentaje', format: 'percent' }
                ]
            },
            'scans-by-hour': {
                head: 'reportTableHeadEscaneos', body: 'reportTableBodyEscaneos',
                cols: [
                    { key: 'hour', label: 'Hora', format: 'hour' },
                    { key: 'scans', label: 'Escaneos', format: 'number' }
                ]
            },
            'scans-by-day-of-week': {
                head: 'reportTableHeadEscaneos', body: 'reportTableBodyEscaneos',
                cols: [
                    { key: 'day', label: 'Dia', format: 'day' },
                    { key: 'scans', label: 'Escaneos', format: 'number' }
                ]
            },
            'scans-per-location': {
                head: 'reportTableHeadEscaneos', body: 'reportTableBodyEscaneos',
                cols: [
                    { key: 'location_name', label: 'Ubicacion' },
                    { key: 'scans', label: 'Escaneos', format: 'number' },
                    { key: 'percentage', label: 'Porcentaje', format: 'percent' }
                ]
            },
            'top-campaigns': {
                head: 'reportTableHeadCampanas', body: 'reportTableBodyCampanas',
                cols: [
                    { key: 'campaign_name', label: 'Campana' },
                    { key: 'company_name', label: 'Empresa' },
                    { key: 'scans', label: 'Escaneos', format: 'number' },
                    { key: 'unique_users', label: 'Usuarios Unicos', format: 'number' }
                ]
            },
            'campaign-comparison': {
                head: 'reportTableHeadCampanas', body: 'reportTableBodyCampanas',
                cols: [
                    { key: 'campaign_name', label: 'Campana' },
                    { key: 'scans', label: 'Escaneos', format: 'number' },
                    { key: 'unique_users', label: 'Unicos', format: 'number' },
                    { key: 'conversion_rate', label: 'Conversion', format: 'percent' }
                ]
            },
            'campaign-roi': {
                head: 'reportTableHeadCampanas', body: 'reportTableBodyCampanas',
                cols: [
                    { key: 'campaign_name', label: 'Campana' },
                    { key: 'budget', label: 'Presupuesto', format: 'currency' },
                    { key: 'scans', label: 'Escaneos', format: 'number' },
                    { key: 'cost_per_scan', label: 'Costo por Escaneo', format: 'currency' },
                    { key: 'roi', label: 'ROI', format: 'percent' }
                ]
            },
            'trend-analysis': {
                head: 'reportTableHeadCampanas', body: 'reportTableBodyCampanas',
                cols: [
                    { key: 'date', label: 'Fecha', format: 'date' },
                    { key: 'scans', label: 'Escaneos', format: 'number' },
                    { key: 'unique_users', label: 'Unicos', format: 'number' }
                ]
            },
            'unique-vs-repeat': {
                head: 'reportTableHeadUsuarios', body: 'reportTableBodyUsuarios',
                cols: [
                    { key: 'campaign_name', label: 'Campana' },
                    { key: 'unique', label: 'Unicos', format: 'number' },
                    { key: 'repeat', label: 'Repetidos', format: 'number' },
                    { key: 'total', label: 'Total', format: 'number' }
                ]
            },
            'user-demographics': {
                head: 'reportTableHeadUsuarios', body: 'reportTableBodyUsuarios',
                cols: [
                    { key: 'category', label: 'Categoria' },
                    { key: 'count', label: 'Cantidad', format: 'number' },
                    { key: 'percentage', label: 'Porcentaje', format: 'percent' }
                ]
            }
        };

        var config = tableConfigs[reportType];
        if (!config) return;

        // Build header
        var headEl = document.getElementById(config.head);
        var bodyEl = document.getElementById(config.body);
        if (!headEl || !bodyEl) return;

        var headHtml = '<tr>';
        config.cols.forEach(function (col) {
            headHtml += '<th>' + col.label + '</th>';
        });
        headHtml += '</tr>';
        headEl.innerHTML = headHtml;

        // Build body
        if (items.length === 0) {
            bodyEl.innerHTML = '<tr><td colspan="' + config.cols.length + '" class="text-center text-light">Sin datos para los filtros seleccionados</td></tr>';
            return;
        }

        var bodyHtml = '';
        items.forEach(function (item) {
            bodyHtml += '<tr>';
            config.cols.forEach(function (col) {
                var val = item[col.key];
                // Try alternate key names from backend
                if (val == null || val === undefined) {
                    if (col.key === 'scans') val = item.total_scans || item.scan_count || item.scans || item.count;
                    else if (col.key === 'unique_users' || col.key === 'unique') val = item.unique_scans || item.unique_scanners || item.unique;
                    else if (col.key === 'repeat') val = item.repeat_scans || item.repeat;
                    else if (col.key === 'total') val = item.total_scans || item.total || item.scan_count;
                    else if (col.key === 'roi') val = item.scans_per_dollar || item.roi;
                    else if (col.key === 'cost_per_scan') val = item.cost_per_scan || (item.budget && item.total_scans ? (item.budget / item.total_scans).toFixed(2) : 0);
                    else val = item[col.key.replace(/_/g, '')] || '';
                }
                switch (col.format) {
                    case 'number':
                        val = formatNumber(val);
                        break;
                    case 'currency':
                        val = formatCurrency(val);
                        break;
                    case 'percent':
                        val = (val != null ? Number(val).toFixed(1) : '0') + '%';
                        break;
                    case 'date':
                        val = formatDate(val);
                        break;
                    case 'hour':
                        val = String(val).padStart(2, '0') + ':00';
                        break;
                    case 'day':
                        val = (typeof val === 'number') ? (DAYS_ES[val] || val) : val;
                        break;
                    default:
                        val = escapeHtml(String(val || ''));
                }
                bodyHtml += '<td>' + val + '</td>';
            });
            bodyHtml += '</tr>';
        });
        bodyEl.innerHTML = bodyHtml;
    }

    async function exportReport(overrideType) {
        var reportType = overrideType || state.currentSubReport;
        var params = getReportParams();
        var separator = params ? '&' : '?';
        var url = state.baseUrl.replace(/\/$/, '') + '/api/v1/export/' + reportType + params + separator + 'format=csv';

        try {
            var headers = {};
            if (state.apiKey) {
                headers['X-API-Key'] = state.apiKey;
            }
            var resp = await fetch(url, { headers: headers });
            if (!resp.ok) throw new Error('Error ' + resp.status);

            var blob = await resp.blob();
            var blobUrl = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = blobUrl;
            a.download = reportType + '_' + new Date().toISOString().split('T')[0] + '.csv';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(blobUrl);
            showToast('Archivo CSV descargado', 'success');
        } catch (err) {
            showToast('Error exportando reporte: ' + err.message, 'error');
        }
    }

    /* ========== SETTINGS (CONFIGURACION) ========== */

    function loadSettings() {
        document.getElementById('settingsApiKey').value = state.apiKey;
        document.getElementById('settingsBaseUrl').value = state.baseUrl;
    }

    function saveSettings() {
        var newKey = document.getElementById('settingsApiKey').value.trim();
        var newUrl = document.getElementById('settingsBaseUrl').value.trim() || window.location.origin;

        state.apiKey = newKey;
        state.baseUrl = newUrl;

        localStorage.setItem('qrtracker_api_key', newKey);
        localStorage.setItem('qrtracker_base_url', newUrl);

        // Also update top bar API key input
        document.getElementById('topApiKey').value = newKey;

        showToast('Configuracion guardada correctamente', 'success');
    }

    async function testConnection() {
        try {
            showToast('Probando conexion...', 'info');
            await api('GET', '/api/v1/companies');
            showToast('Conexion exitosa! La API esta respondiendo correctamente.', 'success');
        } catch (err) {
            showToast('Error de conexion: ' + err.message, 'error');
        }
    }

    /* ========== INITIALIZATION ========== */

    function init() {
        // Set API key from localStorage to top bar input
        var topKeyInput = document.getElementById('topApiKey');
        if (topKeyInput) {
            topKeyInput.value = state.apiKey;
        }

        // Sidebar navigation
        document.querySelectorAll('.nav-item').forEach(function (item) {
            item.addEventListener('click', function (e) {
                e.preventDefault();
                navigate(item.dataset.section);
            });
        });

        // Hamburger menu
        var hamburger = document.getElementById('hamburger');
        var sidebar = document.getElementById('sidebar');
        var overlay = document.getElementById('sidebarOverlay');

        hamburger.addEventListener('click', function () {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
        });

        overlay.addEventListener('click', function () {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        });

        // Top bar API key save
        document.getElementById('saveApiKeyBtn').addEventListener('click', function () {
            var val = document.getElementById('topApiKey').value.trim();
            state.apiKey = val;
            localStorage.setItem('qrtracker_api_key', val);
            showToast('Clave de API guardada', 'success');
            loadSectionData(state.currentSection);
        });

        // Close modal on overlay click
        document.getElementById('modalOverlay').addEventListener('click', function (e) {
            if (e.target === this) closeModal();
        });

        // Close modal on Escape key
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeModal();
        });

        // Load initial section
        loadDashboard();
    }

    // Run init when DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    /* ========== PUBLIC API ========== */
    return {
        // Navigation
        navigate: navigate,

        // Companies
        openCompanyModal: openCompanyModal,
        saveCompany: saveCompany,
        deleteCompany: deleteCompany,

        // Campaigns
        loadCampaigns: loadCampaigns,
        openCampaignModal: openCampaignModal,
        saveCampaign: saveCampaign,
        deleteCampaign: deleteCampaign,

        // QR Codes
        loadQrCodes: loadQrCodes,
        openQrCodeModal: openQrCodeModal,
        saveQrCode: saveQrCode,
        deleteQrCode: deleteQrCode,
        generateQr: generateQr,

        // Locations
        openLocationModal: openLocationModal,
        saveLocation: saveLocation,
        deleteLocation: deleteLocation,

        // Reports
        switchReportTab: switchReportTab,
        switchSubReport: switchSubReport,
        loadCurrentReport: loadCurrentReport,
        exportReport: exportReport,

        // Settings
        saveSettings: saveSettings,
        testConnection: testConnection,

        // Utilities
        closeModal: closeModal,
        showToast: showToast
    };

})();
