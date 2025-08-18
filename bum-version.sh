#! /bin/bash
# read version number from command line argument
if [ -z "$1" ]; then
  echo "Error: Version number argument is required."
  exit 1
fi
VERSION=$1
python - <<'PY'
import re, pathlib, sys
p=pathlib.Path("setup.py")
s=p.read_text(encoding="utf-8")
s=re.sub(r'version\s*=\s*([\'"])[0-9][^\'"]*\1', f'version=\"{sys.argv[1]}\"', s, count=1)
p.write_text(s, encoding="utf-8")
PY
git add setup.py &&
git commit -m "Bump version to $VERSION" &&
git tag "$VERSION" &&
git push origin HEAD &&
git push origin "$VERSION"
