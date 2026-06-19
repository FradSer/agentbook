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
    SeedEntry(
        description=(
            "A Next.js / React app throws 'Hydration failed because the initial "
            "UI does not match what was rendered on the server' (or 'Text content "
            "does not match server-rendered HTML') — the client render diverges "
            "from the server-rendered HTML."
        ),
        error_signature="Hydration failed because the initial UI does not match",
        solution_content=(
            "The server and client produced different markup for the same node. "
            "Usual causes: rendering non-deterministic values during render "
            "(Date.now(), Math.random(), new Date().toLocaleString(), "
            "window/localStorage reads) so SSR and CSR differ; or invalid HTML "
            "nesting (e.g. a <div> inside a <p>, a block inside an inline element) "
            "that the browser auto-corrects. Fix: move client-only / time-dependent "
            "values out of render — read them in useEffect and set state after "
            "mount, or gate the subtree behind a mounted flag (`const [m,setM]="
            "useState(false); useEffect(()=>setM(true),[])`). For deliberate "
            "mismatches use `suppressHydrationWarning`. Fix invalid nesting so the "
            "browser does not rewrite the DOM."
        ),
        solution_steps=[
            "find render code using Date/Math.random/window/localStorage during render",
            "move it into useEffect + state so it runs only on the client after mount",
            "or gate the subtree behind a mounted flag",
            "check for invalid HTML nesting the browser would auto-correct",
        ],
        root_cause_pattern=(
            "server-rendered HTML differs from the first client render — "
            "non-deterministic/client-only values used during render, or invalid "
            "HTML nesting the browser rewrites"
        ),
        localization_cues=[
            "components reading Date.now()/Math.random()/window/localStorage in render",
            "<p>/<div> nesting that violates HTML content rules",
            "the component named in the hydration warning stack",
        ],
        verification=[
            {
                "command": "next build && next start  # then load the page",
                "expected": "no hydration warning in the browser console",
                "buggy": "Hydration failed / Text content does not match",
            }
        ],
        tags=["nextjs", "react", "ssr", "hydration"],
    ),
    SeedEntry(
        description=(
            "A long-running app intermittently fails DB queries with "
            "'psycopg2.OperationalError: SSL connection has been closed "
            "unexpectedly' / 'server closed the connection unexpectedly' — a "
            "pooled connection went stale (idle timeout, DB restart, or a "
            "load-balancer/proxy dropping idle TCP)."
        ),
        error_signature="SSL connection has been closed unexpectedly",
        solution_content=(
            "A connection in the pool was severed server-side (idle timeout, DB "
            "failover, or a proxy like PgBouncer/Railway dropping idle TCP) but the "
            "client still held it. Enable liveness checks so dead connections are "
            "recycled before use. SQLAlchemy: `create_engine(url, pool_pre_ping="
            "True, pool_recycle=300)` — pre_ping validates each checkout, "
            "pool_recycle caps connection age below the server/proxy idle timeout. "
            "Raw psycopg2: set `keepalives=1` and reconnect on OperationalError. "
            "Behind PgBouncer in transaction mode, also disable server-side "
            "prepared statements. Add a bounded retry around transient "
            "OperationalError so one stale connection does not surface as a 500."
        ),
        solution_steps=[
            "set pool_pre_ping=True so each checkout validates the connection",
            "set pool_recycle below the DB/proxy idle timeout (e.g. 300s)",
            "wrap queries in a small retry on transient OperationalError",
            "behind PgBouncer transaction mode, disable prepared statements",
        ],
        root_cause_pattern=(
            "a pooled DB connection was closed server-side (idle timeout / failover "
            "/ proxy) while the client cached it as live; the next use hits a dead "
            "socket"
        ),
        localization_cues=[
            "SQLAlchemy create_engine without pool_pre_ping/pool_recycle",
            "a managed Postgres / PgBouncer / load balancer with an idle timeout",
            "errors appearing only after the app has been idle",
        ],
        verification=[
            {
                "command": "python -c \"from sqlalchemy import create_engine,text; e=create_engine(url,pool_pre_ping=True,pool_recycle=300); e.connect().execute(text('select 1'))\"",
                "expected": "select 1 succeeds even after an idle period",
                "buggy": "OperationalError: SSL connection has been closed unexpectedly",
            }
        ],
        tags=["postgres", "sqlalchemy", "psycopg2", "connection-pool"],
    ),
    SeedEntry(
        description=(
            "TypeScript fails with \"Cannot find module 'X' or its corresponding "
            'type declarations" (ts2307) for a package that is installed and runs '
            "fine at runtime."
        ),
        error_signature="Cannot find module or its corresponding type declarations",
        solution_content=(
            "TypeScript cannot resolve the module's TYPES (runtime resolution is "
            "separate). Common fixes: (1) the package ships no types — install them: "
            "`npm i -D @types/<pkg>`; if none exist, add a declaration "
            "`declare module 'X';` in a *.d.ts. (2) Path-alias imports (`@/...`) "
            "not mirrored in tsconfig — add matching `compilerOptions.paths` (and "
            "`baseUrl`). (3) `moduleResolution` mismatch — for modern ESM/bundlers "
            'set `"moduleResolution": "bundler"` (or "node16"/"nodenext"), and '
            "ensure the package's `exports`/`types` are reachable. (4) A subpath "
            "import needs the `types`-condition in the package exports. Restart the "
            "TS server after editing tsconfig so it reloads."
        ),
        solution_steps=[
            "if the package has no bundled types: npm i -D @types/<pkg> (or add a *.d.ts declare module)",
            "for path aliases: add compilerOptions.paths + baseUrl in tsconfig",
            "set moduleResolution to bundler/node16/nodenext to match your toolchain",
            "restart the TS server so it reloads tsconfig",
        ],
        root_cause_pattern=(
            "TypeScript's type resolution (separate from runtime resolution) cannot "
            "find a declaration: missing @types, an unmapped path alias, or a "
            "moduleResolution mismatch with the package's exports/types"
        ),
        localization_cues=[
            "the import line flagged ts2307",
            "tsconfig.json compilerOptions paths/baseUrl/moduleResolution",
            "the package's package.json exports/types fields",
        ],
        verification=[
            {
                "command": "npx tsc --noEmit",
                "expected": "no ts2307 for the import",
                "buggy": "error TS2307: Cannot find module 'X' or its corresponding type declarations",
            }
        ],
        tags=["typescript", "types", "tsconfig", "module-resolution"],
    ),
    SeedEntry(
        description=(
            "An API request fails authentication with a JWT error — Node "
            "jsonwebtoken throws 'TokenExpiredError: jwt expired', PyJWT raises "
            "'ExpiredSignatureError', or the server returns 401 with 'token "
            "expired'. The token was valid earlier."
        ),
        error_signature="jwt expired",
        solution_content=(
            "The access token's `exp` claim is in the past — by design, JWTs are "
            "short-lived. Do NOT just lengthen `exp`; implement refresh. On 401 "
            "due to expiry, use the refresh token to mint a new access token and "
            "retry the request once (refresh tokens live in an httpOnly cookie / "
            "secure store, not localStorage). If you control both ends and the "
            "clocks differ, add small `clockTolerance` (a few seconds) when "
            "verifying — but real expiry needs a refresh flow, not a wider window. "
            "If 'expired' fires immediately, the signing and verifying clocks are "
            "skewed or `exp` is set in the wrong unit (seconds, not ms)."
        ),
        solution_steps=[
            "decode the token (jwt.io) and check the exp claim vs now",
            "on 401-expired, exchange the refresh token for a new access token and retry once",
            "set exp in SECONDS since epoch (not milliseconds)",
            "if clocks skew, add a few seconds clockTolerance on verify",
        ],
        root_cause_pattern=(
            "the JWT exp claim is in the past (normal short-lived-token expiry, or "
            "clock skew / wrong exp unit); verification rejects it"
        ),
        localization_cues=[
            "jwt.verify / jwt.decode call",
            "the token exp claim and the signing/verifying server clocks",
            "missing refresh-token flow on 401",
        ],
        verification=[
            {
                "command": "node -e \"const jwt=require('jsonwebtoken');try{jwt.verify(tok,secret)}catch(e){console.log(e.name)}\"",
                "expected": "verifies, or you refresh+retry on TokenExpiredError",
                "buggy": "TokenExpiredError: jwt expired",
            }
        ],
        tags=["jwt", "auth", "tokens", "401"],
    ),
    SeedEntry(
        description=(
            "A FastAPI/pydantic request or model construction fails with "
            "'pydantic.ValidationError: N validation error(s) for <Model>' (HTTP "
            "422 Unprocessable Entity from FastAPI) — the input does not match the "
            "model's types/constraints."
        ),
        error_signature="validation error for",
        solution_content=(
            "Pydantic rejected the input against the schema. The error body lists "
            "each failing field with `loc` (where), `type` (which rule), and `msg` "
            "— read it: it names the exact field and why. Common causes: a missing "
            "required field, a wrong type (string where int expected), or an alias "
            "mismatch (the JSON key differs from the field name — set "
            "`populate_by_name=True` or `Field(alias=...)`). For FastAPI 422s, the "
            "client is sending the wrong shape — fix the request, or relax the "
            "model (Optional / default) only if the field is genuinely optional. "
            "Pydantic v2: `model_validate` / `model_config`; do not catch and "
            "ignore ValidationError — surface the `.errors()` so callers can fix "
            "the payload."
        ),
        solution_steps=[
            "read the error's loc/type/msg to find the exact failing field",
            "fix the input shape (missing field, wrong type) or the alias mapping",
            "for genuine optionals, make the field Optional with a default — not a blanket relax",
            "log exc.errors() rather than swallowing the ValidationError",
        ],
        root_cause_pattern=(
            "input data violates the pydantic model schema (missing/extra field, "
            "type mismatch, or field-name vs JSON-alias mismatch)"
        ),
        localization_cues=[
            "the Model the error names and its field types",
            "the request payload keys vs model field names/aliases",
            "FastAPI route response 422 with a detail array",
        ],
        verification=[
            {
                "command": 'python -c "from app import Model; Model.model_validate(payload)"',
                "expected": "constructs without error",
                "buggy": "pydantic.ValidationError: N validation errors for Model",
            }
        ],
        tags=["python", "pydantic", "fastapi", "validation"],
    ),
    SeedEntry(
        description=(
            "git push is rejected: '! [rejected] ... (non-fast-forward)' / "
            "'Updates were rejected because the remote contains work that you do "
            "not have locally' — the remote branch advanced since you last pulled."
        ),
        error_signature="Updates were rejected because the remote contains work",
        solution_content=(
            "Someone pushed commits you do not have; git refuses to overwrite them. "
            "Integrate first: `git pull --rebase origin <branch>` (replays your "
            "commits on top of theirs — cleanest, linear history), resolve any "
            "conflicts, then `git push`. Prefer `--rebase` over a merge pull to "
            "avoid a noisy merge commit. NEVER `git push --force` to a shared "
            "branch — it deletes their work; if you must rewrite your OWN feature "
            "branch, use `--force-with-lease`, which refuses if the remote moved "
            "unexpectedly. If this is a brand-new branch and the remote was created "
            "separately, see the unrelated-histories case instead."
        ),
        solution_steps=[
            "git pull --rebase origin <branch>",
            "resolve conflicts, then git rebase --continue",
            "git push",
            "to rewrite your OWN branch only: git push --force-with-lease (never plain --force on shared)",
        ],
        root_cause_pattern=(
            "the local branch tip is behind the remote tip; a non-fast-forward push "
            "would discard remote commits, so git rejects it"
        ),
        localization_cues=[
            "the rejected ref and 'non-fast-forward' in the push output",
            "git status / git log origin/<branch>..HEAD",
            "a teammate or CI having pushed to the same branch",
        ],
        verification=[
            {
                "command": "git pull --rebase && git push",
                "expected": "push succeeds after integrating remote work",
                "buggy": "! [rejected] ... (non-fast-forward)",
            }
        ],
        tags=["git", "push", "rebase"],
    ),
    SeedEntry(
        description=(
            "A Kubernetes pod is stuck in CrashLoopBackOff — the container starts, "
            "exits non-zero, and kubelet restarts it with growing backoff."
        ),
        error_signature="CrashLoopBackOff",
        solution_content=(
            "The container's main process keeps exiting. Diagnose, do not guess: "
            "`kubectl logs <pod> --previous` shows the crashed instance's output "
            "(the real error), and `kubectl describe pod <pod>` shows the last "
            "state / exit code and events (OOMKilled, liveness-probe failures, "
            "mount errors). Common causes + fixes: app throws on startup (bad "
            "config/env/missing secret — fix the config); the command exits "
            "immediately (wrong entrypoint/args, or a one-shot process where a "
            "long-running one is expected); OOMKilled (exit 137 — raise memory "
            "limits or fix the leak); a liveness probe failing during a slow start "
            "(raise initialDelaySeconds/failureThreshold); or a missing "
            "ConfigMap/Secret/volume. Fix the root cause; restarting alone will not "
            "help."
        ),
        solution_steps=[
            "kubectl logs <pod> --previous  (the crashed instance's real error)",
            "kubectl describe pod <pod>  (exit code, OOMKilled, probe failures, events)",
            "fix the root cause: config/env/secret, entrypoint, memory limit, or probe timing",
            "redeploy and watch kubectl get pod -w",
        ],
        root_cause_pattern=(
            "the container's main process exits non-zero repeatedly — startup "
            "exception, wrong command, OOMKilled, failing liveness probe, or a "
            "missing config/secret/volume"
        ),
        localization_cues=[
            "kubectl logs --previous output",
            "kubectl describe pod: Last State, exit code 137 (OOM) / 1, Events",
            "the Deployment command/args, resources.limits, livenessProbe, env/volumes",
        ],
        verification=[
            {
                "command": "kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[0].state}'",
                "expected": "running (not waiting: CrashLoopBackOff)",
                "buggy": "waiting CrashLoopBackOff; logs --previous shows the startup error",
            }
        ],
        tags=["kubernetes", "k8s", "crashloopbackoff", "deployment"],
    ),
    SeedEntry(
        description=(
            "A React app throws 'Maximum update depth exceeded' (or hangs / "
            "re-renders forever) — a component updates state in a way that "
            "re-triggers itself every render."
        ),
        error_signature="Maximum update depth exceeded",
        solution_content=(
            "State is being set during render or in an effect that runs every "
            "render, causing an infinite render loop. Find the setState that runs "
            "unconditionally: (1) `onClick={handler()}` instead of "
            "`onClick={handler}` calls it during render — pass the reference. (2) "
            "`useEffect(() => setX(...))` with NO dependency array, or a dep that "
            "changes every render (a new object/array/function literal) — add a "
            "correct deps array and memoize unstable deps with useMemo/useCallback. "
            "(3) setting state derived from props directly in the body — compute it "
            "during render instead of storing it. Rule: never call setState "
            "unconditionally during render or in an every-render effect."
        ),
        solution_steps=[
            "pass event handlers by reference: onClick={handler}, not onClick={handler()}",
            "add a correct dependency array to the offending useEffect",
            "memoize object/array/function deps with useMemo/useCallback",
            "derive values during render instead of setState-ing from props",
        ],
        root_cause_pattern=(
            "setState runs on every render (during render, or in a no-deps/unstable-"
            "deps effect), so each update schedules another render — an infinite loop"
        ),
        localization_cues=[
            "a useEffect with no deps array or an object/array/function literal dep",
            "onClick/onChange that invokes the handler instead of passing it",
            "setState called in the component body",
        ],
        verification=[
            {
                "command": "# load the component; React DevTools Profiler should show it settle, not loop",
                "expected": "renders settle after the interaction",
                "buggy": "Warning: Maximum update depth exceeded (infinite re-render)",
            }
        ],
        tags=["react", "hooks", "useeffect", "re-render"],
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
