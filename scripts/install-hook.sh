#!/usr/bin/env bash
# install-hook.sh — installe les deps Python + le pre-commit hook qui régénère
# et valide les artéfacts à chaque commit qui touche data/ ou scripts/.
#
# Lance une fois :
#   bash scripts/install-hook.sh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPTS="$REPO_ROOT/scripts"
HOOK_DIR="$REPO_ROOT/.git/hooks"
HOOK="$HOOK_DIR/pre-commit"

# ─── 1. Sanity check Python ─────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  echo "[install-hook.sh] ERREUR : python3 introuvable dans PATH." >&2
  echo "  Installe Python 3 avant de continuer." >&2
  exit 1
fi
PY_VERSION="$(python3 --version 2>&1 | awk '{print $2}')"
echo "[install-hook.sh] Python détecté : $PY_VERSION"

# ─── 2. Installer / mettre à jour les dépendances ───────────────────────────
REQ="$SCRIPTS/requirements.txt"
if [ ! -f "$REQ" ]; then
  echo "[install-hook.sh] ERREUR : $REQ introuvable." >&2
  exit 1
fi

echo "[install-hook.sh] Installation des dépendances Python ($REQ)…"
# Tente d'abord pip system, fallback sur --user si la machine est gérée externally
if python3 -m pip install --quiet --upgrade -r "$REQ" 2>/dev/null; then
  echo "[install-hook.sh] ✓ deps installées (système)"
elif python3 -m pip install --quiet --upgrade --user -r "$REQ" 2>/dev/null; then
  echo "[install-hook.sh] ✓ deps installées (--user)"
elif python3 -m pip install --quiet --upgrade --break-system-packages -r "$REQ" 2>/dev/null; then
  echo "[install-hook.sh] ✓ deps installées (--break-system-packages)"
else
  echo "[install-hook.sh] ERREUR : impossible d'installer les deps." >&2
  echo "  Lance manuellement : python3 -m pip install -r $REQ" >&2
  echo "  Ou crée un venv : python3 -m venv .venv && source .venv/bin/activate && pip install -r $REQ" >&2
  exit 1
fi

# Vérification : jinja2 doit être importable
if ! python3 -c "import jinja2" 2>/dev/null; then
  echo "[install-hook.sh] ERREUR : jinja2 toujours pas importable après install." >&2
  exit 1
fi

# ─── 3. Installer le hook ──────────────────────────────────────────────────
mkdir -p "$HOOK_DIR"

cat > "$HOOK" <<'HOOK_EOF'
#!/usr/bin/env bash
# pre-commit hook auto-généré par scripts/install-hook.sh
#
# Si data/, scripts/templates/ ou scripts/generate.py changent :
#   1. lance scripts/generate.py pour régénérer README.md + assets/svg/*.svg
#   2. lance scripts/validate.py pour vérifier qu'aucune ressource n'est cassée
#      et que tous les SVG sont XML well-formed
#   3. ajoute les fichiers régénérés au commit
# Échoue le commit si l'une des étapes plante.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
GEN="$REPO_ROOT/scripts/generate.py"
VAL="$REPO_ROOT/scripts/validate.py"

# Détecter si data, templates ou script ont bougé
TRIGGER="$(git diff --cached --name-only --diff-filter=ACM | grep -E '^(data/|scripts/templates/|scripts/generate\.py$|scripts/validate\.py$|scripts/templates/_terminal_window\.svg\.jinja$)' || true)"

if [ -z "$TRIGGER" ]; then
  # Mais on valide quand même si README/assets ont été modifiés manuellement
  TRIGGER_MANUAL="$(git diff --cached --name-only --diff-filter=ACM | grep -E '^(README\.md$|assets/svg/)' || true)"
  if [ -n "$TRIGGER_MANUAL" ]; then
    echo "[pre-commit] README/assets modifiés manuellement — validation seule…"
    python3 "$VAL" || {
      echo "[pre-commit] ÉCHEC validation. Commit annulé." >&2
      exit 1
    }
  fi
  exit 0
fi

echo "[pre-commit] data/ ou scripts/ modifiés — régénération…"
python3 "$GEN" || {
  echo "[pre-commit] ÉCHEC génération. Commit annulé." >&2
  exit 1
}

echo "[pre-commit] Validation des artéfacts générés…"
python3 "$VAL" || {
  echo "[pre-commit] ÉCHEC validation (ressources manquantes ou SVG malformé). Commit annulé." >&2
  exit 1
}

# Stage les fichiers générés / régénérés
git add "$REPO_ROOT/assets/svg/" "$REPO_ROOT/README.md"
echo "[pre-commit] ✓ assets/svg/*.svg et README.md ajoutés au commit."
HOOK_EOF

chmod +x "$HOOK"

echo
echo "[install-hook.sh] ✓ hook installé : $HOOK"
echo "[install-hook.sh] Le prochain commit qui touche data/ ou scripts/templates/"
echo "                  régénèrera + validera les artéfacts automatiquement."
