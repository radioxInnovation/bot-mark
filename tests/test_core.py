import pytest
import re
import os
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
            if hasattr(response, "new_messages"):
                message_history.extend(response.new_messages())

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

def test_agent_consistency_across_interfaces():
    print(f"[DEBUG] Starting consistency check in: {BOTMARK_DIR}")
    bot = BotManager(bot_dir=str(BOTMARK_DIR), allow_system_prompt_fallback = True)

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
            # --- Run agent_by_model ---
            start_run_model = time.time()
            output_by_model = agent_by_model.run_sync("test").output
            run_time_model = time.time() - start_run_model
            print(f"[DEBUG] Output from agent_by_model: {output_by_model}")
            print(f"[DEBUG] agent_by_model response time: {run_time_model:.3f} seconds")

            # --- Run agent_by_string ---
            start_run_string = time.time()
            output_by_string = agent_by_string.run_sync("test").output
            run_time_string = time.time() - start_run_string
            print(f"[DEBUG] Output from agent_by_string: {output_by_string}")
            print(f"[DEBUG] agent_by_string response time: {run_time_string:.3f} seconds")

        except Exception as e:
            pytest.fail(f"[{file_id}] Agent execution failed: {e}")

        assert output_by_model == output_by_string, (
            f"[{file_id}] Mismatch between model-based and string-based agent outputs: "
            f"{output_by_string} - {output_by_model}"
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
            try:
                start_respond = time.time()
                output_by_respond = bot.respond(payload)
                respond_time = time.time() - start_respond
                print(f"[DEBUG] bot.respond() time [Payload #{idx}]: {respond_time:.3f} seconds")
                print(f"[DEBUG] Output from bot.respond() [Payload #{idx}]: {output_by_respond}")
            except Exception as e:
                pytest.fail(f"[{file_id}] bot.respond() failed on payload #{idx}: {e}")

            assert output_by_respond == output_by_model, (
                f"[{file_id}] Mismatch in bot.respond() output [Payload #{idx}]:\n"
                f"Expected: {output_by_model}\nGot:      {output_by_respond}"
            )
