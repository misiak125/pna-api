# PNA API - Backend and REST API Service

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.3-black.svg)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy%202.x-red.svg)](https://www.sqlalchemy.org/)
[![Docker](https://img.shields.io/badge/Docker-MariaDB-2496ED.svg)](https://www.docker.com/)

Server-side application for the PNA dealership management and vehicle reservation platform. It provides a secure REST API consumed by desktop administration clients, manages transactional persistence with MariaDB/MySQL, and coordinates automated local and cloud backups (Backblaze B2).

---

## Origin and Project Evolution

This project is part of a decoupled refactoring of an earlier monolithic system:
- **Predecessor (Full-Stack Monolith):** [motonita-rezerwacje](https://github.com/misiak125/motonita-rezerwacje) - The original full-stack implementation using SQLite.
- **Current Decoupled Architecture:**
  - **Backend API:** [pna-api](https://github.com/misiak125/pna-api) - this repository
  - **Desktop Client:** [pna-client](https://github.com/misiak125/pna-client) - Tkinter GUI desktop application

---


## Architecture and Database Deployment (Dev vs. Production)

### Local Development (Docker Compose)
The included `docker-compose.yml` file is designed strictly as a convenience tool for the **local development environment**. It starts an isolated MariaDB container (`dev-mariadb`) on `127.0.0.1:3306` so developers can get started immediately without installing a database server on their host machine.

### Production Environment and Standalone Database
Docker is **not** used or required in production:
- In production (such as cPanel hosting, VPS, or dedicated servers), the API application runs via a WSGI server (Phusion Passenger via `passenger_wsgi.py` or Gunicorn) and connects directly to a managed or native MariaDB/MySQL database.
- Docker is not required for local development either: you can simply create a MariaDB or MySQL database on your machine or server and enter its connection parameters in `.env`. The application will connect directly using SQLAlchemy.

---

## Key Highlights and Architecture

- Security and Authentication:
  - Cryptographically hashed API keys (SHA-256) evaluated via the `X-API-Key` request header.
  - Dedicated CLI tool (`generate_key.py`) for granting role-based access tokens per employee.
  - Rate limiting via Flask-Limiter to defend against brute-force attacks and service degradation.
  - Enforced HTTPS encryption for all non-local traffic.
- Data Synchronization and Performance:
  - Lightweight change-tracking mechanism (`/api/sync-status`) via `AppState` entity timestamps, allowing clients to poll efficiently without database load.
  - SQLAlchemy 2.x ORM configured with connection pool pre-pinging (`pool_pre_ping`).
  - Production WSGI compatibility (Phusion Passenger / cPanel via `passenger_wsgi.py`).
- Fault Tolerance and Backup Pipelines:
  - Automated database dumping stored locally and mirrored to off-site cloud storage via Backblaze B2 SDK.

---

## Directory Structure

```text
pna-api/
├── logs/                   # Rotating server log files
├── src/
│   ├── __init__.py         # Flask app factory, database engine, rate limiting, and logging setup
│   ├── main.py             # REST API endpoint definitions
│   ├── models.py           # SQLAlchemy domain models
│   ├── utils.py            # Security decorators, audit trail helpers, synchronization routines
│   ├── local_backup.py     # Local database backup utility
│   └── b2_backup.py        # Cloud backup script targeting Backblaze B2
├── docker-compose.yml      # MariaDB service container configuration
├── generate_key.py         # CLI utility to issue new API tokens
├── passenger_wsgi.py       # WSGI entrypoint for hosting environments
└── requirements.txt        # Server dependencies
```

---

## Getting Started

### Prerequisites
- Python 3.10 or higher
- MariaDB or MySQL database (either via Docker Desktop for local dev, or an existing/managed database)

### 1. Environment Configuration
From the `pna-api/` directory, create a `.env` configuration file:
```bash
cp .env.example .env
```
Configure your database credentials in `.env`:
- If using Docker Compose for local dev, the default credentials in `.env.example` work out of the box.
- If using your own local or remote MariaDB/MySQL server, update `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, and `DB_NAME` accordingly.

### 2. Virtual Environment and Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate       # On Linux/macOS
# or: .venv\Scripts\activate    # On Windows

pip install -r requirements.txt
```

### 3. Database Initialization

#### Option A: Quick Local Database via Docker Compose (Dev Only)
If you have Docker Desktop installed and want a quick containerized database:
```bash
docker compose up -d
```
The container `dev-mariadb` binds port `3306` to `127.0.0.1`.

#### Option B: Existing Database
Create a database (e.g. `pna_dev` or your production database name) on your MariaDB/MySQL instance. Tables will be created automatically by SQLAlchemy upon starting the application.

### 4. Generate an API Key
Generate an initial API key for client authentication:
```bash
python generate_key.py <username>
```
Copy the unhashed key displayed in the terminal output (e.g. `a1b2c3d4...`). You will use this key when connecting from the desktop client.

### 5. Run the API Server

#### Local Development Run:
```bash
python -m src.main
```
The server will start listening at `http://127.0.0.1:5000`.

#### Production WSGI Deployment:
In production, point your web server / WSGI host (e.g. cPanel Application Manager, Phusion Passenger, Gunicorn) to `passenger_wsgi.py` or `src.main:application`.

---

## API Reference Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/sync-status` | Returns timestamp of the most recent database modification (used by client Smart Polling) |
| `GET` | `/api/products/free` | Retrieves available inventory with filtering |
| `GET` | `/api/reservations` | Lists active and completed reservations |
| `POST` | `/api/reservations` | Creates a new reservation |
| `POST` | `/api/products` | Registers a new vehicle into inventory |
| `GET` | `/api/customers` | Searches customer records and purchase history |
| `GET` | `/status` | Server health check endpoint |

All data modification and inquiry routes require the authorization header:
```http
X-API-Key: <your_api_token>
```

---

## Auditability and Data Integrity

- Full Change History: Every record modification logs user identity, timestamp, and field deltas into the `history` attribute.
- Rotating Logs: Server logs automatically rotate to maintain bounded storage footprint.
