import json, os, unittest, re, time
import asyncio
from pathlib import Path
from typing import Any, Optional, Union, TextIO, Dict, Mapping
from pydantic import BaseModel

from pydantic_ai.models.test import TestModel
import copy
from pydantic_ai import Agent, StructuredDict
from pydantic_ai.messages import (
    ModelRequest,
    SystemPromptPart,
)

from .markdown_parser import parser
from .responder import engine

from .utils.helpers import traverse_graph, parse_markdown_to_qa_pairs, get_graph, interpret_bool_expression, find_active_topics, get_blocks, get_header, get_images, process_links, get_schema, get_llm_model, get_toolset, render_block, render_named_block, try_answer, make_answer
from . import __version__ as VERSION

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        print("⚠️  python-dotenv is not installed; environment files (.env) will be ignored.")
        return None

script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(script_dir, '.env'))

class BotMarkAgent(Agent[Any, Any]):

    def __init__(self, *args, botmark_json: dict, **kwargs):

        self.botmark_json = botmark_json
        self._init_args = args
        self._init_kwargs = kwargs
        self.lf = self._init_logfire_instance()
        super().__init__(*args, **kwargs)

    def __eq__(self, other):
        if isinstance(other, BotMarkAgent):
            return self.botmark_json == other.botmark_json
        return False

    def __hash__(self):
        return hash(frozenset(self.botmark_json.items()))
    
    def clone(self, include_graphs = True):
        botmark_json=copy.deepcopy(self.botmark_json)
        if not include_graphs:
            botmark_json["graphs"] = []

        return BotMarkAgent(*self._init_args,
                            botmark_json=botmark_json,
                            **copy.deepcopy(self._init_kwargs))
    
    def get_info( self ):
        return self.botmark_json.get("info", "<p>info not found</p>")
    
    def _init_logfire_instance(self):
        try:
            logging = (self.botmark_json or {}).get("header", {}).get("logging", {})
            if "logfire" in logging:
                import logfire  # only import if needed

                lf = logfire.configure(**logging.get("logfire", {}))
                lf.instrument_pydantic_ai()
                return lf
        except ImportError:
            print("⚠️  logfire is not installed; logging is disabled.")
        except Exception as e:
            print(str(e))

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

            active_graph = get_graph( self.botmark_json["graphs"], ranking_fn )

            active_header = get_header(active_blocks, self.botmark_json["header"])
            model = get_llm_model(active_header.get("model"))

            answer = None
         
            if active_graph:
                def filter_funktion(key, value):
                    return "agent" in value.get("classes", [])
                
                active_agents = {k: v for k, v in active_blocks.items() if filter_funktion(k, v)}
                processors: Dict[str, Agent] = { "[*]": self.clone( include_graphs=False ) }

                try:
                    default_config = json.loads( os.getenv("AGENT_DEFAULT_CONFIG", "{}" ))
                except:
                    default_config = {}

                for node in active_graph["graph"]["nodes"].keys():
                    if node in active_agents.keys():
                        bot_json = default_config | active_agents[node].get("content", {})

                        processors[node] = BotMarkAgent( botmark_json= bot_json)
                    elif not node in processors.keys():
                        processors[node] = Agent( TestModel(custom_output_text=f"response of agent {node}") )

                histories, transcript, answer = await traverse_graph(
                    graph_obj=active_graph,
                    processors=processors,
                    initial_history=kwargs.get("message_history", []),
                    selection_model=model,
                    start_message=user_text
                )

            if not answer:
                active_schema = get_schema(active_blocks, topics )

                VENV_BASE_DIR = active_header.get("VENV_BASE_DIR", os.getenv("VENV_BASE_DIR", "/data/venvs"))

                def filter_funktion(key, value):
                    return "agent" in value.get("classes", [])

                INFO = self.get_info()

                active_agents = {k: v for k, v in active_blocks.items() if filter_funktion(k, v)}
                active_prompt = active_blocks.get("prompt")
                final_query = render_block(active_prompt, {"QUERY": user_text}) if active_prompt else user_text                
                active_system = render_named_block(
                    "system", active_blocks, active_header, VERSION, INFO, final_query, topics, VENV_BASE_DIR, {}
                )

                answer = try_answer(active_blocks, active_system, active_header, VERSION, INFO, final_query, VENV_BASE_DIR, topics)

            if answer is None:
                active_toolset = get_toolset(active_blocks)

                query_objects = parser.parse_to_json(final_query) if active_header.get("inspect_user_prompt", False) is True else {}
                query_images = get_images(query_objects.get("images", []), lambda x: True)
                query_links, _ = process_links(query_objects.get("links", []), lambda x: True)

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

                composed_input = [final_query] + non_str_parts + active_images + active_links + query_images + query_links

                result = await super().run(
                    composed_input,
                    model=model,
                    toolsets=active_toolset,
                    output_type=active_schema,
                    **kwargs
                )

                out = result.output

                if isinstance(out, BaseModel):
                    llm_response = out.model_dump_json()    
                elif isinstance(out, (dict, list)):
                    llm_response = json.dumps(out, ensure_ascii=False)
                elif out is None:
                    raise ValueError("Agent returned no output (None).")
                else:
                    llm_response = str(out)

                answer = make_answer(
                    active_blocks, active_system, active_header, VERSION, INFO, final_query, llm_response, VENV_BASE_DIR, topics
                )

                result = await super().run(
                    composed_input,
                    model=TestModel(custom_output_text=answer),
                    **kwargs
                )
                return result

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
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    try:
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
            raise

