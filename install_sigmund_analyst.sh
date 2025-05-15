#!/usr/bin/env bash
#
# install_sigmund_analyst.sh
# --------------------------
# Installs pyqt_code_editor in a virtual environment and registers
# a desktop entry called “Sigmund Analyst”.
#
# You can re-run this script at any time to upgrade to a newer version.

set -euo pipefail

APP_NAME="sigmund-analyst"
VENV_DIR="$HOME/.local/venvs/${APP_NAME}"
WRAPPER="$HOME/.local/bin/${APP_NAME}-launch"
DESKTOP_FILE="$HOME/.local/share/applications/${APP_NAME}.desktop"
PYTHON_BIN="/usr/bin/python3"

if ! "$PYTHON_BIN" --version &>/dev/null; then
  echo "❌  System python3 not found at $PYTHON_BIN"
  exit 1
fi

echo "▶ Creating virtual-env in $VENV_DIR ..."
"$PYTHON_BIN" -m venv "$VENV_DIR"

echo "▶ Installing package ..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install --upgrade pyqt_code_editor
deactivate

echo "▶ Creating wrapper in $WRAPPER ..."
mkdir -p "$(dirname "$WRAPPER")"
cat > "$WRAPPER" << 'EOF'
#!/usr/bin/env bash
# Wrapper that activates the venv, then starts Sigmund-Analyst
VENV_DIR="$HOME/.local/venvs/sigmund-analyst"
source "$VENV_DIR/bin/activate"
exec sigmund-analyst "$@"
EOF
chmod +x "$WRAPPER"

echo "▶ Writing desktop entry $DESKTOP_FILE ..."
mkdir -p "$(dirname "$DESKTOP_FILE")"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=Sigmund Analyst
Comment=Launch the PyQt code-editor (sigmund-analyst)
Exec=$WRAPPER
Icon=accessories-text-editor
Terminal=false
Categories=Development;IDE;
StartupNotify=true
EOF

# Refresh desktop-file cache (non-fatal if the cmd is missing)
update-desktop-database "$(dirname "$DESKTOP_FILE")" 2>/dev/null || true

echo
echo "✅  Done!  Look for "Sigmund Analyst" in your application menu."
