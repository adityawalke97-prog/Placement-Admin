import os
from datetime import timedelta
from functools import wraps

import pymysql
from dotenv import load_dotenv

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify
)


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "ADMIN_SECRET_KEY",
    "change-this-secret-key"
)

# Admin login 30 days
app.permanent_session_lifetime = timedelta(days=30)


# =========================================================
# DATABASE
# =========================================================

def get_db():
    """
    Create database connection.

    Supports TiDB Cloud / MySQL.
    """

    host = os.getenv("DB_HOST")
    port = int(os.getenv("DB_PORT", "4000"))
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")

    if not host:
        raise RuntimeError("DB_HOST is missing in .env")

    if not user:
        raise RuntimeError("DB_USER is missing in .env")

    if not database:
        raise RuntimeError("DB_NAME is missing in .env")

    # TiDB Cloud TLS
    ssl_config = None

    # Enable SSL by default for TiDB/remote DB
    use_ssl = os.getenv(
        "DB_SSL",
        "true"
    ).lower() == "true"

    if use_ssl:
        ssl_config = {
            "ssl": True
        }

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=10,
        read_timeout=20,
        write_timeout=20,
        ssl=ssl_config
    )


# =========================================================
# ADMIN LOGIN PROTECTION
# =========================================================

def admin_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not session.get("admin_id"):
            return redirect(
                url_for("login")
            )

        return func(*args, **kwargs)

    return wrapper


# =========================================================
# CLOSE CONNECTION
# =========================================================

def close_db(connection):
    if connection:
        try:
            if connection.open:
                connection.close()
        except Exception:
            pass


# =========================================================
# TABLE EXISTS
# =========================================================

def table_exists(connection, table_name):

    cursor = None

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_name = %s
            """,
            (table_name,)
        )

        result = cursor.fetchone()

        return bool(
            result and result["total"] > 0
        )

    except pymysql.MySQLError:

        return False

    finally:

        if cursor:

            try:
                cursor.close()
            except Exception:
                pass


# =========================================================
# COLUMN EXISTS
# =========================================================

def column_exists(
    connection,
    table_name,
    column_name
):

    cursor = None

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
            AND table_name = %s
            AND column_name = %s
            """,
            (
                table_name,
                column_name
            )
        )

        result = cursor.fetchone()

        return bool(
            result and result["total"] > 0
        )

    except pymysql.MySQLError:

        return False

    finally:

        if cursor:

            try:
                cursor.close()
            except Exception:
                pass


# =========================================================
# SAFE COUNT
# =========================================================

