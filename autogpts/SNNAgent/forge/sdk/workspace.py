import abc
import json
import os
import subprocess
import typing
from pathlib import Path

from google.cloud import storage


class Workspace(abc.ABC):
    @abc.abstractclassmethod
    def __init__(self, base_path: str) -> None:
        self.base_path = base_path

    @abc.abstractclassmethod
    def read(self, task_id: str, path: str) -> bytes:
        pass

    @abc.abstractclassmethod
    def write(self, task_id: str, path: str, data: bytes) -> None:
        pass

    @abc.abstractclassmethod
    def delete(
        self, task_id: str, path: str, directory: bool = False, recursive: bool = False
    ) -> None:
        pass

    @abc.abstractclassmethod
    def exists(self, task_id: str, path: str) -> bool:
        pass

    @abc.abstractclassmethod
    def list(self, task_id: str, path: str) -> typing.List[str]:
        pass


class LocalWorkspace(Workspace):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()

    def _resolve_path(self, task_id: str, path: str) -> Path:
        path = str(path)
        path = path if not path.startswith("/") else path[1:]
        abs_path = (self.base_path / task_id / path).resolve()
        if not str(abs_path).startswith(str(self.base_path)):
            print("Error")
            raise ValueError(f"Directory traversal is not allowed! - {abs_path}")
        try:
            abs_path.parent.mkdir(parents=True, exist_ok=True)
        except FileExistsError:
            pass
        return abs_path

    def read(self, task_id: str, path: str) -> bytes:
        with open(self._resolve_path(task_id, path), "rb") as f:
            return f.read()

    def write(self, task_id: str, path: str, data: bytes) -> None:
        file_path = self._resolve_path(task_id, path)
        with open(file_path, "wb") as f:
            f.write(data)

    def delete(
        self, task_id: str, path: str, directory: bool = False, recursive: bool = False
    ) -> None:
        path = self.base_path / task_id / path
        resolved_path = self._resolve_path(task_id, path)
        if directory:
            if recursive:
                os.rmdir(resolved_path)
            else:
                os.removedirs(resolved_path)
        else:
            os.remove(resolved_path)

    def exists(self, task_id: str, path: str) -> bool:
        path = self.base_path / task_id / path
        return self._resolve_path(task_id, path).exists()

    def list(self, task_id: str, path: str) -> typing.List[str]:
        # path = self.base_path / task_id / path
        base = self._resolve_path(task_id, path)
        print("DEBUG LIST PATH: " + str(base))
        if not base.exists() or not base.is_dir():
            return []
        return [str(p.relative_to(self.base_path / task_id)) for p in base.iterdir()]

    def execute_python_code(self, task_id: str, script: str, data: str = '', **kwargs):
        """
        Executes Python code, either from a file path or a script as a string.
        Optional parameters can be passed to the executable Python code.

        Parameters:
        - input_data: A string that is either a file path to a Python script or a Python script itself.
        - kwargs: Optional parameters to pass to the Python script.

        Returns:
        - output: The output from executing the Python code.
        - error: Any error that occurred during execution.

        # Example of executing a Python file, assuming there's a file named example.py
        # output, error = execute_python_code('example.py', arg1='value1', arg2='value2')
        # print("Output:", output)
        # print("Error:", error)
        """
        file_path = self._resolve_path(task_id, script) if script not in ['pytest'] else None

        output, error = None, None

        # Prepare optional parameters as a string
        params = ' '.join([f'--{key} {value}' for key, value in kwargs.items()])

        # Check if input_data is a file path
        if (file_path is not None and os.path.isfile(file_path)) or script == 'pytest':
            try:
                if data is None or data == '':
                    # Execute the Python file as a subprocess
                    if script == 'pytest':
                        result = subprocess.run(['pytest'], capture_output=True, text=True, check=True, cwd=(self.base_path / task_id).resolve())
                    else:
                        result = subprocess.run(['python', file_path] + params.split(), capture_output=True, text=True, check=True, cwd=(self.base_path / task_id).resolve())
                    output = result.stdout
                else:
                    process = subprocess.Popen(
                        ['python', file_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        cwd=(self.base_path / task_id).resolve()
                    )
                    parsed_data = None
                    try:
                        parsed_data = json.loads(data)
                        if not isinstance(parsed_data, list):
                            parsed_data = None
                    except ValueError:
                        parsed_data = None

                    output, error = process.communicate('\n'.join(parsed_data) if parsed_data else None)

            except subprocess.CalledProcessError as e:
                error = e.stderr
            except FileNotFoundError as error:
                errorMessage = error.strerror
                return f"ERROR: Could not find script at {file_path}, {errorMessage}"
        else:
            output = "Error"
            error = f"File {script} is not found!"
            """
            # Assume input_data is a Python script
            try:
                # Prepare a local context to capture output
                local_context = {"__name__": "__main__"}
                exec(script, local_context)
                output = "Script executed successfully. Check script for output mechanisms."
            except Exception as e:
                error = str(e)
            """

        return output, error


class GCSWorkspace(Workspace):
    def __init__(self, bucket_name: str, base_path: str = ""):
        self.bucket_name = bucket_name
        self.base_path = Path(base_path).resolve() if base_path else ""
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.get_bucket(self.bucket_name)

    def _resolve_path(self, task_id: str, path: str) -> Path:
        path = str(path)
        path = path if not path.startswith("/") else path[1:]
        abs_path = (self.base_path / task_id / path).resolve()
        if not str(abs_path).startswith(str(self.base_path)):
            print("Error")
            raise ValueError(f"Directory traversal is not allowed! - {abs_path}")
        return abs_path

    def read(self, task_id: str, path: str) -> bytes:
        blob = self.bucket.blob(self._resolve_path(task_id, path))
        if not blob.exists():
            raise FileNotFoundError()
        return blob.download_as_bytes()

    def write(self, task_id: str, path: str, data: bytes) -> None:
        blob = self.bucket.blob(self._resolve_path(task_id, path))
        blob.upload_from_string(data)

    def delete(self, task_id: str, path: str, directory=False, recursive=False):
        if directory and not recursive:
            raise ValueError("recursive must be True when deleting a directory")
        blob = self.bucket.blob(self._resolve_path(task_id, path))
        if not blob.exists():
            return
        if directory:
            for b in list(self.bucket.list_blobs(prefix=blob.name)):
                b.delete()
        else:
            blob.delete()

    def exists(self, task_id: str, path: str) -> bool:
        blob = self.bucket.blob(self._resolve_path(task_id, path))
        return blob.exists()

    def list(self, task_id: str, path: str) -> typing.List[str]:
        prefix = os.path.join(task_id, self.base_path, path).replace("\\", "/") + "/"
        print("DEBUG LIST GCS PATH: " + prefix)
        blobs = list(self.bucket.list_blobs(prefix=prefix))
        return [str(Path(b.name).relative_to(prefix[:-1])) for b in blobs]
