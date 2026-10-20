# Qt Designer forms

Files in this directory are the editable UI sources. Open them with
`pyside6-designer`, then regenerate their Python modules from the project root:

```bash
python scripts/generate_ui.py
```

Do not add application or hardware logic to a `.ui` file.
