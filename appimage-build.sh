#!/bin/bash
APP="sc-controller"
DEPCACHE="/tmp"
BUILDCACHE="/tmp"
EXEC="scc"
LIB="lib"

PYTHON=${PYTHON:-python3}
PYVERSION=$($PYTHON -c 'import sys; print("%d.%d" % sys.version_info[:2])')

EVDEV_VERSION=1.9.1
PYLIBACL_VERSION=0.7.3

ARCH_PYVERSION=3.14
BUNDLED_PY=3.14.7

[ x"$BUILD_APPDIR" == "x" ] && BUILD_APPDIR=$(pwd)/appimage
SITE=usr/lib/python${PYVERSION}/site-packages


function download_dep() {
	NAME=$1
	URL=$2
	if [ -e ../../${NAME}.obstargz ] ; then
		# Special case for OBS
		cp ../../${NAME}.obstargz ${DEPCACHE}/${NAME}.tar.gz
	elif [ -e ${NAME}.tar.gz ] ; then
		cp ${NAME}.tar.gz ${DEPCACHE}/${NAME}.tar.gz
	elif [ -e ${DEPCACHE}/${NAME}.tar.gz ] ; then
		echo "${DEPCACHE}/${NAME}.tar.gz already downloaded"
	else
		wget -c "${URL}" -O ${DEPCACHE}/${NAME}.tar.gz
	fi
}

function build_dep() {
	NAME="$1"
	mkdir -p ${BUILDCACHE}/${NAME}
	pushd ${BUILDCACHE}/${NAME}
	tar --extract --strip-components=1 -f ${DEPCACHE}/${NAME}.tar.gz
	# pip instead of the deprecated 'setup.py install' for third-party deps
	PYTHONPATH=${BUILD_APPDIR}/${SITE} ${PYTHON} \
		-m pip install --no-build-isolation --no-deps \
		--prefix="/usr/" --root="${BUILD_APPDIR}" .
	popd
}

function unpack_dep() {
	NAME="$1"
	pushd ${BUILD_APPDIR}
	tar --extract --exclude="usr/include**" --exclude="usr/lib/pkgconfig**" \
			--exclude="usr/lib/python2.7**" -f ${DEPCACHE}/${NAME}.tar.gz
	popd
}

set -ex		# display commands, terminate after 1st failure

# Verify host Python matches the bundled Arch Python
if [ "$PYVERSION" != "$ARCH_PYVERSION" ] ; then
	echo "ERROR: appimage-build.sh requires Python $ARCH_PYVERSION to build the AppImage,"
	echo "but system Python reports $PYVERSION ($(which ${PYTHON}))."
	echo "Install Python $ARCH_PYVERSION and set PYTHON to its interpreter."
	exit 1
fi

# Download deps
download_dep "python-${BUNDLED_PY}" "https://archive.archlinux.org/packages/p/python/python-${BUNDLED_PY}-1-x86_64.pkg.tar.zst"
download_dep "python-evdev-${EVDEV_VERSION}" "https://github.com/gvalkov/python-evdev/archive/refs/tags/v${EVDEV_VERSION}.tar.gz"
download_dep "pylibacl-${PYLIBACL_VERSION}" "https://files.pythonhosted.org/packages/cd/9e/e23f907c8e2cdc721c3d87eddda0cedee2f7cd7edf22f8439cee67f48a03/pylibacl-${PYLIBACL_VERSION}.tar.gz"
download_dep "python-gobject-3.58.0" "https://archive.archlinux.org/packages/p/python-gobject/python-gobject-3.58.0-1-x86_64.pkg.tar.zst"
download_dep "python-cairo-1.29.1" "https://archive.archlinux.org/packages/p/python-cairo/python-cairo-1.29.1-1-x86_64.pkg.tar.zst"
download_dep "gobject-introspection-runtime-1.86.0" "https://archive.archlinux.org/packages/g/gobject-introspection-runtime/gobject-introspection-runtime-1.86.0-2-x86_64.pkg.tar.zst"
download_dep "gdk-pixbuf2-2.44.7" "https://archive.archlinux.org/packages/g/gdk-pixbuf2/gdk-pixbuf2-2.44.7-1-x86_64.pkg.tar.zst"
download_dep "librsvg-2.62.91" "https://archive.archlinux.org/packages/l/librsvg/librsvg-2%3A2.62.91-1-x86_64.pkg.tar.zst"
download_dep "cairo-1.18.4" "https://archive.archlinux.org/packages/c/cairo/cairo-1.18.4-1-x86_64.pkg.tar.zst"
download_dep "libpng-1.6.58" "https://archive.archlinux.org/packages/l/libpng/libpng-1.6.58-2-x86_64.pkg.tar.zst"
download_dep "icu-78.3" "https://archive.archlinux.org/packages/i/icu/icu-78.3-1-x86_64.pkg.tar.zst"
download_dep "zlib-1.3.2" "https://archive.archlinux.org/packages/z/zlib/zlib-1%3A1.3.2-3-x86_64.pkg.tar.zst"

