# Synthetic samples

This directory holds small, non-identifiable interface fixtures. It is not a medical dataset and it must not be used as a substitute for HPO, Orphanet, Mondo, or literature.

A fixture is loaded only when it is a JSON file under 64 KB and contains:

```json
{
  "kind": "ui-fixture",
  "synthetic": true,
  "id": "short-id",
  "locale": "en",
  "text": "Interface text with no real person and no clinical claim.",
  "notice": "Why this file is synthetic."
}
```

`locale` is `en`, `fr`, or `ar`.
