import setuptools
import os
import re

def find_version():
    with open(os.path.join("botmark", "__init__.py"), encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", content, re.M)
    if match:
        return match.group(1)
    raise RuntimeError("Version not found in __init__.py")

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="botmark",
    version=find_version(),
    author="Frank Rettig",
    author_email="118481987+frettig-radiox@users.noreply.github.com",
    description="BotMark – Define, run, and document LLM chatbots in plain Markdown. Framework for executable, portable, and LLM-agnostic chatbot workflows.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://www.radiox-innovation.de/",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
    install_requires=[
        "httpx==0.28.1",
        "Jinja2==3.1.6",
        "Mako==1.3.10",
        "markdown-it-py==3.0.0",
        "mdit_py_plugins==0.4.2",
        "Pillow==11.3.0",
        "pydantic==2.11.7",
        "pydantic_ai==0.6.2",
        "python-dotenv==1.1.1",
        "python_frontmatter==1.1.0",
        "PyYAML==6.0.2",
        "requests==2.32.4",
    ],
)
