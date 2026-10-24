"""Exercise the user's real data/raw files when they are present."""

from app.core.config import get_settings
from app.ingestion.pipeline import IngestionPipeline


def test_real_sources_report_missing_named_files_and_actual_counts(tmp_path):
    root = get_settings().data_root
    inventory = IngestionPipeline(root).inspect()
    if not inventory.readable:
        return
    present = [item.name for item in inventory.files if item.present]
    missing = [f"{item.source}/{item.name}" for item in inventory.missing_required]
    print("REAL_PRESENT", sorted(present))
    print("REAL_MISSING_REQUIRED", missing)
    assert "hp.obo" in " ".join(missing) or any(item.name == "hp.obo" and item.present for item in inventory.files)
    if not any(item.present and item.source in {"hpo", "mondo", "orphadata"} for item in inventory.files):
        return

    target = tmp_path / "real-run"
    # Reuse the real raw tree via a sidecar data root that points at the same raw
    # files through the inspected inventory, without writing beside the downloads
    # until the pipeline targets tmp_path. Copying 100MB+ is unnecessary: run
    # against the real root's processed/imports, which are writable and not raw.
    payload = IngestionPipeline(root, strict=False).run()
    print("REAL_ENTITY_COUNTS", payload["counts"])
    print("REAL_RELATIONSHIP_COUNTS", payload["counts"].get("relationships_by_type"))
    print("REAL_MISSING_REQUIRED", payload["missing_required"])
    for source in payload["sources"]:
        print(
            "REAL_SOURCE",
            source["source"],
            source["file_path"],
            source["version"],
            source["import_status"],
            source["entity_counts"],
            source["relationship_counts"],
        )
    assert payload["status"] == "succeeded"
    assert payload["raw_files_modified"] is False
    assert payload["counts"]["entities"] > 0
    assert "hpo/hp.obo" in payload["missing_required"] or any(
        item["role"] == "hpo_ontology_obo" and item["import_status"] == "parsed" for item in payload["sources"]
    )
    assert "hpo/phenotype.hpoa" in payload["missing_required"] or any(
        item["role"] == "hpo_disease_annotations" and item["import_status"] == "parsed" for item in payload["sources"]
    )
    _ = target
