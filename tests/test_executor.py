from pathlib import Path
import json
import sys
import zipfile

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from executor import (
    load_task2_text_files,
    determine_mapped_controls,
    run_kubescape_scan,
    save_scan_results_to_csv,
)


def test_load_task2_text_files_reads_two_files(tmp_path):
    file1 = tmp_path / "name_diff.txt"
    file2 = tmp_path / "req_diff.txt"

    file1.write_text("NO DIFFERENCES IN REGARDS TO ELEMENT NAMES", encoding="utf-8")
    file2.write_text("NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS", encoding="utf-8")

    name_content, req_content = load_task2_text_files(str(file1), str(file2))

    assert name_content == "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES"
    assert req_content == "NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS"


def test_determine_mapped_controls_writes_no_differences_found(tmp_path):
    file1 = tmp_path / "name_diff.txt"
    file2 = tmp_path / "req_diff.txt"
    output_file = tmp_path / "controls.txt"

    file1.write_text("NO DIFFERENCES IN REGARDS TO ELEMENT NAMES", encoding="utf-8")
    file2.write_text("NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS", encoding="utf-8")

    result_path = determine_mapped_controls(str(file1), str(file2), str(output_file))
    content = Path(result_path).read_text(encoding="utf-8")

    assert content == "NO DIFFERENCES FOUND"


def test_run_kubescape_scan_returns_dataframe(monkeypatch, tmp_path):
    controls_file = tmp_path / "controls.txt"
    controls_file.write_text("C-0173", encoding="utf-8")

    zip_file = tmp_path / "project-yamls.zip"
    sample_yaml = tmp_path / "deployment.yaml"
    sample_yaml.write_text("apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\n", encoding="utf-8")

    with zipfile.ZipFile(zip_file, "w") as zip_ref:
        zip_ref.write(sample_yaml, arcname="deployment.yaml")

    def fake_run(cmd, capture_output, text):
        output_index = cmd.index("--output") + 1
        output_json_path = Path(cmd[output_index])

        fake_json = {
            "results": [
                {
                    "controlName": "C-0173",
                    "severity": "Medium",
                    "failedResources": ["res1"],
                    "allResources": ["res1", "res2"],
                    "complianceScore": 50,
                    "filePath": "deployment.yaml",
                }
            ]
        }
        output_json_path.write_text(json.dumps(fake_json), encoding="utf-8")

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    monkeypatch.setattr("executor.subprocess.run", fake_run)

    df = run_kubescape_scan(str(controls_file), str(zip_file))

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == [
        "FilePath",
        "Severity",
        "Control name",
        "Failed resources",
        "All Resources",
        "Compliance score",
    ]
    assert len(df) == 1
    assert df.iloc[0]["Control name"] == "C-0173"


def test_save_scan_results_to_csv_creates_file_with_required_headers(tmp_path):
    df = pd.DataFrame(
        [
            {
                "FilePath": "deployment.yaml",
                "Severity": "Medium",
                "Control name": "C-0173",
                "Failed resources": 1,
                "All Resources": 2,
                "Compliance score": 50,
            }
        ]
    )

    output_csv = tmp_path / "scan_results.csv"
    csv_path = save_scan_results_to_csv(df, str(output_csv))

    saved_df = pd.read_csv(csv_path)

    assert Path(csv_path).exists()
    assert list(saved_df.columns) == [
        "FilePath",
        "Severity",
        "Control name",
        "Failed resources",
        "All Resources",
        "Compliance score",
    ]
    assert saved_df.iloc[0]["Control name"] == "C-0173"