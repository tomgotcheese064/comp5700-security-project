from pathlib import Path
import sys
import yaml

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from comparator import (
    load_yaml_files,
    compare_element_names,
    compare_element_and_requirement_differences,
)


def test_load_yaml_files_returns_two_dicts(tmp_path):
    yaml_1 = tmp_path / "file1.yaml"
    yaml_2 = tmp_path / "file2.yaml"

    data_1 = {
        "element1": {
            "name": "Logging",
            "requirements": ["2.1 Logging"]
        }
    }
    data_2 = {
        "element1": {
            "name": "Logging",
            "requirements": ["2.1 Logging"]
        }
    }

    yaml_1.write_text(yaml.safe_dump(data_1), encoding="utf-8")
    yaml_2.write_text(yaml.safe_dump(data_2), encoding="utf-8")

    loaded_1, loaded_2 = load_yaml_files(str(yaml_1), str(yaml_2))

    assert isinstance(loaded_1, dict)
    assert isinstance(loaded_2, dict)
    assert "element1" in loaded_1
    assert "element1" in loaded_2


def test_compare_element_names_writes_no_differences_message(tmp_path):
    yaml_1 = tmp_path / "file1.yaml"
    yaml_2 = tmp_path / "file2.yaml"
    output_dir = tmp_path / "out"

    data_1 = {
        "element1": {
            "name": "Logging",
            "requirements": ["2.1 Logging"]
        }
    }
    data_2 = {
        "element1": {
            "name": "Logging",
            "requirements": ["2.1 Logging"]
        }
    }

    yaml_1.write_text(yaml.safe_dump(data_1), encoding="utf-8")
    yaml_2.write_text(yaml.safe_dump(data_2), encoding="utf-8")

    output_file = compare_element_names(str(yaml_1), str(yaml_2), str(output_dir))
    content = Path(output_file).read_text(encoding="utf-8")

    assert content == "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES"


def test_compare_element_and_requirement_differences_writes_tuple_format(tmp_path):
    yaml_1 = tmp_path / "file1.yaml"
    yaml_2 = tmp_path / "file2.yaml"
    output_dir = tmp_path / "out"

    data_1 = {
        "element1": {
            "name": "Logging",
            "requirements": [
                "2.1 Logging",
                "2.1.1 Enable audit logs (Manual)"
            ]
        }
    }
    data_2 = {
        "element1": {
            "name": "Logging",
            "requirements": [
                "2.1 Logging"
            ]
        },
        "element2": {
            "name": "Alerting",
            "requirements": [
                "2.2.1 Configure alerting (Automated)"
            ]
        }
    }

    yaml_1.write_text(yaml.safe_dump(data_1), encoding="utf-8")
    yaml_2.write_text(yaml.safe_dump(data_2), encoding="utf-8")

    output_file = compare_element_and_requirement_differences(
        str(yaml_1),
        str(yaml_2),
        str(output_dir)
    )
    content = Path(output_file).read_text(encoding="utf-8")

    assert "Alerting,ABSENT-IN-file1.yaml,PRESENT-IN-file2.yaml,NA" in content
    assert "Logging,ABSENT-IN-file2.yaml,PRESENT-IN-file1.yaml,2.1.1 Enable audit logs (Manual)" in content