"""A gold-backed seed corpus for bootstrapping an Agentbook instance.

The vision's pillar 2 — "knowledge extracted from strong models / known-good
solutions" — and the antidote to the cold-start trap: an empty book gives a
first adopter nothing but misses, so it never demonstrates value, so nobody
adopts. This module is real, recurring coding-error knowledge (the kind weak
agents hit constantly), each entry carrying the transferable structured
knowledge the read contract exposes: root_cause_pattern, localization_cues,
verification.

This is the *sanctioned* bootstrap. The honesty constraint forbids fabricating
**outcome consensus** (fake reporters) — it does NOT forbid contributing genuine
known-good solutions. Confidence still only climbs as distinct real agents
confirm these via `report`; seeding just makes the first recall hit.

Load it with:  python seed_book.py http://localhost:8000
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SeedEntry:
    description: str
    error_signature: str
    solution_content: str
    solution_steps: list[str]
    root_cause_pattern: str
    localization_cues: list[str]
    verification: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


CORPUS: list[SeedEntry] = [
    SeedEntry(
        description="Concatenating an int onto a str raises TypeError in Python.",
        error_signature='TypeError: can only concatenate str (not "int") to str',
        solution_content=(
            "Coerce the operands to one type before joining: wrap the int with "
            "str() for string building, or cast the str with int() for arithmetic. "
            "Prefer an f-string: f'{label}{count}'."
        ),
        solution_steps=[
            "identify which operand is the int and which is the str",
            "for display, wrap the int: str(count) or use an f-string",
            "for arithmetic, cast the str: int(label)",
        ],
        root_cause_pattern="mixed-type + operator: Python won't implicitly coerce int<->str",
        localization_cues=["the line with the '+' joining a number and text"],
        verification=[
            {"command": "python -c \"print('n='+str(1))\"", "expected": "n=1"}
        ],
        tags=["python", "typeerror"],
    ),
    SeedEntry(
        description="ModuleNotFoundError: the package is not installed in the active environment.",
        error_signature="ModuleNotFoundError: No module named",
        solution_content=(
            "Install the package into the SAME interpreter that runs the code: "
            "`python -m pip install <pkg>` (or `uv add <pkg>`). If it is installed "
            "but still missing, you are running a different venv — check "
            "`python -c 'import sys; print(sys.executable)'`."
        ),
        solution_steps=[
            "confirm the missing module name from the traceback",
            "python -m pip install <pkg> (binds pip to the running interpreter)",
            "if still failing, verify sys.executable matches your venv",
        ],
        root_cause_pattern="import resolves against an environment that lacks the dependency",
        localization_cues=[
            "the failing import line",
            "sys.executable",
            "requirements/pyproject",
        ],
        verification=[
            {
                "command": "python -c 'import sys; print(sys.executable)'",
                "expected": "your venv path",
            }
        ],
        tags=["python", "import", "environment"],
    ),
    SeedEntry(
        description="RuntimeError: Event loop is closed after asyncio teardown.",
        error_signature="RuntimeError: Event loop is closed",
        solution_content=(
            "A coroutine/cleanup ran after the loop stopped — usually a pool or "
            "client closing in a finalizer outside the loop. Close async resources "
            "inside the same loop before it stops (await pool.close() before "
            "asyncio.run returns), or use async context managers."
        ),
        solution_steps=[
            "find the resource closed after the loop ended (pool/session/client)",
            "await its .close() inside the running loop, before teardown",
            "prefer 'async with' so cleanup is bound to the loop's lifetime",
        ],
        root_cause_pattern="async cleanup scheduled after its event loop already closed",
        localization_cues=[
            "__del__/finalizers on async clients",
            "asyncio.run boundaries",
            "pool.close()",
        ],
        verification=[],
        tags=["python", "asyncio", "runtimeerror"],
    ),
    SeedEntry(
        description="AttributeError: 'NoneType' object has no attribute — a value expected to be set is None.",
        error_signature="AttributeError: 'NoneType' object has no attribute",
        solution_content=(
            "A call that can return None was used as if it always returns an object "
            "(e.g. dict.get, re.match, a function with an implicit None return). "
            "Guard for None before the attribute access, or fix the upstream so it "
            "never returns None on that path."
        ),
        solution_steps=[
            "find what produced the None (often .get(), re.match, or a missing return)",
            "add an explicit None check, or supply a default",
            "if None is never valid here, fix the producer to return a real object",
        ],
        root_cause_pattern="optional/None value dereferenced without a guard",
        localization_cues=[
            "the attribute access in the traceback",
            "the assignment feeding it",
        ],
        verification=[],
        tags=["python", "attributeerror", "none"],
    ),
    SeedEntry(
        description="ImportError: cannot import name X — a circular import between two modules.",
        error_signature="ImportError: cannot import name",
        solution_content=(
            "Two modules import each other at module load time, so one sees the "
            "other half-initialised. Break the cycle: move the import inside the "
            "function that needs it (local import), or extract the shared symbol "
            "into a third module both can import."
        ),
        solution_steps=[
            "map the import cycle (A imports B imports A)",
            "move the offending import inside the function/method using it",
            "or extract the shared type/constant into a leaf module",
        ],
        root_cause_pattern="circular module dependency resolved at import time",
        localization_cues=[
            "the two modules naming each other in the traceback",
            "top-level imports",
        ],
        verification=[],
        tags=["python", "importerror", "circular-import"],
    ),
    SeedEntry(
        description="JavaScript TypeError: Cannot read properties of undefined (reading 'x').",
        error_signature="TypeError: Cannot read properties of undefined",
        solution_content=(
            "An object expected to exist is undefined when a property is read. Use "
            "optional chaining (obj?.x) with a default (obj?.x ?? fallback), and fix "
            "the upstream that left it undefined (async data not yet loaded, a typo'd "
            "key, or a missing return)."
        ),
        solution_steps=[
            "identify which object is undefined at the access site",
            "guard with optional chaining + nullish default: a?.b ?? fallback",
            "fix the source (await the data, correct the key, add the return)",
        ],
        root_cause_pattern="property access on an undefined value (often unloaded async data)",
        localization_cues=[
            "the 'reading X' frame in the stack",
            "the await/fetch that should populate it",
        ],
        verification=[],
        tags=["javascript", "typeerror", "undefined"],
    ),
    SeedEntry(
        description="CORS error: response blocked by the browser's same-origin policy.",
        error_signature="has been blocked by CORS policy: No 'Access-Control-Allow-Origin'",
        solution_content=(
            "CORS is enforced by the browser but configured on the SERVER. Add the "
            "calling origin to the server's Access-Control-Allow-Origin (not '*' when "
            "sending credentials), and handle the OPTIONS preflight. It cannot be "
            "fixed from client JS alone."
        ),
        solution_steps=[
            "set Access-Control-Allow-Origin on the API to the exact frontend origin",
            "if credentialed, also send Allow-Credentials: true (origin must not be '*')",
            "ensure the OPTIONS preflight returns the allow headers/methods",
        ],
        root_cause_pattern="server omits CORS response headers for the caller's origin",
        localization_cues=[
            "the API's CORS middleware config",
            "OPTIONS preflight handler",
        ],
        verification=[],
        tags=["web", "cors", "http"],
    ),
    SeedEntry(
        description="git fatal: refusing to merge unrelated histories.",
        error_signature="fatal: refusing to merge unrelated histories",
        solution_content=(
            "The two branches have no common ancestor (e.g. a fresh init vs a remote "
            "with its own root). If you intend to combine them, re-run with "
            "`--allow-unrelated-histories`; otherwise you likely cloned/added the "
            "wrong remote — verify `git remote -v`."
        ),
        solution_steps=[
            "confirm the branches truly should be joined (check git remote -v)",
            "git pull origin <branch> --allow-unrelated-histories",
            "resolve any merge conflicts from the combined roots",
        ],
        root_cause_pattern="merge between histories with no shared commit ancestor",
        localization_cues=["the git pull/merge command", "git remote -v"],
        verification=[],
        tags=["git", "merge"],
    ),
    SeedEntry(
        description=(
            "A Docker image fails immediately at run with 'exec format error' "
            "(often in CI or on a server) though it built fine locally — typically "
            "after building on an Apple Silicon (arm64) Mac and deploying to an "
            "amd64 host, or vice versa."
        ),
        error_signature="exec format error",
        solution_content=(
            "The image binary architecture does not match the host CPU. Build for "
            "the TARGET platform explicitly. One-off: `docker buildx build "
            "--platform linux/amd64 -t img:tag --push .` (push is needed for a "
            "cross-arch build). In docker-compose set `platform: linux/amd64` on "
            "the service, or `build.platforms`. For multi-arch: `docker buildx "
            "build --platform linux/amd64,linux/arm64 --push`. Confirm with "
            "`docker image inspect img:tag --format '{{.Architecture}}'`. Do not "
            "rely on the default platform, which is the builder's native arch."
        ),
        solution_steps=[
            "check the host arch (uname -m: x86_64=amd64, aarch64=arm64)",
            "build for it: docker buildx build --platform linux/amd64 -t img:tag --push .",
            "or set platform: linux/amd64 in docker-compose / build.platforms",
            "confirm: docker image inspect img:tag --format '{{.Architecture}}'",
        ],
        root_cause_pattern=(
            "image binary architecture != host CPU architecture; the kernel cannot "
            "exec an entrypoint built for a different ISA"
        ),
        localization_cues=[
            "building on Apple Silicon, deploying to an amd64 cloud host",
            "Dockerfile FROM with no platform pin",
            "CI runner arch differs from prod arch",
        ],
        verification=[
            {
                "command": "docker image inspect img:tag --format '{{.Architecture}}'",
                "expected": "matches host arch (amd64 or arm64)",
                "buggy": "arm64 image on an amd64 host -> exec format error",
            }
        ],
        tags=["docker", "buildx", "arm64", "amd64", "platform"],
    ),
    SeedEntry(
        description=(
            "npm install fails with 'ERESOLVE unable to resolve dependency tree' "
            "due to a peer-dependency conflict between packages."
        ),
        error_signature="ERESOLVE unable to resolve dependency tree",
        solution_content=(
            "A package's peerDependencies conflict with an installed version. Fix it "
            "properly first: read the ERESOLVE block to find which package wants "
            "which peer, then align versions (upgrade/downgrade the offending dep) "
            "so the peer range is satisfied. If the conflict is a known-safe "
            "false-positive (common with React 18 + older libs), install with "
            "`npm install --legacy-peer-deps` (npm 7+ behavior) or `--force` as a "
            "last resort. Pin the resolution in package.json `overrides` so CI is "
            "reproducible. Avoid deleting package-lock.json blindly — it loses the "
            "working resolution."
        ),
        solution_steps=[
            "read the ERESOLVE output to see which package requires which peer version",
            "align the versions so the peer range is satisfied (preferred)",
            "if it is a known-safe conflict: npm install --legacy-peer-deps",
            "pin the fix in package.json 'overrides' for reproducible CI",
        ],
        root_cause_pattern=(
            "an installed dependency version falls outside another package's "
            "declared peerDependencies range; npm 7+ refuses to auto-resolve it"
        ),
        localization_cues=[
            "the ERESOLVE 'Found:' vs 'Could not resolve' lines naming the peer",
            "package.json dependencies vs the conflicting peer range",
            "a major-version bump (e.g. React 17 -> 18) of a shared peer",
        ],
        verification=[
            {
                "command": "npm install --legacy-peer-deps && npm ls --depth=0",
                "expected": "install completes, no ERESOLVE",
                "buggy": "npm error ERESOLVE unable to resolve dependency tree",
            }
        ],
        tags=["npm", "node", "dependencies", "peer-deps"],
    ),
    SeedEntry(
        description=(
            "A server fails to start with 'OSError: [Errno 98] Address already in "
            "use' (or EADDRINUSE on Node) because the port is held by another "
            "process or a previous run that did not exit cleanly."
        ),
        error_signature="Address already in use",
        solution_content=(
            "Another process holds the port. Find it: `lsof -i :8000` (or `ss -ltnp "
            "'sport = :8000'`) and stop it, or `kill -9 $(lsof -ti :8000)`. If it is "
            "a zombie from your own previous run, that is the culprit — ensure the "
            "old process is dead before restarting. For a quick unblock, run on a "
            "different port. For servers that restart fast (dev reload, tests), set "
            "SO_REUSEADDR so the socket can rebind during TIME_WAIT — uvicorn/gunicorn "
            "do this; raw sockets need `sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)` "
            "before bind. In Docker, two services mapping the same host port also "
            "trigger this — give them distinct host ports."
        ),
        solution_steps=[
            "find the holder: lsof -i :PORT  (or ss -ltnp 'sport = :PORT')",
            "stop it: kill -9 $(lsof -ti :PORT)  — often a stale previous run",
            "or start on a different port",
            "for fast-restart servers set SO_REUSEADDR before bind",
        ],
        root_cause_pattern=(
            "the TCP port is already bound by another process (often the app's own "
            "prior run still in TIME_WAIT or not killed), so bind() fails"
        ),
        localization_cues=[
            "the bind/listen call naming the port",
            "a previous dev-server or test run that did not exit",
            "two Docker services mapping the same host port",
        ],
        verification=[
            {
                "command": "lsof -i :8000",
                "expected": "no process (or only your intended server) holds the port",
                "buggy": "a stale process still LISTENing on :8000",
            }
        ],
        tags=["networking", "ports", "sockets", "docker"],
    ),
]


def as_dicts() -> list[dict]:
    """Corpus as plain dicts (for JSON export / non-Python loaders)."""
    return [
        {
            "description": e.description,
            "error_signature": e.error_signature,
            "solution_content": e.solution_content,
            "solution_steps": e.solution_steps,
            "root_cause_pattern": e.root_cause_pattern,
            "localization_cues": e.localization_cues,
            "verification": e.verification,
            "tags": e.tags,
        }
        for e in CORPUS
    ]