def safe_count(
    connection,
    table_name
):

    allowed_tables = {
        "users",
        "mock_questions",
        "interview_questions",
        "results"
    }

    if table_name not in allowed_tables:
        return 0

    if not table_exists(
        connection,
        table_name
    ):
        return 0

    cursor = None

    try:

        cursor = connection.cursor()

        cursor.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM `{table_name}`
            """
        )

        result = cursor.fetchone()

        return int(
            result["total"]
            if result
            else 0
        )

    except pymysql.MySQLError:

        return 0

    finally:

        if cursor:

            try:
                cursor.close()
            except Exception:
                pass


# =========================================================
# DASHBOARD STATISTICS
# =========================================================

def get_dashboard_stats():

    connection = None

    stats = {
        "users": 0,
        "mock_questions": 0,
        "interview_questions": 0,
        "results": 0,
        "average_score": 0,
        "new_users": 0,
        "active_users": 0
    }

    try:

        connection = get_db()

        # =================================================
        # TOTAL USERS
        # =================================================

        stats["users"] = safe_count(
            connection,
            "users"
        )

        # =================================================
        # MOCK QUESTIONS
        # =================================================

        stats["mock_questions"] = safe_count(
            connection,
            "mock_questions"
        )

        # =================================================
        # INTERVIEW QUESTIONS
        # =================================================

        stats["interview_questions"] = safe_count(
            connection,
            "interview_questions"
        )

        # =================================================
        # TEST ATTEMPTS
        # =================================================

        stats["results"] = safe_count(
            connection,
            "results"
        )

        # =================================================
        # AVERAGE SCORE
        # =================================================

        if table_exists(
            connection,
            "results"
        ):

            cursor = connection.cursor()

            try:

                if column_exists(
                    connection,
                    "results",
                    "percentage"
                ):

                    cursor.execute(
                        """
                        SELECT
                            COALESCE(
                                AVG(percentage),
                                0
                            ) AS average_score
                        FROM results
                        """
                    )

                elif column_exists(
                    connection,
                    "results",
                    "score"
                ):

                    cursor.execute(
                        """
                        SELECT
                            COALESCE(
                                AVG(score),
                                0
                            ) AS average_score
                        FROM results
                        """
                    )

                else:
                    cursor = None

                if cursor:

                    row = cursor.fetchone()

                    if row:

                        try:
                            stats["average_score"] = round(
                                float(
                                    row.get(
                                        "average_score",
                                        0
                                    ) or 0
                                ),
                                1
                            )
                        except (
                            ValueError,
                            TypeError
                        ):
                            stats["average_score"] = 0

            except pymysql.MySQLError:

                stats["average_score"] = 0

            finally:

                if cursor:

                    try:
                        cursor.close()
                    except Exception:
                        pass

        # =================================================
        # NEW USERS - LAST 30 DAYS
        # =================================================

        if (
            table_exists(
                connection,
                "users"
            )
            and
            column_exists(
                connection,
                "users",
                "created_at"
            )
        ):

            cursor = connection.cursor()

            try:

                cursor.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM users
                    WHERE created_at >=
                    DATE_SUB(
                        NOW(),
                        INTERVAL 30 DAY
                    )
                    """
                )

                row = cursor.fetchone()

                stats["new_users"] = int(
                    row["total"]
                    if row
                    else 0
                )

            except pymysql.MySQLError:

                stats["new_users"] = 0

            finally:

                cursor.close()

        # =================================================
        # ACTIVE USERS - LAST 30 DAYS
        # =================================================

        if (
            table_exists(
                connection,
                "users"
            )
            and
            column_exists(
                connection,
                "users",
                "last_login"
            )
        ):

            cursor = connection.cursor()

            try:

                cursor.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM users
                    WHERE last_login >=
                    DATE_SUB(
                        NOW(),
                        INTERVAL 30 DAY
                    )
                    """
                )

                row = cursor.fetchone()

                stats["active_users"] = int(
                    row["total"]
                    if row
                    else 0
                )

            except pymysql.MySQLError:

                stats["active_users"] = 0

            finally:

                cursor.close()

        return stats

    except Exception:

        return stats

    finally:

        close_db(connection)


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if session.get("admin_id"):

        return redirect(
            url_for("dashboard")
        )

    return redirect(
        url_for("login")
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    # Already logged in
    if session.get("admin_id"):

        return redirect(
            url_for("dashboard")
        )

    admin_email = os.getenv(
        "ADMIN_EMAIL",
        ""
    ).strip().lower()

    admin_password = os.getenv(
        "ADMIN_PASSWORD",
        ""
    )

    admin_name = os.getenv(
        "ADMIN_NAME",
        "Admin"
    )

    # =====================================================
    # CHECK ADMIN CONFIG
    # =====================================================

    if not admin_email or not admin_password:

        return """
        <html>
        <head>
            <title>Admin Configuration Error</title>
        </head>
        <body>
            <h2>Admin login is not configured.</h2>
            <p>
                Please add ADMIN_EMAIL and
                ADMIN_PASSWORD to your .env file.
            </p>
        </body>
        </html>
        """

    # =====================================================
    # POST LOGIN
    # =====================================================

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if (
            email == admin_email
            and
            password == admin_password
        ):

            session.permanent = True

            session["admin_id"] = 1

            session["admin_name"] = admin_name

            session["admin_email"] = admin_email

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid admin email or password.",
            "error"
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@admin_required
def dashboard():

    stats = get_dashboard_stats()

    connection = None

    students = []

    categories = []

    try:

        connection = get_db()

        # =================================================
        # RECENT STUDENTS
        # =================================================

        if table_exists(
            connection,
            "users"
        ):

            cursor = connection.cursor()

            try:

                columns = [
                    "id"
                ]

                if column_exists(
                    connection,
                    "users",
                    "name"
                ):
                    columns.append("name")

                if column_exists(
                    connection,
                    "users",
                    "email"
                ):
                    columns.append("email")

                select_columns = ", ".join(
                    columns
                )

                cursor.execute(
                    f"""
                    SELECT {select_columns}
                    FROM users
                    ORDER BY id DESC
                    LIMIT 10
                    """
                )

                students = cursor.fetchall()

            except pymysql.MySQLError:

                students = []

            finally:

                cursor.close()

        # =================================================
        # SUBJECT PERFORMANCE
        # =================================================

        if (
            table_exists(
                connection,
                "results"
            )
            and
            column_exists(
                connection,
                "results",
                "subject"
            )
        ):

            cursor = connection.cursor()

            try:

                if column_exists(
                    connection,
                    "results",
                    "percentage"
                ):

                    cursor.execute(
                        """
                        SELECT

                            COALESCE(
                                subject,
                                'General'
                            ) AS category,

                            ROUND(
                                AVG(
                                    COALESCE(
                                        percentage,
                                        0
                                    )
                                ),
                                1
                            ) AS average_score,

                            COUNT(*) AS attempts

                        FROM results

                        GROUP BY subject

                        ORDER BY average_score DESC
                        """
                    )

                elif column_exists(
                    connection,
                    "results",
                    "score"
                ):

                    cursor.execute(
                        """
                        SELECT

                            COALESCE(
                                subject,
                                'General'
                            ) AS category,

                            ROUND(
                                AVG(
                                    COALESCE(
                                        score,
                                        0
                                    )
                                ),
                                1
                            ) AS average_score,

                            COUNT(*) AS attempts

                        FROM results

                        GROUP BY subject

                        ORDER BY average_score DESC
                        """
                    )

                categories = cursor.fetchall()

            except pymysql.MySQLError:

                categories = []

            finally:

                cursor.close()

    except Exception:

        students = []

        categories = []

    finally:

        close_db(connection)

    return render_template(
        "dashboard.html",
        stats=stats,
        students=students,
        categories=categories
    )


# =========================================================
# USERS
# =========================================================

@app.route("/users")
@admin_required
def users():

    search = request.args.get(
        "q",
        ""
    ).strip()

    connection = None

    users_list = []

    try:

        connection = get_db()

        if not table_exists(
            connection,
            "users"
        ):

            stats = get_dashboard_stats()

            return render_template(
                "users.html",
                users=[],
                search=search,
                stats=stats
            )

        cursor = connection.cursor()

        try:

            # Check columns
            has_name = column_exists(
                connection,
                "users",
                "name"
            )

            has_email = column_exists(
                connection,
                "users",
                "email"
            )

            has_role = column_exists(
                connection,
                "users",
                "role"
            )

            has_created = column_exists(
                connection,
                "users",
                "created_at"
            )

            select_columns = ["id"]

            if has_name:
                select_columns.append("name")

            if has_email:
                select_columns.append("email")

            if has_role:
                select_columns.append("role")

            if has_created:
                select_columns.append("created_at")

            query = f"""
                SELECT
                    {", ".join(select_columns)}
                FROM users
            """

            params = []

            if search:

                conditions = []

                if has_name:
                    conditions.append(
                        "name LIKE %s"
                    )
                    params.append(
                        f"%{search}%"
                    )

                if has_email:
                    conditions.append(
                        "email LIKE %s"
                    )
                    params.append(
                        f"%{search}%"
                    )

                if conditions:

                    query += (
                        " WHERE "
                        +
                        " OR ".join(
                            conditions
                        )
                    )

            query += """
                ORDER BY id DESC
                LIMIT 200
            """

            cursor.execute(
                query,
                params
            )

            users_list = cursor.fetchall()

        finally:

            cursor.close()

    except Exception as error:

        flash(
            f"Unable to load users: {error}",
            "error"
        )

    finally:

        close_db(connection)

    stats = get_dashboard_stats()

    return render_template(
        "users.html",
        users=users_list,
        search=search,
        stats=stats
    )


# =========================================================
# ANALYTICS API
# =========================================================

@app.route("/api/analytics")
@admin_required
def analytics():

    stats = get_dashboard_stats()

    return jsonify(stats)


# =========================================================
# RECENT RESULTS API
# =========================================================

@app.route("/api/recent-results")
@admin_required
def recent_results():

    connection = None

    try:

        connection = get_db()

        if not table_exists(
            connection,
            "results"
        ):

            return jsonify([])

        cursor = connection.cursor()

        try:

            # =================================================
            # Build dynamic SELECT
            # =================================================

            fields = [
                "r.id AS result_id",
                "r.user_id"
            ]

            if table_exists(
                connection,
                "users"
            ):

                if column_exists(
                    connection,
                    "users",
                    "name"
                ):
                    fields.append(
                        "u.name"
                    )

                if column_exists(
                    connection,
                    "users",
                    "email"
                ):
                    fields.append(
                        "u.email"
                    )

            result_columns = [
                ("subject", "r.subject"),
                ("score", "r.score"),
                (
                    "percentage",
                    "r.percentage"
                ),
                (
                    "total_questions",
                    "r.total_questions"
                ),
                (
                    "test_date",
                    "r.test_date"
                )
            ]

            for column_name, sql_name in result_columns:

                if column_exists(
                    connection,
                    "results",
                    column_name
                ):
                    fields.append(sql_name)

            if table_exists(
                connection,
                "users"
            ):

                query = f"""
                    SELECT
                        {", ".join(fields)}
                    FROM results r
                    LEFT JOIN users u
                        ON u.id = r.user_id
                    ORDER BY r.id DESC
                    LIMIT 20
                """

            else:

                fields_without_alias = []

                for field in fields:
                    fields_without_alias.append(
                        field.replace(
                            "r.",
                            ""
                        )
                    )

                query = f"""
                    SELECT
                        {", ".join(
                            fields_without_alias
                        )}
                    FROM results
                    ORDER BY id DESC
                    LIMIT 20
                """

            cursor.execute(query)

            rows = cursor.fetchall()

            return jsonify(rows)

        finally:

            cursor.close()

    except Exception as error:

        return jsonify({
            "error": str(error)
        }), 500

    finally:

        close_db(connection)


# =========================================================
# STUDENT DETAIL API
# =========================================================

@app.route(
    "/api/student/<int:user_id>"
)
@admin_required
def student_detail(user_id):

    connection = None

    try:

        connection = get_db()

        # =================================================
        # USER
        # =================================================

        if not table_exists(
            connection,
            "users"
        ):

            return jsonify({
                "error": "Users table not found"
            }), 404

        user_columns = ["id"]

        possible_user_columns = [
            "name",
            "email",
            "created_at",
            "role",
            "subscription_status",
            "subscription_expiry",
            "email_verified",
            "login_provider",
            "last_login"
        ]

        for column in possible_user_columns:

            if column_exists(
                connection,
                "users",
                column
            ):
                user_columns.append(
                    column
                )

        cursor = connection.cursor()

        try:

            cursor.execute(
                f"""
                SELECT
                    {", ".join(user_columns)}
                FROM users
                WHERE id = %s
                """,
                (user_id,)
            )

            user = cursor.fetchone()

        finally:

            cursor.close()

        if not user:

            return jsonify({
                "error": "Student not found"
            }), 404

        # =================================================
        # RESULTS
        # =================================================

        results = []

        if table_exists(
            connection,
            "results"
        ):

            result_columns = ["id"]

            possible_result_columns = [
                "user_id",
                "score",
                "test_date",
                "total_questions",
                "percentage",
                "subject"
            ]

            for column in possible_result_columns:

                if column_exists(
                    connection,
                    "results",
                    column
                ):
                    result_columns.append(
                        column
                    )

            cursor = connection.cursor()

            try:

                cursor.execute(
                    f"""
                    SELECT
                        {", ".join(
                            result_columns
                        )}
                    FROM results
                    WHERE user_id = %s
                    ORDER BY id DESC
                    """,
                    (user_id,)
                )

                results = cursor.fetchall()

            finally:

                cursor.close()

        # =================================================
        # SUMMARY
        # =================================================

        total_attempts = len(results)

        average_percentage = 0

        if results:

            values = []

            for result in results:

                value = result.get(
                    "percentage",
                    0
                ) or 0

                try:

                    values.append(
                        float(value)
                    )

                except (
                    ValueError,
                    TypeError
                ):

                    pass

            if values:

                average_percentage = round(
                    sum(values) / len(values),
                    1
                )

        return jsonify({

            "user": user,

            "summary": {

                "total_attempts":
                    total_attempts,

                "average_percentage":
                    average_percentage
            },

            "results":
                results
        })

    except Exception as error:

        return jsonify({
            "error": str(error)
        }), 500

    finally:

        close_db(connection)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health")
def health():

    connection = None

    try:

        connection = get_db()

        cursor = connection.cursor()

        try:

            cursor.execute(
                "SELECT 1 AS test"
            )

            cursor.fetchone()

        finally:

            cursor.close()

        return jsonify({

            "status": "ok",

            "database": "connected"
        })

    except Exception as error:

        return jsonify({

            "status": "error",

            "database": str(error)
        }), 500

    finally:

        close_db(connection)


# =========================================================
# ADMIN INFO
# =========================================================

@app.route("/api/admin-info")
@admin_required
def admin_info():

    return jsonify({

        "id":
            session.get(
                "admin_id"
            ),

        "name":
            session.get(
                "admin_name"
            ),

        "email":
            session.get(
                "admin_email"
            ),

        "logged_in":
            True
    })


# =========================================================
# DATABASE ERROR HANDLER
# =========================================================

@app.errorhandler(
    pymysql.MySQLError
)
def database_error(error):

    return jsonify({

        "error":
            "Database error",

        "message":
            str(error)

    }), 500


# =========================================================
# MOCK QUESTIONS
# =========================================================

@app.route("/mock-questions")
@admin_required
def mock_questions():

    connection = None

    questions = []

    search = request.args.get(
        "q",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    try:

        connection = get_db()

        if not table_exists(
            connection,
            "mock_questions"
        ):

            return render_template(
                "mock_questions.html",
                questions=[],
                total_questions=0,
                java_count=0,
                python_count=0,
                other_count=0,
                search=search,
                category=category
            )

        cursor = connection.cursor()

        try:

            # =================================================
            # CHECK COLUMNS
            # =================================================

            required_columns = [
                "id",
                "question",
                "option1",
                "option2",
                "option3",
                "option4",
                "answer",
                "category"
            ]

            existing_columns = []

            for column in required_columns:

                if column == "id" or column_exists(
                    connection,
                    "mock_questions",
                    column
                ):
                    existing_columns.append(
                        column
                    )

            query = f"""
                SELECT
                    {", ".join(
                        existing_columns
                    )}
                FROM mock_questions
                WHERE 1=1
            """

            params = []

            if search and "question" in existing_columns:

                query += """
                    AND question LIKE %s
                """

                params.append(
                    f"%{search}%"
                )

            if category and "category" in existing_columns:

                query += """
                    AND category = %s
                """

                params.append(
                    category
                )

            query += """
                ORDER BY id DESC
                LIMIT 200
            """

            cursor.execute(
                query,
                params
            )

            questions = cursor.fetchall()

            # =================================================
            # TOTAL
            # =================================================

            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM mock_questions
                """
            )

            row = cursor.fetchone()

            total_questions = int(
                row["total"]
                if row
                else 0
            )

            # =================================================
            # JAVA
            # =================================================

            java_count = 0

            if column_exists(
                connection,
                "mock_questions",
                "category"
            ):

                cursor.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM mock_questions
                    WHERE category = 'Java'
                    """
                )

                java_count = int(
                    cursor.fetchone()["total"]
                )

            # =================================================
            # PYTHON
            # =================================================

            python_count = 0

            if column_exists(
                connection,
                "mock_questions",
                "category"
            ):

                cursor.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM mock_questions
                    WHERE category = 'Python'
                    """
                )

                python_count = int(
                    cursor.fetchone()["total"]
                )

            other_count = max(
                0,
                total_questions
                - java_count
                - python_count
            )

        finally:

            cursor.close()

        return render_template(
            "mock_questions.html",
            questions=questions,
            total_questions=total_questions,
            java_count=java_count,
            python_count=python_count,
            other_count=other_count,
            search=search,
            category=category
        )

    except Exception as error:

        flash(
            f"Unable to load mock questions: {error}",
            "error"
        )

        return render_template(
            "mock_questions.html",
            questions=[],
            total_questions=0,
            java_count=0,
            python_count=0,
            other_count=0,
            search=search,
            category=category
        )

    finally:

        close_db(connection)


