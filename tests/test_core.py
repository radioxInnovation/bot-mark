import re
import asyncio
import time
from pathlib import Path
import pytest
import botmark

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────

# Optional path override via environment variable
BOTMARK_DIR = Path(Path(__file__).parent / "unittests").resolve()

# Gather all .md models once for reuse (ids -> markdown text)
_MD_MAP = {}
if BOTMARK_DIR.exists() and BOTMARK_DIR.is_dir():
    for f in BOTMARK_DIR.rglob("*.md"):
        if f.is_file():
            model_id = f.relative_to(BOTMARK_DIR).with_suffix("").as_posix()
            _MD_MAP[model_id] = f.read_text(encoding="utf-8")
else:
    pytest.skip(f"Botmark test dir not found: {BOTMARK_DIR}", allow_module_level=True)

# Convenience
_MODEL_IDS = list(_MD_MAP.keys())

# Default source (filesystem), kept for backward compatibility
botmark_source = botmark.FileSystemSource(BOTMARK_DIR)


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _collect_all_tests_from_source(source) -> list[tuple[str, str, str, list[dict]]]:
    """
    Collect (label, model_id, test_name, qa_list) tuples using a specific source.
    """
    tests = []
    bot = botmark.BotManager(allow_code_execution=True, botmark_source=source)
    for entry in bot.get_tests():
        model_id = entry.get("model", "(unnamed)")
        for test_name, qa_list in entry.get("tests", []):
            label = f"{model_id}::{test_name}"
            tests.append((label, model_id, test_name, qa_list))
    return tests


def _out(x):
    return getattr(x, "output", x)


def _make_source(kind: str, model_id: str | None = None):
    """
    Create the requested source:
      - 'fs'                → FileSystemSource(BOTMARK_DIR)
      - 'string-single'     → StringSource(model_id, text)
      - 'string-multi'      → StringSource(models=dict)
    """
    if kind == "fs":
        return botmark.FileSystemSource(BOTMARK_DIR)
    elif kind == "string-single":
        if not model_id:
            raise ValueError("model_id required for string-single")
        return botmark.StringSource(model_id=model_id, text=_MD_MAP[model_id])
    elif kind == "string-multi":
        return botmark.StringSource(models=_MD_MAP)
    else:
        raise ValueError(f"Unknown source kind: {kind}")


# ──────────────────────────────────────────────────────────────────────────────
# BASIC SANITY: ensure local import (as you had)
# ──────────────────────────────────────────────────────────────────────────────

def test_imports_local_botmark():
    """
    Ensure that 'import botmark' resolves to the local project folder,
    not to a globally installed site-packages version.
    """
    mod_path = Path(botmark.__file__).resolve()
    repo_root = Path(__file__).resolve().parents[1]
    expected_dir = repo_root / "botmark"

    print(f"[DEBUG] botmark imported from: {mod_path}")

    # must be inside ./botmark (flat layout)
    assert str(mod_path).startswith(str(expected_dir)), (
        f"'botmark' was not imported from the repo.\n"
        f"Found:   {mod_path}\n"
        f"Expected under: {expected_dir}\n"
    )


# ──────────────────────────────────────────────────────────────────────────────
# PARAM DATA: build the full matrix of tests across three source kinds
# ──────────────────────────────────────────────────────────────────────────────

def _param_data_for_all_sources():
    """
    Yields tuples:
      (source_kind, label, model_id, test_name, qa_list)
    covering:
      - fs:              all tests from the filesystem
      - string-single:   all tests, but *per model* using a single-model StringSource
      - string-multi:    all tests using a multi-model StringSource
    """
    # 1) FileSystemSource → collect once
    for t in _collect_all_tests_from_source(_make_source("fs")):
        yield ("fs",) + t

    # 2) StringSource (single) → per model collect
    for mid in _MODEL_IDS:
        src_single = _make_source("string-single", model_id=mid)
        for t in _collect_all_tests_from_source(src_single):
            yield ("string-single",) + t

    # 3) StringSource (multi) → collect once
    for t in _collect_all_tests_from_source(_make_source("string-multi")):
        yield ("string-multi",) + t


