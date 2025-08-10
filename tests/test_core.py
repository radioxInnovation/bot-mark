import pytest
import re
import asyncio
import time
import pytest
import time
from pathlib import Path
from botmark import BotManager

# Optional path override via environment variable
BOTMARK_DIR = Path(Path(__file__).parent / "bots").resolve()

def collect_all_tests():
    print(f"[DEBUG] Using test directory: {BOTMARK_DIR}")
    tests = []
    bot = BotManager(bot_dir=str(BOTMARK_DIR))

    for entry in bot.get_tests():
        model_id = entry.get("model", "(unnamed)")
        for test_name, qa_list in entry.get("tests", []):
            label = f"{model_id}::{test_name}"
            tests.append((label, model_id, test_name, qa_list))

    print(f"[DEBUG] Collected test cases: {len(tests)}")
    return tests

@pytest.mark.parametrize("label,model_id,test_name,qa_list", collect_all_tests())
def test_qa_block(label, model_id, test_name, qa_list):

    bot = BotManager(bot_dir=str(BOTMARK_DIR))
    agent = bot.get_agent_from_model_name(model_id)

    message_history = []

    for i, qa in enumerate(qa_list):

        q = qa.get("question", "").strip()
        expected = qa.get("answer", "").strip()

        if not q or not expected:
            print(f"[DEBUG] [{label}][#{i}] Skipping empty Q/A pair.")
            continue

        try:
            response = agent.run_sync(q, message_history=message_history or None)
            #if hasattr(response, "all_messages"):
            #    print ( message_history )
            #    message_history = response.new_messages()

            actual = getattr(response, "output", str(response)).strip()
            print(f"[DEBUG] [{label}][#{i}] Question: {q}")
            print(f"[DEBUG] Expected: {expected}")
            print(f"[DEBUG] Actual:   {actual}")

            if actual == expected or re.match(expected, actual):
                print(f"[DEBUG] ✅ Test passed.")
                continue
            else:
                pytest.fail(
                    f"[{label}][#{i}] Mismatch in answer:\n"
                    f"Q: {q}\nExpected (regex/str): {expected}\nGot: {actual}"
                )
        except Exception as e:
            pytest.fail(f"[{label}][#{i}] Exception:\nQ: {q}\n{e}")

def _out(x):
    return getattr(x, "output", x)

def test_agent_consistency_across_interfaces():
    print(f"[DEBUG] Starting consistency check in: {BOTMARK_DIR}")
    bot = BotManager(bot_dir=str(BOTMARK_DIR), allow_system_prompt_fallback=True)

    md_files = [f for f in BOTMARK_DIR.rglob("*.md") if f.is_file()]
    relative_md_files = [f.relative_to(BOTMARK_DIR) for f in md_files]

    for rel_path in relative_md_files:
        file_id = rel_path.with_suffix('').as_posix()
        full_path = BOTMARK_DIR / rel_path
        print(f"\n[DEBUG] Testing file: {rel_path} (ID: {file_id})")

        with open(full_path, "r", encoding="utf-8") as file:
            content = file.read()

        # --- Setup and Time: agent_by_model ---
        start_setup_model = time.time()
        agent_by_model = bot.get_agent_from_model_name(file_id)
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
            pytest.fail(f"[{file_id}] Agent execution failed: {e}")

        # Baseline consistency: model vs string (sync)
        assert output_by_model_sync == output_by_string_sync, (
            f"[{file_id}] Mismatch between model-based and string-based agent outputs (sync): "
            f"{output_by_string_sync} - {output_by_model_sync}"
        )
        # Async should match sync
        assert output_by_model_async == output_by_model_sync, (
            f"[{file_id}] Mismatch between model-based async and sync outputs: "
            f"{output_by_model_async} - {output_by_model_sync}"
        )
        assert output_by_string_async == output_by_string_sync, (
            f"[{file_id}] Mismatch between string-based async and sync outputs: "
            f"{output_by_string_async} - {output_by_string_sync}"
        )
        # Cross-consistency: async model vs async string
        assert output_by_model_async == output_by_string_async, (
            f"[{file_id}] Mismatch between model-based and string-based agent outputs (async): "
            f"{output_by_string_async} - {output_by_model_async}"
        )

        payloads = [
            {"model": file_id, "messages": [{"role": "user", "content": "test"}]},
            {"messages": [
                {"role": "system", "content": content},
                {"role": "user", "content": "test"}
            ]},
            {"model": "unknown", "messages": [
                {"role": "system", "content": content },
                {"role": "user", "content": "test"}
            ]}
        ]

        for idx, payload in enumerate(payloads):
            # --- Sync respond ---
            try:
                start_respond = time.time()
                output_by_respond_sync = _out(bot.respond(payload))
                respond_time = time.time() - start_respond
                print(f"[DEBUG] bot.respond() time [Payload #{idx}]: {respond_time:.3f} seconds")
                print(f"[DEBUG] Output from bot.respond() [Payload #{idx}]: {output_by_respond_sync}")
            except Exception as e:
                pytest.fail(f"[{file_id}] bot.respond() failed on payload #{idx}: {e}")

            assert output_by_respond_sync == output_by_model_sync, (
                f"[{file_id}] Mismatch in bot.respond() output [Payload #{idx}]:\n"
                f"Expected: {output_by_model_sync}\nGot:      {output_by_respond_sync}"
            )

            # --- Async respond ---
            try:
                start_respond_async = time.time()
                output_by_respond_async = _out(asyncio.run(bot.respond_async(payload)))
                respond_time_async = time.time() - start_respond_async
                print(f"[DEBUG] bot.respond_async() time [Payload #{idx}]: {respond_time_async:.3f} seconds")
                print(f"[DEBUG] Output from bot.respond_async() [Payload #{idx}]: {output_by_respond_async}")
            except Exception as e:
                pytest.fail(f"[{file_id}] bot.respond_async() failed on payload #{idx}: {e}")

            # Async respond must match both sync respond and baseline
            assert output_by_respond_async == output_by_respond_sync == output_by_model_sync, (
                f"[{file_id}] Mismatch in async respond output [Payload #{idx}]:\n"
                f"Expected: {output_by_model_sync}\n"
                f"bot.respond():      {output_by_respond_sync}\n"
                f"bot.respond_async(): {output_by_respond_async}"
            )
