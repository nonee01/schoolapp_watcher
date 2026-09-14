import ast
import pathlib

def test_package_imports():
    import schoolapp

    assert hasattr(schoolapp, "__version__")


def _own_scope_nodes(fn):
    """Walk a function's own body, stopping at anything that opens a new scope."""
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            stack.extend(ast.iter_child_nodes(node))


def _reads_what_it_binds(fn, path) -> list[str]:
    """Assignments whose value reads the name they are the first to bind."""
    if any(isinstance(n, (ast.Global, ast.Nonlocal)) for n in _own_scope_nodes(fn)):
        return []  # an explicit global/nonlocal makes the rebinding deliberate
    params = {a.arg for a in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]}
    params |= {v.arg for v in (fn.args.vararg, fn.args.kwarg) if v}
    own = list(_own_scope_nodes(fn))
    stores = [(n.lineno, n.id) for n in own if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]

    out = []
    for stmt in sorted((n for n in own if isinstance(n, (ast.Assign, ast.AugAssign))),
                       key=lambda n: n.lineno):
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        names = {t.id for t in ast.walk(ast.Module(body=list(targets), type_ignores=[]))
                 if isinstance(t, ast.Name)}
        # Anything bound on an earlier line already exists: for targets, with ... as,
        # except ... as, tuple unpacking, a previous assignment.
        earlier = params | {name for line, name in stores if line < stmt.lineno}
        for read in ast.walk(stmt.value):
            if isinstance(read, ast.Name) and isinstance(read.ctx, ast.Load) \
                    and read.id in names - earlier:
                out.append(f"{path}:{read.lineno} in {fn.name}(): reads '{read.id}' inside the "
                           f"assignment on line {stmt.lineno} that first binds it")
    return out


def test_no_assignment_reads_the_name_it_binds():
    """`schoolapp s5 table` died with UnboundLocalError: make_semester_app took the
    semester as `code`, and the command wrote check_once's exit code to `code` too,
    so `code = check_once(semester=code)` read a name it had just made local.

    Typer builds every command as a closure over its factory, which is what made
    the collision easy to write and invisible until someone ran the command.
    """
    offenders = []
    for path in sorted(pathlib.Path("schoolapp").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                offenders += _reads_what_it_binds(fn, path)
    assert not offenders, "assignments that read the name they bind:\n" + "\n".join(offenders)
