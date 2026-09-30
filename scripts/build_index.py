"""Index deeplinks.json (BM25 is built in memory; dense embeddings are cached under data/index/)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.embed import get_models  # noqa: E402
from app.pipeline.deeplinks import Catalog  # noqa: E402


def main() -> None:
    t0 = time.perf_counter()
    models = get_models().load()
    cat = Catalog(settings.deeplinks_path, models)
    print(f"indexed {len(cat.entries)} deeplinks (+dummy={cat.dummy is not None}) "
          f"dim={cat.emb.shape[1]} in {time.perf_counter() - t0:.1f}s -> {settings.index_dir}")


if __name__ == "__main__":
    main()
