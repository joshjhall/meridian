"""Pydantic models and demo/web/src/types.ts must agree field for field."""

import re
from enum import StrEnum
from pathlib import Path

import pytest
from pydantic import BaseModel

import models

TYPES_TS = Path(__file__).resolve().parents[2] / "web" / "src" / "types.ts"
SOURCE = TYPES_TS.read_text()

MODELS = {
    name: obj
    for name, obj in vars(models).items()
    if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel
}
ENUMS = {
    name: obj
    for name, obj in vars(models).items()
    if isinstance(obj, type) and issubclass(obj, StrEnum) and obj is not StrEnum
}


def ts_block(kind: str, name: str) -> str:
    match = re.search(rf"export {kind} {name} \{{(.*?)\n\}}", SOURCE, re.S)
    assert match, f"{kind} {name} missing from types.ts"
    return match.group(1)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_interface_fields_match(name):
    model = MODELS[name]
    py_fields = set(model.model_fields) | set(model.model_computed_fields)
    ts_fields = set(re.findall(r"^\s+(\w+)\??:", ts_block("interface", name), re.M))
    assert ts_fields == py_fields


@pytest.mark.parametrize("name", sorted(ENUMS))
def test_enum_values_match(name):
    ts_values = set(re.findall(r'=\s*"([^"]+)"', ts_block("enum", name)))
    assert ts_values == {m.value for m in ENUMS[name]}
