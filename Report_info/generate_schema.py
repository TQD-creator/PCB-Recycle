#!/usr/bin/env python3
"""
PCB Inspection System — Database Schema Diagram  (v2, post-fix)
Run:  python generate_schema.py
Output: schema_diagram.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "#060B12"
TBL_BG   = "#111827"
TBL_HDR  = "#1E3A5F"
COL_FG   = "#CBD5E1"
PK_FG    = "#FCD34D"    # gold   — PK
FK_FG    = "#93C5FD"    # blue   — FK
UN_FG    = "#A78BFA"    # purple — UNIQUE
NEW_FG   = "#34D399"    # mint   — newly added column
NEW_BG   = "#064E3B"    # dark green badge background
ARROW    = "#10B981"    # green  — all relationships are valid now
WARN_BG  = "#78350F"    # amber  — remaining concern (not fixed)
WARN_FG  = "#FDE68A"
TITLE_FG = "#94A3B8"
BORDER   = "#1F2937"

COL_W  = 5.8    # table width
HDR_H  = 0.55   # header height
ROW_H  = 0.40   # row height
NOTE_H = 0.40   # note stripe height


# ─────────────────────────────────────────────────────────────────────────────
def draw_table(ax, x, y, title, columns, note=None, note_ok=False):
    """
    columns: list of (name, sql_type, badge, is_new)
      badge  : "PK" | "FK" | "UNIQUE" | None
      is_new : True  → draws a green NEW pill on the right edge
    note     : optional bottom stripe text
    note_ok  : True = green (fixed), False = amber (remaining concern)
    """
    n = len(columns)
    total_h = HDR_H + n * ROW_H + (NOTE_H if note else 0)

    # outer box
    ax.add_patch(patches.FancyBboxPatch(
        (x, y - total_h), COL_W, total_h,
        boxstyle="round,pad=0.08",
        facecolor=TBL_BG, edgecolor=BORDER, linewidth=1.8, zorder=2,
    ))
    # header
    ax.add_patch(patches.FancyBboxPatch(
        (x, y - HDR_H), COL_W, HDR_H,
        boxstyle="round,pad=0.06",
        facecolor=TBL_HDR, edgecolor=BORDER, linewidth=1.4, zorder=3,
    ))
    ax.text(x + COL_W / 2, y - HDR_H / 2, title,
            ha="center", va="center", color="#F8FAFC",
            fontsize=10, fontweight="bold", fontfamily="monospace", zorder=4)

    for i, (col_name, col_type, badge, is_new) in enumerate(columns):
        row_top = y - HDR_H - i * ROW_H
        row_mid = row_top - ROW_H / 2

        # separator
        ax.plot([x + 0.12, x + COL_W - 0.12], [row_top, row_top],
                color="#1F2937", linewidth=0.7, zorder=3)

        # badge
        if badge:
            badge_color = {"PK": PK_FG, "FK": FK_FG, "UNIQUE": UN_FG}.get(badge, "#6B7280")
            ax.text(x + 0.18, row_mid, badge,
                    ha="left", va="center", color=badge_color,
                    fontsize=7, fontweight="bold", fontfamily="monospace", zorder=4)

        # column name
        name_x = x + 0.72 if badge else x + 0.22
        name_color = (
            PK_FG if badge == "PK" else
            FK_FG if badge == "FK" else
            UN_FG if badge == "UNIQUE" else
            COL_FG
        )
        ax.text(name_x, row_mid, col_name,
                ha="left", va="center", color=name_color,
                fontsize=8.5,
                fontweight="bold" if badge in ("PK", "FK") else "normal",
                fontfamily="monospace", zorder=4)

        # type (right-aligned italic)
        type_x = x + COL_W - (0.75 if is_new else 0.15)
        ax.text(type_x, row_mid, col_type,
                ha="right", va="center", color="#4B5563",
                fontsize=7.5, fontstyle="italic", fontfamily="monospace", zorder=4)

        # NEW pill
        if is_new:
            pill_x = x + COL_W - 0.70
            pill_w, pill_h = 0.58, 0.22
            ax.add_patch(patches.FancyBboxPatch(
                (pill_x, row_mid - pill_h / 2), pill_w, pill_h,
                boxstyle="round,pad=0.03",
                facecolor=NEW_BG, edgecolor=NEW_FG, linewidth=0.8, zorder=4,
            ))
            ax.text(pill_x + pill_w / 2, row_mid, "NEW",
                    ha="center", va="center", color=NEW_FG,
                    fontsize=6.5, fontweight="bold", fontfamily="monospace", zorder=5)

    # bottom note stripe
    if note:
        ny = y - HDR_H - n * ROW_H
        nb_color = "#064E3B" if note_ok else WARN_BG
        ne_color = ARROW    if note_ok else "#D97706"
        nf_color = "#A7F3D0" if note_ok else WARN_FG
        prefix   = "[OK]" if note_ok else "[!]"
        ax.add_patch(patches.Rectangle(
            (x + 0.08, ny - NOTE_H + 0.06), COL_W - 0.16, NOTE_H - 0.1,
            facecolor=nb_color, edgecolor=ne_color, linewidth=1.0, zorder=3,
        ))
        ax.text(x + COL_W / 2, ny - NOTE_H / 2 + 0.05,
                f"{prefix} {note}",
                ha="center", va="center", color=nf_color,
                fontsize=7.2, fontfamily="monospace", zorder=4)

    mid_y = y - total_h / 2
    return {
        "top":    (x + COL_W / 2, y),
        "bottom": (x + COL_W / 2, y - total_h),
        "left":   (x, mid_y),
        "right":  (x + COL_W, mid_y),
        "row_y":  lambda i: y - HDR_H - (i + 0.5) * ROW_H,
        "x": x, "top_y": y, "w": COL_W, "h": total_h,
    }


def arrow(ax, src, dst, label=None, rad=0.0, new=False):
    edge = NEW_FG if new else ARROW
    ax.annotate("", xy=dst, xytext=src,
                arrowprops=dict(
                    arrowstyle="-|>", color=edge, lw=1.8 if not new else 2.2,
                    linestyle="solid",
                    connectionstyle=f"arc3,rad={rad}",
                ), zorder=5)
    if label:
        mx = (src[0] + dst[0]) / 2
        my = (src[1] + dst[1]) / 2
        ax.text(mx, my, label,
                ha="center", va="center", color=edge,
                fontsize=7.5, fontweight="bold", fontfamily="monospace",
                bbox=dict(boxstyle="round,pad=0.25", facecolor=BG,
                          edgecolor=edge, linewidth=0.9),
                zorder=6)


def callout(ax, x, y, title, lines, border_color="#F59E0B"):
    h = 0.44 + len(lines) * 0.33
    ax.add_patch(patches.FancyBboxPatch(
        (x, y - h), 7.2, h,
        boxstyle="round,pad=0.1",
        facecolor="#110C00", edgecolor=border_color, linewidth=1.5, zorder=2,
    ))
    ax.text(x + 0.22, y - 0.26, title,
            ha="left", va="center", color=border_color,
            fontsize=8.5, fontweight="bold", fontfamily="monospace", zorder=3)
    for i, line in enumerate(lines):
        ax.text(x + 0.22, y - 0.26 - (i + 1) * 0.33, line,
                ha="left", va="center", color="#D1D5DB",
                fontsize=7.5, fontfamily="monospace", zorder=3)


# ─────────────────────────────────────────────────────────────────────────────
# FIGURE
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(26, 17))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 26)
ax.set_ylim(0, 17)
ax.axis("off")

# ─────────────────────────────────────────────────────────────────────────────
# TABLES
# col tuple: (name, sql_type, badge, is_new)
# ─────────────────────────────────────────────────────────────────────────────

# ── users ─────────────────────────────────────────────────────────────────────
t_users = draw_table(ax, 0.4, 16.5, "users", [
    ("id",            "INTEGER",  "PK",     False),
    ("username",      "TEXT",     "UNIQUE", False),
    ("password_hash", "TEXT",     None,     False),
    ("role",          "TEXT",     None,     False),
    ("created_at",    "DATETIME", None,     False),
], note="SHA-256, no salt — weak against rainbow tables", note_ok=False)

# ── sessions ──────────────────────────────────────────────────────────────────
t_sess = draw_table(ax, 0.4, 10.2, "sessions", [
    ("token",      "TEXT",     "PK", False),
    ("user_id",    "INTEGER",  "FK", False),
    ("role",       "TEXT",     None, False),
    ("username",   "TEXT",     None, False),
    ("created_at", "DATETIME", None, False),
    ("expires_at", "DATETIME", None, True),   # <-- NEW
], note="Tokens expire after 24 h  (SESSION_TTL_HOURS)", note_ok=True)

# ── scans ─────────────────────────────────────────────────────────────────────
t_scans = draw_table(ax, 9.1, 16.5, "scans", [
    ("task_id",         "TEXT",    "PK", False),
    ("timestamp",       "DATETIME", None, False),
    ("image_url",       "TEXT",    None, False),
    ("total_verified",  "INTEGER", None, False),
    ("total_anomalies", "INTEGER", None, False),
    ("user_id",         "INTEGER", "FK", True),  # <-- NEW
], note="Scan ownership now tracked via user_id FK", note_ok=True)

# ── components ────────────────────────────────────────────────────────────────
t_comp = draw_table(ax, 18.4, 16.5, "components", [
    ("id",              "INTEGER", "PK", False),
    ("task_id",         "TEXT",    "FK", False),
    ("status",          "TEXT",    None, False),
    ("predicted_class", "TEXT",    None, False),
    ("faiss_distance",  "REAL",    None, False),
    ("bbox",            "TEXT",    None, False),
])

# ── modify_approved ───────────────────────────────────────────────────────────
t_mod = draw_table(ax, 9.1, 9.0, "modify_approved", [
    ("id",            "INTEGER",  "PK", False),
    ("task_id",       "TEXT",     "FK", False),
    ("image_url",     "TEXT",     None, False),
    ("corrections",   "TEXT",     None, False),
    ("submitted_at",  "DATETIME", None, False),
    ("status",        "TEXT",     None, False),
    ("reviewed_at",   "DATETIME", None, False),
    ("reviewer_note", "TEXT",     None, False),
    ("submitted_by",  "INTEGER",  "FK", True),  # <-- NEW
], note="Submitter identity now tracked via submitted_by FK", note_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# ARROWS — ALL VALID (no missing FKs remain in DB layer)
# ─────────────────────────────────────────────────────────────────────────────

# users → sessions (unchanged)
arrow(ax,
      (t_users["bottom"][0], t_users["bottom"][1]),
      (t_sess["top"][0],     t_sess["top"][1]),
      label="1 : N", rad=0.0)

# users → scans (NEW FK — user_id)
arrow(ax,
      (t_users["right"][0],  t_users["row_y"](0)),
      (t_scans["left"][0],   t_scans["row_y"](5)),   # row 5 = user_id (new)
      label="1 : N", rad=-0.15, new=True)

# users → modify_approved (NEW FK — submitted_by)
arrow(ax,
      (t_users["bottom"][0] + 0.3, t_users["bottom"][1]),
      (t_mod["left"][0],           t_mod["row_y"](8)),  # row 8 = submitted_by (new)
      label="1 : N", rad=0.3, new=True)

# scans → components (unchanged)
arrow(ax,
      (t_scans["right"][0],  t_scans["row_y"](0)),
      (t_comp["left"][0],    t_comp["row_y"](1)),
      label="1 : N", rad=-0.1)

# scans → modify_approved (unchanged)
arrow(ax,
      (t_scans["bottom"][0], t_scans["bottom"][1]),
      (t_mod["top"][0],      t_mod["top"][1]),
      label="1 : N", rad=0.0)

# ─────────────────────────────────────────────────────────────────────────────
# REMAINING ARCHITECTURAL CONCERNS (not in DB layer — cannot be fixed by schema)
# ─────────────────────────────────────────────────────────────────────────────
callout(ax, 0.3, 4.8, "FAISS Index  (RAM — not in SQLite)  [NOT FIXED]", [
    "• Single global PipelineRegistry singleton",
    "• Shared by ALL users and ALL scans",
    "• APPROVE mutates the shared vector DB for everyone",
    "• Fix: per-board-type namespace or separate FAISS shards",
], border_color="#F59E0B")

callout(ax, 0.3, 2.8, "Celery Worker  (--pool=solo --concurrency=1)  [NOT FIXED]", [
    "• Only 1 scan runs at a time globally — no parallelism",
    "• All users share the same queue — no priority",
    "• Fix: raise --concurrency, add per-user rate limiting",
], border_color="#F59E0B")

callout(ax, 0.3, 1.0, "User Management  [NOT FIXED]", [
    "• Only 2 hard-seeded accounts (admin, user)",
    "• No API to create / update / delete users",
], border_color="#F59E0B")

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE LOG BOX
# ─────────────────────────────────────────────────────────────────────────────
clx, cly = 18.3, 9.0
cl_w, cl_h = 7.3, 4.5
ax.add_patch(patches.FancyBboxPatch(
    (clx, cly - cl_h), cl_w, cl_h,
    boxstyle="round,pad=0.12",
    facecolor="#071a0f", edgecolor=NEW_FG, linewidth=1.8, zorder=2,
))
ax.text(clx + cl_w / 2, cly - 0.28,
        "v2  Schema Fixes Applied",
        ha="center", va="center", color=NEW_FG,
        fontsize=10, fontweight="bold", fontfamily="monospace", zorder=3)

changes = [
    ("sessions.expires_at",        "DATETIME", "Tokens expire after 24 h"),
    ("scans.user_id",              "INTEGER",  "FK -> users.id  (ownership)"),
    ("modify_approved.submitted_by","INTEGER", "FK -> users.id  (authorship)"),
]
for i, (col, typ, desc) in enumerate(changes):
    cy = cly - 0.75 - i * 1.05
    # pill
    ax.add_patch(patches.FancyBboxPatch(
        (clx + 0.2, cy - 0.18), 0.55, 0.34,
        boxstyle="round,pad=0.04",
        facecolor=NEW_BG, edgecolor=NEW_FG, linewidth=0.8, zorder=3,
    ))
    ax.text(clx + 0.47, cy, "NEW",
            ha="center", va="center", color=NEW_FG,
            fontsize=6.5, fontweight="bold", fontfamily="monospace", zorder=4)
    ax.text(clx + 0.9, cy + 0.04, col,
            ha="left", va="center", color="#F8FAFC",
            fontsize=8.5, fontweight="bold", fontfamily="monospace", zorder=3)
    ax.text(clx + 0.9, cy - 0.26, f"{typ}  —  {desc}",
            ha="left", va="center", color="#64748B",
            fontsize=7.5, fontfamily="monospace", zorder=3)
    if i < len(changes) - 1:
        ax.plot([clx + 0.2, clx + cl_w - 0.2],
                [cy - 0.46, cy - 0.46],
                color="#1F2937", linewidth=0.7, zorder=3)

ax.text(clx + cl_w / 2, cly - cl_h + 0.26,
        "Migration: safe ALTER TABLE ADD COLUMN via _migrate_db()",
        ha="center", va="center", color="#4B5563",
        fontsize=7, fontfamily="monospace", zorder=3)

# ─────────────────────────────────────────────────────────────────────────────
# LEGEND
# ─────────────────────────────────────────────────────────────────────────────
lx, ly = 18.3, 4.2
ax.add_patch(patches.FancyBboxPatch(
    (lx, ly - 3.8), 7.3, 4.0,
    boxstyle="round,pad=0.15",
    facecolor="#0D1520", edgecolor=BORDER, linewidth=1.2, zorder=2,
))
ax.text(lx + 3.65, ly - 0.28, "LEGEND",
        ha="center", va="center", color="#F8FAFC",
        fontsize=10, fontweight="bold", fontfamily="monospace", zorder=3)

legend_items = [
    (PK_FG,   "PK   Primary Key"),
    (FK_FG,   "FK   Foreign Key column"),
    (UN_FG,   "UNIQUE constraint"),
    (ARROW,   "——   Valid FK relationship (all green now)"),
    (NEW_FG,  "NEW  Newly added column (v2 fix)"),
    (NEW_FG,  "mint arrow  =  new FK relationship added"),
    ("#F59E0B", "[!]  Remaining concern (not a DB fix)"),
]
for i, (color, text) in enumerate(legend_items):
    iy = ly - 0.68 - i * 0.44
    ax.plot([lx + 0.2, lx + 0.72], [iy, iy], color=color, linewidth=2.5, zorder=3)
    ax.text(lx + 0.9, iy, text,
            va="center", color=color,
            fontsize=8, fontfamily="monospace", zorder=3)

# ─────────────────────────────────────────────────────────────────────────────
# TITLE
# ─────────────────────────────────────────────────────────────────────────────
ax.text(13, 0.58,
        "PCB Inspection System  |  Database Schema  v2  |  pcb_scans.db (SQLite)",
        ha="center", va="center", color=TITLE_FG,
        fontsize=12, fontweight="bold", fontfamily="monospace")
ax.text(13, 0.23,
        "Mint (green) arrows = new FK relationships added in v2  |  All design-gap missing-FKs resolved at DB layer",
        ha="center", va="center", color=NEW_FG,
        fontsize=8.5, fontfamily="monospace")

plt.tight_layout(pad=0.3)
out = "schema_diagram.png"
plt.savefig(out, dpi=160, bbox_inches="tight", facecolor=BG, edgecolor="none")
print(f"[OK] Saved -> {out}")
