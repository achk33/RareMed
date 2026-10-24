# Human Phenotype Ontology

Put manually downloaded HPO files in this directory. Version 0.4 looks for:

- `hp.obo` (required name; absence is reported)
- `phenotype.hpoa` (required name; absence is reported)
- `hp.json`
- `hp.owl`

If `hp.obo` is missing, `hp.json` is parsed instead. If `phenotype.hpoa` is missing, disease-phenotype rows are not invented; Orphadata product 4 can still supply associations.

The original files are never overwritten.
