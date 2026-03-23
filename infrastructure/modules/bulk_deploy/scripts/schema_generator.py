# /// script
# requires-python = ">=3.10"
# dependencies = ["prefect"]
# ///
"""
Terraform external data source that generates an OpenAPI parameter schema
from a Prefect flow entrypoint using `parameter_schema_from_entrypoint`.

Called from infrastructure/ with:
  program = ["uv", "run", "scripts/schema_generator.py"]

Expects a JSON query on stdin with:
  entrypoint  – the entrypoint as written in prefect.yaml (e.g. "weather.py:get_weather")
  folder      – absolute path to the demo folder name (e.g. "/path/to/artifacts")

The script returns the OpenAPI parameter schema as a JSON string  
that can be passed directly to the prefect_deployment resource's 
`parameter_openapi_schema` attribute.
"""

import json
import sys
from pathlib import Path


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(
            json.dumps({"error": f"Invalid JSON on stdin: {exc}"}),
            file=sys.stderr,
        )
        sys.exit(1)

    entrypoint = input_data.get("entrypoint", "")
    folder = input_data.get("folder", "")

    if not entrypoint:
        print(
            json.dumps({"error": "Missing required query parameter: 'entrypoint'"}),
            file=sys.stderr,
        )
        sys.exit(1)

    if not folder:
        print(
            json.dumps({"error": "Missing required query parameter: 'folder'"}),
            file=sys.stderr,
        )
        sys.exit(1)

    # The entrypoint in prefect.yaml is relative to the demo folder, e.g.
    #   weather.py:get_weather
    # We need to build the full path relative to this script's working
    # directory (infrastructure/), so: ../demos/<folder>/<file>:<func>
    if ":" not in entrypoint:
        print(
            json.dumps({"error": f"Entrypoint must contain ':' — got '{entrypoint}'"}),
            file=sys.stderr,
        )
        sys.exit(1)

    file_part, func_name = entrypoint.rsplit(":", maxsplit=1)

    # Resolve to an absolute path so parameter_schema_from_entrypoint can
    # find the source file regardless of cwd quirks.
    resolved_file = Path(folder, file_part).resolve()

    if not resolved_file.is_file():
        print(
            json.dumps({
                "error": (
                    f"Source file not found: {resolved_file}  "
                    f"(folder={folder!r}, entrypoint={entrypoint!r})"
                )
            }),
            file=sys.stderr,
        )
        sys.exit(1)

    qualified_entrypoint = f"{resolved_file}:{func_name}"

    from prefect.utilities.callables import parameter_schema_from_entrypoint

    try:
        schema = parameter_schema_from_entrypoint(qualified_entrypoint)
    except Exception as exc:
        print(
            json.dumps({
                "error": f"Schema generation failed for '{qualified_entrypoint}': {exc}"
            }),
            file=sys.stderr,
        )
        sys.exit(1)

    # Terraform external data sources require every value to be a string.
    result = {"schema": json.dumps(schema.model_dump_for_openapi())}
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
