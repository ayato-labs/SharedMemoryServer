
import asyncio
from typing import Any
from pydantic import RootModel, ValidationError, TypeAdapter

# Simulate the type hint in FastMCP
def validate_bank_files(input_value: Any):
    # Testing union type hint
    adapter = TypeAdapter(dict[str, str] | list[dict[str, str]] | None)
    try:
        adapter.validate_python(input_value)
        print("Validation success")
    except ValidationError as e:
        print(f"Validation error: {e}")

# The failing case reported by the user
failing_input = [{'content': '# Project: ...l_figures_overview.md'}]
print(f"Testing list input: {failing_input}")
validate_bank_files(failing_input)

# Another list case with explicit filename
list_with_filename = [{'filename': 'overview.md', 'content': '# Project: ...'}]
print(f"\nTesting list with filename: {list_with_filename}")
validate_bank_files(list_with_filename)

# The working case
working_input = {"overview.md": "# Project: ..."}
print(f"\nTesting working input: {working_input}")
validate_bank_files(working_input)