# ──────────────────────────────────────────────────────────────────────────────
# QA TESTS (now run for all 3 source kinds)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "source_kind,label,model_id,test_name,qa_list",
    list(_param_data_for_all_sources()),
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_qa_block_all_sources(source_kind, label, model_id, test_name, qa_list):
    source = _make_source(source_kind, model_id=model_id if source_kind == "string-single" else None)
    bot = botmark.BotManager(allow_code_execution=True, botmark_source=source)
    agent = bot._get_agent_from_model_name(model_id)

    message_history = []
    for i, qa in enumerate(qa_list):
        q = qa.get("question", "").strip()
        expected = qa.get("answer", "").strip()

        if not q or not expected:
            print(f"[DEBUG] [{label}][#{i}] Skipping empty Q/A pair.")
            continue

        try:
            response = agent.run_sync(q, message_history=message_history or None)
            actual = getattr(response, "output", str(response)).strip()

            print("ausgebe:" + str(response))
            print(f"[DEBUG] [{label}][#{i}] [{source_kind}] Question: {q}")
            print(f"[DEBUG] Expected: {expected}")
            print(f"[DEBUG] Actual:   {actual}")

            # regex marker
            MARK = "*"
            if (
                actual == expected
                or (
                    expected.startswith(MARK)
                    and expected.endswith(MARK)
                    and re.match(expected[len(MARK):-len(MARK)], actual)
                )
            ):
                print(f"[DEBUG] ✅ Test passed.")
                continue
            else:
                pytest.fail(
                    f"[{label}][#{i}] [{source_kind}] Mismatch in answer:\n"
                    f"Q: {q}\nExpected (regex/str): {expected}\nGot: {actual}"
                )
        except Exception as e:
            pytest.fail(f"[{label}][#{i}] [{source_kind}] Exception:\nQ: {q}\n{e}")


