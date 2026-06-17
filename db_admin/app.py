"""
Database Admin Panel - Flask app for managing Aiven PostgreSQL & Upstash Redis.
Requires admin_root login to use.
"""
import re
import ssl as _ssl
from datetime import datetime, timezone
from functools import wraps

import redis
import sqlalchemy
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from passlib.hash import bcrypt
from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    Table,
    create_engine,
    func,
    inspect,
    text,
)

from config import Config

# ============== App Init ==============
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config["DEBUG"] = Config.DEBUG

# ============== PostgreSQL Engine (sync, for psycopg2) ==============
_db_url = Config.DATABASE_URL
if not _db_url:
    raise RuntimeError("DATABASE_URL is not set in .env")

# Strip sslmode from URL - we handle SSL via connect_args (avoids psycopg2 conflict)
_db_url_clean = _db_url
if "sslmode=require" in _db_url:
    _db_url_clean = _db_url.split("?")[0]
elif "?sslmode=require" in _db_url:
    _db_url_clean = _db_url.split("?sslmode=")[0]

# Build SSL context for Aiven (self-signed cert)
_ssl_ctx = _ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = _ssl.CERT_NONE

try:
    pg_engine = create_engine(
        _db_url_clean,
        echo=False,
        pool_size=3,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"sslmode": "require"},
    )
    # Test connection once
    with pg_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        conn.commit()
    pg_connected = True
except Exception as e:
    pg_connected = False
    pg_engine = None
    print(f"[WARN] PostgreSQL connection failed: {e}")


def get_pg_conn():
    """Get a raw psycopg2 connection for advanced operations."""
    import psycopg2
    from urllib.parse import urlparse

    u = urlparse(Config.DATABASE_URL)
    conn = psycopg2.connect(
        host=u.hostname,
        port=u.port or 5432,
        dbname=u.path.lstrip("/") or "defaultdb",
        user=u.username,
        password=u.password,
        sslmode="require",
    )
    return conn


# ============== Redis Client ==============
_redis_url = Config.REDIS_URL
if _redis_url and _redis_url.startswith("redis://"):
    _redis_url = _redis_url.replace("redis://", "rediss://", 1)

redis_connected = False
redis_client = None
if _redis_url:
    try:
        redis_client = redis.from_url(
            _redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            ssl_cert_reqs=None,
        )
        redis_client.ping()
        redis_connected = True
    except Exception as e:
        redis_connected = False
        redis_client = None
        print(f"[WARN] Redis connection failed: {e}")


# ============== Auth Helpers ==============
def check_admin_root(username: str, password: str) -> bool:
    """Verify admin_root credentials from .env."""
    return (
        username == Config.ADMIN_ROOT_USERNAME
        and password == Config.ADMIN_ROOT_PASSWORD
    )


