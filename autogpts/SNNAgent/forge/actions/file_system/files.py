from typing import List
import base64
import re

from ..registry import action


@action(
    name="list_files",
    description="List files in a directory",
    parameters=[
        {
            "name": "path",
            "description": "Path to the directory",
            "type": "string",
            "required": True,
        }
    ],
    output_type="list[str]",
)
async def list_files(agent, task_id: str, path: str) -> List[str]:
    """
    List files in a workspace directory
    """
    return agent.workspace.list(task_id=task_id, path=str(path))


@action(
    name="write_file",
    description="Write data to a file. If you need to execute a Python script, make sure to use write_file ability at first to create the Python script.",
    parameters=[
        {
            "name": "file_path",
            "description": "Path to the file",
            "type": "string",
            "required": True,
        },
        {
            "name": "data",
            "description": "Data to write to the file.",
            "type": "string",
            "required": True,
        },
    ],
    output_type="None",
)
async def write_file(agent, task_id: str, file_path: str, data: str):
    """
    Write data to a file
    """
    # data = base64.b64decode(data).decode('utf-8')

    if isinstance(data, str):
        data = data.replace('\\n', '\n')
        data = data.encode()

    agent.workspace.write(task_id=task_id, path=file_path, data=data)
    return await agent.db.create_artifact(
        task_id=task_id,
        file_name=file_path.split("/")[-1],
        relative_path=file_path,
        agent_created=True,
    )


@action(
    name="read_file",
    description="Read data from a file",
    parameters=[
        {
            "name": "file_path",
            "description": "Path to the file",
            "type": "string",
            "required": True,
        },
    ],
    output_type="bytes",
)
async def read_file(agent, task_id: str, file_path: str) -> bytes:
    """
    Read data from a file
    """
    return agent.workspace.read(task_id=task_id, path=file_path)
