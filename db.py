import sqlite3
from datetime import datetime, date
from config import DB_PATH, ensure_dirs, QUEUE_STATUS_WAITING, QUEUE_STATUS_CALLING, \
    QUEUE_STATUS_SERVING, QUEUE_STATUS_SKIPPED, QUEUE_STATUS_DONE, QUEUE_STATUS_INVALID, \
    MATERIAL_STATUS_ACTIVE, MATERIAL_STATUS_EXPIRED


def get_conn():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        item_type TEXT,
        item_desc TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_no TEXT NOT NULL,
        customer_id INTEGER,
        customer_name TEXT NOT NULL,
        item_desc TEXT,
        status TEXT NOT NULL DEFAULT 'waiting',
        skip_count INTEGER NOT NULL DEFAULT 0,
        queue_order INTEGER NOT NULL DEFAULT 0,
        called_at TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_no TEXT NOT NULL UNIQUE,
        material_name TEXT NOT NULL,
        material_type TEXT,
        expiry_date TEXT,
        quantity REAL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'active',
        remark TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS repair_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT NOT NULL UNIQUE,
        customer_id INTEGER,
        customer_name TEXT NOT NULL,
        item_desc TEXT,
        repair_content TEXT,
        before_photo TEXT,
        after_photo TEXT,
        status TEXT DEFAULT 'processing',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS material_flow (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_id INTEGER NOT NULL,
        batch_no TEXT NOT NULL,
        repair_order_id INTEGER NOT NULL,
        order_no TEXT NOT NULL,
        customer_id INTEGER,
        customer_name TEXT,
        usage_amount REAL DEFAULT 0,
        used_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE,
        FOREIGN KEY (repair_order_id) REFERENCES repair_orders(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


def add_customer(name, phone="", item_type="", item_desc=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO customers (name, phone, item_type, item_desc) VALUES (?, ?, ?, ?)",
        (name, phone, item_type, item_desc)
    )
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return cid


def get_customers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def generate_ticket_no():
    today = date.today().strftime("%Y%m%d")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM queue WHERE DATE(created_at) = DATE('now','localtime')"
    )
    count = cur.fetchone()[0] + 1
    conn.close()
    return f"A{today}{count:03d}"


def add_queue(customer_id, customer_name, item_desc=""):
    conn = get_conn()
    cur = conn.cursor()
    ticket_no = generate_ticket_no()
    cur.execute(
        "SELECT COALESCE(MAX(queue_order), 0) + 1 FROM queue WHERE status IN ('waiting','calling')"
    )
    order = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO queue (ticket_no, customer_id, customer_name, item_desc, status, queue_order) VALUES (?, ?, ?, ?, ?, ?)",
        (ticket_no, customer_id, customer_name, item_desc, QUEUE_STATUS_WAITING, order)
    )
    conn.commit()
    qid = cur.lastrowid
    conn.close()
    return qid, ticket_no


def get_active_queue():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM queue WHERE status IN ('waiting','calling','serving') ORDER BY queue_order ASC, id ASC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_queue_history(limit=100):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM queue ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_queue_stats():
    from datetime import datetime, date
    today = date.today().isoformat()
    conn = get_conn()
    cur = conn.cursor()

    stats = {
        "waiting": 0,
        "calling": 0,
        "serving": 0,
        "done": 0,
        "invalid": 0,
        "total": 0,
        "avg_wait_sec": 0,
        "current_calling": None,
    }

    cur.execute(
        "SELECT status, COUNT(*) FROM queue WHERE DATE(created_at) = DATE('now','localtime') GROUP BY status"
    )
    for status, cnt in cur.fetchall():
        if status in stats:
            stats[status] = cnt
    stats["total"] = sum(stats[s] for s in ["waiting", "calling", "serving", "done", "invalid"])

    cur.execute(
        "SELECT * FROM queue WHERE status = 'calling' ORDER BY called_at DESC LIMIT 1"
    )
    row = cur.fetchone()
    if row:
        stats["current_calling"] = dict(row)

    cur.execute(
        "SELECT called_at, created_at FROM queue WHERE status IN ('done','serving','calling') "
        "AND DATE(created_at) = DATE('now','localtime') AND called_at IS NOT NULL"
    )
    rows = cur.fetchall()
    total_sec = 0
    count = 0
    for called, created in rows:
        try:
            c1 = datetime.strptime(called, "%Y-%m-%d %H:%M:%S")
            c2 = datetime.strptime(created, "%Y-%m-%d %H:%M:%S")
            total_sec += (c1 - c2).total_seconds()
            count += 1
        except Exception:
            pass
    if count > 0:
        stats["avg_wait_sec"] = int(total_sec / count)

    conn.close()
    return stats


