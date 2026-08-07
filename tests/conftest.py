from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures import write_fixture_ontology, write_sample_files  # noqa: E402
from pipeline.mapper import Lexicon, load_lexicon  # noqa: E402


@pytest.fixture(scope="session")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """fixture 사전 + 테스트 엑셀 3개를 갖춘 임시 프로젝트 루트."""
    root = tmp_path_factory.mktemp("wq_project")
    write_fixture_ontology(root / "ontology")
    write_sample_files(root / "data" / "samples")
    return root


@pytest.fixture(scope="session")
def lexicon(project: Path) -> Lexicon:
    return load_lexicon(
        project / "ontology" / "measurement_terms.csv",
        project / "ontology" / "metadata_terms.csv",
    )
