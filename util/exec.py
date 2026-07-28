#    Copyright 2020 June Hanabi
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from subprocess import run, CompletedProcess, TimeoutExpired
import os.path, traceback
from typing import List, Tuple, Union
from util.path import get_sys_path, get_sys_scripts_folder, get_full_filepath

from settings import decompiler_timeout


def _command_for_file(file_path: str, args: List[str]) -> List[str]:
    extension = os.path.splitext(file_path)[1].lower()
    if os.name == "nt" and extension in ("", ".py", ".pyw"):
        return [get_sys_path(), file_path, *args]
    return [file_path, *args]


def exec_cli(package: str, args: List[str], **kwargs) -> Tuple[bool, Union[CompletedProcess, TimeoutExpired, None]]:
    """
    Executes the cli version of an installed python package

    :param package: Package name to execute
    :param args: Arguments to provide to the package
    :return: Returns tuple of (boolean indicating success, the CompletedProcess object)
    """
    if os.path.isfile(package):
        cmd_list = _command_for_file(package, args)
    elif package == "python3":
        cmd_list = [get_sys_path(), *args]
    else:
        scripts_folder = get_sys_scripts_folder()
        script_path = os.path.join(scripts_folder, package)
        if not os.path.isfile(script_path):
            try:
                script_path = get_full_filepath(scripts_folder, package)
            except FileNotFoundError:
                script_path = None
        if script_path:
            cmd_list = _command_for_file(script_path, args)
        else:
            cmd_list = [get_sys_path(), "-m", package, *args]
    try:
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("timeout", decompiler_timeout)
        result = run(cmd_list, text=True, encoding="utf-8", **kwargs)
    except TimeoutExpired as e:
        return False, e
    except Exception:
        traceback.print_exc()
        if len(cmd_list) > 2:
            print(f"run was [{cmd_list[0]}, -m {args}]")
        else:
            print(f"run was [{cmd_list[0]}, {args}]")
        return False, None
    return (not result.stderr) and (result.returncode == 0), result
