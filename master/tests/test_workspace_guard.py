"""Static guards that make a forgotten workspace filter fail the build instead of leaking one account's fleet to another."""
import ast
import re
from pathlib import Path

from fastapi.routing import APIRoute

from app.deps import current_actor, current_workspace

APP = Path(__file__).resolve().parents[1] / "app"

# routes that are not about one workspace's data: signing in and choosing a workspace, the agent's own key, liveness, docs
NOT_SCOPED = ("/api/v1/auth/", "/api/agent/")
NOT_SCOPED_EXACT = {
    "/api/v1/health", "/llms.txt", "/agent/install.sh", "/agent/agent.py",
    "/api/openapi.json", "/api/docs", "/api/docs/oauth2-redirect", "/api/redoc",
}
# tables that carry workspace_id themselves, and tables that reach it through server_id
DIRECT = ("servers", "categories", "domains", "settings", "api_keys", "telegram_channels", "rule_routes", "incidents",
          "events", "alert_state", "flapping", "issue_acks")
CHILD = ("metrics", "pings", "jobs", "link_traffic", "link_prev")
SCOPED = re.compile(r"\b(%s)\b" % "|".join(DIRECT + CHILD))
REF = re.compile(r"\b(FROM|JOIN|INTO|UPDATE)\s+(%s)\b(?:\s+(?:AS\s+)?(\w+))?" % "|".join(DIRECT + CHILD), re.I)
NOT_ALIAS = {"where", "on", "join", "left", "inner", "set", "values", "group", "order", "limit", "as", "using", "natural", "cross"}
# the only reasons a statement may skip the filter, each naming where its workspace comes from
REASONS = ("server_row", "agent_server", "token_lookup", "retention", "probe_queue", "caller_row", "unique_check")
MARK = re.compile(r"# ws: (\w+)")
# `%` formatting may only name a column (SET %s=?) or an expression to sum (SUM(%s)), never a condition
FORMAT_OK = re.compile(r"SET %s=\?|SUM\(%s\)|PRAGMA table_info\(%s\)")
EXECUTORS = ("execute", "executemany", "executescript")


def _calls(dependant):
    for d in dependant.dependencies:
        yield d.call
        yield from _calls(d)


def test_every_data_route_takes_the_workspace_dependency():
    from app.main import create_app

    app = create_app()
    checked = 0
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path in NOT_SCOPED_EXACT or route.path.startswith(NOT_SCOPED):
            continue
        calls = set(_calls(route.dependant))
        assert current_workspace in calls, "%s %s has no ws: int = Depends(current_workspace)" % (route.methods, route.path)
        assert current_actor in calls, route.path
        checked += 1
    assert checked >= 50  # the walk really saw the API


def _fragments(node):
    """The literal SQL of an execute() argument, and whether some part of it was not a literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value], False
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, lo = _fragments(node.left)
        right, ro = _fragments(node.right)
        return left + right, lo or ro
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        left, lo = _fragments(node.left)
        text = " ".join(left)
        return left, lo or text.count("%s") != len(FORMAT_OK.findall(text))
    return [], True


def _depth0_or(sql: str) -> bool:
    depth = 0
    for i, ch in enumerate(sql):
        depth += ch == "("
        depth -= ch == ")"
        if depth == 0 and re.match(r"\bOR\b", sql[i:i + 3], re.I) and (i == 0 or not sql[i - 1].isalnum()):
            return True
    return False


def sql_problem(sql: str):
    """Why a literal statement on fleet tables is not scoped, or None."""
    if not SCOPED.search(sql):
        return None
    if re.search(r"workspace_id\s*(=|<>|!=|>=|<=|>|<|IN|IS)\s*[^\s]+\s+OR\b|\bOR\s+\(?\s*[\w.]*workspace_id", sql, re.I) or _depth0_or(sql):
        return "OR next to the workspace filter"
    anchored = re.search(r"workspace_id\s*=\s*\?", sql) or re.search(r"INSERT (OR REPLACE )?INTO \w+ \(workspace_id\b", sql, re.I)
    if not anchored:
        return "no workspace_id=? anywhere"
    bare_needed, servers_scoped, children = 0, False, False
    for verb, table, alias in REF.findall(sql):
        if verb.upper() == "INTO" and re.search(r"INTO %s \(workspace_id\b" % table, sql, re.I):
            continue
        if table in CHILD:
            children = True
            continue
        if alias and alias.lower() not in NOT_ALIAS:
            if not re.search(r"\b%s\.workspace_id\s*=\s*(\?|\w+\.workspace_id)|\w+\.workspace_id\s*=\s*%s\.workspace_id\b" % (alias, alias), sql):
                return "%s %s has no workspace filter" % (table, alias)
        else:
            bare_needed += 1
        if table == "servers":
            servers_scoped = True
    if bare_needed > len(re.findall(r"(?<![\w.])workspace_id\s*=\s*\?", sql)):
        return "an unaliased fleet table has no workspace_id=? of its own"
    if children and not servers_scoped:
        return "a per-server table without a scoped join to servers"
    return None


def unscoped(source: str, path: str = "x.py"):
    """(line, problem) of every statement that could read or write another workspace's rows."""
    lines = source.splitlines()
    tree = ast.parse(source)
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in EXECUTORS:
            calls.add(id(node.func))
    for node in ast.walk(tree):
        # db.execute handed around (run = db.execute; getattr(db, "execute")) escapes every check below
        if isinstance(node, ast.Attribute) and node.attr in EXECUTORS and id(node) not in calls:
            yield node.lineno, "execute used without calling it"
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) > 1
                and isinstance(node.args[1], ast.Constant) and node.args[1].value in EXECUTORS):
            yield node.lineno, "execute reached through getattr"
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in EXECUTORS):
            continue
        if node.func.attr == "executescript" and not path.endswith("db.py"):
            yield node.lineno, "executescript outside the migration runner"
            continue
        if not node.args:
            continue
        span = "\n".join(lines[node.lineno - 1: node.end_lineno])
        mark = MARK.search(span)
        if mark and mark.group(1) not in REASONS:
            yield node.lineno, "unknown '# ws:' reason %s" % mark.group(1)
            continue
        parts, opaque = _fragments(node.args[0])
        sql = " ".join(parts)
        if opaque and not path.endswith("db.py"):
            yield node.lineno, "SQL built at run time: %s" % sql[:60]
        elif not mark:
            why = sql_problem(sql)
            if why:
                yield node.lineno, "%s: %s" % (why, sql[:80])


