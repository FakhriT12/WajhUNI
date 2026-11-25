WAJHUNI - LOCAL RESTART GUIDE (WINDOWS)
=======================================

Project folder: C:\Users\ASUS\wajhuni

Use these steps to restart the local development setup after it has stopped.
Keep the backend and frontend terminals open while you use the project.


1. START DOCKER AND THE DATABASE SERVICES
-----------------------------------------

1. Open Docker Desktop and wait until Docker is running.
2. In Docker Desktop, start the existing PostgreSQL container. Start Redis too
   if it is part of your local setup.
3. Check that the containers show as running and that their ports are mapped
   to your computer.

Note: This repository does not currently include a Dockerfile or a
docker-compose.yml file, so there is no project-specific "docker compose up"
command here. Start the containers that were previously created in Docker
Desktop.


2. CHECK THE DATABASE CONNECTION IN DBEAVER
-------------------------------------------

1. Open backend\.env and check that DATABASE_URL points to the PostgreSQL
   container's host, port, and database. Do not copy passwords or secret values
   into this guide or share them.
2. Open the corresponding connection in DBeaver and click "Test Connection".
   The host, port, database, and username must match the backend configuration.
   The usual local PostgreSQL port is 5432, but use the port actually mapped by
   your container.
3. Once connected, run:

       SELECT 1;

   DBeaver should return 1. Leave the database container running.


3. START THE BACKEND
--------------------

Open a PowerShell terminal and run:

    cd C:\Users\ASUS\wajhuni\backend
    .\wajhuni_env\Scripts\Activate.ps1
    uvicorn app.main:app --reload

The terminal should show that Uvicorn is listening on port 8000. Keep this
terminal open.

Check the API in a browser:

    http://127.0.0.1:8000/health

Expected response:

    {"status":"ok","service":"wajhuni-api"}

Interactive API documentation:

    http://127.0.0.1:8000/docs

The backend reads its configuration from backend\.env. It needs DATABASE_URL,
REDIS_URL, and JWT_SECRET_KEY to be set. If startup reports a missing setting,
check that backend\.env exists and contains the required values.


4. REGISTER A TEST USER IN INSOMNIA
-----------------------------------

Create a POST request in Insomnia:

    http://127.0.0.1:8000/api/v1/auth/register

Set the body type to JSON and send:

    {
      "full_name": "Test User",
      "email": "your-new-test-address@tbs.u-tunis.tn",
      "password": "ChangeThis123!"
    }

Use an email domain that is active in the database. The example TBS domain
works only if its seed data has been added. Use a unique email address that has
not already been registered. The password must be at least 10 characters.

The expected status is 201 Created. In development, the backend terminal prints
a verification token for the submitted email. To verify the address, create
another POST request:

    http://127.0.0.1:8000/api/v1/auth/verify-email

Send this JSON body, replacing the placeholder with the token printed in the
backend terminal:

    {
      "token": "PASTE_THE_DEVELOPMENT_TOKEN_HERE"
    }

After verification succeeds, test login with another POST request:

    http://127.0.0.1:8000/api/v1/auth/login

Send the same email and password used for registration:

    {
      "email": "your-new-test-address@tbs.u-tunis.tn",
      "password": "ChangeThis123!"
    }

A successful login returns an access token and a refresh token. The access
token expires after the configured lifetime (15 minutes by default).

To test refresh, create a POST request:

    http://127.0.0.1:8000/api/v1/auth/refresh

Send the current refresh token from the login response:

    {
      "refresh_token": "PASTE_CURRENT_REFRESH_TOKEN_HERE"
    }

A successful refresh returns a new access token and refresh token. The old
refresh token is single-use and can no longer be used.

To test logout, create a POST request:

    http://127.0.0.1:8000/api/v1/auth/logout

Send the latest refresh token in the same JSON shape. The endpoint returns
204 No Content. Logging out revokes the refresh token; an already-issued access
token remains valid until it expires.


5. (OPTIONAL) START THE FRONTEND
--------------------------------

Open a second terminal and run:

    cd C:\Users\ASUS\wajhuni\frontend
    npm run dev

Open the site at:

    http://localhost:3000

Keep the frontend terminal open while using the site.


WHEN STOPPING / STARTING AGAIN
------------------------------

- To stop a development server, press Ctrl+C in its terminal.
- To restart, make sure Docker and the database containers are running, then
  repeat the backend and (if needed) frontend commands above.
- Activating the virtual environment only affects its current terminal.
- A normal restart does not require re-running database migrations.
- If a command fails, read the error in that service's terminal first. Check
  Docker container status, backend\.env configuration, and the DBeaver
  connection before retrying.
