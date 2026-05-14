# **LEGAL_WATCH_DOG**

**LEGAL_WATCH_DOG** is an AI-powered monitoring platform that automatically tracks policy, regulatory, and data changes across global jurisdictions. Built for enterprise teams, it centralizes monitoring, collaboration, and workflow management, ensuring organisations never miss critical updates and can act on them quickly and confidently.

---

## **Cloning the Repository**

1. **Clone the repository:**

```bash
git clone https://github.com/hngprojects/legal-watch-dog-be.git
```

2. **Navigate into the project directory:**

```bash
cd legal-watch-dog-be
```

3. **Switch to the development branch** (if not already on `dev`):

```bash
git checkout dev
```

---

## **Project Architecture**

```bash
legal-watch-dog-be/
│
├── alembic/                             # Alembic migration system
│   ├── versions/                        # Auto-generated migration scripts
│   ├── env.py                           # Alembic environment setup
│   ├── script.py.mako                   # Template for migration scripts
│   └── README                           # Alembic docs / notes
│
├── app/                                 # Main application package
│   ├── __init__.py
│   │
│   ├── api/                             # API layer for routing and versioning
│   │   ├── __init__.py
│   │   │
│   │   ├── core/                        # Core API utilities & config
│   │   │   ├── dependencies/            # Depends(), email utilities, etc.
│   │   │   │   └── email/
│   │   │   │       └── __init__.py
│   │   │   ├── middleware/              # App middlewares (auth, logging, etc.)
│   │   │   │   └── __init__.py
│   │   │   └── config.py                # Core config models/settings
│   │   │
│   │   ├── db/                          # Database module
│   │   │   ├── __init__.py
│   │   │   └── database.py              # DB engine/session setup (SQLModel)
│   │   │
│   │   ├── utils/                       # Helper utilities shared across API
│   │   │   └── __init__.py
│   │   │
│   │   ├── modules/                     # Modules folder for API versions
│   │       └── v1/                      # Version 1 of the API
│   │           ├── __init__.py
│   │           │
│   │           ├── api_access/          # API Access module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── auth/                 # Authentication module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── jurisdictions/       # Jurisdictions module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── notifications/       # Notifications module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── organization/        # Organization module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── projects/            # Projects module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── scraping/            # Scraping module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── tickets/             # Tickets module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── users/               # Users module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           └── waitlist/            # Waitlist module
│   │               ├── __init__.py
│   │               ├── models/
│   │               ├── routes/
│   │               ├── schemas/
│   │               └── service/
│
├── tests/                               # Test suite (pytest)
│   └── __init__.py
│
├── .venv/                               # Local virtual environment
├── .env                                 # Local environment variables
├── .env.sample                          # Template for environment variables
├── .gitignore                           # Files/folders to ignore in Git
├── .python-version                      # Python version used by pyenv
├── alembic.ini                          # Alembic configuration file
├── CONTRIBUTING.md                      # Guidelines for contributors
├── LICENSE                              # License information (MIT, Apache, etc.)
├── main.py                              # FastAPI app entry point
├── pyproject.toml                       # Project dependencies + build config
├── README.md                            # Documentation & setup guide
├── uv.lock                              # Lockfile generated by uv
```

---

## **Setup Instructions**

1. **Install UV (if not already installed)**

```bash
# Using curl (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version

# Or using pip
pip install uv
uv --version
```

2. **Create a virtual environment:**

```bash
python3 -m venv .venv
```

3. **Activate the virtual environment:**

* On macOS/Linux:

```bash
source .venv/bin/activate
```

* On Windows (PowerShell):

```bash
.venv\Scripts\Activate
```

4. **Add or install project dependencies (optional)**
   If you need to add new packages, run:

```bash
uv add <package_name>
uv sync
```
   if you need to install packages, run:
```bash
uv pip install -r pyproject.toml
```

> This updates `uv.lock` automatically.

5. **Create a `.env` file from `.env.sample`:**

```bash
cp .env.sample .env
```

6. **Run the application locally:**

```bash
uv run python main.py --reload
```

> The app will start on the port defined in your `.env` file (default: `8000`).

---

## **Realtime Websocket Updates**

1. **Start Redis** so pub/sub channels are available (`REDIS_URL` is reused for realtime traffic).
2. **Enable the feature flag** by setting the following variables in `.env`:

   ```env
   ENABLE_REALTIME_WEBSOCKETS=true
   REALTIME_WEBSOCKET_PATH=/ws
   REALTIME_NOTIFICATIONS_CHANNEL=events:notifications
   REALTIME_SCRAPE_CHANNEL=events:scrape_jobs
   REALTIME_HEARTBEAT_INTERVAL=30
   ```

3. **Run the API** (e.g., `uvicorn main:app --reload`). The websocket router is mounted automatically when the flag is `true`, and the application lifespan starts a Redis -> websocket relay bridge.
4. **Connect from the frontend** using `ws://<host>:<port>/ws?token=<JWT>`. The `token` query parameter must contain a valid user access token; connections without it are rejected.
5. **Subscribe/receive events.** After database commits, notification and scrape job services emit domain events that the bridge broadcasts only to the intended recipients. Clients can also send lightweight subscription messages over the socket to control which topics they receive.

