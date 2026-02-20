# <center>LunaStore Installation Guide</center>

First, ensure that your server meets the following system requirements:

* **CPU:** 2 or more cores
* **RAM:** 2 GB or more
* **Storage:** 10 GB or more available space
* **Software:** Docker, Docker Compose, Python 3.12+, PostgreSQL 17+, PIP, and an OpenID Connect service (e.g., Authentik).

### 1. Cloning the Source Code

To begin, clone the LunaStore repository:

```bash
git clone https://git.myslivets.com/myslivets/lunastore
cd lunastore
```

### 2. Installing Dependencies

Once you have the source code, install the required Python libraries:

```bash
pip install -r requirements.txt
```

### 3. Configuration

Open `.env.example` in any text editor and configure the environment variables:

#### General & OpenID Settings

| Variable | Description | Default/Example |
| --- | --- | --- |
| `SITE_URL` | Your website's base URL (leave empty if unsure) | `""` (None) |
| `OIDC_CLIENT_ID` | Client ID from your OpenID Connect service |  |
| `OIDC_CLIENT_SECRET` | Client Secret from your OpenID Connect service |  |
| `OIDC_ENDPOINT` | OpenID service discovery endpoint |  |
| `OIDC_TOKEN_ENDPOINT` | Token exchange endpoint |  |
| `OIDC_USER_ENDPOINT` | User info endpoint |  |
| `LOGIN_REDIRECT_URL` | URL where users are redirected after OIDC login | `http://localhost:8088/admin` |
| `LOGOUT_REDIRECT_URL` | URL where users are redirected after logging out |  |
| `OIDC_SIGN_ALGO` | Signature algorithm (usually `RS256`) | `RS256` |
| `OIDC_JWKS_ENDPOINT` | URL to your OpenID service's JWKS |  |

> **Note:** OpenID parameters are optional. LunaStore uses OIDC as an additional login method for the admin panel, but the site and admin panel can function perfectly without it using standard credentials.

#### Database Settings (PostgreSQL)

| Variable | Description | Example |
| --- | --- | --- |
| `DB_NAME` | Database name | `lunastoredb` |
| `DB_USER` | Database username | `postgres` |
| `DB_PASSWORD` | Database password |  |
| `DB_HOST` | Database IP or Domain | `localhost` |
| `DB_PORT` | Database port | `5432` |

After filling in the values, rename the file to `.env`:

```bash
mv .env.example .env
```

### 4. Database Migrations

Apply migrations to set up the database schema:

```bash
python3 manage.py migrate
```

If no errors appear in the console, the database is ready.

### 5. Create Admin Account

To access the admin panel, you need to create a superuser:

```bash
python3 manage.py createsuperuser
```

### 6. Allowed Hosts

Add your server's IP address or domain to the `ALLOWED_HOSTS` list in `lunastore/settings.py`:

```python
ALLOWED_HOSTS = ['your_ip_or_domain']
```

### 7. Deployment

Finally, build and start the project using Docker:

```bash
docker compose up --build -d
```

## ℹ️ Additional Information

LunaStore consists of two main containers:

1. **lunaStore**: handles the main website functionality (runs on port **9088**).
2. **lunaStoreAdmin**: handles the administration panel (runs on port **8088**).

* **Accessing the Admin Panel:** Go to `http://your-ip:8088/admin`.
* **Changing Ports:** If you need to use different ports, modify them in the `docker-compose.yml` file.