class BotmarkSource:

    def __init__( self ):
        pass

    def list_models( self ):
        pass

    def load_botmark(self, model_id):
        pass

class StringSource(BotmarkSource):
    """
    Minimal in-memory source:
    - pass a single (model_id, markdown) OR a dict mapping ids -> markdown strings
    - list_models() returns the same envelope as FileSystemSource
    - load_botmark(model_id) returns the stored markdown or None
    """
    def __init__(self,
                 model_id: Optional[str] = None,
                 text: Optional[str] = None,
                 models: Optional[Mapping[str, str]] = None) -> None:
        super().__init__()

        if models is not None and (model_id is not None or text is not None):
            raise ValueError("Provide EITHER `models` OR (`model_id` and `text`).")

        if models is not None:
            self._models: Dict[str, str] = dict(models)
        else:
            if not model_id or text is None:
                raise ValueError("Provide `model_id` and `text` for single-model usage.")
            self._models = {model_id: text}

        # give everything a created timestamp now
        now = int(time.time())
        self._created: Dict[str, int] = {mid: now for mid in self._models.keys()}

    def list_models(self) -> Dict[str, Any]:
        defaults = {"object": "model", "owned_by": "StringSource"}
        data = []
        for mid in self._models.keys():
            data.append(defaults | {"id": mid, "created": self._created.get(mid, int(time.time()))})
        return {"object": "list", "data": data}

    def load_botmark(self, model_id: str) -> Optional[str]:
        return self._models.get(model_id)

