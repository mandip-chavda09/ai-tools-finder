# AI Tool Finder — MongoDB + Vercel

## Project structure

Keep your existing `static/` folder (CSS, logos, icons, and images) alongside `app.py`.
The six HTML templates are in `templates/`.

## 1. Install dependencies locally

```bash
pip install -r requirements.txt
```

## 2. Set local environment variables (Windows PowerShell)

```powershell
$env:MONGO_URI="your MongoDB Atlas connection string"
$env:FLASK_SECRET_KEY="a-long-random-secret"
python app.py
```

Database name: `ai_tools_db`
Collections: `ai_tools` and `users`

MongoDB Atlas creates the collections automatically when the first documents are inserted.
If you imported your data already, confirm that the collection names are exactly `ai_tools` and `users`.

## 3. Deploy

Push `app.py`, `requirements.txt`, `vercel.json`, `templates/`, and your existing `static/` folder to GitHub.
Import the repository into Vercel.

In Vercel → Project → Settings → Environment Variables, add:
- `MONGO_URI` = your Atlas connection string (include the database name if desired)
- `FLASK_SECRET_KEY` = a long random secret

Add both to Production (and Preview/Development if you use those environments), save, then redeploy.

## Important notes

- Do not commit your MongoDB URI or Flask secret to GitHub.
- In Atlas Network Access, allow connections from Vercel. `0.0.0.0/0` is a broad access rule; use it only if needed and protect the database with a strong database-user password.
- New registrations are stored with Werkzeug password hashes.
- Imported legacy plaintext passwords are upgraded to hashes after a successful login. If your imported passwords are already hashes, this app checks them with Werkzeug's `check_password_hash`.
- The app expects tool documents to have fields such as `name`, `description`, `category`, `url`, `tags`, `pricing`, and optionally `logo` and `created_at`.
- The templates were retained as uploaded. Keep their referenced CSS and image files in the original `static/` folder.
