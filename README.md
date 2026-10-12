# DigitalWardrobe

A Flask app to catalog your clothes, build outfits and plan what to wear.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask db upgrade                     # creates wardrobe.db with all tables
python run.py                        # http://127.0.0.1:5000
```

## Test it

```bash
python -m pytest
```

## Progress

- [x] Phase 0: Flask skeleton
- [x] Phase 1: users, login, profile with avatar
- [ ] Phase 2: wardrobe inventory (CRUD)
- [ ] Phase 3: outfits
- [ ] Phase 4: scheduling + JavaScript
- [ ] Phase 5: polish
