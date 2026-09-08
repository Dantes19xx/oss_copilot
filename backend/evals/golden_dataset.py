"""Golden dataset for the review pipeline: 30 labeled file diffs across 5 categories.

Each example is a single-file patch (the same shape `get_pr_files` returns) with a
ground-truth label. All 30 are hand-crafted (`source: "synthetic"`) rather than pulled
from real PRs — a crafted diff lets us pin down exactly one issue per example with an
unambiguous label, instead of hoping a real PR happens to isolate one and then
second-guessing our own labeling of it. The tradeoff is ecological validity: these are
smaller and cleaner than real-world diffs. Augmenting with a batch of real, manually-
labeled PR files (see `backend/mcp_server/github_client.get_pull_request_files`, already
used for live smoke tests throughout this project) is a documented follow-up, not done
here. Frozen as a Python literal (not fetched live) so eval runs are deterministic and
don't depend on GitHub being reachable or PR content not changing.

Categories (see PLAN.md section 9):
- bug: a real logic error the review should catch
- security: a real security issue (secrets, injection, unsafe eval/deserialize)
- missing_tests: new logic added with no corresponding test change
- breaking_change: a public API changed in a way that breaks callers
- clean: no real issue — tests that the model doesn't invent nitpicks (false positives)
"""

GOLDEN_DATASET = [
    # ---------------------------------------------------------------- bug (6) ----
    {
        "id": "bug-01",
        "category": "bug",
        "expected_has_issue": True,
        "expected_note": "Off-by-one: range(len(items) - 1) skips the last item.",
        "source": "synthetic",
        "filename": "inventory.py",
        "status": "modified",
        "patch": """@@ -10,7 +10,7 @@ def total_quantity(items):
-    total = 0
-    for i in range(len(items)):
-        total += items[i].quantity
-    return total
+    total = 0
+    for i in range(len(items) - 1):
+        total += items[i].quantity
+    return total""",
    },
    {
        "id": "bug-02",
        "category": "bug",
        "expected_has_issue": True,
        "expected_note": "Mutable default argument (list) shared across calls.",
        "source": "synthetic",
        "filename": "cart.py",
        "status": "modified",
        "patch": """@@ -3,7 +3,7 @@ class Cart:
-    def __init__(self, items=None):
-        self.items = items if items is not None else []
+    def __init__(self, items=[]):
+        self.items = items""",
    },
    {
        "id": "bug-03",
        "category": "bug",
        "expected_has_issue": True,
        "expected_note": "Wrong comparison operator: '=' used where '==' was intended inside the condition.",
        "source": "synthetic",
        "filename": "auth.py",
        "status": "modified",
        "patch": """@@ -20,7 +20,7 @@ def is_admin(user):
-    return user.role == "admin"
+    if user.role = "admin":
+        return True
+    return False""",
    },
    {
        "id": "bug-04",
        "category": "bug",
        "expected_has_issue": True,
        "expected_note": "Broad except swallows all exceptions and silently returns None, hiding real errors.",
        "source": "synthetic",
        "filename": "payments.py",
        "status": "modified",
        "patch": """@@ -40,9 +40,12 @@ def charge_card(card, amount):
-    response = gateway.charge(card, amount)
-    return response.transaction_id
+    try:
+        response = gateway.charge(card, amount)
+        return response.transaction_id
+    except Exception:
+        return None""",
    },
    {
        "id": "bug-05",
        "category": "bug",
        "expected_has_issue": True,
        "expected_note": "Loop variable shadows the outer 'file' being processed, so the wrong file's size is reported.",
        "source": "synthetic",
        "filename": "report.py",
        "status": "modified",
        "patch": """@@ -15,8 +15,9 @@ def summarize(file, related_files):
-    size = file.size
-    for other in related_files:
-        size += other.size
-    return size
+    size = file.size
+    for file in related_files:
+        size += file.size
+    return size""",
    },
    {
        "id": "bug-06",
        "category": "bug",
        "expected_has_issue": True,
        "expected_note": "Integer division where float division was clearly intended, silently truncating the average.",
        "source": "synthetic",
        "filename": "stats.py",
        "status": "modified",
        "patch": """@@ -8,5 +8,5 @@ def average(values):
-    return sum(values) / float(len(values))
+    return sum(values) // len(values)""",
    },
    # ----------------------------------------------------------- security (6) ----
    {
        "id": "sec-01",
        "category": "security",
        "expected_has_issue": True,
        "expected_note": "Hardcoded API key/secret committed to source.",
        "source": "synthetic",
        "filename": "config.py",
        "status": "modified",
        "patch": """@@ -1,4 +1,5 @@
 import os

-STRIPE_KEY = os.environ["STRIPE_KEY"]
+STRIPE_KEY = os.environ.get("STRIPE_KEY", "REPLACE_WITH_REAL_HARDCODED_SECRET_00000")
+DEBUG = True""",
    },
    {
        "id": "sec-02",
        "category": "security",
        "expected_has_issue": True,
        "expected_note": "SQL built via f-string interpolation — SQL injection.",
        "source": "synthetic",
        "filename": "users_db.py",
        "status": "modified",
        "patch": """@@ -12,6 +12,6 @@ def find_user(username):
-    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
+    query = f"SELECT * FROM users WHERE username = '{username}'"
+    cursor.execute(query)
     return cursor.fetchone()""",
    },
    {
        "id": "sec-03",
        "category": "security",
        "expected_has_issue": True,
        "expected_note": "Shell command built from unsanitized user input via os.system — command injection.",
        "source": "synthetic",
        "filename": "convert.py",
        "status": "modified",
        "patch": """@@ -5,6 +5,6 @@ def convert_file(user_filename):
-    subprocess.run(["ffmpeg", "-i", user_filename, "out.mp4"], check=True)
+    os.system(f"ffmpeg -i {user_filename} out.mp4")""",
    },
    {
        "id": "sec-04",
        "category": "security",
        "expected_has_issue": True,
        "expected_note": "pickle.loads on untrusted network input — unsafe deserialization, arbitrary code execution.",
        "source": "synthetic",
        "filename": "cache_client.py",
        "status": "modified",
        "patch": """@@ -18,7 +18,7 @@ def get_cached(key):
-    raw = redis_client.get(key)
-    return json.loads(raw) if raw else None
+    raw = redis_client.get(key)
+    return pickle.loads(raw) if raw else None""",
    },
    {
        "id": "sec-05",
        "category": "security",
        "expected_has_issue": True,
        "expected_note": "eval() on a user-supplied expression string — arbitrary code execution.",
        "source": "synthetic",
        "filename": "calc.py",
        "status": "modified",
        "patch": """@@ -6,5 +6,5 @@ def compute(expression):
-    return safe_eval(expression, allowed_names={"pi": 3.14159})
+    return eval(expression)""",
    },
    {
        "id": "sec-06",
        "category": "security",
        "expected_has_issue": True,
        "expected_note": "New admin-only route added without the @require_admin auth check used by sibling routes.",
        "source": "synthetic",
        "filename": "admin_routes.py",
        "status": "modified",
        "patch": """@@ -30,6 +30,11 @@ def list_users():
     return jsonify(users)

+@app.route("/admin/users/<id>", methods=["DELETE"])
+def delete_user(id):
+    db.session.delete(User.query.get(id))
+    db.session.commit()
+    return "", 204
+
 @app.route("/admin/settings", methods=["POST"])
 @require_admin
 def update_settings():""",
    },
    # ------------------------------------------------------- missing_tests (5) ----
    {
        "id": "test-01",
        "category": "missing_tests",
        "expected_has_issue": True,
        "expected_note": "New public function with real branching logic added, no test file touched.",
        "source": "synthetic",
        "filename": "discounts.py",
        "status": "modified",
        "patch": """@@ -20,3 +20,14 @@ def apply_shipping(order):
     return order
+
+def apply_bulk_discount(order):
+    if order.item_count >= 100:
+        order.total *= 0.85
+    elif order.item_count >= 20:
+        order.total *= 0.95
+    return order""",
    },
    {
        "id": "test-02",
        "category": "missing_tests",
        "expected_has_issue": True,
        "expected_note": "New edge case (negative balance) added to existing function, no test for it.",
        "source": "synthetic",
        "filename": "wallet.py",
        "status": "modified",
        "patch": """@@ -8,6 +8,9 @@ def withdraw(wallet, amount):
     if amount > wallet.balance:
         raise InsufficientFundsError()
+    if wallet.balance - amount < wallet.overdraft_limit:
+        raise OverdraftLimitError()
     wallet.balance -= amount
     return wallet""",
    },
    {
        "id": "test-03",
        "category": "missing_tests",
        "expected_has_issue": True,
        "expected_note": "New CLI flag with its own behavior branch added, no test coverage.",
        "source": "synthetic",
        "filename": "cli.py",
        "status": "modified",
        "patch": """@@ -12,6 +12,10 @@ def main():
     parser.add_argument("--verbose", action="store_true")
+    parser.add_argument("--dry-run", action="store_true")
     args = parser.parse_args()
+    if args.dry_run:
+        print("Would run:", build_plan(args))
+        return
     run(args)""",
    },
    {
        "id": "test-04",
        "category": "missing_tests",
        "expected_has_issue": True,
        "expected_note": "Bug fix (null check) with no regression test added to cover the case that was crashing.",
        "source": "synthetic",
        "filename": "profile.py",
        "status": "modified",
        "patch": """@@ -14,7 +14,9 @@ def display_name(user):
-    return user.nickname.strip()
+    if user.nickname is None:
+        return user.email.split("@")[0]
+    return user.nickname.strip()""",
    },
    {
        "id": "test-05",
        "category": "missing_tests",
        "expected_has_issue": True,
        "expected_note": "New API endpoint added with real logic, no test file in the diff.",
        "source": "synthetic",
        "filename": "routes/orders.py",
        "status": "added",
        "patch": """@@ -0,0 +1,10 @@
+@app.route("/orders/<id>/cancel", methods=["POST"])
+def cancel_order(id):
+    order = Order.query.get_or_404(id)
+    if order.status == "shipped":
+        return jsonify(error="cannot cancel a shipped order"), 400
+    order.status = "cancelled"
+    db.session.commit()
+    return jsonify(order.to_dict())""",
    },
    # ----------------------------------------------------- breaking_change (5) ----
    {
        "id": "break-01",
        "category": "breaking_change",
        "expected_has_issue": True,
        "expected_note": "Public function parameter renamed (user_id -> id) — breaks existing keyword-argument callers.",
        "source": "synthetic",
        "filename": "api/users.py",
        "status": "modified",
        "patch": """@@ -5,5 +5,5 @@ class UserAPI:
-    def get_user(self, user_id):
-        return self.client.get(f"/users/{user_id}")
+    def get_user(self, id):
+        return self.client.get(f"/users/{id}")""",
    },
    {
        "id": "break-02",
        "category": "breaking_change",
        "expected_has_issue": True,
        "expected_note": "Return type changed from a dict to a dataclass instance — breaks callers doing dict-style access.",
        "source": "synthetic",
        "filename": "parser.py",
        "status": "modified",
        "patch": """@@ -10,6 +10,6 @@ def parse_config(path):
-    data = yaml.safe_load(path.read_text())
-    return {"host": data["host"], "port": data["port"]}
+    data = yaml.safe_load(path.read_text())
+    return Config(host=data["host"], port=data["port"])""",
    },
    {
        "id": "break-03",
        "category": "breaking_change",
        "expected_has_issue": True,
        "expected_note": "Required default value removed from a public constructor parameter — breaks existing no-arg callers.",
        "source": "synthetic",
        "filename": "client.py",
        "status": "modified",
        "patch": """@@ -3,5 +3,5 @@ class ApiClient:
-    def __init__(self, timeout=30):
+    def __init__(self, timeout):
         self.timeout = timeout""",
    },
    {
        "id": "break-04",
        "category": "breaking_change",
        "expected_has_issue": True,
        "expected_note": "Exception type raised on invalid input changed from ValueError to a new custom exception — breaks existing except ValueError callers.",
        "source": "synthetic",
        "filename": "validators.py",
        "status": "modified",
        "patch": """@@ -6,7 +6,7 @@ def validate_email(email):
     if "@" not in email:
-        raise ValueError("invalid email")
+        raise InvalidEmailError("invalid email")
     return email""",
    },
    {
        "id": "break-05",
        "category": "breaking_change",
        "expected_has_issue": True,
        "expected_note": "Public method removed outright with no deprecation, breaking any external caller of the old name.",
        "source": "synthetic",
        "filename": "legacy_api.py",
        "status": "modified",
        "patch": """@@ -18,9 +18,6 @@ class ReportGenerator:
     def generate_pdf(self, data):
         return self._render(data, fmt="pdf")

-    def generate_csv(self, data):
-        return self._render(data, fmt="csv")
-
     def _render(self, data, fmt):
         ...""",
    },
    # -------------------------------------------------------------- clean (8) ----
    {
        "id": "clean-01",
        "category": "clean",
        "expected_has_issue": False,
        "expected_note": "Docstring-only change, no behavior affected.",
        "source": "synthetic",
        "filename": "utils.py",
        "status": "modified",
        "patch": """@@ -1,5 +1,7 @@
 def slugify(text):
-    # turns text into a url slug
+    \"\"\"Convert text into a URL-friendly slug (lowercase, hyphen-separated).\"\"\"
     return "-".join(text.lower().split())""",
    },
    {
        "id": "clean-02",
        "category": "clean",
        "expected_has_issue": False,
        "expected_note": "Type hints added to an already-correct, already-tested function; no behavior change.",
        "source": "synthetic",
        "filename": "math_utils.py",
        "status": "modified",
        "patch": """@@ -1,4 +1,4 @@
-def clamp(value, low, high):
+def clamp(value: float, low: float, high: float) -> float:
     return max(low, min(value, high))""",
    },
    {
        "id": "clean-03",
        "category": "clean",
        "expected_has_issue": False,
        "expected_note": "Straightforward equivalent refactor (list comprehension instead of a loop), same behavior, already covered by existing tests.",
        "source": "synthetic",
        "filename": "collections_utils.py",
        "status": "modified",
        "patch": """@@ -4,7 +4,4 @@ def active_usernames(users):
-    result = []
-    for u in users:
-        if u.is_active:
-            result.append(u.username)
-    return result
+    return [u.username for u in users if u.is_active]""",
    },
    {
        "id": "clean-04",
        "category": "clean",
        "expected_has_issue": False,
        "expected_note": "Renaming a purely internal/private loop variable for clarity, no external effect.",
        "source": "synthetic",
        "filename": "batch.py",
        "status": "modified",
        "patch": """@@ -6,6 +6,6 @@ def process_batch(items):
-    for x in items:
-        handle(x)
+    for item in items:
+        handle(item)""",
    },
    {
        "id": "clean-05",
        "category": "clean",
        "expected_has_issue": False,
        "expected_note": "Adding a debug-level log statement guarded correctly; no logic change, no security exposure (no secrets logged).",
        "source": "synthetic",
        "filename": "worker.py",
        "status": "modified",
        "patch": """@@ -22,6 +22,7 @@ def process_job(job):
     result = handler(job.payload)
+    logger.debug("processed job %s in %sms", job.id, elapsed_ms)
     return result""",
    },
    {
        "id": "clean-06",
        "category": "clean",
        "expected_has_issue": False,
        "expected_note": "Constant extracted to a named variable for readability; identical behavior.",
        "source": "synthetic",
        "filename": "pricing.py",
        "status": "modified",
        "patch": """@@ -3,5 +3,6 @@ def final_price(price):
-    return price * 1.2
+    VAT_RATE = 1.2
+    return price * VAT_RATE""",
    },
    {
        "id": "clean-07",
        "category": "clean",
        "expected_has_issue": False,
        "expected_note": "Version string bump only, mechanical change with no logic.",
        "source": "synthetic",
        "filename": "__init__.py",
        "status": "modified",
        "patch": """@@ -1 +1 @@
-__version__ = "1.4.2"
+__version__ = "1.4.3\"""",
    },
    {
        "id": "clean-08",
        "category": "clean",
        "expected_has_issue": False,
        "expected_note": "New private helper function, fully covered by the new test in the same PR (test file not shown here, but the function itself is simple and correct) — should not be flagged as missing tests based on this file alone without evidence.",
        "source": "synthetic",
        "filename": "text_utils.py",
        "status": "modified",
        "patch": """@@ -10,3 +10,7 @@ def normalize(text):
     return text.strip().lower()
+
+
+def _strip_accents(text: str) -> str:
+    import unicodedata
+    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))""",
    },
]

assert len(GOLDEN_DATASET) == 30