BYPASSES = [
    'db.execute("SELECT * FROM servers WHERE id=?", (1,))',
    'db.execute(sql + " GROUP BY h")',
    'db.execute("SELECT * FROM pings p JOIN servers t ON t.workspace_id=p.x")',
    'db.execute("SELECT * FROM servers WHERE id=? OR workspace_id=?", (1, 2))',
    'db.execute("SELECT * FROM servers WHERE workspace_id=? OR 1=1", (2,))',
    'db.execute("SELECT * FROM servers WHERE workspace_id>=?", (1,))',
    'db.execute("SELECT * FROM servers a JOIN servers b ON b.id=a.id WHERE a.workspace_id=?", (1,))',
    'db.execute("SELECT * FROM incidents WHERE workspace_id=? AND server_id IN (SELECT id FROM servers)", (1,))',
    'db.execute("SELECT * FROM metrics WHERE ts>? AND 1 IN (SELECT workspace_id=? FROM settings)", (1, 2))',
    'db.execute("SELECT * FROM jobs WHERE server_id=?", (1,))',
    'db.execute("SELECT * FROM servers WHERE %s" % cond)',
    'db.execute(f"SELECT * FROM servers WHERE workspace_id={ws}")',
    'run = db.execute',
    'getattr(db, "execute")("SELECT * FROM servers")',
    'db.executescript("DELETE FROM servers")',
    'db.execute("SELECT * FROM servers WHERE id=?", (1,))  # ws: trust me',
]
GOOD = [
    'db.execute("SELECT * FROM servers WHERE id=? AND workspace_id=?", (1, 2))',
    'db.execute("DELETE FROM metrics WHERE ts<?", (1,))  # ws: retention - by age',
    'db.execute("INSERT INTO events (workspace_id, ts) VALUES (?,?)", (1, 2))',
    'db.execute("PRAGMA foreign_key_check")',
    'db.execute("UPDATE servers SET %s=? WHERE id=? AND workspace_id=?" % field, (1, 2, 3))',
    'db.execute("SELECT m.ts FROM metrics m JOIN servers s ON s.id=m.server_id WHERE s.workspace_id=? AND (? = 1 OR s.category_id IS ?)", (1, 1, None))',
    'db.execute("SELECT * FROM pings p JOIN servers s ON s.id=p.server_id JOIN servers t ON t.workspace_id=s.workspace_id WHERE s.workspace_id=?", (1,))',
]


def test_the_statement_guard_catches_every_bypass_it_knows():
    for snippet in BYPASSES:
        assert list(unscoped(snippet)), snippet
    for snippet in GOOD:
        assert list(unscoped(snippet)) == [], (snippet, list(unscoped(snippet)))


def test_every_statement_on_fleet_tables_names_its_workspace():
    problems = [
        "%s:%d %s" % (path.relative_to(APP), line, sql)
        for path in sorted(APP.rglob("*.py"))
        for line, sql in unscoped(path.read_text(encoding="utf-8"), str(path))
    ]
    assert not problems, "statements without a workspace filter or a '# ws:' reason:\n" + "\n".join(problems)
