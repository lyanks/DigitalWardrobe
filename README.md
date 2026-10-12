# DigitalWardrobe

A Flask app to catalog your clothes, build outfits and plan what to wear.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask db upgrade                     # creates wardrobe.db with all tables
python seed.py                       # adds the clothing categories (safe to re-run)
python run.py                        # http://127.0.0.1:5000
```

## Optional: Sign in with Google

Copy `.env.example` to `.env` and fill in `GOOGLE_CLIENT_ID` and
`GOOGLE_CLIENT_SECRET` from Google Cloud Console. Without them the app works
normally and simply hides the Google button.

## Test it

```bash
python -m pytest
```

## Progress

- [x] Phase 0: Flask skeleton
- [x] Phase 1: users, login, profile with avatar
- [x] Phase 2: wardrobe inventory (CRUD)
- [ ] Phase 3: outfits
- [ ] Phase 4: scheduling + JavaScript
- [ ] Phase 5: polish
