from __future__ import annotations

import json
import time
import subprocess
from itertools import islice

from ..registry import action
import os

@action(
    name="execute_python_file",
    description="Execute a Python script file. You should ensure that the file you want to run is created with the correct content before attempting to run it.",
    parameters=[
        {
            "name": "script_path",
            "description": "The path to the Python script file to run",
            "type": "string",
            "required": True,
        },
        {
            "name": "data",
            "description": "The optional data to pass to the Python script into STDIN in the form of a JSON array string",
            "type": "string",
            "required": False,
        }
    ],
    output_type="str",
)
async def execute_python_file(agent, task_id: str, script_path: str, data: str = None) -> str:
    """Return the results of the Python script run

    Args:
        script_path (str): The path to the Python script to run.
        data (str): Optional data to pass to the Python script into STDIN in the form of a JSON array string.

    Returns:
        str: The results of the script run.
    """

    output, error = agent.workspace.execute_python_code(task_id=task_id, script=script_path, data=data)
    return f"OUTPUT: {output}\nERROR: {error}"
    # try:
    #   process = subprocess.Popen(
    #     ['python', f"agbenchmark_config/temp_folder/{script_path}"],
    #     stdout=subprocess.PIPE,
    #     stderr=subprocess.STDOUT,
    #     text=True
    #   )
    # except subprocess.CalledProcessError as error:
    #     return f"ERROR: , {str(error.output)}"
    # except FileNotFoundError as error:
    #     errorMessage = error.strerror
    #     return f"ERROR: Could not find script at {script_path}, {errorMessage}"

    # parsed_data = None
    # try:
    #     parsed_data = json.loads(data)
    #     if not isinstance(parsed_data, list):
    #         parsed_data = None
    # except ValueError:
    #     parsed_data = None

    # output, errors = process.communicate('\n'.join(parsed_data) if parsed_data else None)

    # return f"OUTPUT: {output}\nERRORS: {errors}"