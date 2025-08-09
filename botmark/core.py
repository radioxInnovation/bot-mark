import json, os, unittest, re
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Optional, Union, TextIO, Dict

from pydantic_ai.models.test import TestModel
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    SystemPromptPart,
)

from .markdown_parser import parser
from .responder import engine
from .utils.helpers import parse_markdown_to_qa_pairs, interpret_bool_expression, find_active_topics, get_blocks, get_header, get_images, process_links, get_schema, get_model, get_llm_model, get_models, get_toolset, render_block, render_named_block, try_answer, make_answer
from . import __version__ as VERSION

script_dir = os.path.dirname(os.path.abspath(__file__))

load_dotenv(dotenv_path=os.path.join(script_dir, '.env'))

class BotMarkAgent(Agent[Any, Any]):

    def __init__(self, *args, botmark_json: dict, **kwargs):
        self.botmark_json = botmark_json
        super().__init__(*args, **kwargs)

    def __eq__(self, other):
        if isinstance(other, BotMarkAgent):
            return self.botmark_json == other.botmark_json
        return False

    def __hash__(self):
        return hash(frozenset(self.botmark_json.items()))
    
    def get_info( self ):
        return self.botmark_json.get("info", "<p>info not found</p>")

    def get_tests(self):
        test_cases = []
        ranking_function = lambda block: 1 if "unittest" in block.get("classes", []) else -1
        unittests = get_blocks(self.botmark_json["codeblocks"], ranking_function= ranking_function)

        for test_name, test_block in unittests.items():
            qa_list = parse_markdown_to_qa_pairs(test_block.get("content"))
            if not qa_list:
                continue
            test_cases.append((test_name, qa_list))

        return test_cases
    
    async def run(self, user_input, **kwargs) -> Any:
        try:
            tables = self.botmark_json["tables"]
            topics_table = tables.get("topic")

            # robust: str oder list behandeln
            if isinstance(user_input, str):
                user_text = user_input
                non_str_parts = []
            elif isinstance(user_input, list):
                user_text = "".join([s for s in user_input if isinstance(s, str)])
                non_str_parts = [x for x in user_input if not isinstance(x, str)]
            else:
                user_text = str(user_input)
                non_str_parts = []

            topics = {}
            if topics_table:
                topics = find_active_topics(topics_table, user_text)

            ranking_fn = lambda block: interpret_bool_expression(
                block.get("attributes", {}).get("match"), topics
            )

            active_blocks = get_blocks(self.botmark_json["codeblocks"], ranking_fn)
            active_schema = get_schema(active_blocks, topics )
            active_header = get_header(active_blocks, self.botmark_json["header"])

            model = get_llm_model(active_header.get("model"))
            VENV_BASE_DIR = active_header.get("VENV_BASE_DIR", os.getenv("VENV_BASE_DIR", "/data/venvs"))

            def filter_funktion(key, value):
                return "agent" in value.get("classes", [])

            INFO = self.get_info()

            active_agents = {k: v for k, v in active_blocks.items() if filter_funktion(k, v)}
            active_prompt = active_blocks.get("prompt")
            final_query = render_block(active_prompt, {"QUERY": user_text}) if active_prompt else user_text

            query_objects = parser.parse_to_json(final_query) if active_header.get("inspect_user_prompt", False) is True else {}
            query_images = get_images(query_objects.get("images", []), lambda x: True)
            query_links, _ = process_links(query_objects.get("links", []), lambda x: True)
            active_system = render_named_block(
                "system", active_blocks, active_header, VERSION, INFO, final_query, topics, VENV_BASE_DIR, {}
            )

            answer = try_answer(active_blocks, active_system, active_header, VERSION, INFO, final_query, VENV_BASE_DIR, topics)

            if answer is None:
                active_toolset = get_toolset(active_blocks)
                predicate = lambda block: interpret_bool_expression(block.get("match"), topics) >= 0

                active_images = get_images(self.botmark_json.get("images", []), predicate)
                active_links, mcp_servers = process_links(self.botmark_json.get("links", []), predicate)

                system_parts = [SystemPromptPart(content=active_system)]
                history = kwargs.get("message_history", [])
                if not history:
                    kwargs["message_history"] = [ModelRequest(parts=system_parts)]
                else:
                    head = history[0]
                    head.parts = system_parts + head.parts
                    kwargs["message_history"] = history

                # finaler Input: Query + evtl. nicht-String-Teile + aktive/query-Assets
                composed_input = [final_query] + non_str_parts + active_images + active_links + query_images + query_links

                # 1) echter Lauf
                result = await super().run(
                    composed_input,
                    model=model,
                    toolsets=active_toolset,
                    output_type=active_schema,
                    **kwargs
                )
                llm_response = result.output.model_dump_json() if active_schema else str(result.output)

                # 2) deterministische Ausgabe rendern
                answer = make_answer(
                    active_blocks, active_system, active_header, VERSION, INFO, final_query, llm_response, VENV_BASE_DIR, topics
                )

                result = await super().run(
                    composed_input,
                    model=TestModel(custom_output_text=answer),
                    **kwargs
                )
                return result

            # Direkte Antwort via TestModel
            result = await super().run(
                user_input,
                model=TestModel(custom_output_text=answer),
                **kwargs
            )
            return result

        except Exception as e:
            return await super().run(
                user_input,
                model=TestModel(custom_output_text=f'ERROR: {str(e)}'),
                **kwargs
            )



    def run_sync(self, *args, **kwargs) -> Any:

        try:
            return asyncio.run(self.run(*args, **kwargs))
        except RuntimeError as e:
            if "running event loop" in str(e):
                # Notebook/FastAPI: versuche, die existierende Loop zu verwenden
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    try:
                        # optionaler Komfort: nest_asyncio, falls vorhanden
                        import nest_asyncio  # type: ignore
                        nest_asyncio.apply()
                        return loop.run_until_complete(self.run(*args, **kwargs))
                    except Exception as inner:
                        raise RuntimeError(
                            "run_sync wurde innerhalb einer laufenden Event Loop aufgerufen. "
                            "Bitte stattdessen 'await run(...)' verwenden."
                        ) from inner
                else:
                    return loop.run_until_complete(self.run(*args, **kwargs))
            # anderer RuntimeError → weiterwerfen
            raise

