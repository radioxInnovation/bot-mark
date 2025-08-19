import setuptools

# Minimum required version of pydantic-ai-slim
PAI_MIN_V = "0.4.8"

# All extras supported by pydantic-ai-slim
pai_extras = [
    "logfire",
    "evals",
    "openai",
    "vertexai",
    "google",
    "anthropic",
    "groq",
    "mistral",
    "cohere",
    "bedrock",
    "huggingface",
    "duckduckgo",
    "tavily",
    "cli",
    "mcp",
    "a2a",
    "ag-ui",
]

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Optional dependencies
extras = {
    "remote-files": ["requests>=2.32.4"],
    "jinja2": ["Jinja2>=3.1.6"],
    "mako": ["Mako>=1.3.10"],
    "templates": ["Jinja2>=3.1.6", "Mako>=1.3.10"],
    "dotenv": ["python-dotenv>=1.1.1"],
    "pydantic_ai": [f"pydantic-ai[all]>={PAI_MIN_V}"],
    "pydantic": ["pydantic"],
}

# forward all slim extras
for extra in pai_extras:
    extras[extra] = [f"pydantic-ai-slim[{extra}]>={PAI_MIN_V}"]

# "all" combines everything
extras["all"] = [
    "Jinja2>=3.1.6",
    "Mako>=1.3.10",
    "python-dotenv>=1.1.1",
    "requests>=2.32.4",
    "pydantic",
] + [f"pydantic-ai-slim[{extra}]>={PAI_MIN_V}" for extra in pai_extras]

setuptools.setup(
    name="botmark",
    version="1.1.9",
    author="Frank Rettig",
    author_email="118481987+frettig-radiox@users.noreply.github.com",
    description="BotMark – Define, run, and document LLM chatbots in plain Markdown. Framework for executable, portable, and LLM-agnostic chatbot workflows.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://www.radiox-innovation.de/",
    packages=setuptools.find_packages(),
    include_package_data=True,
    license="MIT",  # SPDX expression
    license_files=["LICENSE"],  # ensure LICENSE file is included
    classifiers=[
        # Removed deprecated license classifier
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.11",
    install_requires=[
        f"pydantic-ai-slim>={PAI_MIN_V}",
    ],
    extras_require=extras,
)
