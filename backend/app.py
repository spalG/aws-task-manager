"""
TaskFlow Backend — Flask + PyMySQL + AWS RDS
"""

import os
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

load_dotenv()

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────
app = Flask(__name__, static_folder="../frontend", static_url_path="/")
CORS(app, resources={r"/api/*": {"origins": "*"}})  # tighten in production

# ── DB Config ─────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "<rds-endpoint>"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "user":     os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "taskflow"),
    "charset":  "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
    # SSL for RDS
    "ssl": {"ssl_disabled": os.getenv("DB_SSL_DISABLED", "false").lower() == "true"},
}


def get_db():
    """Return a new PyMySQL connection."""
    return pymysql.connect(**DB_CONFIG)


# ── Schema Init ───────────────────────────────────────────
def init_db():
    """Create tables if they don't exist."""
    sql = """
    CREATE TABLE IF NOT EXISTS tasks (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        title       VARCHAR(255) NOT NULL,
        description TEXT,
        priority    ENUM('low','medium','high') NOT NULL DEFAULT 'medium',
        status      ENUM('todo','in_progress','done') NOT NULL DEFAULT 'todo',
        assigned_to VARCHAR(100),
        due_date    DATE,
        created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    logger.info("Database schema ready.")


# ── Helpers ───────────────────────────────────────────────
def ok(data, status=200):
    return jsonify(data), status


def err(msg, status=400):
    return jsonify({"error": msg}), status


def task_from_row(row):
    """Serialise a DB row to a dict safe for JSON."""
    return {
        "id":          row["id"],
        "title":       row["title"],
        "description": row["description"],
        "priority":    row["priority"],
        "status":      row["status"],
        "assigned_to": row["assigned_to"],
        "due_date":    row["due_date"].isoformat() if row["due_date"] else None,
        "created_at":  row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at":  row["updated_at"].isoformat() if row["updated_at"] else None,
    }


VALID_PRIORITY = {"low", "medium", "high"}
VALID_STATUS   = {"todo", "in_progress", "done"}


# ── Routes ────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the frontend."""
    return app.send_static_file("index.html")


# ─── Health Check ───
@app.route("/health")
def health():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return ok({"status": "healthy", "db": "connected", "ts": datetime.utcnow().isoformat()})
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return ok({"status": "degraded", "db": "unreachable", "error": str(exc)}, 503)


# ─── GET /api/tasks ───
@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    status   = request.args.get("status")
    priority = request.args.get("priority")
    search   = request.args.get("q")
    limit    = min(int(request.args.get("limit", 200)), 500)
    offset   = int(request.args.get("offset", 0))

    sql    = "SELECT * FROM tasks WHERE 1=1"
    params = []

    if status and status in VALID_STATUS:
        sql += " AND status = %s"
        params.append(status)
    if priority and priority in VALID_PRIORITY:
        sql += " AND priority = %s"
        params.append(priority)
    if search:
        sql += " AND (title LIKE %s OR description LIKE %s)"
        like = f"%{search}%"
        params += [like, like]

    sql += " ORDER BY FIELD(priority,'high','medium','low'), created_at DESC"
    sql += " LIMIT %s OFFSET %s"
    params += [limit, offset]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return ok({"tasks": [task_from_row(r) for r in rows], "count": len(rows)})


# ─── POST /api/tasks ───
@app.route("/api/tasks", methods=["POST"])
def create_task():
    body = request.get_json(silent=True) or {}

    title = (body.get("title") or "").strip()
    if not title:
        return err("title is required")
    if len(title) > 255:
        return err("title must be 255 characters or fewer")

    priority = body.get("priority", "medium")
    if priority not in VALID_PRIORITY:
        return err(f"priority must be one of {sorted(VALID_PRIORITY)}")

    status = body.get("status", "todo")
    if status not in VALID_STATUS:
        return err(f"status must be one of {sorted(VALID_STATUS)}")

    due_date    = body.get("due_date") or None
    assigned_to = (body.get("assigned_to") or "").strip() or None
    description = (body.get("description") or "").strip() or None

    sql = """
        INSERT INTO tasks (title, description, priority, status, assigned_to, due_date)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (title, description, priority, status, assigned_to, due_date))
            new_id = cur.lastrowid
            cur.execute("SELECT * FROM tasks WHERE id = %s", (new_id,))
            row = cur.fetchone()

    logger.info("Created task #%d: %s", new_id, title)
    return ok({"task": task_from_row(row), "message": "Task created"}, 201)


# ─── GET /api/tasks/<id> ───
@app.route("/api/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            row = cur.fetchone()

    if not row:
        return err("Task not found", 404)
    return ok({"task": task_from_row(row)})


# ─── PUT /api/tasks/<id> ───
@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    # Check exists
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            existing = cur.fetchone()

    if not existing:
        return err("Task not found", 404)

    body = request.get_json(silent=True) or {}
    fields, params = [], []

    if "title" in body:
        title = body["title"].strip()
        if not title:
            return err("title cannot be empty")
        fields.append("title = %s"); params.append(title)

    if "description" in body:
        fields.append("description = %s")
        params.append(body["description"].strip() or None)

    if "priority" in body:
        if body["priority"] not in VALID_PRIORITY:
            return err(f"priority must be one of {sorted(VALID_PRIORITY)}")
        fields.append("priority = %s"); params.append(body["priority"])

    if "status" in body:
        if body["status"] not in VALID_STATUS:
            return err(f"status must be one of {sorted(VALID_STATUS)}")
        fields.append("status = %s"); params.append(body["status"])

    if "assigned_to" in body:
        fields.append("assigned_to = %s")
        params.append(body["assigned_to"].strip() or None)

    if "due_date" in body:
        fields.append("due_date = %s")
        params.append(body["due_date"] or None)

    if not fields:
        return err("No fields to update")

    params.append(task_id)
    sql = f"UPDATE tasks SET {', '.join(fields)} WHERE id = %s"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            updated = cur.fetchone()

    logger.info("Updated task #%d", task_id)
    return ok({"task": task_from_row(updated), "message": "Task updated"})


# ─── DELETE /api/tasks/<id> ───
@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tasks WHERE id = %s", (task_id,))
            if not cur.fetchone():
                return err("Task not found", 404)
            cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))

    logger.info("Deleted task #%d", task_id)
    return ok({"message": "Task deleted"})


# ─── GET /api/stats ───
@app.route("/api/stats", methods=["GET"])
def stats():
    sql = """
        SELECT
            COUNT(*) AS total,
            SUM(status = 'todo')        AS todo,
            SUM(status = 'in_progress') AS in_progress,
            SUM(status = 'done')        AS done,
            SUM(priority = 'high')      AS high_priority,
            SUM(priority = 'medium')    AS medium_priority,
            SUM(priority = 'low')       AS low_priority
        FROM tasks
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()

    return ok({"stats": {k: int(v or 0) for k, v in row.items()}})


# ── Error Handlers ────────────────────────────────────────
@app.errorhandler(404)
def not_found(_):
    return err("Not found", 404)


@app.errorhandler(405)
def method_not_allowed(_):
    return err("Method not allowed", 405)


@app.errorhandler(500)
def internal(_):
    return err("Internal server error", 500)


# ── Entry Point ───────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "production") == "development"
    logger.info("Starting TaskFlow on port %d (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