# =========================================================
# ADD MOCK QUESTION
# =========================================================

@app.route(
    "/mock-questions/add",
    methods=["GET", "POST"]
)
@admin_required
def add_mock_question():

    if request.method == "POST":

        question = request.form.get(
            "question",
            ""
        ).strip()

        option1 = request.form.get(
            "option1",
            ""
        ).strip()

        option2 = request.form.get(
            "option2",
            ""
        ).strip()

        option3 = request.form.get(
            "option3",
            ""
        ).strip()

        option4 = request.form.get(
            "option4",
            ""
        ).strip()

        answer = request.form.get(
            "answer",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        # =================================================
        # VALIDATION
        # =================================================

        if not all([
            question,
            option1,
            option2,
            option3,
            option4,
            answer,
            category
        ]):

            flash(
                "All fields are required.",
                "error"
            )

            return render_template(
                "add_mock_question.html"
            )

        connection = None

        try:

            connection = get_db()

            if not table_exists(
                connection,
                "mock_questions"
            ):

                flash(
                    "mock_questions table does not exist.",
                    "error"
                )

                return render_template(
                    "add_mock_question.html"
                )

            required = [
                "question",
                "option1",
                "option2",
                "option3",
                "option4",
                "answer",
                "category"
            ]

            missing = []

            for column in required:

                if not column_exists(
                    connection,
                    "mock_questions",
                    column
                ):

                    missing.append(
                        column
                    )

            if missing:

                flash(
                    "Missing columns: "
                    + ", ".join(missing),
                    "error"
                )

                return render_template(
                    "add_mock_question.html"
                )

            cursor = connection.cursor()

            try:

                cursor.execute(
                    """
                    INSERT INTO mock_questions
                    (
                        question,
                        option1,
                        option2,
                        option3,
                        option4,
                        answer,
                        category
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        question,
                        option1,
                        option2,
                        option3,
                        option4,
                        answer,
                        category
                    )
                )

            finally:

                cursor.close()

            flash(
                "Mock question added successfully.",
                "success"
            )

            return redirect(
                url_for("mock_questions")
            )

        except Exception as error:

            flash(
                f"Unable to add question: {error}",
                "error"
            )

            return render_template(
                "add_mock_question.html"
            )

        finally:

            close_db(connection)

    return render_template(
        "add_mock_question.html"
    )


# =========================================================
# AI ANALYTICS
# =========================================================

@app.route("/ai-analytics")
@admin_required
def ai_analytics():

    stats = get_dashboard_stats()

    connection = None

    data = {

        "total_students":
            stats["users"],

        "active_students":
            stats["active_users"],

        "test_attempts":
            stats["results"],

        "average_score":
            stats["average_score"],

        "mock_questions":
            stats["mock_questions"],

        "interview_questions":
            stats["interview_questions"],

        "subjects": []
    }

    try:

        connection = get_db()

        if (
            table_exists(
                connection,
                "results"
            )
            and
            column_exists(
                connection,
                "results",
                "subject"
            )
        ):

            cursor = connection.cursor()

            try:

                if column_exists(
                    connection,
                    "results",
                    "percentage"
                ):

                    cursor.execute(
                        """
                        SELECT
                            COALESCE(
                                subject,
                                'General'
                            ) AS subject,

                            COUNT(*) AS attempts,

                            ROUND(
                                AVG(
                                    COALESCE(
                                        percentage,
                                        0
                                    )
                                ),
                                1
                            ) AS average_score

                        FROM results

                        GROUP BY subject

                        ORDER BY attempts DESC
                        """
                    )

                elif column_exists(
                    connection,
                    "results",
                    "score"
                ):

                    cursor.execute(
                        """
                        SELECT
                            COALESCE(
                                subject,
                                'General'
                            ) AS subject,

                            COUNT(*) AS attempts,

                            ROUND(
                                AVG(
                                    COALESCE(
                                        score,
                                        0
                                    )
                                ),
                                1
                            ) AS average_score

                        FROM results

                        GROUP BY subject

                        ORDER BY attempts DESC
                        """
                    )

                data["subjects"] = (
                    cursor.fetchall()
                )

            finally:

                cursor.close()

    except Exception:

        data["subjects"] = []

    finally:

        close_db(connection)

    return render_template(
        "ai_analytics.html",
        stats=stats,
        data=data
    )


# =========================================================
# ANALYTICS PAGE
# =========================================================

@app.route("/analytics")
@admin_required
def analytics_page():

    stats = get_dashboard_stats()

    return render_template(
        "analytics.html",
        stats=stats
    )


# =========================================================
# SETTINGS
# =========================================================

@app.route("/settings")
@admin_required
def settings():

    return render_template(
        "settings.html",
        admin_name=session.get(
            "admin_name",
            "Admin"
        ),
        admin_email=session.get(
            "admin_email",
            ""
        )
    )


# =========================================================
# INTERVIEW QUESTIONS
# =========================================================

@app.route("/interview-questions")
@admin_required
def interview_questions():

    connection = None

    questions = []

    try:

        connection = get_db()

        if not table_exists(
            connection,
            "interview_questions"
        ):

            return render_template(
                "interview_questions.html",
                questions=[],
                total=0
            )

        cursor = connection.cursor()

        try:

            cursor.execute(
                """
                SELECT *
                FROM interview_questions
                ORDER BY id DESC
                LIMIT 500
                """
            )

            questions = cursor.fetchall()

        finally:

            cursor.close()

        total = safe_count(
            connection,
            "interview_questions"
        )

        return render_template(
            "interview_questions.html",
            questions=questions,
            total=total
        )

    except Exception as error:

        flash(
            f"Database error: {error}",
            "error"
        )

        return render_template(
            "interview_questions.html",
            questions=[],
            total=0
        )

    finally:

        close_db(connection)


# =========================================================
# RESULTS PAGE
# =========================================================

@app.route("/results")
@admin_required
def results():

    connection = None

    results_list = []

    try:

        connection = get_db()

        if not table_exists(
            connection,
            "results"
        ):

            return render_template(
                "results.html",
                results=[],
                total=0
            )

        # =================================================
        # DYNAMIC RESULT COLUMNS
        # =================================================

        result_columns = [
            "id",
            "user_id",
            "score",
            "total_questions",
            "percentage",
            "test_date",
            "subject"
        ]

        existing_result_columns = []

        for column in result_columns:

            if column == "id":

                existing_result_columns.append(
                    column
                )

            elif column_exists(
                connection,
                "results",
                column
            ):

                existing_result_columns.append(
                    column
                )

        cursor = connection.cursor()

        try:

            if table_exists(
                connection,
                "users"
            ):

                user_fields = []

                if column_exists(
                    connection,
                    "users",
                    "name"
                ):
                    user_fields.append(
                        "u.name"
                    )

                if column_exists(
                    connection,
                    "users",
                    "email"
                ):
                    user_fields.append(
                        "u.email"
                    )

                fields = [
                    f"r.{column}"
                    for column in
                    existing_result_columns
                ]

                fields.extend(
                    user_fields
                )

                cursor.execute(
                    f"""
                    SELECT
                        {", ".join(fields)}
                    FROM results r

                    LEFT JOIN users u
                        ON u.id = r.user_id

                    ORDER BY r.id DESC

                    LIMIT 500
                    """
                )

            else:

                cursor.execute(
                    f"""
                    SELECT
                        {", ".join(
                            existing_result_columns
                        )}
                    FROM results

                    ORDER BY id DESC

                    LIMIT 500
                    """
                )

            results_list = cursor.fetchall()

        finally:

            cursor.close()

        total = safe_count(
            connection,
            "results"
        )

        return render_template(
            "results.html",
            results=results_list,
            total=total
        )

    except Exception as error:

        flash(
            f"Database error: {error}",
            "error"
        )

        return render_template(
            "results.html",
            results=[],
            total=0
        )

    finally:

        close_db(connection)


# =========================================================
# RESULT DETAILS
# =========================================================

@app.route(
    "/result/<int:result_id>",
    endpoint="result_details"
)
@admin_required
def result_details(result_id):

    connection = None

    try:

        connection = get_db()

        if not table_exists(
            connection,
            "results"
        ):

            flash(
                "Results table not found.",
                "error"
            )

            return redirect(
                url_for("results")
            )

        cursor = connection.cursor()

        try:

            if table_exists(
                connection,
                "users"
            ):

                cursor.execute(
                    """
                    SELECT
                        r.*,
                        u.name AS student_name,
                        u.email AS student_email

                    FROM results r

                    LEFT JOIN users u
                        ON u.id = r.user_id

                    WHERE r.id = %s

                    LIMIT 1
                    """,
                    (result_id,)
                )

            else:

                cursor.execute(
                    """
                    SELECT *
                    FROM results
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (result_id,)
                )

            result = cursor.fetchone()

        finally:

            cursor.close()

        if not result:

            flash(
                "Result not found.",
                "error"
            )

            return redirect(
                url_for("results")
            )

        return render_template(
            "result_details.html",
            result=result
        )

    except Exception as error:

        flash(
            f"Database error: {error}",
            "error"
        )

        return redirect(
            url_for("results")
        )

    finally:

        close_db(connection)


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    return jsonify({
        "error": "Page not found"
    }), 404


@app.errorhandler(500)
def internal_server_error(error):

    return jsonify({
        "error": "Internal server error"
    }), 500


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "5001"
        )
    )

    # Debug should be false on Render/production
    debug_mode = (
        os.getenv(
            "FLASK_DEBUG",
            "false"
        ).lower()
        == "true"
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug_mode
    )