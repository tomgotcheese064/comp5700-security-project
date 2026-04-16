from pathlib import Path
from typing import Dict, Tuple, Set, List
import yaml


def _normalize_text(text: str) -> str:
    return " ".join(str(text).strip().split())


def _yaml_to_name_requirements_map(yaml_data: Dict) -> Dict[str, Set[str]]:
    """
    Convert YAML like:
    element1:
      name: Logging
      requirements:
        - 2.1 Logging
    into:
    {
        "Logging": {"2.1 Logging"}
    }
    """
    result: Dict[str, Set[str]] = {}

    for _, value in yaml_data.items():
        if not isinstance(value, dict):
            continue

        name = _normalize_text(value.get("name", ""))
        requirements = value.get("requirements", [])

        if not name:
            continue

        if isinstance(requirements, str):
            requirements = [requirements]

        cleaned_requirements = {
            _normalize_text(req) for req in requirements if _normalize_text(req)
        }

        result[name] = cleaned_requirements

    return result


def load_yaml_files(yaml_file_1: str, yaml_file_2: str) -> Tuple[Dict, Dict]:
    """
    Task-2 Function 1:
    Automatically takes the two YAML files as input from Task-1.
    """
    path1 = Path(yaml_file_1)
    path2 = Path(yaml_file_2)

    if not path1.exists():
        raise FileNotFoundError(f"File not found: {yaml_file_1}")
    if not path2.exists():
        raise FileNotFoundError(f"File not found: {yaml_file_2}")

    if path1.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError(f"Not a YAML file: {yaml_file_1}")
    if path2.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError(f"Not a YAML file: {yaml_file_2}")

    with open(path1, "r", encoding="utf-8") as f:
        data1 = yaml.safe_load(f) or {}

    with open(path2, "r", encoding="utf-8") as f:
        data2 = yaml.safe_load(f) or {}

    if not isinstance(data1, dict):
        raise ValueError(f"Invalid YAML structure in: {yaml_file_1}")
    if not isinstance(data2, dict):
        raise ValueError(f"Invalid YAML structure in: {yaml_file_2}")

    return data1, data2


def compare_element_names(
    yaml_file_1: str,
    yaml_file_2: str,
    output_dir: str = "output_text"
) -> str:
    """
    Task-2 Function 2:
    Identify differences in the two YAML files with respect to names of key data elements.
    Output is a TEXT file.
    """
    data1, data2 = load_yaml_files(yaml_file_1, yaml_file_2)

    map1 = _yaml_to_name_requirements_map(data1)
    map2 = _yaml_to_name_requirements_map(data2)

    names1 = set(map1.keys())
    names2 = set(map2.keys())

    only_in_1 = sorted(names1 - names2)
    only_in_2 = sorted(names2 - names1)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    file1_name = Path(yaml_file_1).name
    file2_name = Path(yaml_file_2).name
    output_file = output_path / f"{Path(yaml_file_1).stem}-vs-{Path(yaml_file_2).stem}-element-name-differences.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        if not only_in_1 and not only_in_2:
            f.write("NO DIFFERENCES IN REGARDS TO ELEMENT NAMES")
        else:
            for name in only_in_1:
                f.write(f"{name},ABSENT-IN-{file2_name},PRESENT-IN-{file1_name}\n")
            for name in only_in_2:
                f.write(f"{name},ABSENT-IN-{file1_name},PRESENT-IN-{file2_name}\n")

    return str(output_file)


def compare_element_and_requirement_differences(
    yaml_file_1: str,
    yaml_file_2: str,
    output_dir: str = "output_text"
) -> str:
    """
    Task-2 Function 3:
    Identify differences in:
      (i) names of key data elements
      (ii) requirements for the key data elements

    Output tuple format:
    NAME,ABSENT-IN-<FILENAME>,PRESENT-IN-<FILENAME>,NA
    NAME,ABSENT-IN-<FILENAME>,PRESENT-IN-<FILENAME>,REQ1
    """
    data1, data2 = load_yaml_files(yaml_file_1, yaml_file_2)

    map1 = _yaml_to_name_requirements_map(data1)
    map2 = _yaml_to_name_requirements_map(data2)

    names1 = set(map1.keys())
    names2 = set(map2.keys())

    file1_name = Path(yaml_file_1).name
    file2_name = Path(yaml_file_2).name

    lines: List[str] = []

    for name in sorted(names1 - names2):
        lines.append(f"{name},ABSENT-IN-{file2_name},PRESENT-IN-{file1_name},NA")

    for name in sorted(names2 - names1):
        lines.append(f"{name},ABSENT-IN-{file1_name},PRESENT-IN-{file2_name},NA")

    for name in sorted(names1 & names2):
        reqs1 = map1[name]
        reqs2 = map2[name]

        missing_from_2 = sorted(reqs1 - reqs2)
        missing_from_1 = sorted(reqs2 - reqs1)

        for req in missing_from_2:
            lines.append(f"{name},ABSENT-IN-{file2_name},PRESENT-IN-{file1_name},{req}")

        for req in missing_from_1:
            lines.append(f"{name},ABSENT-IN-{file1_name},PRESENT-IN-{file2_name},{req}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    output_file = output_path / f"{Path(yaml_file_1).stem}-vs-{Path(yaml_file_2).stem}-element-requirement-differences.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        if not lines:
            f.write("NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS")
        else:
            for line in lines:
                f.write(line + "\n")

    return str(output_file)


def main():
    yaml_file_1 = "output_yaml/cis-r1-chain-of-thought-kdes.yaml"
    yaml_file_2 = "output_yaml/cis-r2-chain-of-thought-kdes.yaml"

    name_diff_file = compare_element_names(yaml_file_1, yaml_file_2)
    req_diff_file = compare_element_and_requirement_differences(yaml_file_1, yaml_file_2)

    print(f"Element name differences saved to: {name_diff_file}")
    print(f"Element/requirement differences saved to: {req_diff_file}")


if __name__ == "__main__":
    main()