---

## **Database Setup**

### Step 1: Create a Database User

```sql
CREATE USER db_user WITH PASSWORD 'your_password';
```

* Replace `db_user` → your preferred database username.
* Replace `'your_password'` → a secure password.

---

### Step 2: Create the Database

```sql
CREATE DATABASE legal_watch_dog_db;
```

* Replace `legal_watch_dog_db` → your preferred database name.

---

### Step 3: Grant Permissions

```sql
GRANT ALL PRIVILEGES ON DATABASE legal_watch_dog_db TO db_user;
```

---
\q

### Step 4: Update `.env` File

```env
DATABASE_URL=postgresql://db_user:your_password@localhost/legal_watch_dog_db
```

---

### Step 5: Verify Connection

```bash
psql -U db_user -d legal_watch_dog_db -h localhost
```

---

### Step 6: Run Database Migrations

```bash
alembic upgrade head
```

> **Do not run** `alembic revision --autogenerate -m 'initial migration'` initially.

---

### Step 7: Updating Migrations

When adding new tables or modifying models:

```bash
alembic revision --autogenerate -m "Migration message"
alembic upgrade head
```

---

## **Running Tests with Pytest**

1. **Run all tests:**

```bash
pytest
```

2. **Run tests with coverage:**

```bash
uv add pytest-cov
pytest --cov=api
```

---

## **Code Quality & Linting**

### Running Linters (Ruff)

1. **Check linting with Ruff:**

```bash
uv run ruff check .
```




2. **Check formatting with Ruff:**

```bash
uv run ruff format --check .
```

3. **Auto-fix lint errors and formatting:**

```bash
uv run ruff check . --fix
uv run ruff format .
```

---

## **Pre-Commit Hooks (Code Quality)**

To maintain code quality and consistency, this project uses pre-commit hooks for linting and formatting. These hooks automatically run checks before each commit to catch errors early and ensure the codebase stays clean.

**Setup Instructions:**

1. Install the pre-commit package (if not already installed):

```bash
pip install -r -requirements.txt
```
or

```bash
uv add pre-commit
```

2. Install the hooks defined in the repository:

```bash
pre-commit install
```

3. Run all hooks against all files manually to check your code before committing:

```bash
pre-commit run --all-files
```

After this setup, pre-commit will automatically run linting and formatting checks before each commit.

---

## **Testing CI Locally with `act`**

You can run GitHub Actions workflows locally using **act**.

### **Install act**

**macOS (Homebrew):**

```bash
brew install act
```

**Linux:**

```bash
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
sudo mv ./bin/act /usr/local/bin/act
```

**Windows (Chocolatey):**

```powershell
choco install act-cli
```

---

### **Run the CI workflow locally**

> Before running act, make sure your local database credentials in your `.env` match those configured in the CI workflow. For example:

```env
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=user
DB_PASS=password
DB_NAME=dbname
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

```bash
act pull_request
```

If your workflow uses Docker services (Postgres, Redis), run with a larger image:

```bash
act pull_request -P ubuntu-latest=catthehacker/ubuntu:act-latest
```

You can also run with verbose mode:

```bash
act -v pull_request
```

---

## **Starting the Celery Server**

### **On Linux or macOS**

#### Scraping Worker

Handles scraping tasks, optimized for concurrency with gevent:

```bash
celery -A app.celery_app worker \
  --pool=gevent \
  --concurrency=200 \
  --queues=scraping \
  --loglevel=info
```

#### LLM / Processing Worker

Handles processing tasks, including notifications and other high-priority jobs:

```bash
celery -A app.celery_app worker \
  --pool=prefork \
  --concurrency=4 \
  --queues=processing \
  --loglevel=info
```

#### Persistence Worker

Handles database persistence tasks, optimized for stability:

```bash
celery -A app.celery_app worker \
  --pool=prefork \
  --concurrency=2 \
  --queues=persistence \
  --hostname=persister@%h \
  --loglevel=info \
  --max-tasks-per-child=100 \
  --prefetch-multiplier=1
```

#### Beat Scheduler

Schedules periodic tasks:

```bash
celery -A app.celery_app beat --loglevel=info
```

> Run each command in a **separate terminal window** or as background processes.

---

### **On Windows**

#### Scraping Worker

```bash
python -m celery -A app.celery_app worker \
  --pool=threads \
  --concurrency=200 \
  --queues=scraping \
  --loglevel=info
```

#### LLM / Processing Worker

```bash
python -m celery -A app.celery_app worker \
  --pool=threads \
  --concurrency=4 \
  --queues=processing \
  --loglevel=info
```

#### Persistence Worker

```bash
python -m celery -A app.celery_app worker \
  --pool=threads \
  --concurrency=2 \
  --queues=persistence \
  --hostname=persister@%h \
  --loglevel=info \
  --max-tasks-per-child=100 \
  --prefetch-multiplier=1
```

#### Beat Scheduler

```bash
python -m celery -A app.celery_app beat --loglevel=info
```
---

## **Contribution Guidelines**

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request to understand our development process, testing requirements, and code standards.