# Operations (shared I/O layer)

**Operations** are shared, app-agnostic layers for **external I/O** (GitHub API, Discord, notifications, etc.). Any Django app can use them; they are **not** part of the per-app **service API** (which is for database writes only).

| Operation | App | Doc | Purpose |
|-----------|-----|-----|---------|
| **GitHub** | `github_ops` | [github.md](github.md) | Clone, push, fetch file, create PR/issue/comment; token resolution. |
| **Discord** | *(planned)* | *(e.g. discord.md)* | Send notifications to Discord; used by other apps. |

**When to add a new operation:** When multiple apps need the same external integration (e.g. “notify via Discord”). Create a dedicated app (e.g. `discord_ops`) and a doc in this folder, then list it in the table above.

**Service API vs Operations:** Service API = one place per app for **database** create/update/delete. Operations = shared **external** I/O (GitHub, Discord, etc.) used by many apps.
