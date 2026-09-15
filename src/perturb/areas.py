from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pathspec
import yaml


@dataclass(frozen=True)
class Area:
    slug: str
    paths: list[str]
    issues_label: str


@dataclass(frozen=True)
class AreaSet:
    areas: list[Area]
    errors: list[str]

    def touches(self, files: Iterable[str]) -> set[str]:
        file_list = list(files)
        result: set[str] = set()
        for area in self.areas:
            spec = pathspec.PathSpec.from_lines("gitignore", area.paths)
            if any(spec.match_file(f) for f in file_list):
                result.add(area.slug)
        return result

    def in_area(
        self,
        labels: Iterable[str] = (),
        plan_areas: Iterable[str] = (),
    ) -> set[str]:
        label_set = set(labels)
        plan_area_set = set(plan_areas)
        result: set[str] = set()
        for area in self.areas:
            if area.issues_label in label_set or area.slug in plan_area_set:
                result.add(area.slug)
        return result


def load_areas(path: Path) -> AreaSet:
    if not path.exists():
        return AreaSet([], [])
    doc = yaml.safe_load(path.read_text())
    if not isinstance(doc, dict) or not isinstance(doc.get("areas"), dict):
        return AreaSet([], ["areas.yaml: expected a dict with an 'areas' dict"])
    areas_map: dict = doc["areas"]
    areas: list[Area] = []
    errors: list[str] = []
    for slug, entry in areas_map.items():
        if not isinstance(entry, dict) or "paths" not in entry:
            errors.append(f"area '{slug}': missing 'paths' key, skipped")
            continue
        issues_label = entry.get("issues_label") or f"area:{slug}"
        areas.append(Area(slug=slug, paths=list(entry["paths"]), issues_label=issues_label))
    return AreaSet(areas=areas, errors=errors)


def read_plan_areas(text: str) -> list[str]:
    parts = text.split("---", 2)
    if len(parts) < 3:
        return []
    fm = yaml.safe_load(parts[1])
    if not isinstance(fm, dict):
        return []
    areas = fm.get("areas")
    return areas if isinstance(areas, list) else []
