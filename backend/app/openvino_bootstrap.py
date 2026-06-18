from __future__ import annotations

import importlib.util
import os
from pathlib import Path

_OPENVINO_DLL_HANDLES: list[object] = []


def configure_openvino_environment() -> None:
    if os.name != "nt":
        return

    spec = importlib.util.find_spec("openvino")
    if spec is None or spec.origin is None:
        return

    openvino_libs = Path(spec.origin).resolve().parent / "libs"
    if not openvino_libs.exists():
        return

    openvino_libs_str = str(openvino_libs)
    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(os.pathsep) if current_path else []
    if openvino_libs_str not in path_parts:
        os.environ["PATH"] = openvino_libs_str + (os.pathsep + current_path if current_path else "")

    try:
        _OPENVINO_DLL_HANDLES.append(os.add_dll_directory(openvino_libs_str))
    except (AttributeError, OSError):
        return
