# Development

Regenerate and verify both public marketplace layouts after changing `payload-src/`:

```sh
uv run python scripts/sync_public_marketplace.py
uv run python scripts/sync_public_marketplace.py --check
```

Build and verify an immutable release artifact:

```sh
uv run python scripts/build_release.py --output /path/to/release --mcp-url https://black-vector.com/sensai/mcp
uv run python scripts/verify_release.py --bundle /path/to/release
```
