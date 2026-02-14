# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **UUID columns**: Use `UUID(as_uuid=False)` with `Mapped[str]`, `default=lambda: str(uuid4())`, `server_default=text("gen_random_uuid()")`.
- **Timestamps**: `DateTime(timezone=True)` with `default=lambda: datetime.now(UTC)`, `server_default=text("now()")`. `updated_at` adds `onupdate=lambda: datetime.now(UTC)`.
- **Enum status fields**: Define `str, Enum` classes, use `.value` for `default=`, wrap in `text("'...'")` for `server_default=`.
- **Relationships**: Use `TYPE_CHECKING` guard for forward refs. Both sides need `back_populates`. Parent side uses `cascade="all, delete-orphan"`. For 1:1, use `unique=True` on FK column + `uselist=False` on the reverse relationship.
- **Models registration**: Import in `backend/app/models/__init__.py` and add to `__all__`.
- **Alembic merge migrations**: When multiple migrations share the same `down_revision` (forked heads), set `down_revision = ("rev_a", "rev_b")` on the new migration to merge them into a single head. Downgrade with explicit target revision, not `-1`.

---

## 2026-02-14 - S11-001
- Implemented BlogCampaign and BlogPost SQLAlchemy models
- Files changed:
  - `backend/app/models/blog.py` (new) — BlogCampaign + BlogPost models with enums
  - `backend/app/models/__init__.py` — registered both models
  - `backend/app/models/project.py` — added `blog_campaigns` relationship
  - `backend/app/models/keyword_cluster.py` — added `blog_campaign` relationship (1:1 via uselist=False)
- **Learnings:**
  - For 1:1 relationships: put `unique=True` on the FK column (BlogCampaign.cluster_id) and `uselist=False` on the reverse side (KeywordCluster.blog_campaign)
  - Pre-existing mypy error in `internal_link.py:243` (unparameterized `dict`) — not related to this change
  - ruff and import checks pass cleanly
---

## 2026-02-14 - S11-002
- Created Alembic migration for blog_campaigns and blog_posts tables
- Files changed:
  - `backend/alembic/versions/0026_create_blog_tables.py` (new) — migration creating both tables with all columns, indexes, FK constraints, and UNIQUE constraint on cluster_id
- **Learnings:**
  - Migration `da1ea5f253b0` (auto-generated, widening internal_links status) also descended from `0025`, creating a fork. Fixed by making `0026` a merge migration with `down_revision = ("0025", "da1ea5f253b0")` — this collapses the two branches into a single head.
  - For merge migrations, `alembic downgrade -1` fails with "Ambiguous walk" — must target a specific revision like `alembic downgrade da1ea5f253b0`.
  - `down_revision` type annotation for merge revisions: `str | tuple[str, ...] | None`
---

