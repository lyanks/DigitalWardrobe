# Putting Digital Wardrobe online (free)

Goal: open the app on your phone at `https://YOURNAME.pythonanywhere.com`,
pay nothing, and keep changing the code in PyCharm whenever you like.

Everywhere below, `YOURNAME` means your PythonAnywhere username.

## Why PythonAnywhere

| Need | PythonAnywhere free plan |
| --- | --- |
| Run a Flask app | Yes, it is built for Python web apps |
| Keep the database | SQLite is a normal file on its disk, so it stays between restarts |
| Keep uploaded photos | Also normal files on disk (512 MB in total) |
| HTTPS (needed for Google login) | Yes, free |
| Card details | Not asked for |

Most other free hosts (Render, Railway, Fly, Vercel) either sleep, ask for a
card, or wipe the disk on every restart, which would delete `wardrobe.db`
and every photo. PythonAnywhere keeps both.

The limits worth knowing:

- **Every 3 months** PythonAnywhere emails you; log in and press
  **"Run until 3 months from today"** on the Web tab, or the site is switched off
  (nothing is deleted, you can switch it back on).
- **The internet is filtered** on free accounts: the app can only reach sites
  on their [allow-list](https://www.pythonanywhere.com/whitelist/). Google
  login and GitHub are on it. "Fill in from a shop link" (autofill) works only
  for shops on that list; for others, type the details by hand.
- One website per account, and the address is fixed to `YOURNAME.pythonanywhere.com`.

## How the pieces fit

```
PyCharm (your computer) --git push--> GitHub --git pull--> PythonAnywhere --https--> your phone
       code + tests                    code only            code + .env + wardrobe.db + uploads/
```

Git only carries **code**. `.env`, `wardrobe.db` and `uploads/` are in
`.gitignore`, so the server keeps its own secrets, its own database and its
own photos. Pushing new code never overwrites your clothes.

---

## Part 1. One-time setup (about 20 minutes)

### 1. Push your code to GitHub

In PyCharm: **Git > Commit** everything you want online, then **Git > Push**.
Check on github.com/lyanks/DigitalWardrobe that the newest commit is there.

### 2. Make the account

Sign up for a **Beginner (free)** account at <https://www.pythonanywhere.com>.
Your username becomes part of the address, so pick it with that in mind.

### 3. Download the code onto the server

Dashboard > **New console > Bash**, then:

```bash
git clone https://github.com/lyanks/DigitalWardrobe.git
cd DigitalWardrobe
python3.13 -m venv .venv          # use the newest python3.x the console has (try python3.14 first)
source .venv/bin/activate
pip install -r requirements.txt
```

This is the same as what you did on your computer: a private set of libraries
(`.venv`) just for this project.

### 4. Make the server's .env

Still in the console. First get a strong random secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Then create the file with `nano .env` and paste (your own values):

```
SECRET_KEY=the-long-random-string-from-above
BEHIND_PROXY=1
GOOGLE_CLIENT_ID=same-as-on-your-computer
GOOGLE_CLIENT_SECRET=same-as-on-your-computer
```

Save with Ctrl+O, Enter, then Ctrl+X.

- `SECRET_KEY` signs the login cookie. A new one here means nobody can forge
  a login, and it is different from your computer's, which is fine.
- `BEHIND_PROXY=1` is explained in `config.py`: it makes Flask build
  `https://` links, which Google insists on.

### 5. Create the database

```bash
flask db upgrade     # builds wardrobe.db from the migrations
python seed.py       # adds the clothing categories
```

(Want your existing clothes online instead of starting empty? See Part 3.)

### 6. Create the website

Open the **Web** tab > **Add a new web app** > Next > **Manual configuration**
(not "Flask"; manual lets us use our own `create_app()`) > pick the **same
Python version** you used in step 3.

Then, on the Web tab page that opens, fill in:

| Setting | Value |
| --- | --- |
| Source code | `/home/YOURNAME/DigitalWardrobe` |
| Working directory | `/home/YOURNAME/DigitalWardrobe` |
| Virtualenv | `/home/YOURNAME/DigitalWardrobe/.venv` |
| Static files: URL `/static/` | Directory `/home/YOURNAME/DigitalWardrobe/app/static` |
| Force HTTPS | Enabled |

The static files line lets PythonAnywhere send CSS, JS and fonts itself,
which is faster than going through Flask.

### 7. Point the WSGI file at the app

On the Web tab, click the link next to **WSGI configuration file**
(`/var/www/YOURNAME_pythonanywhere_com_wsgi.py`). Delete everything in it,
paste the contents of `deploy/pythonanywhere_wsgi.py` from this project, and
change `YOURNAME`. Save.

### 8. Start it

Press the green **Reload** button and open `https://YOURNAME.pythonanywhere.com`.
If you see an error page, the **Error log** link on the Web tab says why
(the last lines are the newest).

### 9. Tell Google about the new address

Google only sends people back to addresses you have approved.

1. <https://console.cloud.google.com> > **APIs & Services > Credentials** >
   click your OAuth client.
2. Under **Authorised redirect URIs** add
   `https://YOURNAME.pythonanywhere.com/login/google/callback`
3. Keep the `http://127.0.0.1:5000/...` ones too, so login still works on
   your computer. Save. It can take a few minutes to start working.
4. If the consent screen is still in **Testing**, only the Google accounts
   listed under **Test users** can log in. That is fine for just you.

### 10. Put it on your phone

Open the address in your phone's browser, log in, then
**Share > Add to Home Screen** (iPhone) or **menu > Add to Home screen** (Android).
It now opens like an app.

---

## Part 2. Every time you change something

1. Change and test in PyCharm as usual (`python -m pytest`).
2. Commit and push.
3. On PythonAnywhere open a Bash console (the **Consoles** tab keeps old ones) and run:

```bash
bash ~/DigitalWardrobe/deploy/update.sh
```

That script pulls the new code, installs new libraries, runs new migrations,
and reloads the site. Open `deploy/update.sh` to see each step explained.

Never edit code directly on the server: the next `git pull` would clash with
it. Change it in PyCharm and push.

---

## Part 3 (optional). Move your existing clothes and photos

Only do this right after setup, before you add things on the phone,
because it replaces the server's database.

1. On your computer, put `wardrobe.db` and the `uploads` folder into one zip
   (`wardrobe_backup.zip`).
2. PythonAnywhere **Files** tab > open `DigitalWardrobe/` > **Upload a file**.
3. In a Bash console:

```bash
cd ~/DigitalWardrobe
unzip -o wardrobe_backup.zip      # overwrites the empty wardrobe.db and uploads/
source .venv/bin/activate && flask db upgrade
rm wardrobe_backup.zip
```

4. Reload on the Web tab.

Your passwords keep working (only their hashes are in the database), but you
will be logged out, because the `SECRET_KEY` is different.

## Backups

The server's `wardrobe.db` and `uploads/` exist only there. Every so often,
Files tab > download `wardrobe.db`, or zip both in a console
(`zip -r backup.zip wardrobe.db uploads`) and download the zip.
