import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="botmark",
    version="1.0.9",
    author="Frank Rettig",
    author_email="118481987+frettig-radiox@users.noreply.github.com",
    description="BotMark – Define, run, and document LLM chatbots in plain Markdown. Framework for executable, portable, and LLM-agnostic chatbot workflows.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://www.radiox-innovation.de/",
    packages=setuptools.find_packages(),
    include_package_data=True,
    license="License :: OSI Approved :: MIT License",
    classifiers=[
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
    ],
    python_requires=">=3.11",
    install_requires=[
        "pydantic>=2.11.7",
        "pydantic_ai>=0.4.8",
    ],

    # Optional dependencies, grouped by feature
    extras_require={
        "remote-files": ["requests>=2.32.4"],

        # Template engines
        "jinja2": ["Jinja2>=3.1.6"],
        "mako": ["Mako>=1.3.10"],
        "templates": ["Jinja2>=3.1.6", "Mako>=1.3.10"],

        # Logging support
        "logfire": ["logfire"],

        # .env file support
        "dotenv": ["python-dotenv>=1.1.1"],

        # "all" installs every optional extra
        "all": [
            "Jinja2>=3.1.6",
            "Mako>=1.3.10",
            "logfire",
            "python-dotenv>=1.1.1",
            "requests>=2.32.4",
        ],
    }
)
