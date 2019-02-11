#! /usr/local/bin/fish

git pull
./make_website.py
python -m http.server &
open -a Safari http://0.0.0.0:8000/docs/
