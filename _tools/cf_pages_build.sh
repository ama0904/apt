#!/bin/sh
# Cloudflare Pages build: the same steps as .github/workflows/deploy.yml.
# Pages settings: build command "sh _tools/cf_pages_build.sh", output directory "www.apetto.com.tw",
# environment variable PYTHON_VERSION=3.12 (and FITSTUDIO_API_KEY if the fitting room needs one).
set -e
pip install beautifulsoup4 lxml pillow numpy
python _tools/optimize_images.py
python _tools/crop_images.py
python _tools/site_builder.py build
cp _tools/admin.html www.apetto.com.tw/admin.html
rm -rf www.apetto.com.tw/_raw_html
# not for the public: the source data (pages are built from it; admin reads it through GitHub), page templates, mirror logs.
# _data/uploads stays: product photos added in admin are served from there.
rm -rf www.apetto.com.tw/_templates www.apetto.com.tw/_mirror_log.txt www.apetto.com.tw/_mirror_manifest.json
rm -f www.apetto.com.tw/_data/*.json
