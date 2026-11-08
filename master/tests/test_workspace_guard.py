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
# every table that holds fleet data, directly (workspace_id) or through server_id
SCOPED = re.compile(
    r"\b(servers|categories|domains|settings|api_keys|telegram_channels|rule_routes|incidents|events|alert_state|flapping"
    r"|metrics|pings|jobs|link_traffic|link_prev)\b"
)
FILTERED = re.compile(r"workspace_id\s*=\s*\?|INSERT (OR REPLACE )?INTO \w+ \(workspace_id\b", re.I)


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
    """The literal SQL pieces of an execute() argument, and whether some part was not a literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value], False
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        left, lo = _fragments(node.left)
        if isinstance(node.op, ast.Mod):
            return left, lo
        right, ro = _fragments(node.right)
        return left + right, lo or ro
    if isinstance(node, ast.Name) and node.id == "_COUNT":
        return [], False  # categories' subquery, joined by workspace in the statement around it
    return [], True


def unscoped(source: str):
    """(line, sql) of every execute() on a fleet table with no workspace filter and no '# ws:' reason in its span."""
    lines = source.splitlines()
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("execute", "executemany") and node.args):
            continue
        parts, opaque = _fragments(node.args[0])
        sql = " ".join(parts)
        justified = "# ws:" in "\n".join(lines[node.lineno - 1: node.end_lineno])
        touches = SCOPED.search(sql) is not None
        if (touches and not FILTERED.search(sql) and not justified) or (opaque and not touches and not justified):
            yield node.lineno, sql[:90] or "<built at run time>"


def test_the_statement_guard_catches_a_missing_filter():
    bad = 'db.execute("SELECT * FROM servers WHERE id=?", (1,))\ndb.execute(sql + " GROUP BY h")\n'
    bad += 'db.execute("SELECT * FROM pings p JOIN servers t ON t.workspace_id=p.x")\n'
    good = 'db.execute("SELECT * FROM servers WHERE id=? AND workspace_id=?", (1, 2))\n'
    good += 'db.execute("DELETE FROM metrics WHERE ts<?", (1,))  # ws: retention\n'
    good += 'db.execute("INSERT INTO events (workspace_id, ts) VALUES (?,?)", (1, 2))\ndb.execute("PRAGMA foreign_key_check")\n'
    assert [line for line, _ in unscoped(bad)] == [1, 2, 3]
    assert list(unscoped(good)) == []


def test_every_statement_on_fleet_tables_names_its_workspace():
    problems = [
        "%s:%d %s" % (path.relative_to(APP), line, sql)
        for path in sorted(APP.rglob("*.py"))
        for line, sql in unscoped(path.read_text(encoding="utf-8"))
    ]
    assert not problems, "statements without a workspace filter or a '# ws:' reason:\n" + "\n".join(problems)
