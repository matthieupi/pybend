# N3TX API Documentation

> Stale generated snapshot. These files include removed join models and incorrect
> schema endpoint labels. They are retained for provenance, not current API use.
> Read the [API index](../API_INDEX.md) and query the running app's class schema.

## Generator And Status

The matching generator is
[`generate_docs.py`](../../packages/n3tx-core/src/n3tx_core/utils/generate_docs.py).
It reads the process-local `registered_models`, writes to `Path("docs")` relative
to the working directory, and labels registry names as schema endpoints. It does
not record a source revision or registration manifest. The exact invocation that
produced this directory is unknown; freshness and reproducibility are unproven.
Do not run it from the repository root: its output can overwrite maintained docs.
Regeneration requires an isolated destination, explicit models and a generator
contract review in a separate authorized change. It was not run in this pass.

## Preserved Snapshots

- [comments_comments](./comments_comments.md) (legacy generated relationship)

- [products](./products.md)
- [users](./users.md)
- [products_comments](./products_comments.md)
- [comments_likes](./comments_likes.md)
- [products_likes](./products_likes.md)
