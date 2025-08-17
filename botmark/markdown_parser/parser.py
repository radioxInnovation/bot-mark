import html, re, time
#import yaml
from ..utils.yaml_parser import yaml

from .renderer import md, parse_attributes

from ..utils.helpers import CodeBlock, read_file_content

from botmark.utils.logging import log_info
import json

def parse_to_json(markdown: str ) -> dict:
    items = get_named_items(markdown)

    def make_codeblock ( block ):

        if "agent" in block.get("classes") and block.get("language") == "markdown":
            return CodeBlock( language="json", attributes = block.get("attributes", {}), content=json.dumps( parse_to_json( block.get("content"))), classes=block.get("classes", []) ).to_json()
            
        return block.to_json() 

    if "codeblocks" in items:
        items["codeblocks"] = [
            make_codeblock ( cb )  for cb in items["codeblocks"] if hasattr(cb, "to_json")
        ]
    return items

class MermaidParser:
    def __init__(self):
        self.node_pattern = re.compile(
            r'(\w+)\s*\["(.*?)"\]|(\w+)\s*\[(.*?)\]|(\w+)\s*\(\((.*?)\)\)|'
            r'(\w+)\s*\((.*?)\)|(\w+)\s*\{(.*?)\}|(\w+)\s*>(.*?)\]', re.VERBOSE)
        self.edge_pattern = re.compile(
            r"(?P<source>\w+|[*])(?:\[[^\]]*\]|\(\([^\)]*\)\)|\([^\)]*\)|\{[^\}]*\}|\"[^\"]*\")?"
            r"\s*(?P<style>(--+>|==+>|(?:-\.){1,3}->))\s*"
            r"(?:\|(?P<label>.*?)\|\s*)?"
            r"(?P<target>\w+|[*])(?:\[[^\]]*\]|\(\([^\)]*\)\)|\([^\)]*\)|\{[^\}]*\}|\"[^\"]*\")?",
            re.VERBOSE
        )
        self.state_edge_pattern = re.compile(
            r'(?P<source>\[?\*?\]?\w*)\s*-->\s*(?P<target>\[?\*?\]?\w*)\s*(?::\s*(?P<label>.+))?'
        )

    def parse(self, code):
        lines = code.strip().splitlines()
        ast = {
            "title": None,
            "type": "flowchart",  # default
            "nodes": {},
            "edges": []
        }
        connected_nodes = set()

        # Detect title and diagram type
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("title:"):
                ast["title"] = stripped[len("title:"):].strip()
            elif "stateDiagram-v2" in stripped:
                ast["type"] = "stateDiagram-v2"
            elif stripped.startswith("flowchart"):
                ast["type"] = "flowchart"

        for line in lines:
            line = line.strip()
            if not line or line.startswith("%%") or line.startswith("title:"):
                continue

            if ast["type"] == "flowchart":
                for match in self.edge_pattern.finditer(line):
                    source = match.group("source")
                    target = match.group("target")
                    style = match.group("style")
                    label = match.group("label")
                    ast["edges"].append({
                        "source": source,
                        "target": target,
                        "label": html.unescape(label.strip()) if label else None,
                        "style": style
                    })
                    connected_nodes.update([source, target])

                for match in self.node_pattern.finditer(line):
                    groups = match.groups()
                    shapes = ['box', 'box', 'round', 'round', 'rhombus', 'asymmetric']
                    for i in range(0, len(groups), 2):
                        node_id = groups[i]
                        label = groups[i + 1]
                        if node_id and node_id in connected_nodes:
                            shape = shapes[i // 2]
                            ast["nodes"][node_id] = {
                                "id": node_id,
                                "label": html.unescape(label.strip()) if label else None,
                                "shape": shape
                            }
                            break

            elif ast["type"] == "stateDiagram-v2":
                for match in self.state_edge_pattern.finditer(line):
                    source = match.group("source").strip()
                    target = match.group("target").strip()
                    label = match.group("label")

                    for node_id in [source, target]:
                        if node_id not in ast["nodes"]:
                            ast["nodes"][node_id] = {
                                "id": node_id,
                                "label": node_id,
                                "shape": "state"
                            }

                    ast["edges"].append({
                        "source": source,
                        "target": target,
                        "label": html.unescape(label.strip()) if label else None,
                        "style": "-->"
                    })

        # Add fallback nodes for any missing ones (flowchart only)
        for edge in ast["edges"]:
            for node_id in (edge["source"], edge["target"]):
                if node_id not in ast["nodes"]:
                    ast["nodes"][node_id] = {"id": node_id, "label": node_id, "shape": "box"}

        return ast

def find_valid_paths(graph, max_depth, max_seconds=0.1, max_paths=None):
    start_node = "[*]"
    end_node = "[*]"
    valid_paths = []

    # prepare an adjacency list
    adjacency = {}
    for edge in graph["edges"]:
        adjacency.setdefault(edge["source"], []).append(edge["target"])

    start_time = time.time()
    stack = [([start_node], 0)]  # [(path, depth)]

    while stack:
        if time.time() - start_time > max_seconds:
            break  # time limit

        if max_paths is not None and len(valid_paths) >= max_paths:
            break  # path limit erreicht

        path, depth = stack.pop()
        current = path[-1]

        if current == end_node and len(path) > 1:
            valid_paths.append(path)
            continue  # stop if [*]

        if depth >= max_depth:
            continue

        for neighbor in adjacency.get(current, []):
            stack.append((path + [neighbor], depth + 1))

    return sorted(valid_paths, key=len)

def get_named_items(md_text):
    #md = MarkdownIt("commonmark").use(attrs_plugin).use(container_plugin, "info") .enable("fence").enable("table")
    #md.validateLink = lambda url: True
    frontmatter_header, content_with_comment = get_header_and_content(md_text)
    content = re.sub(r'<!--.*?-->', '', content_with_comment, flags=re.DOTALL)
    tokens = md.parse( content )

    table_patterns = {
        "topic": [ {"name": "description"}, {"name": "prompt_prefix", "default": "" }, {"name": "prompt_suffix", "default": "" }, {"name": "prompt_regex", "default": "" }, {"name": "disabled", "default": "no" } ],
    }

    tables = {}
    codeblocks = []
    images = []
    links = []
    graphs = []
    collecting = False
    info_tokens = []

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.type == "container_info_open":
            collecting = True
        elif token.type == "container_info_close":
            collecting = False
        elif collecting:
            info_tokens.append( token )

        # Tabellen
        if token.type == "table_open":
            i += 1
            headers = []
            rows = []
            while tokens[i].type != "table_close":
                if tokens[i].type == "thead_open":
                    i += 2
                    while tokens[i].type != "tr_close":
                        if tokens[i].type == "th_open":
                            i += 1
                            headers.append(tokens[i].content.strip().lower())
                            i += 2
                        else:
                            i += 1
                    i += 2
                elif tokens[i].type == "tbody_open":
                    i += 1
                    while tokens[i].type != "tbody_close":
                        if tokens[i].type == "tr_open":
                            i += 1
                            row = []
                            while tokens[i].type != "tr_close":
                                if tokens[i].type == "td_open":
                                    i += 1
                                    row.append(tokens[i].content.strip())
                                    i += 2
                                else:
                                    i += 1
                            rows.append(row)
                            i += 1
                        else:
                            i += 1
                    i += 1
                else:
                    i += 1

            # Match table to a known pattern
            for table_name, pattern in table_patterns.items():
                expected_headers = [col["name"].lower() for col in pattern if not "default" in col] + [ table_name.lower()]
                if all(h in headers for h in expected_headers):
                    # Convert rows to dicts with optional defaults
                    table_data = []
                    for row in rows:
                        row_dict = {}
                        for idx, col in enumerate(pattern):
                            header = col["name"]
                            default = col.get("default", None)
                            value = row[headers.index(header)] if header in headers else default
                            row_dict[header] = value
                        if not "disabled" in row_dict or not is_truthy(row_dict["disabled"]):
                            table_data.append(row_dict | {"name": row[headers.index(table_name)]})
                    tables[table_name] = table_data
                    break  # Stop after first match

        elif token.type == "fence":
            lang, attrs = parse_info_string( token.info )
            ident = attrs.get("id", None )
            if ident:
                attrs["class"] = attrs["class"].split(" ") if "class" in attrs else []
                if not "disabled" in attrs["class"]:
                    content = token.content 
                    src = attrs.get("src")
                    if src:
                        timeout = int( attrs.get("timeout", 10 ))
                        try:
                            content = read_file_content ( src, timeout, is_binary=False )
                        except Exception as e:
                            print (e)
                    code_block = CodeBlock( **{ "language": lang, "classes": attrs["class"], "content": content, "attributes": {k: v for k, v in attrs.items() if k != "class"} })

                    if ident == "graph":
                        max_steps = int(code_block.get("attributes").get("max-steps", 10 ))
                        max_seconds = float(code_block.get("attributes").get("timeout-seconds", 2.0))
                        max_paths = int(code_block.get("attributes").get("max-paths", 1000))
                        parsed_graph = MermaidParser().parse( code_block.get("content"))
                        graphs.append( { "graph": parsed_graph, "valid_paths": find_valid_paths( parsed_graph, max_depth=max_steps, max_seconds=max_seconds, max_paths=max_paths), "attributes": attrs } )
                    else:
                        codeblocks.append( code_block )
        elif token.type == "inline":
            for child in token.children or []:

                classes = child.attrs["class"].split(" ") if "class" in child.attrs else []

                if not "disabled" in classes:
                    if child.type == "image":
                        images.append( child.attrs )
                    elif child.type == "link_open":
                        links.append( child.attrs )

        i += 1
    return { "header": frontmatter_header, "codeblocks": codeblocks, "images": images, "links": links, "tables": tables, "graphs": graphs, "info": md.renderer.render(info_tokens, md.options, {}) }

def get_header_and_content(markdown_text: str):
    """
    Extract metadata (YAML front matter) and content between BOTMARK markers.
    Falls back gracefully if no front matter is present.
    """
    start_pattern = r"<!--\s*BOTMARK\s*START\s*-->"
    end_pattern = r"<!--\s*BOTMARK\s*END\s*-->"

    start_match = re.search(start_pattern, markdown_text, re.IGNORECASE)
    end_match = re.search(end_pattern, markdown_text, re.IGNORECASE)

    start_index = start_match.end() if start_match else 0
    end_index = end_match.start() if end_match else len(markdown_text)

    extracted = markdown_text[start_index:end_index].strip()

    metadata = {}
    content = extracted

    # Check for YAML front matter style: ---\n...\n---
    fm_pattern = r"^---\s*\n(.*?)\n---\s*\n?(.*)$"
    fm_match = re.match(fm_pattern, extracted, re.DOTALL)

    if fm_match:
        yaml_block, body = fm_match.groups()
        try:
            metadata = yaml.safe_load(yaml_block) or {}
            content = body.strip()
        except Exception as e:
            # You can replace log_info with print or logging
            print(f"⚠️ YAML parse error: {e}")
            metadata = {}
            content = extracted

    return metadata, content

# def get_header_and_content(markdown_text: str):
#     # Define regex patterns for flexible MARKBOT START and END markers
#     start_pattern = r"<!--\s*BOTMARK\s*START\s*-->"
#     end_pattern = r"<!--\s*BOTMARK\s*END\s*-->"

#     # Find the positions of the markers
#     start_match = re.search(start_pattern, markdown_text, re.IGNORECASE)
#     end_match = re.search(end_pattern, markdown_text, re.IGNORECASE)

#     # Calculate slicing indices
#     start_index = start_match.end() if start_match else 0
#     end_index = end_match.start() if end_match else len(markdown_text)

#     # Extract the block between the markers
#     extracted = markdown_text[start_index:end_index].strip()

#     try:
#         post = frontmatter.loads(extracted)
#         metadata = post.metadata
#         content = post.content
#         return metadata, content
#     except Exception as e:
#         log_info(f"⚠️ frontmatter parse error: {e}")
#         return {}, extracted

def parse_attrs(attr_block: str) -> dict:
    #md = MarkdownIt("commonmark").use(attrs_plugin)
    get_attrs = parse_attributes #lambda x: md.parse(x)[1].children[0].attrs
    attrs = list(map(get_attrs, [f'[](){attr_block.strip()}', f'![](){attr_block.strip()}' ]))
    common_keys = set(attrs[0]).intersection(*[d.keys() for d in attrs[1:]])
    return {k: attrs[0][k] for k in common_keys}


def parse_info_string(info: str):
    lang = ""
    attrs = {}
    match = re.match(r'^(\w+)?\s*(\{.*\})?', info.strip())
    if not match:
        return "", {}
    lang = match.group(1) or ""
    attr_block = match.group(2)
    if attr_block:
        attrs = parse_attrs( attr_block )
    return lang, attrs

def is_truthy(value) -> bool:
    epsilon = 1e-4 
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, float):
        return abs(value) > epsilon
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False
