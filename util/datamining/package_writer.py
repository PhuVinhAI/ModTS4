"""Create Sims 4 packages through LlamaLogic.Packages."""

import json
import os
import shutil
import subprocess
import tempfile
from typing import Iterable, NamedTuple


LLAMALOGIC_PACKAGES_VERSION = "3.8.2"

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_TOOL_PROJECT = os.path.join(
    _PROJECT_ROOT, "tools", "Ts4PackageTool", "Ts4PackageTool.csproj"
)
_TOOL_DLL = os.path.join(
    _PROJECT_ROOT,
    "tools",
    "Ts4PackageTool",
    "bin",
    "Release",
    "net8.0",
    "Ts4PackageTool.dll",
)


class PackageResource(NamedTuple):
    type_id: int
    group: int
    instance: int
    data: bytes


def _resource_key(resource):
    return resource.type_id, resource.group, resource.instance


def _validated_resources(resources):
    # type: (Iterable[PackageResource]) -> list
    ordered = sorted(resources, key=_resource_key)
    seen = set()
    validated = []
    for resource in ordered:
        key = _resource_key(resource)
        if key in seen:
            raise ValueError(
                "Duplicate resource key: {:08X}!{:08X}!{:016X}".format(*key)
            )
        if not 0 <= resource.type_id <= 0xFFFFFFFF:
            raise ValueError("Resource type is outside uint32: {}".format(resource.type_id))
        if not 0 <= resource.group <= 0xFFFFFFFF:
            raise ValueError("Resource group is outside uint32: {}".format(resource.group))
        if not 0 <= resource.instance <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError(
                "Resource instance is outside uint64: {}".format(resource.instance)
            )
        seen.add(key)
        validated.append(
            PackageResource(
                resource.type_id,
                resource.group,
                resource.instance,
                bytes(resource.data),
            )
        )
    return validated


def _tool_sources():
    tool_directory = os.path.dirname(_TOOL_PROJECT)
    return [
        os.path.join(tool_directory, name)
        for name in ("Ts4PackageTool.csproj", "Program.cs", "packages.lock.json")
        if os.path.exists(os.path.join(tool_directory, name))
    ]


def _tool_needs_build():
    if not os.path.isfile(_TOOL_DLL):
        return True
    dll_mtime = os.path.getmtime(_TOOL_DLL)
    return any(os.path.getmtime(path) > dll_mtime for path in _tool_sources())


def _run_process(command, action):
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Cannot {} because the .NET SDK is not installed or dotnet is not on PATH.".format(
                action
            )
        )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        raise RuntimeError("Failed to {}: {}".format(action, details or "unknown error"))
    return completed.stdout.strip()


def _ensure_tool():
    if not _tool_needs_build():
        return
    _run_process(
        [
            "dotnet",
            "restore",
            _TOOL_PROJECT,
            "--locked-mode",
            "--nologo",
        ],
        "restore Ts4PackageTool dependencies",
    )
    _run_process(
        [
            "dotnet",
            "build",
            _TOOL_PROJECT,
            "--configuration",
            "Release",
            "--no-restore",
            "--nologo",
            "--verbosity",
            "quiet",
        ],
        "build Ts4PackageTool",
    )


def _run_tool(*arguments):
    _ensure_tool()
    return _run_process(
        ["dotnet", _TOOL_DLL] + list(arguments),
        "run Ts4PackageTool",
    )


def package_tool_version():
    """Return the LlamaLogic.Packages version loaded by the .NET tool."""
    return _run_tool("version")


def write_package(resources, output_path):
    # type: (Iterable[PackageResource], str) -> str
    """Write resources to a DBPF package using LlamaLogic.Packages."""
    ordered = _validated_resources(resources)
    output_path = os.path.abspath(output_path)
    output_directory = os.path.dirname(output_path)
    if output_directory:
        os.makedirs(output_directory, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ts4-package-") as temp_directory:
        manifest_resources = []
        for index, resource in enumerate(ordered):
            payload_name = "resource-{:05d}.bin".format(index)
            payload_path = os.path.join(temp_directory, payload_name)
            with open(payload_path, "wb") as payload_file:
                payload_file.write(resource.data)
            manifest_resources.append(
                {
                    "type": "{:08X}".format(resource.type_id),
                    "group": "{:08X}".format(resource.group),
                    "instance": "{:016X}".format(resource.instance),
                    "path": payload_name,
                    "compression": "off",
                }
            )

        manifest_path = os.path.join(temp_directory, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as manifest_file:
            json.dump({"resources": manifest_resources}, manifest_file, indent=2)

        temporary_output = os.path.join(temp_directory, "output.package")
        _run_tool("create", manifest_path, temporary_output)
        shutil.copyfile(temporary_output, output_path)
    return output_path


def build_package(resources):
    # type: (Iterable[PackageResource]) -> bytes
    """Build package bytes using LlamaLogic.Packages (compatibility API)."""
    with tempfile.TemporaryDirectory(prefix="ts4-package-bytes-") as temp_directory:
        output_path = os.path.join(temp_directory, "output.package")
        write_package(resources, output_path)
        with open(output_path, "rb") as package_file:
            return package_file.read()
