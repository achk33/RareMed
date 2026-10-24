"""Load synthetic UI fixtures.

Only small JSON files under data/samples that declare themselves as synthetic
UI fixtures are read. Raw ontology and literature directories are never opened.
"""

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.schemas.dataset import SampleList, UiFixture

MAX_SAMPLE_BYTES = 65_536


class _FixtureFile(BaseModel):
    kind: str
    synthetic: bool
    id: str = Field(min_length=1, max_length=80)
    locale: str
    text: str = Field(min_length=1, max_length=2000)
    notice: str = Field(min_length=1, max_length=500)


def load_ui_fixtures(root: Path) -> SampleList:
    directory = root / "samples"
    fixtures: list[UiFixture] = []
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            fixture = _read_fixture(path)
            if fixture is not None:
                fixtures.append(fixture)
    return SampleList(
        fixtures=fixtures,
        note=(
            "These fixtures are synthetic interface text. They are not patient "
            "records and they are not a medical dataset."
        ),
    )


def _read_fixture(path: Path) -> UiFixture | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_SAMPLE_BYTES:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        parsed = _FixtureFile.model_validate(payload)
    except ValidationError:
        return None
    if parsed.kind != "ui-fixture" or parsed.synthetic is not True:
        return None
    if parsed.locale not in {"en", "fr", "ar"}:
        return None
    return UiFixture(id=parsed.id, locale=parsed.locale, text=parsed.text, notice=parsed.notice)
