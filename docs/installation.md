# <center>LunaStore Installation Instructions</center>

First of all, you should make sure that your server for installation meets the following requirements:

* **CPU**: 2 or more cores
* **RAM**: 2 or more GB of RAM
* **Storage**: 10 or more GB of disk space
* **..as well as the presence of installed Docker, Docker Compose, Python 3.12+, PostgreSQL 17+, PIP, an OpenID (Authentik-like) service, and our LunaSpire engine**

BTW, we recently introduced an automatic LunaStore installer (located in the project root; setup.sh / setup.ps1, depending on your system).

Whether to use manual or automatic installation is entirely up to you.

### 1. Downloading the sources

To begin with, you should clone the LunaStore sources:

```bash
git clone [https://git.myslivets.com/myslivets/lunastore](https://git.myslivets.com/myslivets/lunastore)
```

### 2. Installing libraries

After you have downloaded the sources, you need to download the required libraries:

```bash
pip install -r requirements.txt
```

### 3. Configuration setup

Then, after the installation, open `.env.example` in any text editor convenient for you and configure it:

#### Main configuration and OpenID configuration

| Variable | Description | Default |
| ------ | ----------- | ---- |
| SITE_URL | Your site's URL; leave blank if you don't know what you are doing | `""` (None) |
| OIDC_CLIENT_ID | Client ID of your OpenID (Authentik-like) service; | |
| OIDC_CLIENT_SECRET | Client Secret Key of your OpenID service; | |
| OIDC_ENDPOINT | Endpoint for the OpenID service | |
| OIDC_TOKEN_ENDPOINT | Endpoint for the token | |
| OIDC_USER_ENDPOINT | Endpoint for getting user info in the OpenID service | |
| LOGIN_REDIRECT_URL | The URL to which the user will be redirected when logging into an account via your OpenID service (usually, you should redirect the user to the LunaStore admin panel itself; for example: `http://localhost:8088/admin`) | |
| LOGOUT_REDIRECT_URL | The same as LOGIN_REDIRECT_URL, but here the URL is for logging out of the account | |
| OIDC_SIGN_ALGO | Signing algorithm for OpenID, but usually you should specify `RS256` (depends on your OpenID service) | `RS256` |
| OIDC_JWKS_ENDPOINT | URL to your JWKS in your OpenID service | |

> **Clarification**: Usually, the parameters related to OpenID can be left untouched, because OpenID is used in LunaStore as an additional method for logging into the admin account. At the same time, the admin panel can easily work without OpenID, just like the entire site.

#### DB Setup (PostgreSQL)

| Variable | Description | Default |
| ------ | ----------- | ----- |
| DB_NAME | The name of your database (for example, lunastoredb) | `lunastoredb` |
| DB_USER | The account name of your database (for example, postgres) | `postgres` |
| DB_PASSWORD | The password for your database | |
| DB_HOST | IP/domain of your database (make sure in advance that your database can be connected to via this IP/domain) | `127.0.0.1` |
| DB_PORT | The port on which the database is running | `5432` |

#### Internal LunaStore Configuration

| Variable | Description | Default |
| ------ | ----------- | ----- |
| EXTERNAL_MEDIA_URL | Direct HTTP link to the folder with internal UGC content (largely, specifying it is not mandatory, but still, it wouldn't hurt) | `http://192.168.1.10/media/` |
| SECRET_KEY | The secret key from Django itself (i.e., the site); of course, it's better not to show this key to anyone | mysuperkey123 |
| DEBUG | Project debugging mode (roughly speaking, with DEBUG running, you will get a lot of logs directly for debugging the project), but for production we advise setting it to True | False |
| LUNASPIRE_SECRET_KEY | The secret key from our LunaSpire engine; it must match what you specified in the .env of LunaSpire itself | supersecretkey |
| LUNASPIRE_URL | Direct URL to the LunaSpire instance | `http://192.168.1.10:8080` |
| API_URL | Direct URL to the LunaStore API | `http://192.168.1.10:7088` |
| ALLOWED_HOSTS | A list of IPs/addresses (without http/https) from which it will be possible to access LunaStore. `;` in this variable is a separator between multiple IPs/domains | `192.168.1.10;192.168.1.1` |
| CORS_ALLOWED_ORIGINS | Allowed IPs/domains for CORS. The separator here is the same as in ALLOWED_HOSTS | `http://192.168.1.10;http://192.168.1.1` |
| MOTD_LIST | MOTD of your LunaStore instance; There can be several of them, and they will be shown randomly. The separator here is the same. | `Windows XP;time to serve drinks and decide fates` |
| BCRYPT_ROUNDS | Indicates how many times the hashing process will be performed on the bcrypt side; Usually, it is better to leave the default value | 12 |
| REGISTRATION_IS_ENABLED | Indicates whether registration in LunaStore is enabled | `True` |
| DEVELOPER_REGISTRATION_IS_ENABLED | Indicates whether it is necessary to obtain developer status before uploading an application to LunaStore | `True` |
| RETENTION_ACTIVITY_LOG_DAYS | Indicates how many days data from the User Activity Log (including user IPs) is stored based on the GDPR policy | 0 |
| INVITES_ON_REGISTER | Indicates whether registration is available only by invite code | `True` |
| MAX_INVITE_USES_COUNT | Indicates how many times users can be invited per 1 invite code | 3 |
| MAX_INVITE_DAYS_LIMIT | Indicates how many times users can be invited per day | 7 |

And now, rename `.env.example` to `.env`:

```bash
mv .env.example .env
```

### 4. Applying DB migrations

After that, you will need to apply migrations to your database for LunaStore to work correctly:

```bash
make migrate
```
..or `make dev-migrate`, all this depends on whether you want to bring up the production or development version of LunaStore.

And then:

```bash
make cachetable
```
..or `make dev-cachetable`

### 5. Creating a root user

In order for you to be able to access the admin panel without any problems, you need to create an administrator account:

```bash
make superuser
```
..or `make dev-superuser`

### 6. Building LunaStore

And the finale - building the sources and starting the instance! To build and start your LunaStore, write the following:

```bash
make build
```
..or `make dev-build`

And then, after building the project, write the following:

```bash
make up
```
..or `make dev-up`

## ℹ️ Additional information

LunaStore consists of 3 containers:

1. **lunaStore**: holds the main functionality and pages of the site (runs on port **9088**)
2. **lunaStoreAdmin**: holds the functionality of the admin panel and other things necessary for the adequate operation of the admin panel (runs on port **8088**)
3. **lunaStoreAPI**: holds the API functionality (runs on port **7088**)

* **Access to the admin panel**: to get there, go to `http://your-ip:8088/admin`
* **Changing ports**: if you want to change ports, you will need to change them in the `docker-compose.yml` or `docker-compose.dev.yml` file (depending on which version of LunaStore you brought up)