# Prepare & build deps
export PYTHONPATH=${BUILD_APPDIR}/${SITE}
mkdir -p "$PYTHONPATH"
if [[ $(grep ID_LIKE /etc/os-release) == *"suse"* ]] ; then
	# Special handling for OBS
	ln -s lib64 ${BUILD_APPDIR}/usr/lib
	export PYTHONPATH="$PYTHONPATH":${BUILD_APPDIR}/usr/lib64/python${PYVERSION}/site-packages/
	LIB=lib64
fi

build_dep "python-evdev-${EVDEV_VERSION}"
build_dep "pylibacl-${PYLIBACL_VERSION}"
unpack_dep "python-${BUNDLED_PY}"
unpack_dep "libpng-1.6.58"
unpack_dep "python-cairo-1.29.1"
unpack_dep "python-gobject-3.58.0"
unpack_dep "gobject-introspection-runtime-1.86.0"
unpack_dep "gdk-pixbuf2-2.44.7"
unpack_dep "cairo-1.18.4"
unpack_dep "librsvg-2.62.91"
unpack_dep "icu-78.3"
unpack_dep "zlib-1.3.2"

# Verify bundled Python runs and matches the host ABI
PYTHONHOME=${BUILD_APPDIR}/usr ${BUILD_APPDIR}/usr/bin/python${PYVERSION} \
	-c 'import sys; print("Bundled Python OK:", sys.version.split()[0])'
HOST_SUFFIX=$(${PYTHON} -c 'import importlib.machinery; print(importlib.machinery.EXTENSION_SUFFIXES[0])')
BUNDLED_SUFFIX=$(PYTHONHOME=${BUILD_APPDIR}/usr ${BUILD_APPDIR}/usr/bin/python${PYVERSION} \
	-c 'import importlib.machinery; print(importlib.machinery.EXTENSION_SUFFIXES[0])')
if [ "$HOST_SUFFIX" != "$BUNDLED_SUFFIX" ] ; then
	echo "ERROR: host Python extension suffix '$HOST_SUFFIX' does not match bundled"
	echo "Python extension suffix '$BUNDLED_SUFFIX'. C modules would not load."
	exit 1
fi