def call_next():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM queue WHERE status = ? ORDER BY queue_order ASC, id ASC LIMIT 1",
        (QUEUE_STATUS_WAITING,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    cur.execute(
        "UPDATE queue SET status = ?, called_at = datetime('now','localtime') WHERE id = ?",
        (QUEUE_STATUS_CALLING, row["id"])
    )
    conn.commit()
    conn.close()
    return dict(row)


def mark_serving(qid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE queue SET status = ? WHERE id = ?", (QUEUE_STATUS_SERVING, qid))
    conn.commit()
    conn.close()


def mark_done(qid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE queue SET status = ? WHERE id = ?", (QUEUE_STATUS_DONE, qid))
    conn.commit()
    conn.close()


def mark_skipped(qid, max_skip):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM queue WHERE id = ?", (qid,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    new_count = row["skip_count"] + 1
    if new_count >= max_skip:
        cur.execute(
            "UPDATE queue SET status = ?, skip_count = ? WHERE id = ?",
            (QUEUE_STATUS_INVALID, new_count, qid))
        conn.commit()
        conn.close()
        return "invalid"
    cur.execute(
        "SELECT COALESCE(MAX(queue_order), 0) FROM queue WHERE status IN ('waiting','calling')")
    max_order = cur.fetchone()[0] or 0
    cur.execute(
        "UPDATE queue SET status = ?, skip_count = ?, queue_order = ? WHERE id = ?",
        (QUEUE_STATUS_WAITING, new_count, max_order + 1, qid))
    conn.commit()
    conn.close()
    return "requeued"


def add_material(batch_no, material_name, material_type="", expiry_date="", quantity=0, remark=""):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO materials (batch_no, material_name, material_type, expiry_date, quantity, status, remark) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (batch_no, material_name, material_type, expiry_date, quantity, MATERIAL_STATUS_ACTIVE, remark))
        conn.commit()
        mid = cur.lastrowid
        conn.close()
        return mid
    except sqlite3.IntegrityError:
        conn.close()
        return None


def get_materials():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM materials ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_material_status(mid, status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE materials SET status = ? WHERE id = ?", (status, mid))
    conn.commit()
    conn.close()


def get_material_by_id(mid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM materials WHERE id = ?", (mid,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def consume_material(mid, amount):
    if amount <= 0:
        return False, "用量必须大于0"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM materials WHERE id = ?", (mid,))
    mat = cur.fetchone()
    if not mat:
        conn.close()
        return False, "批次不存在"
    qty = mat["quantity"] or 0
    if qty < amount:
        conn.close()
        return False, f"库存不足 (剩余 {qty}, 需要 {amount})"
    cur.execute("UPDATE materials SET quantity = quantity - ? WHERE id = ?", (amount, mid))
    conn.commit()
    conn.close()
    return True, "扣减成功"


def add_material_flow_with_consume(material_id, batch_no, repair_order_id, order_no,
                                   customer_id, customer_name, usage_amount):
    ok, msg = consume_material(material_id, usage_amount)
    if not ok:
        return None, msg
    fid = add_material_flow(material_id, batch_no, repair_order_id, order_no,
                            customer_id, customer_name, usage_amount)
    return fid, "登记成功"


def add_repair_order(customer_id, customer_name, item_desc="", repair_content=""):
    conn = get_conn()
    cur = conn.cursor()
    while True:
        base = datetime.now().strftime("%Y%m%d%H%M%S")
        cur.execute("SELECT COUNT(*) FROM repair_orders WHERE order_no LIKE ?", (f"R{base}%",))
        suffix = cur.fetchone()[0]
        order_no = f"R{base}{suffix:02d}" if suffix else f"R{base}"
        try:
            cur.execute(
                "INSERT INTO repair_orders (order_no, customer_id, customer_name, item_desc, repair_content) VALUES (?, ?, ?, ?, ?)",
                (order_no, customer_id, customer_name, item_desc, repair_content))
            conn.commit()
            break
        except sqlite3.IntegrityError:
            continue
    rid = cur.lastrowid
    conn.close()
    return rid, order_no


def get_repair_orders():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM repair_orders ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_repair_photos(rid, before_photo=None, after_photo=None):
    conn = get_conn()
    cur = conn.cursor()
    if before_photo is not None:
        cur.execute("UPDATE repair_orders SET before_photo = ? WHERE id = ?", (before_photo, rid))
    if after_photo is not None:
        cur.execute("UPDATE repair_orders SET after_photo = ? WHERE id = ?", (after_photo, rid))
    conn.commit()
    conn.close()


def add_material_flow(material_id, batch_no, repair_order_id, order_no, customer_id, customer_name, usage_amount=0):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO material_flow (material_id, batch_no, repair_order_id, order_no, customer_id, customer_name, usage_amount) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (material_id, batch_no, repair_order_id, order_no, customer_id, customer_name, usage_amount))
    conn.commit()
    fid = cur.lastrowid
    conn.close()
    return fid


def get_flow_by_material(material_id=None, batch_no=None):
    conn = get_conn()
    cur = conn.cursor()
    if material_id:
        cur.execute("SELECT * FROM material_flow WHERE material_id = ? ORDER BY id DESC", (material_id,))
    elif batch_no:
        cur.execute("SELECT * FROM material_flow WHERE batch_no = ? ORDER BY id DESC", (batch_no,))
    else:
        cur.execute("SELECT * FROM material_flow ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_flow_by_order(order_no):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM material_flow WHERE order_no = ? ORDER BY id DESC", (order_no,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_flow_by_repair_order_id(repair_order_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM material_flow WHERE repair_order_id = ? ORDER BY id ASC", (repair_order_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_expired_materials():
    today = date.today().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM materials WHERE status = ? AND expiry_date != '' AND expiry_date <= ?",
        (MATERIAL_STATUS_ACTIVE, today))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_flows_combined(customer_name="", order_no="", batch_no="", material_name=""):
    conn = get_conn()
    cur = conn.cursor()
    sql = """
        SELECT mf.*,
               m.material_name,
               m.material_type,
               m.expiry_date,
               m.status AS material_status,
               ro.item_desc,
               ro.repair_content,
               c.phone AS customer_phone
        FROM material_flow mf
        LEFT JOIN materials m ON mf.material_id = m.id
        LEFT JOIN repair_orders ro ON mf.repair_order_id = ro.id
        LEFT JOIN customers c ON mf.customer_id = c.id
        WHERE 1=1
    """
    params = []
    if customer_name:
        sql += " AND mf.customer_name LIKE ?"
        params.append(f"%{customer_name}%")
    if order_no:
        sql += " AND mf.order_no LIKE ?"
        params.append(f"%{order_no}%")
    if batch_no:
        sql += " AND mf.batch_no LIKE ?"
        params.append(f"%{batch_no}%")
    if material_name:
        sql += " AND m.material_name LIKE ?"
        params.append(f"%{material_name}%")
    sql += " ORDER BY mf.id DESC"
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