class FileSystemSource(BotmarkSource):
    def __init__(self, bot_dir="."):
        super().__init__()
        self.bot_dir = bot_dir

    def list_models(self) -> Dict[str, Any]:
        """Return all available models in bot_dir."""

        botmark_models = []
        if self.bot_dir:
            models_dir = Path(self.bot_dir)
            if models_dir.exists() and models_dir.is_dir():
                for f in models_dir.rglob("*.md"):
                    if f.is_file():
                        try:
                            created = int(f.stat().st_mtime)
                        except Exception:
                            created = int(time.time())

                        # relative Pfad ohne Endung
                        relative_path = f.relative_to(models_dir).with_suffix("")  # entfernt die Endung
                        botmark_models.append( {"id": str(relative_path).replace("\\", "/"), "created": created } )

        defaults = { "object": "model", "owned_by": "FileSystemProvider" }
        return {
            "object": "list",
            "data": [ defaults | m for m in botmark_models ]
        }

    def load_botmark(self, model_id: str):
        """
        Load and return the raw BotMark markdown string for the given model.
        Only `.md` files are supported.
        """
        if not model_id or not self.bot_dir:
            return None

        models_dir = Path(self.bot_dir)
        if not models_dir.exists() or not models_dir.is_dir():
            return None

        model_path = models_dir / (model_id + ".md")
        if model_path.is_file():
            try:
                with open(model_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(f"⚠️ Error loading {model_path}: {e}")
                return None

        return None

class BotManager:

    def __init__(self, default_model: Optional[Union[str, dict, TextIO]] = None,  adapt_payload = lambda x: x, response_parser = lambda x: x.output, allow_system_prompt_fallback: bool = False, allow_code_execution: bool = False, botmark_source = None ):

        if botmark_source is None:
            botmark_source = [FileSystemSource(".")]
        elif not isinstance(botmark_source, list):
            botmark_source = [botmark_source]
        self.botmark_sources = botmark_source

        self.adapt_payload = adapt_payload
        self.response_parser = response_parser
        self.allow_system_prompt_fallback = allow_system_prompt_fallback
        self.allow_code_execution = allow_code_execution
        self.botmark_source = botmark_source

        self.agent = None
        if hasattr(default_model, 'read'):
            self.agent = self.get_agent( default_model.read() )

        elif isinstance(default_model, str):
            self.agent = self._get_agent_from_model_name( default_model )

        elif isinstance(default_model, dict):
            self.agent = self.get_agent( default_model )

    def get_info( self, model_name: Optional[str] = None):
        model_data = self._load_from_sources( model_name)
        if model_data:
            return self.get_agent( parser.parse_to_json( model_data) ).get_info()
        return self.agent.get_info() if self.agent else f"<p>info not found</p>"

    def get_agent( self, bot_definition: Union[str, dict] ):

        bot_json = bot_definition if isinstance(bot_definition, dict) else parser.parse_to_json(bot_definition )
        
        try:
            bot_json = json.loads( os.getenv("AGENT_DEFAULT_CONFIG", "{}" ))  | bot_json
        except:
            pass

        if not self.allow_code_execution:
            disallowed = {"mako", "python", "fstring"}
            kept = []

            for i, block in enumerate(bot_json.get("codeblocks", []) or []):
                lang = (block.get("language") or "").lower()
                if lang in disallowed:
                    ident = (
                        block.get("id")
                        or block.get("name")
                        or (block.get("attributes") or {}).get("id")
                        or (block.get("attributes") or {}).get("name")
                        or f"index:{i}"
                    )
                    print(f"⚠️ allow_code_execution=False — filtered codeblock '{ident}' (language='{lang}')")
                else:
                    kept.append(block)

            bot_json["codeblocks"] = kept

        agent_kwargs = {
            "botmark_json": bot_json,
            "model": TestModel()
        }

        agent = BotMarkAgent(**agent_kwargs)
        return agent

    def _get_agent_from_model_name( self, model_name ):
        model_data = parser.parse_to_json( self._load_from_sources( model_name ) )
        return  self.get_agent( model_data ) if model_data else None

    def get_tests(self):
        tests = [{ "model": "", "tests": self.agent.get_tests()}]  if self.agent else []
        for model_info in self.get_models().get("data", []):
            model_id = model_info["id"]
            bm_code = parser.parse_to_json( self._load_from_sources( model_id ) )
            agent = self.get_agent( bm_code )
            tests += [{"model": model_id, "tests": agent.get_tests()}]
        return tests

    def get_models(self) -> dict:
        all_models = {"object": "list", "data": []}
        seen_ids = set()
        for source in self.botmark_sources:
            models = source.list_models().get("data", [])
            for m in models:
                if m["id"] not in seen_ids:
                    all_models["data"].append(m)
                    seen_ids.add(m["id"])
        return all_models
        
    def _load_from_sources(self, model_id: str) -> Optional[str]:
        for source in self.botmark_sources:
            content = source.load_botmark(model_id)
            if content:
                return content
        return None

    def _model_exists(self, model_list: dict, model_id: str) -> bool:
        for model in model_list.get("data", []):
            if model.get("id") == model_id:
                return True
        return False
       
    def respond_sync(self, json_payload: dict) -> str:
        json_payload = self.adapt_payload(json_payload)
        model_name = json_payload.get( "model", None )
        models = self.get_models()

        if self._model_exists(models, model_name):
            model_data = parser.parse_to_json( self._load_from_sources( model_name ) )
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
    
    async def respond(self, json_payload: Dict) -> str:
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

        if self._model_exists(models, model_name):
            model_data = parser.parse_to_json( self._load_from_sources(model_name) )
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
