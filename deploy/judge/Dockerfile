# The judge instance: this code, on the cloud profile, with nothing real in it.
#
# ADR 0009 puts it on a Nebius Serverless AI Endpoint running an arbitrary
# container on a no-GPU Compute VM — about $36/month for a `2vcpu-8gb` preset
# run continuously, against $2,957 for the same month on an H100 endpoint for a
# process that does no GPU work.
#
# Principle 5: the same code as the personal instance, separated only by compute
# profile. There is no demo branch in here and nothing is stubbed. What differs
# is two environment variables and the database the image was built with.
#
# Build from the repository root:
#
#     docker build -f deploy/judge/Dockerfile -t second-shift-judge .
#
# ---------------------------------------------------------------------------
# What this image must not carry, and how that is enforced
# ---------------------------------------------------------------------------
#
# Not the brain, not a real database, not `data/payloads/`. Each `COPY` below
# names exactly what it takes rather than taking the tree and excluding what it
# must not — an allowlist stays correct when somebody adds a directory, and a
# denylist silently stops being one. `.dockerignore` is a second line, not the
# first.
#
# The database is built here from a seed rather than copied from anywhere, so
# there is no path by which a real one reaches this image, and
# `check-judge-package.py` runs against the result at build time: a build that
# somehow produced real rows fails rather than shipping.

# ---------------------------------------------------------------------------
# The web export
# ---------------------------------------------------------------------------
FROM node:24-slim AS web

WORKDIR /build
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY apps/web ./
# Empty base: the API serves these files from its own origin, so there is no
# CORS and no second process to be down. The Spark deploy builds it the same way.
ENV NEXT_PUBLIC_API_BASE=""
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN npm run build

# ---------------------------------------------------------------------------
# The orchestrator, and the night it will show
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Everything the deployment decides, in one place. `SECOND_SHIFT_PROFILE` is
# pinned rather than probed: a no-GPU VM would resolve to `cloud` anyway — no
# nvidia-smi, no local endpoint — but a demo whose capability report depends on
# a probe behaving as expected in an environment nobody tested is a demo with a
# variable in it. The reason the report gives changes with this choice, and the
# pinned one is still honest: "no local reasoner is bound on this profile".
ENV SECOND_SHIFT_PROFILE=cloud \
    SECOND_SHIFT_SYNTHETIC=1 \
    SECOND_SHIFT_DB=/srv/second-shift/data/judge.db \
    SECOND_SHIFT_ARTIFACTS=/srv/second-shift/data/artifacts \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /srv/second-shift

# Named individually. Adding `packages/` or `apps/` wholesale is how the brain
# or a stray database arrives in an image six months from now.
COPY apps/api ./apps/api
COPY packages/seed ./packages/seed
COPY config ./config
COPY scripts/check-judge-package.py ./scripts/check-judge-package.py
COPY --from=web /build/out ./apps/web/out

# Pinned. `constraints.txt` is the same file the Spark installs against, so the
# judge instance and the personal instance run the same versions.
RUN python -m pip install --no-cache-dir --upgrade pip \
 && python -m pip install --no-cache-dir \
      -e ./apps/api -e ./packages/seed \
      -c ./apps/api/constraints.txt

# The demo's night, built into the image. At image build rather than at start:
# a cold start that seeds is a cold start that can fail, and every replica would
# otherwise hold a night written at a different instant. Seed 42 is the one the
# screenshots in `docs/` were taken against.
RUN mkdir -p "$(dirname "$SECOND_SHIFT_DB")" \
 && python -m secondshift_seed --seed 42 --db "$SECOND_SHIFT_DB"

# The build fails rather than shipping a database carrying anything a judge must
# never see. It passes trivially today because the line above just wrote the
# database from a seed — which is the point: it is here to catch the day
# somebody changes that line.
RUN python ./scripts/check-judge-package.py "$SECOND_SHIFT_DB"

# Nothing here needs root, and an endpoint running arbitrary containers is not
# the place to find out otherwise.
RUN useradd --system --uid 10001 --create-home judge \
 && chown -R judge:judge /srv/second-shift
USER judge

EXPOSE 8080

# `/health` is the whole check. A judge instance that cannot answer it has
# nothing to demonstrate.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,os,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ['PORT']+'/health').status==200 else 1)"

CMD ["sh", "-c", "exec uvicorn secondshift.api.main:app --host 0.0.0.0 --port ${PORT}"]