def login_required(f):
    """Decorator to require admin_root login."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)

    return decorated


# ============== Routes: Login ==============
@app.route("/login", methods=["GET"])
def login_page():
    if session.get("admin_logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if check_admin_root(username, password):
        session["admin_logged_in"] = True
        session["login_time"] = datetime.now(timezone.utc).isoformat()
        flash("Login successful!", "success")
        return redirect(url_for("dashboard"))
    else:
        flash("Incorrect username or password!", "danger")
        return redirect(url_for("login_page"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login_page"))


# ============== Routes: Dashboard ==============
@app.route("/")
@login_required
def dashboard():
    # Get PostgreSQL stats
    pg_stats = {"tables": [], "connected": pg_connected}
    if pg_connected and pg_engine:
        try:
            inspector = inspect(pg_engine)
            # Only show steam schema tables
            for schema_name in ["public", "steam"]:
                try:
                    tables_raw = inspector.get_table_names(schema=schema_name)
                except Exception:
                    continue
                for tname in tables_raw:
                    # Count rows
                    try:
                        full_name = f"{schema_name}.{tname}"
                        with pg_engine.connect() as conn:
                            row_count = conn.execute(
                                text(f'SELECT COUNT(*) FROM "{schema_name}"."{tname}"')
                            ).scalar()
                    except Exception:
                        row_count = "N/A"
                    pg_stats["tables"].append(
                        {
                            "schema": schema_name,
                            "name": tname,
                            "full_name": full_name,
                            "row_count": row_count,
                        }
                    )
        except Exception as e:
            pg_stats["error"] = str(e)

    # Get Redis stats
    redis_stats = {"connected": redis_connected, "keys_count": 0, "memory": "N/A"}
    if redis_connected and redis_client:
        try:
            info = redis_client.info(section="memory")
            redis_stats["keys_count"] = redis_client.dbsize()
            redis_stats["memory"] = info.get("used_memory_human", "N/A")
        except Exception as e:
            redis_stats["error"] = str(e)

    return render_template(
        "dashboard.html", pg_stats=pg_stats, redis_stats=redis_stats
    )


# ============== Routes: PostgreSQL - Browse Table ==============
@app.route("/pg/table/<schema>/<table_name>")
@login_required
def pg_view_table(schema, table_name):
    """View data in a table with pagination."""
    if not pg_connected:
        flash("Cannot connect to PostgreSQL.", "danger")
        return redirect(url_for("dashboard"))

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search_col = request.args.get("search_col", "")
    search_val = request.args.get("search_val", "")
    order_col = request.args.get("order_col", "")
    order_dir = request.args.get("order_dir", "ASC")

    try:
        inspector = inspect(pg_engine)
        columns_info = inspector.get_columns(table_name, schema=schema)
        pk_cols = inspector.get_pk_constraint(table_name, schema=schema)
        pk_names = pk_cols.get("constrained_columns", []) if pk_cols else []

        # Get foreign keys
        fks = inspector.get_foreign_keys(table_name, schema=schema)

        # Get unique constraints
        unique_constraints = inspector.get_unique_constraints(table_name, schema=schema)

        # Get indexes
        indexes = inspector.get_indexes(table_name, schema=schema)

        # Handle array types - we can't display them nicely, so convert to strings
        column_names = [c["name"] for c in columns_info]
        safe_cols = ", ".join(f'"{c["name"]}"' for c in columns_info)
        full_name = f'"{schema}"."{table_name}"'

        # Build query
        base_query = f"SELECT {safe_cols} FROM {full_name}"
        count_query = f"SELECT COUNT(*) FROM {full_name}"
        params = {}

        if search_col and search_val and search_col in column_names:
            where_clause = f' WHERE "{search_col}"::text ILIKE :search'
            base_query += where_clause
            count_query += where_clause
            params["search"] = f"%{search_val}%"

        # Order
        if order_col and order_col in column_names:
            safe_dir = "ASC" if order_dir.upper() == "ASC" else "DESC"
            base_query += f' ORDER BY "{order_col}" {safe_dir}'

        # Pagination
        offset = (page - 1) * per_page
        base_query += f" LIMIT {per_page} OFFSET {offset}"

        with pg_engine.connect() as conn:
            total_rows = conn.execute(text(count_query), params).scalar()
            rows = conn.execute(text(base_query), params).fetchall()
        total_pages = max(1, (total_rows + per_page - 1) // per_page)

        # Format rows for display
        formatted_rows = []
        for row in rows:
            formatted = {}
            for col_obj, val in zip(columns_info, row):
                col_name = col_obj["name"]
                # Convert to displayable string
                if val is None:
                    formatted[col_name] = '<span class="null-value">NULL</span>'
                elif isinstance(val, (list, dict)):
                    import json

                    formatted[col_name] = json.dumps(val, ensure_ascii=False, default=str)
                elif isinstance(val, datetime):
                    formatted[col_name] = val.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    formatted[col_name] = str(val)
            formatted_rows.append(formatted)

        # Determine primary key for edit links
        primary_key = pk_names[0] if pk_names else (column_names[0] if column_names else None)

    except Exception as e:
        flash(f"Error reading table: {e}", "danger")
        return redirect(url_for("dashboard"))

    return render_template(
        "pg_table.html",
        schema=schema,
        table_name=table_name,
        columns=columns_info,
        column_names=column_names,
        rows=formatted_rows,
        total_rows=total_rows,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        search_col=search_col,
        search_val=search_val,
        order_col=order_col,
        order_dir=order_dir,
        primary_key=primary_key,
        pk_names=pk_names,
        fks=fks,
        unique_constraints=unique_constraints,
        indexes=indexes,
    )


# ============== Routes: PostgreSQL - Edit Row ==============
@app.route("/pg/edit/<schema>/<table_name>", methods=["POST"])
@login_required
def pg_edit_row(schema, table_name):
    """Update a row in a table."""
    if not pg_connected:
        flash("Cannot connect to PostgreSQL.", "danger")
        return redirect(url_for("dashboard"))

    try:
        inspector = inspect(pg_engine)
        columns_info = inspector.get_columns(table_name, schema=schema)
        pk_cols = inspector.get_pk_constraint(table_name, schema=schema)
        pk_names = pk_cols.get("constrained_columns", []) if pk_cols else []
        column_names = [c["name"] for c in columns_info]
        full_name = f'"{schema}"."{table_name}"'

        # Build WHERE clause from all PK values submitted
        if not pk_names:
            flash("Table has no primary key - cannot edit.", "warning")
            return redirect(url_for("pg_view_table", schema=schema, table_name=table_name))

        where_parts = []
        where_params = {}
        for pk in pk_names:
            pk_val = request.form.get(f"pk_{pk}", "")
            where_parts.append(f'"{pk}" = :pk_{pk}')
            where_params[f"pk_{pk}"] = _smart_convert(pk_val, columns_info, pk)

        # Build SET clause from submitted form values
        set_parts = []
        set_params = {}
        for col in columns_info:
            col_name = col["name"]
            if col_name in pk_names:
                continue  # Don't update PK
            form_val = request.form.get(f"col_{col_name}")
            if form_val is not None:
                set_parts.append(f'"{col_name}" = :set_{col_name}')
                set_params[f"set_{col_name}"] = _smart_convert(form_val, columns_info, col_name)

        if not set_parts:
            flash("No data to update.", "warning")
            return redirect(
                url_for("pg_view_table", schema=schema, table_name=table_name)
            )

        set_clause = ", ".join(set_parts)
        where_clause = " AND ".join(where_parts)
        all_params = {**where_params, **set_params}

        update_sql = f"UPDATE {full_name} SET {set_clause} WHERE {where_clause}"
        with pg_engine.begin() as conn:
            conn.execute(text(update_sql), all_params)

        flash("Update successful!", "success")
    except Exception as e:
        flash(f"Error updating: {e}", "danger")

    return redirect(
        url_for(
            "pg_view_table",
            schema=schema,
            table_name=table_name,
            page=request.form.get("current_page", 1),
        )
    )


# ============== Routes: PostgreSQL - Add Row ==============
@app.route("/pg/add/<schema>/<table_name>", methods=["POST"])
@login_required
def pg_add_row(schema, table_name):
    """Insert a new row into a table."""
    if not pg_connected:
        flash("Cannot connect to PostgreSQL.", "danger")
        return redirect(url_for("dashboard"))

    try:
        inspector = inspect(pg_engine)
        columns_info = inspector.get_columns(table_name, schema=schema)
        pk_cols = inspector.get_pk_constraint(table_name, schema=schema)
        pk_names = pk_cols.get("constrained_columns", []) if pk_cols else []
        column_names = [c["name"] for c in columns_info]
        full_name = f'"{schema}"."{table_name}"'

        col_parts = []
        val_placeholders = []
        insert_params = {}

        for col in columns_info:
            col_name = col["name"]
            # Skip auto-increment PKs (serial/bigserial)
            if col_name in pk_names and col.get("autoincrement", True):
                continue
            form_val = request.form.get(f"new_col_{col_name}")
            if form_val is not None and form_val != "":
                col_parts.append(f'"{col_name}"')
                val_placeholders.append(f":new_{col_name}")
                insert_params[f"new_{col_name}"] = _smart_convert(form_val, columns_info, col_name)

        if not col_parts:
            flash("No data to insert.", "warning")
            return redirect(
                url_for("pg_view_table", schema=schema, table_name=table_name)
            )

        cols_clause = ", ".join(col_parts)
        vals_clause = ", ".join(val_placeholders)
        insert_sql = f"INSERT INTO {full_name} ({cols_clause}) VALUES ({vals_clause})"

        with pg_engine.begin() as conn:
            conn.execute(text(insert_sql), insert_params)

        flash("Row added successfully!", "success")
    except Exception as e:
        flash(f"Error adding row: {e}", "danger")

    return redirect(
        url_for(
            "pg_view_table",
            schema=schema,
            table_name=table_name,
            page=request.form.get("current_page", 1),
        )
    )


# ============== Routes: PostgreSQL - Delete Row ==============
@app.route("/pg/delete/<schema>/<table_name>", methods=["POST"])
@login_required
def pg_delete_row(schema, table_name):
    """Delete a row from a table."""
    if not pg_connected:
        flash("Cannot connect to PostgreSQL.", "danger")
        return redirect(url_for("dashboard"))

    try:
        inspector = inspect(pg_engine)
        columns_info = inspector.get_columns(table_name, schema=schema)
        pk_cols = inspector.get_pk_constraint(table_name, schema=schema)
        pk_names = pk_cols.get("constrained_columns", []) if pk_cols else []
        full_name = f'"{schema}"."{table_name}"'

        if not pk_names:
            flash("Table has no primary key - cannot delete safely.", "warning")
            return redirect(
                url_for("pg_view_table", schema=schema, table_name=table_name)
            )

        where_parts = []
        where_params = {}
        for pk in pk_names:
            pk_val = request.form.get(f"del_pk_{pk}", "")
            where_parts.append(f'"{pk}" = :del_pk_{pk}')
            where_params[f"del_pk_{pk}"] = _smart_convert(pk_val, columns_info, pk)

        where_clause = " AND ".join(where_parts)
        delete_sql = f"DELETE FROM {full_name} WHERE {where_clause}"

        with pg_engine.begin() as conn:
            result = conn.execute(text(delete_sql), where_params)
        if result.rowcount > 0:
            flash(f"Deleted {result.rowcount} row(s).", "success")
        else:
            flash("No matching data to delete.", "warning")

    except Exception as e:
        flash(f"Error deleting data: {e}", "danger")

    return redirect(
        url_for(
            "pg_view_table",
            schema=schema,
            table_name=table_name,
            page=request.form.get("current_page", 1),
        )
    )


# ============== Routes: PostgreSQL - Create Table ==============
@app.route("/pg/create-table", methods=["GET"])
@login_required
def pg_create_table_form():
    return render_template("pg_create_table.html")


@app.route("/pg/create-table", methods=["POST"])
@login_required
def pg_create_table():
    if not pg_connected:
        flash("Cannot connect to PostgreSQL.", "danger")
        return redirect(url_for("dashboard"))

    schema = request.form.get("schema", "steam").strip()
    table_name = request.form.get("table_name", "").strip()
    raw_sql = request.form.get("raw_sql", "").strip()

    if not table_name and not raw_sql:
        flash("Please enter a table name or raw SQL.", "danger")
        return redirect(url_for("pg_create_table_form"))

    try:
        if raw_sql:
            # Execute raw SQL
            with pg_engine.begin() as conn:
                conn.execute(text(raw_sql))
            flash("SQL executed successfully!", "success")
        else:
            # Build columns from form
            col_count = int(request.form.get("column_count", 0))
            col_defs = []
            for i in range(col_count):
                col_name = request.form.get(f"col_name_{i}", "").strip()
                col_type = request.form.get(f"col_type_{i}", "VARCHAR(255)").strip()
                col_nullable = request.form.get(f"col_nullable_{i}")
                col_pk = request.form.get(f"col_pk_{i}")
                col_default = request.form.get(f"col_default_{i}", "").strip()

                if not col_name:
                    continue
                col_def = f'"{col_name}" {col_type}'
                if col_pk == "on":
                    col_def += " PRIMARY KEY"
                if col_nullable != "on":
                    col_def += " NOT NULL"
                if col_default:
                    col_def += f" DEFAULT {col_default}"
                col_defs.append(col_def)

            if not col_defs:
                col_defs = ['id SERIAL PRIMARY KEY', '"created_at" TIMESTAMPTZ DEFAULT NOW()']

            # Create schema if needed
            with pg_engine.begin() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
                create_sql = (
                    f"CREATE TABLE IF NOT EXISTS {schema}.{table_name} (\n  "
                    + ",\n  ".join(col_defs)
                    + "\n)"
                )
                conn.execute(text(create_sql))
            flash(f"Table {schema}.{table_name} created successfully!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for("dashboard"))


# ============== Routes: PostgreSQL - Drop Table ==============
@app.route("/pg/drop-table/<schema>/<table_name>", methods=["POST"])
@login_required
def pg_drop_table(schema, table_name):
    """Drop a table."""
    if not pg_connected:
        flash("Cannot connect to PostgreSQL.", "danger")
        return redirect(url_for("dashboard"))

    confirm = request.form.get("confirm_name", "")
    expected = f"{schema}.{table_name}"
    if confirm != expected:
        flash(f'Please type exactly "{expected}" to confirm table deletion.', "danger")
        return redirect(url_for("dashboard"))

    try:
        with pg_engine.begin() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{table_name}" CASCADE'))
        flash(f"Table {expected} dropped.", "success")
    except Exception as e:
        flash(f"Error dropping table: {e}", "danger")

    return redirect(url_for("dashboard"))


# ============== Routes: PostgreSQL - Raw SQL ==============
@app.route("/pg/sql", methods=["GET"])
@login_required
def pg_sql_form():
    return render_template("pg_sql.html")


@app.route("/pg/sql", methods=["POST"])
@login_required
def pg_sql_execute():
    """Execute raw SQL and return results."""
    if not pg_connected:
        return jsonify({"error": "Cannot connect to PostgreSQL."}), 500

    raw_sql_val = request.form.get("raw_sql", "").strip()
    if not raw_sql_val:
        return jsonify({"error": "Please enter SQL."}), 400

    try:
        is_select = raw_sql_val.strip().upper().startswith("SELECT") or raw_sql_val.strip().upper().startswith("WITH")
        is_explain = raw_sql_val.strip().upper().startswith("EXPLAIN")

        if is_select or is_explain:
            with pg_engine.connect() as conn:
                result = conn.execute(text(raw_sql_val))
                if result.returns_rows:
                    columns = list(result.keys())
                    rows = [list(row) for row in result.fetchall()]
                    # Limit to 500 rows for display
                    truncated = len(rows) >= 500
                    if truncated:
                        rows = rows[:500]
                    return jsonify(
                        {
                            "columns": columns,
                            "rows": rows,
                            "row_count": len(rows),
                            "truncated": truncated,
                            "is_select": True,
                        }
                    )
                else:
                    return jsonify(
                        {"message": "Query executed (no rows returned).", "is_select": False}
                    )
        else:
            with pg_engine.begin() as conn:
                result = conn.execute(text(raw_sql_val))
            return jsonify(
                {
                    "message": f"Command executed. Rows affected: {result.rowcount if hasattr(result, 'rowcount') else 'N/A'}",
                    "is_select": False,
                }
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ============== Routes: Redis - View Logs ==============
@app.route("/redis/logs")
@login_required
def redis_logs():
    """View Redis keys and values (log viewer)."""
    if not redis_connected:
        flash("Cannot connect to Redis.", "danger")
        return redirect(url_for("dashboard"))

    pattern = request.args.get("pattern", "*")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)

    try:
        all_keys = []
        # Scan keys safely
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=100)
            all_keys.extend(keys)
            if cursor == 0:
                break

        all_keys.sort()
        total_keys = len(all_keys)

        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        page_keys = all_keys[start:end]

        # Get values
        key_values = []
        for key in page_keys:
            try:
                key_type = redis_client.type(key)
                ttl = redis_client.ttl(key)
                if key_type == "string":
                    val = redis_client.get(key)
                    # Truncate long values
                    display_val = val[:500] + "..." if val and len(val) > 500 else val
                elif key_type == "hash":
                    val = redis_client.hgetall(key)
                    display_val = str(val)[:500]
                elif key_type == "list":
                    length = redis_client.llen(key)
                    val = f"List with {length} items"
                    display_val = val
                elif key_type == "set":
                    length = redis_client.scard(key)
                    val = f"Set with {length} members"
                    display_val = val
                elif key_type == "zset":
                    length = redis_client.zcard(key)
                    val = f"Sorted Set with {length} members"
                    display_val = val
                else:
                    val = "Unknown type"
                    display_val = val

                key_values.append(
                    {
                        "key": key,
                        "type": key_type,
                        "ttl": ttl if ttl != -2 else "Key not found",
                        "value": display_val,
                        "full_value": str(val) if isinstance(val, (dict, list)) else val,
                    }
                )
            except Exception as e:
                key_values.append(
                    {
                        "key": key,
                        "type": "error",
                        "ttl": "N/A",
                        "value": f"Error: {e}",
                        "full_value": str(e),
                    }
                )

        total_pages = max(1, (total_keys + per_page - 1) // per_page)

    except Exception as e:
        flash(f"Error reading Redis: {e}", "danger")
        return redirect(url_for("dashboard"))

    return render_template(
        "redis_logs.html",
        key_values=key_values,
        pattern=pattern,
        page=page,
        per_page=per_page,
        total_keys=total_keys,
        total_pages=total_pages,
    )


# ============== Routes: Redis - Delete Key ==============
@app.route("/redis/delete-key", methods=["POST"])
@login_required
def redis_delete_key():
    """Delete a Redis key."""
    if not redis_connected:
        flash("Cannot connect to Redis.", "danger")
        return redirect(url_for("redis_logs"))

    key = request.form.get("key", "").strip()
    pattern = request.form.get("current_pattern", "*")
    page = request.form.get("current_page", 1)

    if not key:
        flash("Please provide a key to delete.", "danger")
        return redirect(url_for("redis_logs", pattern=pattern, page=page))

    try:
        result = redis_client.delete(key)
        if result:
            flash(f"Key deleted: {key}", "success")
        else:
            flash(f"Key does not exist: {key}", "warning")
    except Exception as e:
        flash(f"Error deleting key: {e}", "danger")

    return redirect(url_for("redis_logs", pattern=pattern, page=page))


# ============== Routes: Redis - Add Key ==============
@app.route("/redis/add-key", methods=["POST"])
@login_required
def redis_add_key():
    """Add a new key-value to Redis."""
    if not redis_connected:
        flash("Cannot connect to Redis.", "danger")
        return redirect(url_for("redis_logs"))

    key = request.form.get("new_key", "").strip()
    value = request.form.get("new_value", "").strip()
    key_type = request.form.get("new_type", "string")
    ttl = request.form.get("new_ttl", "").strip()

    if not key or not value:
        flash("Please enter key and value.", "danger")
        return redirect(url_for("redis_logs"))

    try:
        if key_type == "string":
            redis_client.set(key, value)
        elif key_type == "list":
            redis_client.rpush(key, value)
        elif key_type == "set":
            redis_client.sadd(key, value)
        elif key_type == "hash":
            # value format: field1=val1,field2=val2
            pairs = dict(p.split("=", 1) for p in value.split(",") if "=" in p)
            if pairs:
                redis_client.hset(key, mapping=pairs)
            else:
                flash("Hash format required: field1=value1,field2=value2", "danger")
                return redirect(url_for("redis_logs"))
        else:
            redis_client.set(key, value)

        if ttl:
            redis_client.expire(key, int(ttl))

        flash(f"Key added: {key}", "success")
    except Exception as e:
        flash(f"Error adding key: {e}", "danger")

    return redirect(url_for("redis_logs"))



# ============== API: Get table columns ==============
@app.route("/api/table-columns/<schema>/<table_name>")
@login_required
def api_table_columns(schema, table_name):
    """API to get column info for a table."""
    if not pg_connected:
        return jsonify({"error": "PostgreSQL not connected"}), 500
    try:
        inspector = inspect(pg_engine)
        columns = inspector.get_columns(table_name, schema=schema)
        pk = inspector.get_pk_constraint(table_name, schema=schema)
        return jsonify(
            {
                "columns": columns,
                "primary_keys": pk.get("constrained_columns", []) if pk else [],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ============== Helpers ==============
def _smart_convert(val: str, columns_info: list, col_name: str):
    """Convert form string value to appropriate Python type."""
    if val == "":
        return None
    if val.upper() == "NULL":
        return None

    # Find column type info
    col_type = None
    for c in columns_info:
        if c["name"] == col_name:
            col_type = str(c.get("type", "")).upper()
            break

    if col_type:
        if any(
            t in col_type
            for t in ["INT", "SERIAL", "BIGINT", "SMALLINT", "INTEGER", "BIGSERIAL"]
        ):
            try:
                return int(val)
            except ValueError:
                return val
        if any(t in col_type for t in ["FLOAT", "DOUBLE", "REAL", "NUMERIC", "DECIMAL"]):
            try:
                return float(val)
            except ValueError:
                return val
        if "BOOL" in col_type:
            return val.lower() in ("true", "1", "yes", "on")
        if "JSON" in col_type:
            import json

            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return val
        if "ARRAY" in col_type:
            # Simple array parsing: {a,b,c}
            val = val.strip()
            if val.startswith("{") and val.endswith("}"):
                import ast

                try:
                    return ast.literal_eval(val)
                except (ValueError, SyntaxError):
                    return [x.strip() for x in val[1:-1].split(",")]
            return [x.strip() for x in val.split(",")]

    return val


# ============== Run ==============
if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)