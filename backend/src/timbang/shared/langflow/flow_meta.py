"""Langflow flow metadata + tweaks builder.

Reads node IDs from langflow/*.json so the caller never hardcodes them.
build_tweaks() returns a unique session_id and a tweaks dict that:
  - injects session_id + should_store_message=False into every ChatInput
    and ChatOutput node (prevents Langflow from reusing history across
    requests — root cause of the "vendor A output for file B" bug)
  - optionally injects file_path into File nodes
  - optionally injects input_value into ChatInput nodes
"""

from __future__ import annotations

import json
import uuid
from functools import cache
from pathlib import Path
from typing import Any

# backend/src/timbang/shared/langflow/flow_meta.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[5]
LANGFLOW_DIR = REPO_ROOT / "langflow"


@cache
def get_flow_node_ids(flow_file: str) -> dict[str, list[str]]:
    """Return {'chat_input': [...], 'chat_output': [...], 'files': [...]}."""
    flow_path = LANGFLOW_DIR / flow_file
    if not flow_path.exists():
        raise FileNotFoundError(f"Flow file not found: {flow_path}")

    with flow_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    chat_input_ids: list[str] = []
    chat_output_ids: list[str] = []
    file_ids: list[str] = []

    for node in data.get("data", {}).get("nodes", []):
        nd = node.get("data", {})
        node_type = nd.get("type", "")
        node_id = node.get("id", "")
        if node_type == "ChatInput":
            chat_input_ids.append(node_id)
        elif node_type == "ChatOutput":
            chat_output_ids.append(node_id)
        elif node_type == "File":
            file_ids.append(node_id)

    return {
        "chat_input": chat_input_ids,
        "chat_output": chat_output_ids,
        "files": file_ids,
    }


def build_tweaks(
    flow_file: str,
    *,
    input_value: str | None = None,
    file_paths: dict[str, str] | None = None,
) -> tuple[str, dict[str, dict[str, Any]]]:
    """Build (session_id, tweaks) for a Langflow run request."""
    node_ids = get_flow_node_ids(flow_file)
    session_id = str(uuid.uuid4())
    tweaks: dict[str, dict[str, Any]] = {}

    for nid in node_ids["chat_input"]:
        tweak: dict[str, Any] = {
            "session_id": session_id,
            "should_store_message": False,
        }
        if input_value is not None:
            tweak["input_value"] = input_value
        tweaks[nid] = tweak

    for nid in node_ids["chat_output"]:
        tweaks[nid] = {
            "session_id": session_id,
            "should_store_message": False,
        }

    if file_paths:
        for nid, path in file_paths.items():
            # Langflow 1.12 FileComponent reads "path" (Files, FileInput).
            # Value must be a list. Path MUST be relative to the Langflow
            # storage dir (format "flow_id/timestamp_filename" from the
            # /api/v1/files/upload response), NOT absolute.
            tweaks[nid] = {"path": [str(path)]}

    return session_id, tweaks
