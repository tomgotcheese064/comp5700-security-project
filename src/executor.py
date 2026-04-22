from __future__ import annotations

import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


OUTPUT_TEXT_DIR = Path("output_text")
OUTPUT_CSV_DIR = Path("output_csv")

CSV_COLUMNS = [
    "FilePath",
    "Severity",
    "Control name",
    "Failed resources",
    "All Resources",
    "Compliance score",
]

CONTROL_KEYWORD_MAPPING: Dict[str, List[str]] = {
    "audit logs": ["C-0130"],
    "enable audit logs": ["C-0130"],
    "client ca file": ["C-0174"],
    "anonymous auth": ["C-0172"],
    "authorization-mode": ["C-0173"],
    "read-only-port": ["C-0175"],
    "streaming-connection-idle-timeout": ["C-0176"],
    "eventrecordqps": ["C-0180"],
    "event-qps": ["C-0180"],
    "rotate-certificates": ["C-0182"],
    "rotatekubeletservercertificate": ["C-0183"],
    "service account tokens": ["C-0190"],
    "cluster-admin role": ["C-0185"],
    "access to secrets": ["C-0186"],
    "wildcard use": ["C-0187"],
    "create pods": ["C-0188"],
    "default service accounts": ["C-0189"],
    "kubeconfig file permissions": ["C-0238"],
    "kubelet kubeconfig file ownership": ["C-0167"],
    "kubelet configuration file permissions": ["C-0170"],
    "kubelet configuration file ownership": ["C-0171"],
}


def _read_text_file(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if path.suffix.lower() != ".txt":
        raise ValueError(f"Not a TEXT file: {file_path}")
    return path.read_text(encoding="utf-8").strip()


def _write_text_file(file_path: str | Path, content: str) -> str:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _is_no_difference_text(content: str) -> bool:
    normalized = content.strip()
    return normalized in {
        "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES",
        "NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS",
        "NO DIFFERENCES FOUND",
    }


def _extract_controls_from_text(content: str) -> List[str]:
    lowered = content.lower()
    controls: List[str] = []

    for keyword, mapped_controls in CONTROL_KEYWORD_MAPPING.items():
        if keyword in lowered:
            controls.extend(mapped_controls)

    deduped: List[str] = []
    seen = set()
    for control in controls:
        if control not in seen:
            deduped.append(control)
            seen.add(control)

    return deduped


def _safe_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        return len(value)
    return 0


def _coerce_score(value: Any) -> Any:
    if isinstance(value, (int, float, str)):
        return value
    return ""


def _fallback_dataframe(label: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "FilePath": label,
                "Severity": "",
                "Control name": label,
                "Failed resources": 0,
                "All Resources": 0,
                "Compliance score": "",
            }
        ],
        columns=CSV_COLUMNS,
    )


def _collect_candidate_rows(obj: Any, rows: List[Dict[str, Any]], fallback_path: str = "") -> None:
    if isinstance(obj, dict):
        control_name = (
            obj.get("controlName")
            or obj.get("control_name")
            or obj.get("name")
            or obj.get("controlID")
            or obj.get("controlId")
            or ""
        )
        severity = obj.get("severity", "")
        failed_resources = (
            obj.get("failedResources")
            or obj.get("failed_resources")
            or obj.get("failed")
            or []
        )
        all_resources = (
            obj.get("allResources")
            or obj.get("all_resources")
            or obj.get("resources")
            or []
        )
        compliance_score = (
            obj.get("complianceScore")
            or obj.get("compliance_score")
            or obj.get("score")
            or ""
        )
        file_path = (
            obj.get("filePath")
            or obj.get("filepath")
            or obj.get("path")
            or fallback_path
        )

        has_control_signal = bool(control_name)
        has_result_signal = any(
            key in obj
            for key in [
                "failedResources",
                "failed_resources",
                "failed",
                "allResources",
                "all_resources",
                "resources",
                "complianceScore",
                "compliance_score",
                "score",
            ]
        )

        if has_control_signal and has_result_signal:
            rows.append(
                {
                    "FilePath": file_path,
                    "Severity": severity,
                    "Control name": control_name,
                    "Failed resources": _safe_count(failed_resources),
                    "All Resources": _safe_count(all_resources),
                    "Compliance score": _coerce_score(compliance_score),
                }
            )

        for value in obj.values():
            _collect_candidate_rows(value, rows, fallback_path=fallback_path)

    elif isinstance(obj, list):
        for item in obj:
            _collect_candidate_rows(item, rows, fallback_path=fallback_path)


def _parse_kubescape_json(json_path: Path, fallback_label: str) -> pd.DataFrame:
    if not json_path.exists():
        return _fallback_dataframe(fallback_label)

    raw_text = json_path.read_text(encoding="utf-8").strip()

    if not raw_text:
        return _fallback_dataframe(fallback_label)

    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError:
        return _fallback_dataframe(fallback_label)

    rows: List[Dict[str, Any]] = []
    _collect_candidate_rows(raw, rows, fallback_path=fallback_label)

    if not rows:
        return _fallback_dataframe(fallback_label)

    df = pd.DataFrame(rows)
    for column in CSV_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[CSV_COLUMNS]


