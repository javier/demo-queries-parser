#!/usr/bin/env python3
"""
export_queries.py

Usage:
    python export_queries.py --input input.yaml --output queries.txt

This script reads a multi-document YAML file, extracts the JSON stored under
the key "console-configuration.json" (inside the ConfigMap with the saved queries),
parses it, and then writes a plain-text file listing all saved queries in a
readable format.
"""

import argparse
import json
import re
import sys

def extract_console_configuration_json(yaml_text):
    """
    Extracts the block of text for the console-configuration.json field from the YAML text.
    This function searches for a line that starts with "console-configuration.json:" followed by a pipe ("|")
    and then collects the indented block that follows.
    """
    # Use regex to find the key and capture the block.
    # The pattern looks for a line like "console-configuration.json: |" then captures all subsequent lines
    # that are indented (or blank) until a line that is not indented.
    pattern = re.compile(
        r'^[ \t]*console-configuration\.json:\s*\|\s*\n'  # key line with pipe
        r'((?:[ \t]+.*\n)+)',  # one or more lines that start with whitespace
        re.MULTILINE
    )
    match = pattern.search(yaml_text)
    if not match:
        sys.exit("ERROR: Could not find console-configuration.json block in the input YAML.")
    # The captured block still has its common indent; remove that indent.
    block = match.group(1)
    # Determine the indent by looking at the first non-blank line:
    indent_match = re.match(r'^([ \t]+)', block)
    if indent_match:
        indent = indent_match.group(1)
    else:
        indent = ""
    # Remove the common indent from each line.
    lines = block.splitlines()
    stripped_lines = [line[len(indent):] if line.startswith(indent) else line for line in lines]
    json_text = "\n".join(stripped_lines)
    return json_text

def format_queries(data):
    """
    Given the parsed JSON data from the console configuration, iterate over the savedQueries
    and return a string containing all queries formatted in a human‐readable way.
    
    The expected structure is:
    {
       "githubBanner": true,
       "readOnly": true,
       "savedQueries": [
         {
           "title": "Category Title",
           "description": "Description ...",
           "queries": [
              {"name": "Query Name", "value": "SQL text with newlines..."},
              ...
           ]
         },
         ...
       ]
    }
    """
    output_lines = []
    saved_queries = data.get("savedQueries", [])
    for category in saved_queries:
        cat_title = category.get("title", "No Category Title")
        cat_desc = category.get("description", "")
        output_lines.append(f"Category: {cat_title}")
        if cat_desc:
            output_lines.append(f"Description: {cat_desc}")
        output_lines.append("=" * 40)
        queries = category.get("queries", [])
        for query in queries:
            qname = query.get("name", "No Query Name")
            qvalue = query.get("value", "")
            output_lines.append(f"Query Name: {qname}")
            output_lines.append("-" * 40)
            output_lines.append(qvalue.rstrip())  # remove trailing whitespace
            output_lines.append("=" * 40)
            output_lines.append("")  # extra blank line for spacing
        output_lines.append("\n")  # extra blank line between categories
    return "\n".join(output_lines)

def main():
    parser = argparse.ArgumentParser(
        description="Extract queries from a YAML file containing a console configuration JSON block."
    )
    parser.add_argument("--input", "-i", required=True, help="Input YAML file")
    parser.add_argument("--output", "-o", required=True, help="Output text file for the queries")
    args = parser.parse_args()

    # Read the entire YAML file as text.
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            yaml_text = f.read()
    except Exception as e:
        sys.exit(f"Error reading input file: {e}")

    # Extract the JSON block from the YAML.
    json_text = extract_console_configuration_json(yaml_text)

    # Parse the JSON.
    try:
        config = json.loads(json_text)
    except Exception as e:
        sys.exit(f"Error parsing JSON from console-configuration.json block: {e}")

    # Format the queries into a plain text output.
    output_text = format_queries(config)

    # Write the output.
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_text)
    except Exception as e:
        sys.exit(f"Error writing output file: {e}")

    print(f"Queries exported successfully to {args.output}")

if __name__ == "__main__":
    main()

