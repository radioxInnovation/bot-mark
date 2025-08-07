--[[
extract_info.lua - A Pandoc Lua filter for extracting specific class-based content
==================================================================================

Description:
------------
This filter allows you to extract only the contents of Div blocks with a specific class
(e.g., :::info) and output them without the outer Div wrapper. It also optionally
truncates code blocks to a maximum number of characters.

The filter supports the following metadata variables via Pandoc command-line arguments:

Metadata parameters:
--------------------
- extractclass (string, optional)
    The class name to filter for (e.g., "info", "userdoc").
    If not provided or empty, the entire document will be included (no filtering).

- maxlength (number, optional)
    The maximum number of characters allowed in code blocks.
    Defaults to 500. Truncated blocks will end with "…".

Usage:
------

Basic usage — export the full document:
    pandoc system_fault_reporter.md \
        --lua-filter=extract_info.lua \
        -o full.docx

Filter by class — export only :::info sections:
    pandoc system_fault_reporter.md \
        --lua-filter=extract_info.lua \
        -M extractclass=info \
        -o info_only.docx

Filter by class and limit code block size:
    pandoc system_fault_reporter.md \
        --lua-filter=extract_info.lua \
        -M extractclass=info \
        -M maxlength=300 \
        -o info_limited.docx

Export everything but limit code blocks:
    pandoc system_fault_reporter.md \
        --lua-filter=extract_info.lua \
        -M maxlength=200 \
        -o full_limited.docx

Notes:
------
- The filter only applies the character limit to code blocks (`~~~` or indented code).
- Paragraphs, headers, and other elements are not truncated.
- If `extractclass` is empty or not set, no filtering is applied — the full document is exported.

]]

local class_to_extract = ""     -- default: empty = export everything
local max_length = 2000          -- default max characters for code blocks

-- Read metadata passed via -M extractclass=... and -M maxlength=...
function Meta(meta)
  if meta.extractclass then
    class_to_extract = pandoc.utils.stringify(meta.extractclass)
  end
  if meta.maxlength then
    local n = tonumber(pandoc.utils.stringify(meta.maxlength))
    if n then
      max_length = n
    end
  end
end

-- Check if a Div has the desired class (only if class is set)
local function has_target_class(el)
  return class_to_extract == "" or (el.classes and el.classes:includes(class_to_extract))
end

-- Truncate code block content to max_length characters
function CodeBlock(el)
  if #el.text > max_length then
    el.text = el.text:sub(1, max_length) .. "…"
  end
  return el
end

-- Extract content from matching Divs, or all if no class specified
function Pandoc(doc)
  local extracted = {}

  for _, el in ipairs(doc.blocks) do
    if el.t == "Div" and has_target_class(el) then
      for _, inner in ipairs(el.content) do
        table.insert(extracted, inner)
      end
    elseif class_to_extract == "" then
      table.insert(extracted, el)
    end
  end

  return pandoc.Pandoc(extracted, doc.meta)
end
