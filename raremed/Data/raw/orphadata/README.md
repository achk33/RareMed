# Orphadata

Put official Orphadata XML exports in this directory or a subdirectory. Version 0.4 inspects the actual schema and extracts:

- `product1` — disorders, synonyms, and external references
- `product4` — HPO associations with frequency
- `product3` — classification membership when an Orpha classification id is present
- `product6` — gene associations when the official tags are present
- `product7` — disorder-disorder associations when the official tags are present

Archives are not extracted. A folder whose name ends in `.zip` is walked like any other directory. Raw XML is never overwritten.