class BotManager:

    def __init__(self, default_model: Optional[Union[str, dict, TextIO]] = None, bot_dir: str = ".",  adapt_payload = lambda x: x, response_parser = lambda x: x.output, allow_system_prompt_fallback: bool = False ):
        if not os.path.isdir(bot_dir):
            raise FileNotFoundError(f"Bot directory '{bot_dir}' does not exist.")

        self.bot_dir = bot_dir
        self.adapt_payload = adapt_payload
        self.response_parser = response_parser
        self.allow_system_prompt_fallback = allow_system_prompt_fallback
        self.agent = None
        if hasattr(default_model, 'read'):
            self.agent = self.get_agent( default_model.read() )

        elif isinstance(default_model, str):
            self.agent = self.get_agent_from_model_name( default_model )

        elif isinstance(default_model, dict):
            self.agent = self.get_agent( default_model )

    def get_info( self, model_name: Optional[str] = None):
        model_data = get_model( model_name, self.bot_dir)
        if model_data:
            return self.get_agent( model_data ).get_info()
        return self.agent.get_info() if self.agent else f"<p>info not found</p>"

    def get_agent( self, bot_definition: Union[str, dict] ):

        bot_json = bot_definition if isinstance(bot_definition, dict) else parser.parse_to_json(bot_definition )

        try:
            bot_json = json.loads( os.getenv("AGENT_DEFAULT_CONFIG", {} ))  | bot_json
        except:
            pass

        agent_kwargs = {
            "botmark_json": bot_json,
            "model": TestModel()
        }

        agent = BotMarkAgent(**agent_kwargs)
        return agent

    def get_agent_from_model_name( self, model_name ):
        model_data = get_model( model_name, self.bot_dir)
        return  self.get_agent( model_data ) if model_data else None

    def get_tests(self):
        tests = [{ "model": "", "tests": self.agent.get_tests()}]  if self.agent else []
        for model_info in self.get_models().get("data", []):
            model_id = model_info["id"]
            agent = self.get_agent( get_model( model_id, self.bot_dir) )
            tests += [{"model": model_id, "tests": agent.get_tests()}]
        return tests

    def get_models( self ) -> dict:
        return get_models( self.bot_dir )
    
    def model_exists(self, model_list: dict, model_id: str) -> bool:
        for model in model_list.get("data", []):
            if model.get("id") == model_id:
                return True
        return False
       
    def respond(self, json_payload: dict) -> str:
        json_payload = self.adapt_payload(json_payload)
        model_name = json_payload.get( "model", None )
        models = self.get_models()

        if self.model_exists(models, model_name):
            model_data = get_model( model_name, self.bot_dir)
            response = engine.respond( self.get_agent( model_data ), json_payload ) 
        else:
            if self.agent:
                response = engine.respond( self.agent, json_payload )
            elif self.allow_system_prompt_fallback:
                system_prompt = ""
                for message in json_payload.get("messages", []):
                    if message.get("role") == "system":
                        system_prompt += message.get("content", "")
                response = engine.respond( self.get_agent( system_prompt ), json_payload )
            else:
                raise ValueError( f"Model '{model_name}' not found, no fallback agent available, and system prompt fallback is disabled." )

        return self.response_parser( response )
    

    async def respond_async(self, json_payload: Dict) -> str:
        """
        Async counterpart to respond_sync: prepares payload, selects the agent,
        calls the engine asynchronously, and returns the parsed string response.
        """
        json_payload = self.adapt_payload(json_payload)
        model_name = json_payload.get("model", None)
        models = self.get_models()

        async def _call_engine_async(agent, payload):
            # Prefer a native async engine method; otherwise run sync in a thread.
            if hasattr(engine, "respond_async"):
                return await engine.respond_async(agent, payload)
            return await asyncio.to_thread(engine.respond, agent, payload)

        if self.model_exists(models, model_name):
            model_data = get_model(model_name, self.bot_dir)
            response = await _call_engine_async(self.get_agent(model_data), json_payload)
        else:
            if self.agent:
                response = await _call_engine_async(self.agent, json_payload)
            elif self.allow_system_prompt_fallback:
                system_prompt = "".join(
                    m.get("content", "")
                    for m in json_payload.get("messages", [])
                    if m.get("role") == "system"
                )
                response = await _call_engine_async(self.get_agent(system_prompt), json_payload)
            else:
                raise ValueError(
                    f"Model '{model_name}' not found, no fallback agent available, "
                    f"and system prompt fallback is disabled."
                )

        return self.response_parser(response)