# Remove unneeded files
rm -f "${BUILD_APPDIR}/usr/${LIB}/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-ani.so"
rm -f "${BUILD_APPDIR}/usr/${LIB}/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-bmp.so"
rm -f "${BUILD_APPDIR}/usr/${LIB}/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-gif.so"
rm -f "${BUILD_APPDIR}/usr/${LIB}/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-icns.so"
rm -f "${BUILD_APPDIR}/usr/${LIB}/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-ico.so"
rm -f "${BUILD_APPDIR}/usr/${LIB}/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-jasper.so"
rm -f "${BUILD_APPDIR}/usr/${LIB}/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-jpeg.so"
rm -f "${BUILD_APPDIR}/usr/${LIB}/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-qtif.so"
rm -f "${BUILD_APPDIR}/usr/${LIB}/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-tga.so"
rm -f "${BUILD_APPDIR}/usr/${LIB}/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-tiff.so"
rm -Rf "${BUILD_APPDIR}/usr/lib/cmake"
rm -Rf "${BUILD_APPDIR}/usr/share/doc"
rm -Rf "${BUILD_APPDIR}/usr/share/gtk-doc"
rm -Rf "${BUILD_APPDIR}/usr/share/locale"
rm -Rf "${BUILD_APPDIR}/usr/share/man"
rm -Rf "${BUILD_APPDIR}/usr/share/thumbnailers"
rm -Rf "${BUILD_APPDIR}/usr/share/vala"
rm -Rf "${BUILD_APPDIR}/usr/share/icu"

# Build important part
${PYTHON} -m pip wheel --no-build-isolation --no-deps \
	--wheel-dir ${BUILD_APPDIR}/wheel . || exit 1
# Remove files from previous builds
rm -Rf ${BUILD_APPDIR}/${SITE}/scc \
	${BUILD_APPDIR}/${SITE}/sccontroller-*.dist-info \
	${BUILD_APPDIR}/${SITE}/sccontroller-*.egg-info \
	${BUILD_APPDIR}/${SITE}/libuinput*.so \
	${BUILD_APPDIR}/${SITE}/libcemuhook*.so \
	${BUILD_APPDIR}/${SITE}/libhiddrv*.so \
	${BUILD_APPDIR}/${SITE}/libsc_by_bt*.so \
	${BUILD_APPDIR}/${SITE}/libremotepad*.so
rm -f ${BUILD_APPDIR}/usr/bin/scc ${BUILD_APPDIR}/usr/bin/scc-* \
	${BUILD_APPDIR}/usr/bin/sc-controller
${PYTHON} -m pip install --no-build-isolation --no-deps --no-index \
	--ignore-installed \
	--prefix ${BUILD_APPDIR}/usr ${BUILD_APPDIR}/wheel/sccontroller-*.whl || exit 1
rm -Rf ${BUILD_APPDIR}/wheel

# Move udev stuff
mv ${BUILD_APPDIR}/usr/lib/udev/rules.d/69-${APP}.rules ${BUILD_APPDIR}/
rmdir ${BUILD_APPDIR}/usr/lib/udev/rules.d/
rmdir ${BUILD_APPDIR}/usr/lib/udev/
cp "/usr/include/linux/input-event-codes.h" ${BUILD_APPDIR}/usr/${LIB}/python${PYVERSION}/site-packages/scc/

# Move & patch desktop file
mv ${BUILD_APPDIR}/usr/share/applications/${APP}.desktop ${BUILD_APPDIR}/
sed -i "s/Icon=.*/Icon=${APP}/g" ${BUILD_APPDIR}/${APP}.desktop
sed -i "s/Exec=.*/Exec=.\/usr\/bin\/scc gui/g" ${BUILD_APPDIR}/${APP}.desktop

# Convert icon
convert -background none ${BUILD_APPDIR}/usr/share/pixmaps/${APP}.svg ${BUILD_APPDIR}/${APP}.png

# Copy appdata.xml
mkdir -p ${BUILD_APPDIR}/usr/share/metainfo/
cp scripts/${APP}.appdata.xml ${BUILD_APPDIR}/usr/share/metainfo/${APP}.appdata.xml

# Fix shebangs
for x in "${BUILD_APPDIR}/usr/bin"/sc-controller "${BUILD_APPDIR}/usr/bin"/scc* ; do
	sed -i 's|^#!.*python.*|#!/usr/bin/env python3|' "$x"
done

# Copy AppRun script
cp scripts/appimage-AppRun.sh ${BUILD_APPDIR}/AppRun
chmod +x ${BUILD_APPDIR}/AppRun

echo "Run appimagetool -n ${BUILD_APPDIR} to finish prepared appimage"
