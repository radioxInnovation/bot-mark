import setuptools

PAI_VERSION = "0.4.8"

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
    # your existing features
    "remote-files": ["requests>=2.32.4"],
    "jinja2": ["Jinja2>=3.1.6"],
    "mako": ["Mako>=1.3.10"],
    "templates": ["Jinja2>=3.1.6", "Mako>=1.3.10"],
    "dotenv": ["python-dotenv>=1.1.1"],

    # full pydantic-ai (instead of slim)
    "pydantic_ai": [f"pydantic-ai[all]>={PAI_VERSION}"],
}

# forward all slim extras
for extra in pai_extras:
    extras[extra] = [f"pydantic-ai-slim[{extra}]>={PAI_VERSION}"]

# "all" combines everything
extras["all"] = [
    "Jinja2>=3.1.6",
    "Mako>=1.3.10",
    "python-dotenv>=1.1.1",
    "requests>=2.32.4",
] + [f"pydantic-ai-slim[{extra}]>={PAI_VERSION}" for extra in pai_extras]

setuptools.setup(
    name="botmark",
    version="1.1.0",
    author="Frank Rettig",
    author_email="118481987+frettig-radiox@users.noreply.github.com",
    description="BotMark – Define, run, and document LLM chatbots in plain Markdown. Framework for executable, portable, and LLM-agnostic chatbot workflows.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://www.radiox-innovation.de/",
    packages=setuptools.find_packages(),
    include_package_data=True,
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.11",
    install_requires=[
        "pydantic>=2.11.7",
        f"pydantic-ai-slim>={PAI_VERSION}",
    ],
    extras_require=extras,
)
