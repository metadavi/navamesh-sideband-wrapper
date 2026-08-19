[app]
title = Navamesh Farm
package.name = navameshfarm
package.domain = farm.navamesh

source.dir = .
source.include_exts = py,png,jpg,jpeg,webp,ttf,kv,pyi,typed,so,0,1,2,3,atlas,frag,html,css,js,whl,zip,gz,woff2,pdf,epub,pgm,opus,h,c
source.include_patterns = assets/*,assets/fonts/*,assets/audio/notifications/*,share/*
source.exclude_patterns = app_storage/*,venv/*,Makefile,./Makefil*,requirements,precompiled/*,parked/*,./setup.py,Makef*,./Makefile,Makefile,bin/*,build/*,dist/*,__pycache__/*

version.regex = __version__ = ['"](.*)['"]
version.filename = %(source.dir)s/main.py
android.numeric_version = 20260818

requirements = kivy==2.3.0,libbz2,sqlite3,pillow==10.2.0,qrcode==7.3.1,usb4a,usbserial4a,able_recipe,libwebp,libogg,libopus,opusfile,numpy,codec2,pycodec2,sh,pynacl,typing-extensions,mistune>=3.0.2,beautifulsoup4,lxst

android.gradle_dependencies =  com.android.support:support-compat:28.0.0
#android.enable_androidx = True
#android.add_aars = patches/support-compat-28.0.0.aar

p4a.local_recipes = ../recipes/

# Custom file-blacklist for the packaged python bundle. This REPLACES p4a's
# built-in blacklist, so blacklist.txt is a copy of p4a's defaults plus our own
# entries at the end — keep it in sync if p4a's defaults ever change.
#
# The entry that matters: `cryptography/*`. RNS pulls cryptography in
# transitively (lxst -> rns>=1.0.4 -> cryptography>=3.4.7), and p4a's pip step
# runs under an x86_64 host interpreter, so it resolves the *host* manylinux
# wheel and packages an x86_64 _rust.abi3.so into an arm64-v8a APK. The backend
# service then dies instantly on start with:
#   dlopen failed: ".../cryptography/hazmat/bindings/_rust.abi3.so" is for
#   EM_X86_64 (62) instead of EM_AARCH64 (183)
# which presents as a silently dead radio — no :service_sidebandservice process,
# no RNS, no announces, "No devices heard yet" forever. RNS only uses
# cryptography opportunistically and falls back to its own pure-python provider
# (RNS/Cryptography/*), which is what every working build through 1.9.8 shipped.
#
# This lives in the spec (not in scripts/build_apk.sh) so it applies to EVERY
# build host — the macOS Docker build and the Fedora Linux build alike.
# Verify after building:
#   unzip -p <apk> lib/arm64-v8a/libpybundle.so | tar -t | grep site-packages/cryptography
# must print nothing.
android.blacklist_src = blacklist.txt

icon.filename = %(source.dir)s/assets/farm/icon.png
icon.adaptive_foreground.filename = %(source.dir)s/assets/farm/icon_fg.png
icon.adaptive_background.filename = %(source.dir)s/assets/farm/icon_bg.png
presplash.filename = %(source.dir)s/assets/farm/presplash.png
android.presplash_color = #1a0f0a

# TODO: Fix inability to set "user" orientation from spec
# This is currently handled by patching the APK manifest
orientation = portrait
fullscreen = 0

android.permissions = INTERNET,REQUEST_INSTALL_PACKAGES,POST_NOTIFICATIONS,WAKE_LOCK,FOREGROUND_SERVICE,CHANGE_WIFI_MULTICAST_STATE,BLUETOOTH_SCAN,BLUETOOTH_ADVERTISE,BLUETOOTH_CONNECT,ACCESS_NETWORK_STATE,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,MANAGE_EXTERNAL_STORAGE,ACCESS_BACKGROUND_LOCATION,RECORD_AUDIO,REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,FOREGROUND_SERVICE_CONNECTED_DEVICE,MODIFY_AUDIO_SETTINGS,RECEIVE_BOOT_COMPLETED

android.api = 33
android.minapi = 24
android.ndk = 28c
android.skip_update = False
android.accept_sdk_license = True
android.release_artifact = apk
android.archs = arm64-v8a
#android.archs = arm64-v8a,armeabi-v7a
#android.logcat_filters = *:S python:D

services = sidebandservice:services/sidebandservice.py:foreground
android.whitelist = lib-dynload/termios.so
android.manifest.intent_filters = patches/intent-filter.xml

# android.add_libs_armeabi_v7a = ../libs/armeabi/*.so*
# android.add_libs_arm64_v8a = ../libs/arm64/*.so*

[buildozer]
log_level = 2
warn_on_root = 0
build_dir = ./.buildozer
bin_dir = ./bin
