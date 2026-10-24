#!/usr/bin/env python3
"""
JSON schema validator for the GTM agent regression tests.

Reads a JSON spec from argv[1] (a file with {"schema": {...}, "required": [...]})
and the candidate output from stdin. Validates that the output parses as JSON
and matches the schema. Exits 0 on pass, 1 on fail. Prints a JSON report.

The schema uses a minimal subset:
  - "type": "object" | "string" | "number" | "boolean" | "array"
  - "required": [list of required keys] (for objects)
  - "items": {schema} (for arrays)
  - "additionalProperties": false (optional, default true)
"""
import json
import sys


def validate(value, schema, path="$"):
    errors = []
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object, got {type(value).__name__}")
            return errors
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required key '{key}'")
        if schema.get("additionalProperties", True) is False:
            allowed = set(schema.get("required", [])) | set(schema.get("properties", {}).keys())
            for key in value:
                if key not in allowed:
                    errors.append(f"{path}: unexpected key '{key}'")
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                errors.extend(validate(value[key], sub, f"{path}.{key}"))
    elif expected == "array":
        if not isinstance(value, list):
            errors.append(f"{path}: expected array, got {type(value).__name__}")
            return errors
        items = schema.get("items", {})
        for i, item in enumerate(value):
            errors.extend(validate(item, items, f"{path}[{i}]"))
    elif expected == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string, got {type(value).__name__}")
    elif expected == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{path}: expected number, got {type(value).__name__}")
    elif expected == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{path}: expected boolean, got {type(value).__name__}")
    return errors


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"pass": False, "errors": ["no schema file provided"]}))
        sys.exit(1)
    with open(sys.argv[1]) as f:
        spec = json.load(f)
    schema = spec["schema"]
    text = sys.stdin.read().strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        # Fall back: extract the first balanced {...} object from prose.
        start = text.find("{")
        if start == -1:
            print(json.dumps({"pass": False, "errors": ["no JSON object found in output"]}))
            sys.exit(1)
        depth = 0
        in_str = False
        esc = False
        end = -1
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            print(json.dumps({"pass": False, "errors": ["unbalanced JSON object in output"]}))
            sys.exit(1)
        try:
            value = json.loads(text[start:end + 1])
        except json.JSONDecodeError as e:
            print(json.dumps({"pass": False, "errors": [f"invalid JSON: {e}"]}))
            sys.exit(1)
    errors = validate(value, schema)
    report = {"pass": len(errors) == 0, "errors": errors}
    print(json.dumps(report))
    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
