# Scripts

Version 0.1 does not download medical datasets. Place those files in `data/raw/` yourself.

`check_stack.py` calls a running API and prints health plus dependency status:

```powershell
python scripts\check_stack.py
```

The default base URL is `http://localhost:8000`. Override it with `RAREMED_API_URL`.
