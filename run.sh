#!/bin/bash
C_MODULES=(uinput hiddrv sc_by_bt remotepad cemuhook)
C_VERSION_uinput=9
C_VERSION_hiddrv=5
C_VERSION_sc_by_bt=3
C_VERSION_remotepad=1
C_VERSION_cemuhook=1

PYTHON=${PYTHON:-python3}

function module_extension() {
	"$PYTHON" -c 'import importlib.machinery; print(importlib.machinery.EXTENSION_SUFFIXES[0])'
}

function rebuild_c_modules() {
	local cmod="$1"
	echo "lib$cmod$EXT_SUFFIX is outdated or missing, building one"
	echo "Please wait, this should be done only once."
	echo ""

	for cm in "${C_MODULES[@]}"; do
		rm -f "./lib${cm}${EXT_SUFFIX}"
	done

	"$PYTHON" setup.py build || exit 1
	echo ""

	for cm in "${C_MODULES[@]}"; do
		built=$(ls build/lib*/lib${cm}*.so 2>/dev/null | head -1)
		if [ -n "$built" ]; then
			ln -sf "$built" "./$(basename "$built")" || exit 1
			echo "Symlinked ./$(basename "$built") -> $built"
		fi
	done
	echo ""
}

# Ensure correct cwd
cd "$(dirname "$0")"

EXT_SUFFIX=$(module_extension)

# Check if c modules are compiled and actual
for cmod in "${C_MODULES[@]}"; do
	modfile="lib${cmod}${EXT_SUFFIX}"
	if [ ! -f "$modfile" ]; then
		rebuild_c_modules "$cmod"
		continue
	fi
	eval expected_version=\$C_VERSION_${cmod}
	reported_version=$(PYTHONPATH="." "$PYTHON" -c 'import ctypes; lib=ctypes.CDLL("./'"$modfile"'"); print(lib.'${cmod}'_module_version())' 2>/dev/null)
	if [ "x$reported_version" != "x$expected_version" ]; then
		rebuild_c_modules "$cmod"
	fi
done

# Set PATH
SCRIPTS="$(pwd)/scripts"
export PATH="$SCRIPTS:$PATH"
export PYTHONPATH=".:$PYTHONPATH"
export SCC_SHARED="$(pwd)"

# Execute
exec "$PYTHON" 'scripts/sc-controller' "$@"