# ──────────────────────────────────────────────────────────────────────────────
# CONSISTENCY TESTS (run per source kind)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("source_kind", ["fs", "string-single", "string-multi"])
def test_agent_consistency_across_interfaces_all_sources(source_kind):
    print(f"[DEBUG] Starting consistency check in: {BOTMARK_DIR} ({source_kind})")

    # For string-single we iterate each model separately; for others one bot is fine
    model_ids = _MODEL_IDS if source_kind != "string-single" else _MODEL_IDS

    for rel_id in model_ids:
        # Build source instance
        src = (
            _make_source("fs")
            if source_kind == "fs"
            else _make_source(source_kind, model_id=rel_id if source_kind == "string-single" else None)
        )
        bot = botmark.BotManager(
            allow_system_prompt_fallback=True,
            allow_code_execution=True,
            botmark_source=src,
        )

        file_id = rel_id  # already relative id with '/'
        full_path = (BOTMARK_DIR / (file_id + ".md")).resolve()
        print(f"\n[DEBUG] ({source_kind}) Testing file: {file_id} @ {full_path}")

        content = _MD_MAP[file_id]

        # --- Setup and Time: agent_by_model ---
        start_setup_model = time.time()
        agent_by_model = bot._get_agent_from_model_name(file_id)
        setup_time_model = time.time() - start_setup_model
        print(f"[DEBUG] agent_by_model setup time: {setup_time_model:.6f} seconds")

        # --- Setup and Time: agent_by_string ---
        start_setup_string = time.time()
        agent_by_string = bot.get_agent(content)
        setup_time_string = time.time() - start_setup_string
        print(f"[DEBUG] agent_by_string setup time: {setup_time_string:.6f} seconds")

        try:
            # --- Run agent_by_model (sync) ---
            start_run_model = time.time()
            output_by_model_sync = _out(agent_by_model.run_sync("test"))
            run_time_model = time.time() - start_run_model
            print(f"[DEBUG] Output from agent_by_model (sync): {output_by_model_sync}")
            print(f"[DEBUG] agent_by_model (sync) response time: {run_time_model:.3f} seconds")

            # --- Run agent_by_string (sync) ---
            start_run_string = time.time()
            output_by_string_sync = _out(agent_by_string.run_sync("test"))
            run_time_string = time.time() - start_run_string
            print(f"[DEBUG] Output from agent_by_string (sync): {output_by_string_sync}")
            print(f"[DEBUG] agent_by_string (sync) response time: {run_time_string:.3f} seconds")

            # --- Run agent_by_model (async) ---
            start_run_model_async = time.time()
            output_by_model_async = _out(asyncio.run(agent_by_model.run("test")))
            run_time_model_async = time.time() - start_run_model_async
            print(f"[DEBUG] Output from agent_by_model (async): {output_by_model_async}")
            print(f"[DEBUG] agent_by_model (async) response time: {run_time_model_async:.3f} seconds")

            # --- Run agent_by_string (async) ---
            start_run_string_async = time.time()
            output_by_string_async = _out(asyncio.run(agent_by_string.run("test")))
            run_time_string_async = time.time() - start_run_string_async
            print(f"[DEBUG] Output from agent_by_string (async): {output_by_string_async}")
            print(f"[DEBUG] agent_by_string (async) response time: {run_time_string_async:.3f} seconds")

        except Exception as e:
            pytest.fail(f"[{file_id}] ({source_kind}) Agent execution failed: {e}")

        # Baseline consistency: model vs string (sync)
        assert output_by_model_sync == output_by_string_sync, (
            f"[{file_id}] ({source_kind}) Mismatch between model-based and string-based outputs (sync): "
            f"{output_by_string_sync} - {output_by_model_sync}"
        )
        # Async should match sync
        assert output_by_model_async == output_by_model_sync, (
            f"[{file_id}] ({source_kind}) Mismatch model async vs sync: "
            f"{output_by_model_async} - {output_by_model_sync}"
        )
        assert output_by_string_async == output_by_string_sync, (
            f"[{file_id}] ({source_kind}) Mismatch string async vs sync: "
            f"{output_by_string_async} - {output_by_string_sync}"
        )
        # Cross-consistency: async model vs async string
        assert output_by_model_async == output_by_string_async, (
            f"[{file_id}] ({source_kind}) Mismatch async model vs async string: "
            f"{output_by_string_async} - {output_by_model_async}"
        )

        # Finally test the payload-based interface parity
        payloads = [
            {"model": file_id, "messages": [{"role": "user", "content": "test"}]},
            {"messages": [
                {"role": "system", "content": content},
                {"role": "user", "content": "test"}
            ]},
            {"model": "unknown", "messages": [
                {"role": "system", "content": content},
                {"role": "user", "content": "test"}
            ]},
        ]

        for idx, payload in enumerate(payloads):
            # --- Sync respond ---
            try:
                start_respond = time.time()
                output_by_respond_sync = _out(bot.respond_sync(payload))
                respond_time = time.time() - start_respond
                print(f"[DEBUG] bot.respond_sync() time [Payload #{idx}]: {respond_time:.3f} seconds")
                print(f"[DEBUG] Output from bot.respond_sync() [Payload #{idx}]: {output_by_respond_sync}")
            except Exception as e:
                pytest.fail(f"[{file_id}] ({source_kind}) bot.respond_sync() failed on payload #{idx}: {e}")

            assert output_by_respond_sync == output_by_model_sync, (
                f"[{file_id}] ({source_kind}) Mismatch in bot.respond_sync() output [Payload #{idx}]:\n"
                f"Expected: {output_by_model_sync}\nGot:      {output_by_respond_sync}"
            )

            # --- Async respond ---
            try:
                start_respond_async = time.time()
                output_by_respond_async = _out(asyncio.run(bot.respond(payload)))
                respond_time_async = time.time() - start_respond_async
                print(f"[DEBUG] bot.respond() time [Payload #{idx}]: {respond_time_async:.3f} seconds")
                print(f"[DEBUG] Output from bot.respond() [Payload #{idx}]: {output_by_respond_async}")
            except Exception as e:
                pytest.fail(f"[{file_id}] ({source_kind}) bot.respond() failed on payload #{idx}: {e}")

            assert output_by_respond_async == output_by_respond_sync == output_by_model_sync, (
                f"[{file_id}] ({source_kind}) Mismatch in async respond output [Payload #{idx}]:\n"
                f"Expected: {output_by_model_sync}\n"
                f"bot.respond_sync(): {output_by_respond_sync}\n"
                f"bot.respond():      {output_by_respond_async}"
            )
