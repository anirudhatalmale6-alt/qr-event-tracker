# QR Event Tracker

Plataforma de seguimiento de escaneos QR para campanas de marketing.

## Requisitos

- Python 3.12+
- PostgreSQL 16+
- Docker y Docker Compose (opcional)

## Inicio Rapido con Docker

```bash
# Copiar configuracion
cp .env.example .env

# Editar .env con tus valores
# nano .env

# Levantar servicios
docker compose up -d

# La aplicacion estara disponible en http://localhost:8000
```

## Inicio Manual

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con la URL de tu base de datos PostgreSQL

# Ejecutar migraciones
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Panel de Administracion

Accede a `http://localhost:8000/` para el panel de administracion.

Ingresa tu API Key en el campo superior derecho (por defecto: `changeme-api-key-12345`).

## Endpoints Principales

| Endpoint | Metodo | Descripcion |
|---|---|---|
| `/scan/{code}` | GET | Escaneo de codigo QR (publico) |
| `/api/v1/companies` | CRUD | Gestion de empresas |
| `/api/v1/campaigns` | CRUD | Gestion de campanas |
| `/api/v1/qr-codes` | CRUD | Gestion de codigos QR |
| `/api/v1/qr/generate` | POST | Generar imagen QR |
| `/api/v1/locations` | CRUD | Gestion de ubicaciones |
| `/api/v1/reports/{tipo}` | GET | Reportes analiticos |
| `/api/v1/export/{tipo}` | GET | Exportar reportes (CSV) |

## Tipos de Reportes

- `scans-per-campaign` - Escaneos por campana
- `scans-per-company` - Escaneos por empresa
- `scans-by-geography` - Escaneos por geografia
- `scans-by-device` - Escaneos por dispositivo
- `scans-by-hour` - Escaneos por hora del dia
- `scans-by-day-of-week` - Escaneos por dia de la semana
- `top-campaigns` - Campanas con mas escaneos
- `unique-vs-repeat` - Visitantes unicos vs repetidos
- `campaign-comparison` - Comparacion de campanas
- `scans-per-location` - Escaneos por ubicacion fisica
- `user-demographics` - Demografia de usuarios
- `campaign-roi` - ROI de campanas
- `trend-analysis` - Analisis de tendencia
- `geographic-heatmap` - Datos para mapa de calor
- `conversion-funnel` - Embudo de conversion

## Seguridad

Todos los endpoints administrativos requieren el header `X-API-Key`.
El endpoint de escaneo tiene rate limiting (60 solicitudes/minuto por IP).
