#!/bin/bash
# Put your newest code live. Run it on PythonAnywhere, in a Bash console:
#     bash ~/DigitalWardrobe/deploy/update.sh
# (First push your commits to GitHub from PyCharm.)

set -e  # stop at the first command that fails

cd ~/DigitalWardrobe
source .venv/bin/activate

git pull                          # 1. download the commits you pushed
pip install -q -r requirements.txt  # 2. install any new libraries
flask db upgrade                  # 3. apply new migrations (keeps your data)
python seed.py                    # 4. add any new categories (safe to re-run)

# 5. Restart the website. PythonAnywhere reloads the app whenever its
#    WSGI file changes, and `touch` "changes" it without editing anything.
touch /var/www/"$(whoami)"_pythonanywhere_com_wsgi.py

echo "Done: the site is running the new code."
