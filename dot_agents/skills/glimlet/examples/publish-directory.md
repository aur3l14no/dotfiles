# Publish A Local Artifact

The directory must contain `index.html`.

```bash
python3 scripts/glimlet.py publish ./artifact-dir --title "Demo" --ttl 7d --json
```

The CLI writes `./artifact-dir/.glimlet_id` after a successful publish.