def load_task2_text_files(
    element_name_diff_file: str,
    element_requirement_diff_file: str,
) -> Tuple[str, str]:
    """
    Task-3 Function 1:
    Automatically takes the two TEXT files as input from Task-2.
    """
    name_content = _read_text_file(element_name_diff_file)
    requirement_content = _read_text_file(element_requirement_diff_file)
    return name_content, requirement_content


def determine_mapped_controls(
    element_name_diff_file: str,
    element_requirement_diff_file: str,
    output_file: str = "output_text/kubescape-controls.txt",
) -> str:
    """
    Task-3 Function 2:
    Determines if there are differences and writes either:
    - NO DIFFERENCES FOUND
    - or mapped Kubescape controls
    """
    name_content, requirement_content = load_task2_text_files(
        element_name_diff_file,
        element_requirement_diff_file,
    )

    no_name_diff = name_content.strip() == "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES"
    no_req_diff = requirement_content.strip() == "NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS"

    if no_name_diff and no_req_diff:
        return _write_text_file(output_file, "NO DIFFERENCES FOUND")

    combined_text = f"{name_content}\n{requirement_content}"
    controls = _extract_controls_from_text(combined_text)

    if not controls:
        controls = sorted({control for values in CONTROL_KEYWORD_MAPPING.values() for control in values})

    return _write_text_file(output_file, "\n".join(controls))


def _run_subprocess_and_parse(cmd: List[str], json_output: Path, fallback_label: str) -> pd.DataFrame:
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode not in (0, 1):
        return _fallback_dataframe(fallback_label)

    return _parse_kubescape_json(json_output, fallback_label)


def run_kubescape_scan(
    controls_file: str,
    zip_file: str = "project-yamls.zip",
) -> pd.DataFrame:
    """
    Task-3 Function 3:
    Executes Kubescape on project-yamls.zip based on the controls file.
    Returns a pandas DataFrame.
    """
    controls_path = Path(controls_file)
    zip_path = Path(zip_file)

    if not controls_path.exists():
        raise FileNotFoundError(f"Controls file not found: {controls_file}")
    if not zip_path.exists():
        raise FileNotFoundError(f"Zip file not found: {zip_file}")

    controls_text = controls_path.read_text(encoding="utf-8").strip()
    selected_controls = [line.strip() for line in controls_text.splitlines() if line.strip()]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        extracted_dir = temp_dir_path / "project_yamls"
        extracted_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extracted_dir)

        frames: List[pd.DataFrame] = []

        if selected_controls == ["NO DIFFERENCES FOUND"]:
            json_output = temp_dir_path / "kubescape_all_controls.json"
            cmd = [
                "kubescape",
                "scan",
                str(extracted_dir),
                "--format",
                "json",
                "--output",
                str(json_output),
            ]
            frames.append(_run_subprocess_and_parse(cmd, json_output, "ALL_CONTROLS"))
        else:
            for control_id in selected_controls:
                json_output = temp_dir_path / f"{control_id}.json"
                cmd = [
                    "kubescape",
                    "scan",
                    "control",
                    control_id,
                    str(extracted_dir),
                    "--format",
                    "json",
                    "--output",
                    str(json_output),
                ]
                frames.append(_run_subprocess_and_parse(cmd, json_output, control_id))

        if not frames:
            return _fallback_dataframe("NO_SCAN_RESULTS")

        combined = pd.concat(frames, ignore_index=True)

        if combined.empty:
            return _fallback_dataframe("NO_SCAN_RESULTS")

        for column in CSV_COLUMNS:
            if column not in combined.columns:
                combined[column] = ""

        return combined[CSV_COLUMNS]


def save_scan_results_to_csv(
    scan_df: pd.DataFrame,
    output_csv: str = "output_csv/kubescape_scan_results.csv",
) -> str:
    """
    Task-3 Function 4:
    Generates a CSV file with the required headers.
    """
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = scan_df.copy()
    for column in CSV_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df = df[CSV_COLUMNS]
    df.to_csv(output_path, index=False)
    return str(output_path)


def main() -> None:
    name_diff_file = "output_text/cis-r1-chain-of-thought-kdes-vs-cis-r2-chain-of-thought-kdes-element-name-differences.txt"
    requirement_diff_file = "output_text/cis-r1-chain-of-thought-kdes-vs-cis-r2-chain-of-thought-kdes-element-requirement-differences.txt"

    controls_file = determine_mapped_controls(name_diff_file, requirement_diff_file)
    scan_df = run_kubescape_scan(controls_file, "project-yamls.zip")
    csv_path = save_scan_results_to_csv(scan_df)

    print(f"Controls file saved to: {controls_file}")
    print(f"CSV saved to: {csv_path}")
    print(scan_df)


if __name__ == "__main__":
    main()