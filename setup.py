import setuptools
import os
import re

# Version aus __init__.py lesen
def find_version():
    with open(os.path.join("chatmark", "__init__.py"), encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", content, re.M)
    if match:
        return match.group(1)
    raise RuntimeError("Version not found in __init__.py")

setuptools.setup(
    version=find_version()
)
