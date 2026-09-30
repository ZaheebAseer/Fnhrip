# Quick start (Windows)

Open PowerShell in this folder (the one that contains `backend` and `frontend`).

1. Create your settings file:

   ```
   copy .env.example .env
   notepad .env
   ```

2. In Notepad, replace every `replace-with-...` value after the `=` sign. Use a long random
   value for `FNHRIP_SECRET_KEY` and your own password for each user. No spaces and no
   quotation marks. Save with Ctrl+S (make sure the file is named `.env`, not `.env.txt`).

3. Start the app. In PowerShell, use `.\` before the file name:

   ```
   .\run.bat
   ```

   This creates the virtual environment, installs the requirements, seeds the demo database
   and starts the server. The login page opens at http://localhost:5000/login.html.

4. Sign in with username `admin` and the value you set for `FNHRIP_ADMIN_PASSWORD`.
   The other users are `officer`, `operator`, `ml_engineer` and `viewer`.

To stop the server, press Ctrl+C in the terminal.

## Troubleshooting

- "run.bat is not recognized": type `.\run.bat` (with the dot and backslash) or `cmd /c run.bat`.
- "Database seeding failed": check that `.env` exists, is named exactly `.env`, and has a value on all six lines.
- Login says unauthorized: the password must match `.env` exactly. Edit `.env`, save, and restart.
- The page looks old: press Ctrl+Shift+R to reload without the browser cache.
