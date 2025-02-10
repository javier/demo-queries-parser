#!/usr/bin/env python3
"""
import_queries.py

Usage:
  python import_queries.py --yaml input.yaml --plain queries.txt --output new.yaml

This script reads:
  1. A plain text file (e.g. queries.txt) that contains queries in a human‑readable format.
  2. An original multi‑document YAML file that contains a block for "console-configuration.json".

It parses the plain text file into a JSON structure (a dictionary with a "savedQueries" key)
and then updates the JSON stored in the YAML file’s console-configuration.json block (preserving other keys)
with the new "savedQueries" value. The updated YAML file is then written out.
"""

import argparse
import json
import re
import sys

def parse_plain_text(text):
    """
    Parse the plain text file produced by the export script.
    
    The expected format is:
    
      Category: <Category Title>
      Description: <Optional description>
      ========================================
      Query Name: <Query Name>
      ----------------------------------------
      <query text (can span multiple lines)>
      ========================================
      
      [Optional blank lines; then next query, etc.]
    
    This function returns a dict of the form:
      { "savedQueries": [
            { "title": "...", "description": "...", "queries": [
                  { "name": "...", "value": "..." },
                  ...
              ]
            },
            ...
         ]
      }
    """
    lines = text.splitlines()
    saved_queries = []
    current_category = None
    current_query = None
    state = "init"  # states: init, category_header, in_category, in_query_header, in_query_value

    # helper: check if a line is made entirely of a given character (e.g. '=' or '-')
    def is_separator_line(line, char):
        line_stripped = line.strip()
        return line_stripped and all(c == char for c in line_stripped)

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        if line.startswith("Category:"):
            # Found a new category. If one was open, close it.
            if current_category is not None:
                if current_query is not None:
                    # Finalize the open query.
                    current_query["value"] = "\n".join(current_query["value"]).rstrip()
                    current_category["queries"].append(current_query)
                    current_query = None
                saved_queries.append(current_category)
            cat_title = line[len("Category:"):].strip()
            current_category = {"title": cat_title, "description": "", "queries": []}
            state = "category_header"
            i += 1
            # Check if the next nonblank line is a description.
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and lines[i].startswith("Description:"):
                current_category["description"] = lines[i][len("Description:"):].strip()
                i += 1
            # Next, expect a separator line (a line of '=')
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and is_separator_line(lines[i], "="):
                state = "in_category"
                i += 1
            continue

        if state == "in_category" and line.startswith("Query Name:"):
            # Start a new query in the current category.
            if current_query is not None:
                # Finalize any previously open query.
                current_query["value"] = "\n".join(current_query["value"]).rstrip()
                current_category["queries"].append(current_query)
                current_query = None
            qname = line[len("Query Name:"):].strip()
            current_query = {"name": qname, "value": []}
            state = "in_query_header"
            i += 1
            # Skip any blank lines and expect the next line to be a '-' separator.
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and is_separator_line(lines[i], "-"):
                state = "in_query_value"
                i += 1
            else:
                sys.exit(f"Error: Expected a '-' separator after Query Name at line {i+1}.")
            continue

        if state == "in_query_value":
            # In the query value block; look for a line that is a '=' separator
            if is_separator_line(line, "="):
                # End of the current query.
                current_query["value"] = "\n".join(current_query["value"]).rstrip()
                current_category["queries"].append(current_query)
                current_query = None
                state = "in_category"
                i += 1
                continue
            else:
                # Accumulate query text.
                current_query["value"].append(line)
                i += 1
                continue

        # If the line does not match any expected pattern, just skip it.
        i += 1

    # End of file: finalize any open query/category.
    if current_query is not None:
        current_query["value"] = "\n".join(current_query["value"]).rstrip()
        current_category["queries"].append(current_query)
    if current_category is not None:
        saved_queries.append(current_category)
    return {"savedQueries": saved_queries}

def extract_console_configuration_json_block(yaml_text):
    """
    Extract the JSON block from the YAML for the key "console-configuration.json:".
    
    Returns a tuple (start_index, end_index, indent, json_text) where:
      - start_index, end_index: the indices in the yaml_text corresponding to the block to replace.
      - indent: the common indent of the block.
      - json_text: the current JSON text (with the indent removed).
    """
    pattern = re.compile(
        r'(^[ \t]*console-configuration\.json:\s*\|\s*\n)'  # key line (group 1)
        r'((?:[ \t]+.*\n)+)',  # indented block (group 2)
        re.MULTILINE
    )
    match = pattern.search(yaml_text)
    if not match:
        sys.exit("ERROR: Could not find console-configuration.json block in the YAML file.")
    start_index = match.start(2)
    end_index = match.end(2)
    block_text = match.group(2)
    # Determine common indent from the first nonempty line.
    first_line = block_text.splitlines()[0]
    indent_match = re.match(r'^([ \t]+)', first_line)
    indent = indent_match.group(1) if indent_match else ""
    # Remove the indent from each line.
    json_lines = []
    for line in block_text.splitlines():
        if line.startswith(indent):
            json_lines.append(line[len(indent):])
        else:
            json_lines.append(line)
    json_text = "\n".join(json_lines)
    return start_index, end_index, indent, json_text

def main():
    parser = argparse.ArgumentParser(
        description="Import queries from a plain text file into a YAML file by updating the console-configuration.json block."
    )
    parser.add_argument("--yaml", "-y", required=True, help="Input YAML file")
    parser.add_argument("--plain", "-p", required=True, help="Plain text file with queries")
    parser.add_argument("--output", "-o", required=True, help="Output YAML file")
    args = parser.parse_args()

    # Read the plain text file.
    try:
        with open(args.plain, "r", encoding="utf-8") as f:
            plain_text = f.read()
    except Exception as e:
        sys.exit(f"Error reading plain text file: {e}")

    # Parse the plain text into the new savedQueries structure.
    new_config = parse_plain_text(plain_text)
    # new_config is a dict like { "savedQueries": [...] }

    # Read the original YAML file as text.
    try:
        with open(args.yaml, "r", encoding="utf-8") as f:
            yaml_text = f.read()
    except Exception as e:
        sys.exit(f"Error reading YAML file: {e}")

    # Extract the existing console-configuration.json block.
    start_idx, end_idx, indent, existing_json_text = extract_console_configuration_json_block(yaml_text)
    try:
        original_config = json.loads(existing_json_text)
    except Exception as e:
        sys.exit(f"Error parsing JSON from YAML block: {e}")

    # Update the "savedQueries" key with the new value.
    original_config["savedQueries"] = new_config.get("savedQueries", [])

    # Dump the updated JSON with indentation.
    new_json_text = json.dumps(original_config, indent=2)
    # Re-indent each line with the captured indent.
    new_json_lines = new_json_text.splitlines()
    indented_new_json = "\n".join(indent + line for line in new_json_lines) + "\n"

    # Replace the original block in the YAML text with the new JSON block.
    updated_yaml_text = yaml_text[:start_idx] + indented_new_json + yaml_text[end_idx:]

    # Write the updated YAML text to the output file.
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(updated_yaml_text)
    except Exception as e:
        sys.exit(f"Error writing output YAML file: {e}")

    print(f"Updated YAML file written to {args.output}")

if __name__ == "__main__":
    main()

