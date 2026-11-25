"""carplay-advanced.sh (CarPlay Advanced Settings installer): filesystem-level tests, no head unit.

Only the absolute path constants of a temporary copy of the production script are redirected into a temporary directory. QNX-only
tools (uname, pidin, on, mount, df, sync, OnOffDSICommander) and ssh are simulated; cp/mv/dd/diff/grep/ksh are the host's own.
The ssh stand-in runs the remote command locally, as the head unit would (landing on hu-jacinto unless TEST_LAND says otherwise).
Every test runs under a POSIX shell and a Korn-compatible shell. CPA_SH / CPA_KSH may select host executables; Cygwin sh + mksh are used on Windows.
"""
import hashlib, os, shlex, shutil, struct, subprocess, sys, tempfile, unittest, urllib.parse, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE / 'carplay-advanced.sh'
FILES = ('CarPlayMenu.manifest', 'CarPlayMenu.xml', 'CarPlayMenu_ALL_Texts.zip', 'libCarPlayMenu.so', 'librghook.so',
         'librghook-kombi.so', 'librghook-most.so', 'librghook-both.so', 'libcppinch.so', 'libcpreboot.so', 'libcpprobe.so', 'boot.sh',
         'restart.sh')
LIBS = ('libCarPlayMenu.so', 'librghook.so', 'librghook-kombi.so', 'librghook-most.so', 'librghook-both.so', 'libcppinch.so',
        'libcpreboot.so', 'libcpprobe.so', 'libCarPlayMenu-hud.so')
HMI_VERSION = b'NBTevo_ID5_1803_Release ID5_1803-510-1749MA Build 71'          # no trailing newline, as in the firmware
START_SCREEN = b'#!/bin/sh \n\n# Start QNX screen resource manager\nCONFIGFILE=${GRAPHICS_ROOT}/graphics.conf\nscreen -c $CONFIGFILE &\n'
MARK = b'CarPlayMenu boot hook'
# The supported-software table of the copy under test: fake HmiMain3D / libconn_carplay.so contents and their hashes
HMI_006, HMI_1703, CONN = b'HmiMain3D 006', b'HmiMain3D 1703', b'libconn_carplay'
sha = lambda b: hashlib.sha256(b).hexdigest()
TABLE = ['# software file sha256',
         'TEST_006 HmiMain3D %s' % sha(HMI_006), 'TEST_006 libconn_carplay.so %s' % sha(CONN),
         'TEST_1703 HmiMain3D %s' % sha(HMI_1703), 'TEST_1703 libconn_carplay.so %s' % sha(CONN)]
POSIX_SHELL = os.environ.get('CPA_SH') or '/bin/sh'
KORN_SHELL = os.environ.get('CPA_KSH') or shutil.which('ksh')
SHELLS = [s for s in (POSIX_SHELL, KORN_SHELL) if s]


def elf(tag=b'new', etype=3, machine=40):
    data = bytearray(64)
    data[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HHI', data, 16, etype, machine, 1)
    struct.pack_into('<H', data, 40, 52)
    return bytes(data) + tag


class Base(object):
    SHELL = POSIX_SHELL

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cpa-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = r = Path(self.tmp.name)
        self.p = {
            'REMOTE_NODE': r / 'net/hu-omap',
            'FS_ROOT': r / 'fs',
            'HMI_VERSION_FILE': r / 'opt/hmi/ID5/data/ro/version.txt',
            'HMI_BIN': r / 'opt/hmi/bin/zipped/HmiMain3D',
            'HMI_BIN_PLAIN': r / 'opt/hmi/bin/HmiMain3D',
            'CONN_LIB': r / 'opt/conn/lib/carplay/devctrl/libconn_carplay.so',
            'PLUGIN': r / 'var/opt/hmi/data/rw/Plugins/CarPlayMenu',
            'SETTINGS': r / 'var/opt/hmi/data/rw/carplaymenu',
            'START_SCREEN': r / 'sysbin/start_screen.sh',
            'LAYOUT': r / 'opt/hmi/data/ro/mini/id5/widget/generated/Spec_State_Merged.pbw',
            'LAYOUT_ID5': r / 'opt/hmi/ID5/data/ro/mini/id5/widget/generated/Spec_State_Merged.pbw',
            'LAYOUT_COMMON': r / 'opt/hmi/data/ro/common/widget/generated/Spec_State_Merged.pbw',
            'LAYOUT_COMMON_ID5': r / 'opt/hmi/ID5/data/ro/common/widget/generated/Spec_State_Merged.pbw',
            'MMIPOD': r / 'opt/conn/bin/carplay/mm-ipod',
            'CONNECTIVITY': r / 'opt/conn/bin/Connectivity',
            'CARPLAY_INI': r / 'opt/conn/data/carplay/carplay.ini',
            'NBT_AAD_PLUGIN': r / 'opt/hmi/ID5/data/ro/Plugins/NbtAad',
            'BACKUPS': r / 'var/opt/carplay-advanced-backups',
            'LOCK': r / 'var/opt/carplay-advanced.lock',
            'STAGE': r / 'stage',
            'SHELL_TMP': r / 'tmp',
            'SHMEM': r / 'dev/shmem',
            'PROBE_HOST': r / 'stubs/probe-host',
        }
        for path in self.p.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        (self.p['FS_ROOT'] / 'opt/hmi/ID5').mkdir(parents=True)
        (self.p['REMOTE_NODE'] / 'fs/sda0/opt/hmi/ID5').mkdir(parents=True)
        self.p['HMI_VERSION_FILE'].write_bytes(HMI_VERSION)
        self.p['HMI_BIN'].write_bytes(HMI_006)
        self.p['CONN_LIB'].write_bytes(CONN)
        self.p['START_SCREEN'].write_bytes(START_SCREEN)
        self.p['START_SCREEN'].chmod(0o755)
        self.p['LAYOUT'].write_bytes(b'PBW original layout')
        self.p['LAYOUT_COMMON_ID5'].write_bytes(b'PBW original common layout')
        self.p['MMIPOD'].write_bytes(elf(b'mm-ipod', etype=2))
        self.p['CONNECTIVITY'].write_bytes(elf(b'Connectivity' * 100, etype=2))
        self.p['CARPLAY_INI'].write_bytes(b'Option: 750_480\n[Screen]\nWidth=750\n')
        content = SOURCE.read_text()
        lines = content.splitlines()
        for key, value in self.p.items():
            matches = [n for n, line in enumerate(lines) if line.startswith(key + '=')]
            self.assertEqual(len(matches), 1, key)
            lines[matches[0]] = key + '=' + shlex.quote(str(value))
        (pw,) = [n for n, line in enumerate(lines) if line.startswith('SSH_PASSWORD=')]
        lines[pw] = "SSH_PASSWORD='pw & for tests'"
        (rw,) = [n for n, line in enumerate(lines) if line.startswith('RESTART_WAIT=')]
        lines[rw] = 'RESTART_WAIT=0'                                     # the stand-in appreset "restarts" at once
        start = lines.index('supported_table() {') + 2                   # after "cat <<'EOF'"
        end = lines.index('EOF', start)
        lines[start:end] = TABLE
        if sys.platform == 'cygwin':
            # Cygwin's fork/exec loader tries to load the dummy ARM ELF in LD_PRELOAD before the
            # shell probe stub can run. Keep the installer branch under test, but pass the
            # library path as data to the stand-in instead of asking Cygwin to load it.
            lines = [line.replace('LD_PRELOAD=$1 "$PROBE_HOST"', 'TEST_PROBE_LIB=$1 "$PROBE_HOST"') for line in lines]
        self.script = r / 'carplay-advanced.sh'
        self.script.write_text('\n'.join(lines) + '\n')
        self.bin = r / 'stubs'
        self.bin.mkdir(exist_ok=True)
        # Stand-in for libcpprobe.so's constructor output. On Cygwin, avoid LD_PRELOAD of the dummy ARM ELF
        # into a shell process; the copied installer passes the path through TEST_PROBE_LIB instead.
        if sys.platform == 'cygwin':
            probe_body = 'case "$TEST_PROBE_LIB" in *libcpprobe.so) [ -n "${TEST_PROBE:-}" ] && echo "$TEST_PROBE" ;; esac\nexit 0'
        else:
            probe_body = 'case "$LD_PRELOAD" in *libcpprobe.so) [ -n "${TEST_PROBE:-}" ] && echo "$TEST_PROBE" ;; esac\nexit 0'
        self.stub('probe-host', probe_body)
        self.calls_file = r / "calls"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'], TEST_CALLS=str(self.calls_file),
                        TEST_ROOT=str(r), TEST_SHELL=self.SHELL)
        self.stub('uname', 'if [ "$1" = -s ]; then echo "${TEST_SYSNAME:-QNX}"; else echo "${TEST_NODE:-hu-omap}"; fi')
        self.stub('mount', 'echo "mount $*" >> "$TEST_CALLS"\n'
                  '[ "${TEST_MOUNT_RC:-0}" = 0 ] || exit 1\n'
                  'chmod u+w "$TEST_ROOT/sysbin"')
        self.stub('df', 'if [ "$1" = -k ]; then echo "Filesystem 1024-blocks Used Available Capacity Mounted on"; '
                  'echo "/dev/hd0t177 100000 1000 ${TEST_DF_AVAIL:-500000} 1% /var"; '
                  'else echo "Filesystem 512-blocks Used Available Capacity Mounted on"; '
                  'echo "/dev/hd0t178 100 10 90 10% $TEST_ROOT/fs"; fi')
        self.stub('sync', 'echo sync >> "$TEST_CALLS"; exit "${TEST_SYNC_RC:-0}"')
        self.stub('nc', 'echo "nc $*" >> "$TEST_CALLS"; exit "${TEST_NC_RC:-0}"')                # the reachability probe
        self.stub('OnOffDSICommander', 'echo "appreset $*" >> "$TEST_CALLS"; sleep "${TEST_HMI_SLEEP:-0}"; exit "${TEST_HMI_RC:-0}"')
        self.stub('on', 'echo on >> "$TEST_CALLS"\n'
                  '[ "$1" = -f ] && { [ "$2" = "$TEST_ROOT/net/hu-omap" ] || [ "$2" = hu-omap ]; } || exit 90\n'
                  'shift 2; prog=$1; shift\n'        # -f node <program>
                  'TEST_NODE=${TEST_FORWARD_NODE:-hu-omap}; export TEST_NODE\n'
                  'case "$prog" in */sh|*/ksh) exec "$TEST_SHELL" "$@" ;; *) exec "$prog" "$@" ;; esac')
        # ssh: the master connection (-fN) and its exit (-O) only succeed; a command runs locally as on the head unit
        self.stub('ssh', 'cmd=; seen=0\n'
                  'while [ "$#" -gt 0 ]; do case "$1" in\n'
                  '  -o) shift 2 ;;\n'
                  '  -fN) echo ssh-master >> "$TEST_CALLS"\n'
                  '       if [ "$SSH_ASKPASS_REQUIRE" = force ]; then echo "askpass:$("$SSH_ASKPASS" Password:)" >> "$TEST_CALLS"; fi\n'
                  '       exit "${TEST_SSH_RC:-0}" ;;\n'
                  '  -O) exit 0 ;;\n'
                  '  *) if [ "$seen" = 0 ]; then echo "ssh-host $1" >> "$TEST_CALLS"; seen=1; else cmd=$1; fi; shift ;;\n'
                  'esac; done\n'
                  'cmd=$(printf "%s" "$cmd" | sed "s#/bin/ksh#$TEST_SHELL#g; s#/bin/sh #$TEST_SHELL #g; s#/bin/cat#cat#g")\n'
                  'TEST_SYSNAME=QNX; TEST_NODE=${TEST_LAND:-hu-jacinto}; export TEST_SYSNAME TEST_NODE\n'
                  '[ -z "${TEST_CMDS:-}" ] || printf "%s\\n" "$cmd" >> "$TEST_CMDS"\n'
                  'case "$cmd" in *"carplay-advanced.sh restart"*) [ -z "${TEST_RESTART_SILENT:-}" ] || exec sleep 30 ;; esac\n'
                  'exec sh -c "$cmd"')
        self.stub('pidin', 'if [ "$1" = -p ]; then\n'
                  '  echo "pid euid"; echo "$2 ${TEST_EUID:-0}"; exit 0\n'
                  'fi\n'
                  'echo "pid Arguments"\n'
                  'if [ -f "$TEST_ROOT/processes" ]; then cat "$TEST_ROOT/processes"; fi')
        self.pl = self.payload()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)

    def payload(self, tag=b'new'):
        """The plugin files in plugin/ next to the script (the folder a computer uploads, and --payload on the head unit)."""
        dest = self.root / 'plugin'
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir()
        for lib in LIBS:
            (dest / lib).write_bytes(elf(tag + lib.encode()))
        (dest / 'CarPlayMenu.manifest').write_text('<plugin>\n\t<name>CarPlayMenu</name>\n</plugin>\n')
        (dest / 'CarPlayMenu.xml').write_text('<pluginApps><pluginApp applicationType="Radio"/></pluginApps>\n')
        (dest / 'CarPlayMenu-hud.xml').write_text('<pluginApps><pluginApp applicationType="Radio" hud="1"/></pluginApps>\n')
        with zipfile.ZipFile(dest / 'CarPlayMenu_ALL_Texts.zip', 'w') as z:
            z.writestr('db', b'texts')
        # boot.sh: records that it ran, and links like the real one for the switches that are on. The real boot.sh uses QNX "ln -sP"
        # (a path-manager link that overrides the original file in place); the host has no path-manager, so "ln -sf" stands in for it.
        (dest / 'boot.sh').write_text('#!/bin/ksh\necho "boot %s" >> "$TEST_CALLS"\n'
                                      'D=%s\n[ -f $D/hud_guidance ] && ln -sf $D/mm-ipod %s\nexit 0\n'
                                      % (tag.decode(), self.p['SETTINGS'], self.p['MMIPOD']))
        (dest / 'restart.sh').write_text('#!/bin/ksh\nexit 0\n')
        return dest

    def run_script(self, *args, rc=0, **env):
        e = dict(self.env, **{k: str(v) for k, v in env.items()})
        if args and args[0] == 'install' and '--payload' not in args and 'TEST_SYSNAME' not in env:
            args += ('--payload', str(self.pl))                 # on the head unit: the files are given
        if args and args[0] == 'install' and '--hmi' not in args and 'TEST_SYSNAME' not in env:
            args += ('--hmi', 'TEST_006')                       # ... and the software the computer found by hash
        res = subprocess.run([self.SHELL, str(self.script)] + list(args), env=e, capture_output=True, timeout=60)
        out = res.stdout.decode() + res.stderr.decode()
        if rc is not None:
            self.assertEqual(res.returncode, rc, out)
        return out

    def calls(self):
        return self.calls_file.read_text().splitlines() if self.calls_file.exists() else []

    def backups(self, action=None):
        b = self.p['BACKUPS']
        return sorted(d for d in b.iterdir() if d.name != 'originals' and (action is None or d.name.endswith('-' + action))) \
            if b.exists() else []

    def assert_plugin(self, tag=b'new'):
        src = self.pl
        for f in FILES:
            self.assertEqual((self.p['PLUGIN'] / f).read_bytes(), (src / f).read_bytes(), f)

    def hooked(self):
        return self.p['START_SCREEN'].read_bytes().count(MARK)


class InstallTest(Base):
    def test_refuses_non_root(self):
        out = self.run_script('install', rc=1, TEST_EUID=501)
        self.assertIn('Root SSH access could not be verified', out)

    def test_install_on_the_unit_needs_the_hash_check(self):
        out = self.run_script('install', '--hmi', '', rc=1)
        self.assertIn('needs a computer', out)
        self.assertIn("Unknown software 'ID5_1903'", self.run_script('install', '--hmi', 'ID5_1903', rc=1))
        self.assertFalse(self.p['PLUGIN'].exists())
        self.assertEqual(self.p['START_SCREEN'].read_bytes(), START_SCREEN)
        self.assertIn('supported software TEST_006', self.run_script('install', '--dry-run'))

    def test_refuses_symlinked_start_screen(self):
        real = self.root / 'elsewhere.sh'
        real.write_bytes(START_SCREEN)
        self.p['START_SCREEN'].unlink()
        self.p['START_SCREEN'].symlink_to(real)
        self.assertIn('it is a link', self.run_script('install', rc=1))

    def test_refuses_two_hook_lines(self):
        self.p['START_SCREEN'].write_bytes(START_SCREEN + b'x # ' + MARK + b'\ny # ' + MARK + b'\n')
        self.assertIn('2 boot-hook lines', self.run_script('install', rc=1))

    def test_refuses_bad_library(self):
        (self.pl / 'librghook.so').write_bytes(elf(machine=3))        # x86
        out = self.run_script('install', rc=1)
        self.assertIn('Not an ARM shared library', out)
        self.assertFalse(self.p['BACKUPS'].exists())
        self.assertEqual(list(self.pl.glob('check-*')), [])

    def test_refuses_bad_script_in_payload(self):
        (self.pl / 'boot.sh').write_text('if [ x ]; then\n')
        self.assertIn('boot.sh does not parse', self.run_script('install', rc=1))

    def test_install_hud_only_on_id6(self):
        # iDrive 6, turn-by-turn only: the menu plugin and HMI patches are skipped; only the mm-ipod route-guidance wrapper is built.
        out = self.run_script('install', '--kind', 'id6', '--mode', 'hud')
        self.assertIn('SUCCESS: install completed', out)
        self.assertIn('no reboot', out.lower())
        # the plugin dir: librghook, boot.sh and the HUD-only menu under the plugin's names, with the hud_only marker
        self.assertTrue((self.p['PLUGIN'] / 'librghook.so').exists())
        self.assertTrue((self.p['PLUGIN'] / 'boot.sh').exists())
        self.assertTrue((self.p['PLUGIN'] / 'CarPlayMenu.manifest').exists())
        self.assertEqual((self.p['PLUGIN'] / 'libCarPlayMenu.so').read_bytes(), elf(b'newlibCarPlayMenu-hud.so'))
        self.assertIn('hud="1"', (self.p['PLUGIN'] / 'CarPlayMenu.xml').read_text())
        self.assertFalse((self.p['PLUGIN'] / 'libCarPlayMenu-hud.so').exists())
        self.assertFalse((self.p['PLUGIN'] / 'libcppinch.so').exists())                # no HMI-side hooks
        self.assertTrue((self.p['PLUGIN'] / 'hud_only').exists())
        # the route-guidance wrapper: a copy of the original mm-ipod, the wrapper script and the switch
        self.assertEqual((self.p['SETTINGS'] / 'bin' / 'mm-ipod').read_bytes(), elf(b'mm-ipod', etype=2))
        wrap = (self.p['SETTINGS'] / 'mm-ipod').read_text()
        self.assertIn('librghook.so', wrap)
        self.assertIn('exec', wrap)
        self.assertTrue((self.p['SETTINGS'] / 'hud_guidance').exists())
        # boot hook added and the relink made mm-ipod a link to the wrapper
        self.assertEqual(self.hooked(), 1)
        self.assertTrue(self.p['MMIPOD'].is_symlink())

    def test_install_hud_through_a_linked_rw(self):
        # iDrive 5 (HMI 1803): /var/opt/hmi/data/rw is a link to the disk folder, and a first install has no Plugins/ there. QNX
        # mkdir -p fails with "File exists" when its last path is a link to an existing folder (checked in IDEmu); the stand-in does so.
        rw = self.p['SETTINGS'].parent
        disk = rw.parent / 'ID5'
        rw.rename(disk)
        shutil.rmtree(disk / 'Plugins')
        rw.symlink_to(disk)
        self.stub('mkdir', 'if [ "$1" = -p ]; then for a; do last=$a; done\n'
                  '  if [ -L "$last" ]; then echo "mkdir: $last: File exists" >&2; exit 1; fi\n'
                  'fi\nexec /bin/mkdir "$@"')
        out = self.run_script('install', '--kind', 'id5', '--mode', 'hud')
        self.assertIn('SUCCESS: install completed', out)
        self.assertNotIn('File exists', out)
        self.assertTrue(rw.is_symlink())
        self.assertTrue((disk / 'Plugins/CarPlayMenu/librghook.so').exists())
        self.assertTrue((disk / 'carplaymenu/mm-ipod').exists())
        self.assertTrue(self.p['MMIPOD'].is_symlink())

    def test_scanned_needs_a_build_tab_for_this_hmi(self):
        out = self.run_script('install', '--hmi', 'scanned', rc=1)
        self.assertIn('--hmi scanned needs', out)
        (self.pl / 'build.tab').write_text('hmi another build\ntouchFn 1\n')
        self.assertIn('build.tab is for another HMI build', self.run_script('install', '--hmi', 'scanned', rc=1))
        self.assertFalse(self.p['PLUGIN'].exists())
        tab = 'hmi %s\ntouchFn 43c02c\n' % HMI_VERSION.decode()
        (self.pl / 'build.tab').write_text(tab)
        out = self.run_script('install', '--hmi', 'scanned')
        self.assertIn('SUCCESS: install completed', out)
        self.assertEqual((self.p['PLUGIN'] / 'build.tab').read_text(), tab)
        out = self.run_script('install')                                               # a known build again: no build.tab
        self.assertFalse((self.p['PLUGIN'] / 'build.tab').exists())

    def test_full_stack_on_id6_needs_no_hash(self):
        # the full plugin can still be forced on iDrive 6 (the plugin self-detects; no hash is required there).
        out = self.run_script('install', '--kind', 'id6', '--mode', 'full', '--hmi', '')
        self.assertIn('SUCCESS: install completed', out)
        self.assertTrue((self.p['PLUGIN'] / 'libCarPlayMenu.so').exists())
        self.assertTrue((self.p['PLUGIN'] / 'CarPlayMenu.manifest').exists())

    def test_install_needs_payload(self):
        self.assertIn('install needs the plugin files', self.run_script('install', '--payload', '', rc=1))
        (self.pl / 'restart.sh').unlink()
        self.assertIn('No complete plugin', self.run_script('install', rc=1))
        self.assertFalse(self.p['BACKUPS'].exists())

    def test_host_is_for_computers(self):
        self.assertIn('--host is for runs from a computer', self.run_script('status', '--host', 'root@x', rc=1))

    def test_refuses_without_space(self):
        out = self.run_script('install', rc=1, TEST_DF_AVAIL=100)
        self.assertIn('Not enough free space', out)
        self.assertFalse(self.p['BACKUPS'].exists())

    def test_refuses_stale_lock(self):
        self.p['LOCK'].mkdir()
        self.assertIn('stale lock', self.run_script('install', rc=1))
        self.assertTrue(self.p['LOCK'].exists())

    def test_dry_run_changes_nothing(self):
        out = self.run_script('install', '--dry-run')
        self.assertIn('DRY RUN: all checks passed', out)
        self.assertIn('add the boot-hook line', out)
        self.assertFalse(self.p['BACKUPS'].exists())
        self.assertFalse(self.p['PLUGIN'].exists())
        self.assertFalse(self.p['LOCK'].exists())
        self.assertEqual(self.p['START_SCREEN'].read_bytes(), START_SCREEN)
        self.assertEqual(self.calls(), [])

    def test_fresh_install(self):
        out = self.run_script('install')
        self.assertIn('SUCCESS: install completed', out)
        self.assert_plugin()
        ss = self.p['START_SCREEN'].read_bytes().split(b'\n')
        self.assertEqual(ss[0], b'#!/bin/sh ')
        self.assertIn(MARK, ss[1])
        self.assertIn(str(self.p['PLUGIN']).encode() + b'/boot.sh', ss[1])
        self.assertEqual(b'\n'.join(ss[:1] + ss[2:]), START_SCREEN)
        orig = self.p['BACKUPS'] / 'originals'
        self.assertEqual((orig / 'start_screen.sh').read_bytes(), START_SCREEN)
        self.assertEqual((orig / 'Spec_State_Merged.pbw').read_bytes(), self.p['LAYOUT'].read_bytes())
        self.assertEqual((orig / 'Spec_State_Merged-common.pbw').read_bytes(), self.p['LAYOUT_COMMON_ID5'].read_bytes())
        self.assertEqual((orig / 'mm-ipod').read_bytes(), self.p['MMIPOD'].read_bytes())
        self.assertEqual((orig / 'Connectivity').read_bytes(), self.p['CONNECTIVITY'].read_bytes())
        self.assertEqual((orig / 'carplay.ini').read_bytes(), self.p['CARPLAY_INI'].read_bytes())
        (b,) = self.backups('install')
        self.assertTrue((b / 'COMMITTED').exists())
        self.assertEqual((b / 'start_screen.sh').read_bytes(), START_SCREEN)
        self.assertFalse((b / 'plugin').exists())
        self.assertIn('boot new', self.calls())
        self.assertFalse(self.p['LOCK'].exists())
        self.assertNotIn('mount', ' '.join(self.calls()))                           # the directory was writable
        self.assertNotIn('appreset', ' '.join(self.calls()))

    def test_remounts_read_only_system(self):
        (self.root / 'sysbin').chmod(0o555)
        self.addCleanup((self.root / 'sysbin').chmod, 0o755)
        self.run_script('install')
        self.assertIn('mount -o remount rw %s' % (self.root / 'fs'), self.calls())
        self.assertEqual(self.hooked(), 1)
        self.assertEqual(list((self.root / 'sysbin').glob('.start_screen*')), [])

    def test_read_only_system_and_failed_remount(self):
        (self.root / 'sysbin').chmod(0o555)
        self.addCleanup((self.root / 'sysbin').chmod, 0o755)
        old = self.p['MMIPOD']
        out = self.run_script('install', rc=1, TEST_MOUNT_RC=1)
        self.assertIn('Cannot remount', out)
        self.assertFalse(self.p['PLUGIN'].exists())
        self.assertEqual(self.p['START_SCREEN'].read_bytes(), START_SCREEN)
        self.assertTrue(old.exists())

    def test_update_keeps_settings_and_backs_up_old_plugin(self):
        self.run_script('install')
        settings = self.p['SETTINGS']
        settings.mkdir(exist_ok=True)
        (settings / 'fullscreen').write_text('1')
        (settings / 'hud_guidance').write_text('1')
        (settings / 'mm-ipod').write_text('#!/bin/ksh\nexec wrapper\n')
        (settings / 'bin').mkdir()
        (settings / 'bin/mm-ipod').write_bytes(self.p['MMIPOD'].read_bytes())
        old_plugin = {f: (self.p['PLUGIN'] / f).read_bytes() for f in FILES}
        self.pl = self.payload(tag=b'v2')
        self.run_script('install')
        self.assert_plugin()
        b = self.backups('install')[-1]
        for f in FILES:
            self.assertEqual((b / 'plugin' / f).read_bytes(), old_plugin[f], f)
        self.assertEqual((settings / 'fullscreen').read_text(), '1')                 # switches stay in place
        self.assertEqual((b / 'settings-copy/hud_guidance').read_text(), '1')
        self.assertFalse((b / 'settings-copy/bin').exists())
        self.assertEqual(self.hooked(), 1)                                            # not added twice
        self.assertIn('boot v2', self.calls())                                        # the new boot.sh relinked

    def test_existing_link_is_removed_to_reach_original_then_relinked(self):
        settings = self.p['SETTINGS']
        settings.mkdir(exist_ok=True)
        (settings / 'hud_guidance').write_text('1')
        (settings / 'mm-ipod').write_text('#!/bin/ksh\nexec wrapper\n')
        real = self.p['MMIPOD'].read_bytes()
        self.p['MMIPOD'].unlink()
        self.p['MMIPOD'].symlink_to(settings / 'mm-ipod')
        out = self.run_script('install')
        self.assertIn('Removed the earlier link', out)
        b = self.backups('install')[-1]
        self.assertIn(str(self.p['MMIPOD']), (b / 'unlinked').read_text())
        self.assertTrue(self.p['MMIPOD'].is_symlink())                                # made again by boot.sh
        self.assertNotEqual(real, b'')

    def test_firmware_change_after_first_backup_is_kept_too(self):
        self.run_script('install')
        self.p['CONNECTIVITY'].write_bytes(elf(b'updated Connectivity', etype=2))
        out = self.run_script('install')
        self.assertIn('differs from the kept original', out)
        b = self.backups('install')[-1]
        self.assertEqual((b / 'system/Connectivity').read_bytes(), self.p['CONNECTIVITY'].read_bytes())
        self.assertNotEqual((self.p['BACKUPS'] / 'originals/Connectivity').read_bytes(), self.p['CONNECTIVITY'].read_bytes())

    def test_hook_from_hook_tool_is_recognised(self):
        line = b'[ -f x/boot.sh ] && ksh x/boot.sh > /dev/null 2>&1   # ' + MARK + b' (tools/car/carplaymenu_hook.sh)'
        lines = START_SCREEN.split(b'\n')
        self.p['START_SCREEN'].write_bytes(b'\n'.join(lines[:1] + [line] + lines[1:]))
        out = self.run_script('install')
        self.assertIn('already had the hook', out)
        self.assertIn('replace the older boot-hook line', out)       # it only tried /var, which does not exist yet at boot
        self.assertEqual(self.hooked(), 1)
        ss = self.p['START_SCREEN'].read_bytes().split(b'\n')
        self.assertIn(b'CPM_BOOT=/fs/sda1/opt/hmi/data/ID5/Plugins/CarPlayMenu/boot.sh', ss[1])
        self.assertEqual(b'\n'.join(ss[:1] + ss[2:]), START_SCREEN)
        self.assertEqual((self.p['BACKUPS'] / 'originals/start_screen.sh').read_bytes(), START_SCREEN)
        self.assertNotIn('replace the older', self.run_script('install'))   # current line: left as it is

    def test_hook_line_runs_boot_sh(self):
        self.run_script('install')
        line = self.p['START_SCREEN'].read_bytes().split(b'\n')[1].decode()
        (self.p['PLUGIN'] / 'boot.sh').write_text('echo ran > %s\n' % (self.root / 'ran'))
        subprocess.run(['/bin/sh', '-c', line.replace('/bin/ksh', 'sh')], check=True)   # /fs/sda1 is absent here: the /var copy runs
        self.assertEqual((self.root / 'ran').read_text(), 'ran\n')

    def test_failure_after_switch_rolls_back(self):
        self.run_script('install')
        old_plugin = {f: (self.p['PLUGIN'] / f).read_bytes() for f in FILES}
        hooked = self.p['START_SCREEN'].read_bytes()
        self.p['START_SCREEN'].write_bytes(START_SCREEN)                              # as if someone removed the hook
        out = self.run_script('install', rc=1, TEST_SYNC_RC=1)
        self.assertIn('Previous files restored', out)
        for f in FILES:
            self.assertEqual((self.p['PLUGIN'] / f).read_bytes(), old_plugin[f], f)
        self.assertEqual(self.p['START_SCREEN'].read_bytes(), START_SCREEN)
        b = self.backups('install')[-1]
        self.assertTrue((b / 'ROLLED_BACK').exists())
        self.assertFalse((b / 'COMMITTED').exists())
        self.assertFalse(self.p['LOCK'].exists())
        self.assertNotEqual(hooked, START_SCREEN)

    def test_fresh_install_failure_rolls_back_to_nothing(self):
        out = self.run_script('install', rc=1, TEST_SYNC_RC=1)
        self.assertIn('Previous files restored', out)
        self.assertFalse(self.p['PLUGIN'].exists())
        self.assertEqual(self.p['START_SCREEN'].read_bytes(), START_SCREEN)

    def test_restart_after_success(self):
        out = self.run_script('install', '--restart-hmi')
        self.assertIn('appreset', self.calls()[-1])
        self.assertIn('OnOffDSICommander appreset', out)
        self.assertFalse(self.p['LOCK'].exists())

    def test_restart_without_onoff_uses_plugin_reboot(self):
        (self.bin / 'OnOffDSICommander').unlink()                     # HMI ID5_1703-490 has none
        out = self.run_script('install', '--restart-hmi', rc=3)       # the host's cat ignores the preload: "did not happen"
        self.assertIn('libcpreboot.so', out)
        self.assertIn('reboot did not happen', out)
        self.assert_plugin()
        self.assertFalse(self.p['LOCK'].exists())

    def hud_probe_script(self):
        self.script.write_text(self.script.read_text().replace('HUD_PROBE_WAIT=8', 'HUD_PROBE_WAIT=1'))
        self.p['PLUGIN'].mkdir(parents=True, exist_ok=True)                           # an installed plugin
        self.p['SETTINGS'].mkdir(parents=True, exist_ok=True)

    def test_hud_probe_needs_the_plugin(self):
        self.assertIn('Nothing to ask: install the plugin', self.run_script('hud-probe', rc=1))

    def test_hud_probe_without_the_plugin_answering(self):
        self.hud_probe_script()
        self.p['SHMEM'].mkdir(parents=True, exist_ok=True)
        (self.p['SHMEM'] / 'carplaymenu.log').write_text('CarPlayMenu: HUD: HUDTerminal 82/00 at device 0101\n')
        out = self.run_script('hud-probe')
        self.assertIn('HUDTerminal 82/00 at device 0101', out)                   # what the plugin found at its start
        self.assertIn("did not take the test channel", out)
        self.assertIn('SUCCESS: hud-probe completed', out)
        self.assertFalse((self.p['SHMEM'] / 'carplaymenu-hudcmd').exists())
        self.assertFalse((self.p['SETTINGS'] / 'hud_debug').exists())              # put back as it was (off)

    def test_hud_probe_lists_surfaces_and_names(self):
        self.hud_probe_script()
        shm = self.p['SHMEM']
        shm.mkdir(parents=True, exist_ok=True)
        self.p['SETTINGS'].mkdir(parents=True, exist_ok=True)
        (self.p['SETTINGS'] / 'hud_debug').write_text('1\n')                      # was on: stays on
        log = shm / 'carplaymenu.log'
        log.write_text('CarPlayMenu: HUD: MOST client 3, device 2003\n')
        # a stand-in for the plugin: takes the batch and answers like the cluster would (MINI F5x form for 5, BMW 6WB form for 0x1f)
        fake = ('for i in $(seq 1 100); do if [ -f "$1/carplaymenu-hudcmd" ]; then rm -f "$1/carplaymenu-hudcmd"; {\n'
                'echo "CarPlayMenu: HUD in   0101>2003 fkt c04 op d len 6: 00 05 00 78 00 48"\n'
                'echo "CarPlayMenu: HUD in   0101>2003 fkt c04 op d len 6: 00 18 00 00 00 00"\n'
                'echo "CarPlayMenu: HUD in   0101>2003 fkt c04 op d len 7: 00 1f 01 00 dd 00 9e"\n'
                'echo "CarPlayMenu: HUD seen 0101>201f fkt 22b op d len 7: 00 01 00 05 01 00 04"\n'
                '} >> "$1/carplaymenu.log"; exit 0; fi; sleep 0.2; done\n')
        (self.root / 'fake.sh').write_text(fake)
        bg = subprocess.Popen(['/bin/sh', str(self.root / 'fake.sh'), str(shm)])
        self.addCleanup(bg.kill)
        out = self.run_script('hud-probe')
        self.assertIn('0x0005: 120 x 72 (MINI F5x form)', out)
        self.assertIn('0x001f: 221 x 158 (BMW 6WB form)', out)
        self.assertNotIn('0x0018', out)                                               # 0 x 0: no such surface
        self.assertIn('fkt 22b op d len 7: 00 01 00 05 01 00 04', out)
        self.assertTrue((self.p['SETTINGS'] / 'hud_debug').exists())

    def test_hud_probe_step_draws_a_test_picture(self):
        self.hud_probe_script()
        shm = self.p['SHMEM']
        shm.mkdir(parents=True, exist_ok=True)
        got = self.root / 'batch.txt'
        fake = ('for i in $(seq 1 50); do if [ -f "$1/carplaymenu-hudcmd" ]; then mv "$1/carplaymenu-hudcmd" "$2"; exit 0; fi; '
                'sleep 0.1; done\n')
        (self.root / 'fake.sh').write_text(fake)
        bg = subprocess.Popen(['/bin/sh', str(self.root / 'fake.sh'), str(shm), str(got)])
        self.addCleanup(bg.kill)
        out = self.run_script('hud-probe', '--probe-step', '6wb-hud:draw')
        self.assertIn('PROBE-STEP 6wb-hud:draw taken', out)
        lines = got.read_text().split()
        self.assertEqual(lines[0], '@2')                                              # to the HUD terminal 82/02
        self.assertIn('001701', ' '.join(lines))                                      # 6WB: the area 0x17 shown
        bg.wait(5)
        out = self.run_script('hud-probe', '--probe-step', 'mini:clear', rc=1)        # nobody takes it now
        self.assertIn('PROBE-STEP mini:clear not taken', out)
        self.assertFalse((shm / 'carplaymenu-hudcmd').exists())
        self.assertIn('Unknown test picture', self.run_script('hud-probe', '--probe-step', 'x:draw', rc=1))

    def test_restart_finds_onoff_outside_the_path(self):
        # on the car the SSH shell's PATH has no /opt/core/bin: the installer looks there itself (ONOFF_BINS)
        (self.bin / 'OnOffDSICommander').rename(self.root / 'OnOffDSICommander')
        self.script.write_text(self.script.read_text().replace(
            "ONOFF_BINS='/opt/core/bin/OnOffDSICommander /opt/car/bin/OnOffDSICommander'",
            "ONOFF_BINS='/nonexistent/OnOffDSICommander %s'" % (self.root / 'OnOffDSICommander')))
        out = self.run_script('restart')
        self.assertIn('Restarting the head unit (%s appreset)' % (self.root / 'OnOffDSICommander'), out)
        self.assertIn('appreset appreset', self.calls())

    def test_restart_with_onoff_on_jacinto(self):
        # HMI 1703: only hu-jacinto has it (/opt/car/bin); hu-omap runs it there with on -f hu-jacinto
        (self.bin / 'OnOffDSICommander').unlink()
        j = self.root / 'net/hu-jacinto/opt/car/bin/OnOffDSICommander'
        j.parent.mkdir(parents=True)
        j.write_text('#!/bin/sh\necho "jacinto appreset $*" >> "$TEST_CALLS"\n')
        j.chmod(0o755)
        self.script.write_text(self.script.read_text().replace('ONOFF_JACINTO=/net/hu-jacinto/', 'ONOFF_JACINTO=%s/net/hu-jacinto/' % self.root))
        self.stub('on', 'echo "on $*" >> "$TEST_CALLS"\n'
                  '[ "$1" = -f ] && [ "$2" = hu-jacinto ] || exit 90\nshift 2; prog=$1; shift\n'
                  'exec "$TEST_ROOT/net/hu-jacinto$prog" "$@"')
        out = self.run_script('restart')
        self.assertIn('Restarting the head unit (on -f hu-jacinto /opt/car/bin/OnOffDSICommander appreset)', out)
        self.assertIn('jacinto appreset appreset', self.calls())

    def test_restart_falls_back_to_libcpreboot(self):
        self.run_script('install')
        out = self.run_script('restart', rc=3, TEST_HMI_RC=1)                         # appreset fails: libcpreboot.so next
        self.assertIn('appreset did not restart the head unit; restarting with', out)
        self.assertIn('reboot did not happen', out)
        # appreset returns 0 but the unit is still up after RESTART_WAIT: libcpreboot.so too
        self.script.write_text(self.script.read_text().replace('RESTART_WAIT=0', 'RESTART_WAIT=1'))
        out = self.run_script('restart', rc=3)
        self.assertIn('appreset did not restart the head unit; restarting with', out)

    def test_restart_action(self):
        self.assertIn('would be restarted', self.run_script('restart', '--dry-run'))
        self.assertNotIn('appreset', ' '.join(self.calls()))
        self.run_script('restart')
        self.assertIn('appreset', ' '.join(self.calls()))
        self.assertIn('goes with install or uninstall', self.run_script('status', '--restart-hmi', rc=1))

    def test_here_documents_without_tmp(self):
        """A unit without /tmp: ksh would fail on the first here-document ("can't create temporary file"), so TMPDIR becomes
        /dev/shmem; an existing /tmp or a TMPDIR that is set is left alone."""
        self.stub('pidin', 'echo "tmpdir ${TMPDIR:-unset}" >> "$TEST_CALLS"\n'
                  'if [ "$1" = -p ]; then echo "pid euid"; echo "$2 ${TEST_EUID:-0}"; exit 0; fi\necho "pid Arguments"')
        self.p['SHMEM'].mkdir()
        env = {k: v for k, v in self.env.items() if k != 'TMPDIR'}
        res = subprocess.run([self.SHELL, str(self.script), 'status'], env=env, capture_output=True, timeout=60)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn('tmpdir %s' % self.p['SHMEM'], self.calls())
        self.calls_file.unlink()
        self.p['SHELL_TMP'].mkdir()
        subprocess.run([self.SHELL, str(self.script), 'status'], env=env, capture_output=True, timeout=60, check=True)
        self.assertIn('tmpdir unset', self.calls())
        self.calls_file.unlink()
        self.run_script('status', TMPDIR='/somewhere')
        self.assertIn('tmpdir /somewhere', self.calls())

    def test_restart_failure_is_exit_3(self):
        self.run_script('install', '--restart-hmi', rc=3, TEST_HMI_RC=1)
        self.assert_plugin()

    def test_forwarded_from_jacinto(self):
        out = self.run_script('install', '--dry-run', TEST_NODE='hu-jacinto')
        self.assertIn('Entering hu-omap', out)
        self.assertIn('DRY RUN', out)
        self.assertEqual(self.calls()[0], 'on')

    def test_forwarding_loop_refused(self):
        out = self.run_script('install', TEST_NODE='hu-jacinto', TEST_FORWARD_NODE='hu-jacinto', rc=1)
        self.assertIn('forwarding loop', out)


class FromComputerTest(Base):
    """Runs on a computer: one SSH connection, upload to STAGE on hu-omap, the script runs itself there."""
    def computer(self, *args, rc=0, **env):
        return self.run_script(*args, rc=rc, TEST_SYSNAME='Linux', **env)

    def test_install_over_ssh(self):
        out = self.computer('install')
        self.assertIn('Uploaded plugin/', out)
        self.assertIn('Done: CarPlay Advanced Settings is installed', out)
        self.assert_plugin()
        self.assertEqual(self.hooked(), 1)
        self.assertFalse(self.p['STAGE'].exists())                                    # upload removed
        calls = self.calls()
        self.assertEqual(calls[0], 'nc -z -G 4 169.254.199.99 22')                        # reachable first
        self.assertEqual(calls[1:4], ['ssh-master', 'askpass:pw & for tests', 'ssh-host root@169.254.199.99'])
        self.assertEqual(calls.count('ssh-master'), 1)                                # one login
        self.assertIn('on', calls)                                                    # sshd on hu-jacinto: on -f hu-omap
        (b,) = self.backups('install')                                                # the run's backup, copied to BACKUP/
        local = self.root / 'BACKUP'
        self.assertIn('Backup copied to BACKUP/%s' % b.name, out)
        self.assertTrue((local / b.name / 'installer-output.log').is_file())             # the head unit's full output
        for f in b.rglob('*'):
            if f.is_file():
                self.assertEqual((local / b.name / f.relative_to(b)).read_bytes(), f.read_bytes(), f)
        self.assertEqual((local / 'originals/Connectivity').read_bytes(), self.p['CONNECTIVITY'].read_bytes())
        self.assertEqual((local / 'originals/start_screen.sh').read_bytes(), START_SCREEN)
        self.assertNotIn('appreset', ' '.join(calls))

    def test_supported_by_hash(self):
        self.p['HMI_VERSION_FILE'].write_bytes(b'NBTevo_ID5_1703_Release ID5_1703-490-1650ZD Build 139')
        self.p['HMI_BIN'].write_bytes(HMI_1703)
        out = self.computer('install')
        self.assertIn('Supported software: TEST_1703', out)
        self.assertIn('supported software TEST_1703, checked by hash', out)
        self.assertIn('Done: CarPlay Advanced Settings is installed', out)

    def test_plain_hmi_binary_when_there_is_no_zipped_one(self):
        self.p['HMI_BIN'].unlink()
        self.p['HMI_BIN_PLAIN'].write_bytes(HMI_006)
        self.assertIn('Supported software: TEST_006', self.computer('install', '--dry-run'))

    def test_unsupported_software_is_refused_with_an_issue_link(self):
        self.p['HMI_VERSION_FILE'].write_bytes(b'NBTevo_ID5_1903_Release ID5_1903-999 Build 12')
        self.p['HMI_BIN'].write_bytes(b'HmiMain3D other')
        out = self.computer('install', rc=1)
        self.assertIn('not in the supported list', out)
        self.assertIn(sha(b'HmiMain3D other'), out)
        self.assertIn('Nothing was installed', out)
        self.assertFalse(self.p['STAGE'].exists())                                    # nothing uploaded
        self.assertFalse(self.p['PLUGIN'].exists())
        (link,) = [l.strip() for l in out.splitlines() if l.strip().startswith('https://github.com/')]
        url = urllib.parse.urlsplit(link)
        self.assertEqual(url.path, '/st1ng/nbtevo-carplay-advanced/issues/new')
        q = urllib.parse.parse_qs(url.query)
        self.assertEqual(q['title'], ['Support for HMI NBTevo_ID5_1903_Release ID5_1903-999 Build 12'])
        self.assertIn('HmiMain3D sha256: %s' % sha(b'HmiMain3D other'), q['body'][0].splitlines())
        self.assertIn('libconn_carplay.so sha256: %s' % sha(CONN), q['body'][0].splitlines())
        # status reports it too, but still runs
        out = self.computer('status')
        self.assertIn('not in the supported list', out)
        self.assertIn('Plugin: not installed', out)

    def unknown_scannable(self):
        version = b'NBTevo_ID5_1803_Release ID5_1803-510-1749I Build 66'
        self.p['HMI_VERSION_FILE'].write_bytes(version)
        elf, want = synth_hmi()
        self.p['HMI_BIN'].write_bytes(elf)
        return version.decode(), elf, want

    def issue_link(self, out):
        (link,) = [l.strip() for l in out.splitlines() if l.strip().startswith('https://github.com/')]
        return urllib.parse.parse_qs(urllib.parse.urlsplit(link).query)

    def test_unknown_build_is_scanned_and_installed_with_yes(self):
        version, elf, want = self.unknown_scannable()
        out = self.computer('install', '--yes')
        self.assertIn('This HMI build is not supported yet: ' + version, out)
        self.assertIn('Installing with the scanned addresses (--yes)', out)
        self.assertIn('not yet supported: addresses from the HMI scan', out)
        self.assertIn('Done: CarPlay Advanced Settings is installed', out)
        tab = (self.p['PLUGIN'] / 'build.tab').read_text().splitlines()
        self.assertEqual(tab[0], 'hmi ' + version)
        self.assertEqual(tab[1:], want)
        q = self.issue_link(out)
        self.assertEqual(q['title'], ['Scanned HMI ' + version])
        body = q['body'][0].splitlines()
        self.assertIn('HmiMain3D sha256: %s' % sha(elf), body)
        self.assertIn(want[0], body)                                                 # the addresses
        self.assertIn('scan sha256: %s' % sha(('\n'.join(l for l in want if not l.startswith('#')) + '\n').encode()), body)

    def test_unknown_build_scanned_needs_a_yes(self):
        self.unknown_scannable()
        out = self.computer('install', rc=1)                                           # no terminal, no --yes
        self.assertIn('This HMI build is not supported yet', out)
        self.assertIn('run again on a terminal (or with --yes)', out)
        self.assertFalse(self.p['STAGE'].exists())                                    # nothing uploaded
        self.assertFalse(self.p['PLUGIN'].exists())
        self.assertEqual(self.issue_link(out)['title'][0][:12], 'Scanned HMI ')
        out = self.computer('install', '--dry-run')                                    # a dry run needs no yes
        self.assertIn('DRY RUN', out)

    def test_known_build_runs_the_scan_check(self):
        # the made-up HmiMain3D of the tests is no ELF: the check cannot agree, which is a note only (the built-in table is used)
        out = self.computer('install')
        self.assertIn('Supported software: TEST_006', out)
        self.assertIn('The HMI scan does not agree with the built-in table for TEST_006', out)
        self.assertIn('Done: CarPlay Advanced Settings is installed', out)
        self.assertFalse((self.p['PLUGIN'] / 'build.tab').exists())

    def test_hud_probe_from_the_computer_is_saved(self):
        self.script.write_text(self.script.read_text().replace('HUD_PROBE_WAIT=8', 'HUD_PROBE_WAIT=1'))
        self.p['PLUGIN'].mkdir(parents=True, exist_ok=True)
        self.p['SETTINGS'].mkdir(parents=True, exist_ok=True)
        self.p['SHMEM'].mkdir(parents=True, exist_ok=True)
        (self.p['SHMEM'] / 'carplaymenu.log').write_text('CarPlayMenu: HUD: registry: HUDTerminal 82/02 at device 0102\n')
        out = self.computer('hud-probe')
        self.assertIn('Asking the cluster and the HUD', out)
        self.assertIn('HUDTerminal 82/02 at device 0102', out)
        (saved,) = (self.root / 'BACKUP').glob('hud-probe-*.txt')
        self.assertIn('SUCCESS: hud-probe completed', saved.read_text())
        self.assertNotIn('Checking the head unit software', out)                      # no 60 MB read for a probe
        self.assertIn('Visual check skipped (no terminal)', out)
        self.assertFalse(self.p['STAGE'].exists())

    def test_mmipod_unknown_is_a_note(self):
        mm = sha(elf(b'mm-ipod', etype=2))
        out = self.computer('install')
        self.assertIn('mm-ipod is not one we know (sha256 %s)' % mm, out)
        self.assertIn('Done: CarPlay Advanced Settings is installed', out)

    def test_mmipod_known(self):
        mm = sha(elf(b'mm-ipod', etype=2))
        s = self.script.read_text()
        start = s.index("mmipod_table() {\n    cat <<'EOF'\n") + len("mmipod_table() {\n    cat <<'EOF'\n")
        self.script.write_text(s[:start] + '%s  TEST_006 TEST_1703\n' % mm + s[start:])
        self.assertIn('mm-ipod is a known one (TEST_006, TEST_1703)', self.computer('install', '--dry-run'))

    def test_mmipod_hashed_from_the_kept_copy_when_linked(self):
        mm = sha(elf(b'mm-ipod', etype=2))
        self.computer('install', '--hud')
        self.assertTrue(self.p['MMIPOD'].is_symlink())                                # now the wrapper
        out = self.computer('status')
        self.assertIn('mm-ipod is not one we know (sha256 %s)' % mm, out)              # the original, not the wrapper script

    def test_unsupported_report_has_the_mmipod_hash(self):
        self.p['HMI_VERSION_FILE'].write_bytes(b'NBTevo_ID5_1903_Release ID5_1903-999 Build 12')
        self.p['HMI_BIN'].write_bytes(b'HmiMain3D other')
        out = self.computer('install', rc=1)
        self.assertIn('mm-ipod sha256: %s' % sha(elf(b'mm-ipod', etype=2)), self.issue_link(out)['body'][0].splitlines())

    def test_missing_library_is_unsupported(self):
        self.p['CONN_LIB'].unlink()
        out = self.computer('install', rc=1)
        self.assertIn('libconn_carplay.so  missing', out)

    def test_hmi_option_refused_from_a_computer(self):
        self.assertIn('--hmi is for runs on the head unit', self.computer('install', '--hmi', 'TEST_006', rc=1))

    def test_login_with_the_password(self):
        self.computer('status')
        self.assertIn('askpass:pw & for tests', self.calls())                         # ssh got it from the helper

    def test_login_without_a_password(self):
        self.script.write_text(self.script.read_text().replace("SSH_PASSWORD='pw & for tests'", 'SSH_PASSWORD='))
        self.computer('status')
        self.assertIn('ssh-master', self.calls())
        self.assertFalse([c for c in self.calls() if c.startswith('askpass')])         # ssh asks itself

    def test_install_landing_on_omap(self):
        out = self.computer('install', '--host', 'root@10.0.0.2', TEST_LAND='hu-omap')
        self.assertIn('Done: CarPlay Advanced Settings is installed', out)
        self.assertNotIn('on', self.calls())
        self.assertIn('ssh-host root@10.0.0.2', self.calls())

    def test_dry_run_over_ssh(self):
        out = self.computer('install', '--dry-run')
        self.assertIn('DRY RUN', out)
        self.assertFalse(self.p['PLUGIN'].exists())
        self.assertEqual(self.hooked(), 0)
        self.assertFalse(self.p['STAGE'].exists())
        self.assertFalse((self.root / 'BACKUP').exists())

    def test_restart_after_the_backup_copy(self):
        out = self.computer('install', '--restart-hmi')
        self.assertIn('appreset', ' '.join(self.calls()))
        self.assertLess(out.index('Backup copied'), out.index('Restarting the head unit'))
        self.assertTrue(any((self.root / 'BACKUP').glob('*-install/COMMITTED')))

    def test_files_copied_here_before_the_upload(self):
        out = self.computer('install')
        self.assertLess(out.index('Copying the head unit files this run may change'), out.index('Uploading the plugin'))
        (pre,) = (self.root / 'BACKUP').glob('*-install-before')
        self.assertEqual((pre / ('system' + str(self.p['START_SCREEN']))).read_bytes(), START_SCREEN)   # as it was: no hook line
        self.assertEqual((pre / ('system' + str(self.p['MMIPOD']))).read_bytes(), elf(b'mm-ipod', etype=2))
        manifest = (pre / 'manifest.txt').read_text()
        self.assertIn('absent  %s' % self.p['PLUGIN'], manifest)                       # first install
        self.assertIn('Before', out)
        # the next run copies the installed plugin first; the plugin's own links are named, not copied
        self.computer('uninstall')
        self.computer('install', '--hud')
        out = self.computer('install')
        pre = sorted((self.root / 'BACKUP').glob('*-install-before'))[-1]
        manifest = (pre / 'manifest.txt').read_text()
        self.assertIn('folder  %s' % self.p['PLUGIN'], manifest)
        self.assertIn('link    %s' % self.p['MMIPOD'], manifest)
        self.assertTrue((pre / ('folders' + str(self.p['SETTINGS'])) / 'bin' / 'mm-ipod').is_file())   # its original

    def test_second_hud_install_on_top_of_one(self):
        # a second --hud on top of one stopped at "mm-ipod is missing or already a link" (issue #9): the wrapper now gets the
        # original the first install kept
        original = self.p['MMIPOD'].read_bytes()
        self.computer('install', '--hud')
        self.assertTrue(self.p['MMIPOD'].is_symlink())
        out = self.computer('install', '--hud')
        self.assertNotIn('missing or already a link', out)
        self.assertIn('the wrapper gets the kept original', out)
        self.assertIn('Done: CarPlay Advanced Settings is installed', out)
        self.assertTrue(self.p['MMIPOD'].is_symlink())
        self.assertEqual((self.p['SETTINGS'] / 'bin' / 'mm-ipod').read_bytes(), original)
        self.computer('uninstall')
        self.assertFalse(self.p['MMIPOD'].is_symlink())

    def test_failed_copy_stops_before_the_upload(self):
        (self.root / 'BACKUP').write_text('not a folder')
        out = self.computer('install', rc=1)
        self.assertIn('nothing was sent to the head unit or changed', out)
        self.assertFalse(self.p['STAGE'].exists())
        self.assertFalse(self.p['PLUGIN'].exists())
        self.assertEqual(self.hooked(), 0)

    def test_dry_run_copies_nothing(self):
        self.computer('install', '--dry-run')
        self.assertFalse(list((self.root / 'BACKUP').glob('*-before')))

    def test_restart_without_the_plugin_sends_libcpreboot(self):
        (self.bin / 'OnOffDSICommander').unlink()                      # and no plugin installed: the computer sends libcpreboot.so
        out = self.computer('restart', rc=3)                           # the host's cat ignores the preload: "did not happen"
        self.assertNotIn('Neither OnOffDSICommander nor libcpreboot.so', out)
        self.assertIn('libcpreboot.so', out)
        self.assertIn('reboot did not happen', out)

    def test_hud_install_offers_the_restart(self):
        out = self.computer('install', '--hud')
        self.assertIn('A restart of the head unit is needed', out)
        self.assertIn('for the HUD-only', out)
        self.assertIn('sh carplay-advanced.sh restart', out)                           # no terminal: how to restart later
        self.assertTrue((self.p['PLUGIN'] / 'libcpreboot.so').is_file())               # "restart" works without OnOffDSICommander

    def test_restart_does_not_wait_for_the_dropped_connection(self):
        # a real reboot leaves the SSH session hanging until a timeout: the installer stops once the head unit says it restarts
        import time
        t0 = time.monotonic()
        out = self.computer('install', '--restart-hmi', TEST_HMI_SLEEP='60')
        self.assertLess(time.monotonic() - t0, 40)
        self.assertIn('The head unit is restarting', out)

    def test_restart_after_install_runs_the_uploaded_script(self):
        # the restart after an install runs the uploaded script, never a script streamed into "/bin/sh -s" (QNX's sh reads a pipe
        # one byte at a time, a round trip each through on -f: issue #12, BMW F31, never reached the reboot)
        cmds = self.root / 'cmds'
        for extra in (('--restart-hmi',), ('--hud', '--restart-hmi')):
            with self.subTest(extra=extra):
                if cmds.exists():
                    cmds.unlink()
                if extra[0] == '--hud':
                    self.computer('uninstall')
                out = self.computer('install', *extra, TEST_CMDS=str(cmds))
                self.assertIn('The head unit is restarting', out)
                run = cmds.read_text().splitlines()
                self.assertFalse([c for c in run if ' -s ' in c or c.endswith(' -s')], run)
                restart = [c for c in run if c.endswith('carplay-advanced.sh restart')]
                self.assertEqual(len(restart), 1, run)
                self.assertIn(str(self.p['STAGE']), restart[0])
                self.assertIn('appreset', ' '.join(self.calls()))

    def test_unconfirmed_restart_is_a_note_not_an_error(self):
        self.script.write_text(self.script.read_text().replace('REBOOT_CONFIRM_S=75', 'REBOOT_CONFIRM_S=2'))
        out = self.computer('install', '--restart-hmi', rc=3, TEST_RESTART_SILENT='1')
        self.assertIn('did not confirm the restart in 2 s', out)
        self.assertIn('What was installed is complete', out)
        self.assertIn('sh carplay-advanced.sh restart', out)
        self.assertNotIn('ERROR', out)
        self.assertTrue(any((self.root / 'BACKUP').glob('*-install/COMMITTED')))

    def test_known_build_mapped_by_hand(self):
        # a known build the HMI scan's patterns do not cover, without Full-screen CarPlay (as ID5_1607-490-1610T Build 153)
        s = self.script.read_text()
        start = s.index("supported_table() {\n    cat <<'EOF'\n") + len("supported_table() {\n    cat <<'EOF'\n")
        self.script.write_text(s[:start] + 'TEST_006 scan none\nTEST_006 fullscreen none\n' + s[start:])
        out = self.computer('install')
        self.assertIn('Supported software: TEST_006', out)
        self.assertIn("TEST_006 was mapped by hand (the HMI scan's patterns do not cover it)", out)
        self.assertIn('TEST_006 has no Full-screen CarPlay yet', out)
        self.assertNotIn('does not agree with the built-in table', out)               # no request for a report
        self.assertIn('Done: CarPlay Advanced Settings is installed', out)

    def test_plugin_checked_before_connecting(self):
        (self.pl / 'librghook.so').write_bytes(elf(machine=3))                       # x86
        self.assertIn('Not an ARM shared library', self.computer('install', rc=1))
        self.assertEqual(self.calls(), [])
        self.pl = self.payload()
        with zipfile.ZipFile(self.pl / 'CarPlayMenu_ALL_Texts.zip', 'w') as z:
            z.writestr('db', b'texts')
        (self.pl / 'CarPlayMenu_ALL_Texts.zip').write_bytes(b'XX' + (self.pl / 'CarPlayMenu_ALL_Texts.zip').read_bytes())
        self.assertIn('Invalid ZIP signature', self.computer('install', rc=1))
        self.pl = self.payload()
        (self.pl / 'CarPlayMenu.manifest').write_text('<plugin/>\n')
        self.assertIn('does not name the CarPlayMenu plugin', self.computer('install', rc=1))
        self.assertEqual(self.calls(), [])

    def test_status_and_uninstall_over_ssh(self):
        self.computer('install')
        self.assertIn('Plugin: installed', self.computer('status'))
        out = self.computer('uninstall')
        self.assertIn('Done: CarPlay Advanced Settings is uninstalled', out)
        self.assertTrue(any((self.root / 'BACKUP').glob('*-uninstall/COMMITTED')))
        self.assertFalse(self.p['PLUGIN'].exists())
        self.assertEqual(self.hooked(), 0)

    def test_failure_on_the_head_unit_is_reported(self):
        out = self.computer('install', rc=1, TEST_EUID=501)
        self.assertIn('Root SSH access could not be verified', out)
        self.assertIn('reported a failure (exit 1)', out)
        self.assertFalse(self.p['STAGE'].exists())
        # only the copy made before the upload; the head unit wrote no backup of its own
        self.assertEqual([d.name.endswith('-install-before') for d in (self.root / 'BACKUP').iterdir()], [True])

    def test_missing_plugin_file(self):
        (self.pl / 'libcppinch.so').unlink()
        self.assertIn('build.sh', self.computer('install', rc=1))
        self.assertEqual(self.calls(), [])                                            # nothing sent

    def test_connection_failure(self):
        self.assertIn('Cannot connect', self.computer('status', rc=1, TEST_SSH_RC=255))

    def test_unreachable_head_unit(self):
        out = self.computer('install', rc=1, TEST_NC_RC=1)
        self.assertIn('does not answer on port 22', out)
        self.assertNotIn('ssh-master', self.calls())                                 # no login tried

    def test_summary(self):
        out = self.computer('install')
        self.assertIn('Done: CarPlay Advanced Settings is installed', out)
        self.assertIn('A restart of the head unit is needed', out)
        self.assertNotIn('SUCCESS: install completed', out)                          # the head unit's closing lines: in the summary
        self.assertIn('answers on port 22', out)

    def test_payload_option_refused(self):
        self.assertIn('--payload is for runs on the head unit', self.computer('install', '--payload', '/x', rc=1))


class UninstallStatusTest(Base):
    def install_with_switches(self):
        self.run_script('install')
        settings = self.p['SETTINGS']
        settings.mkdir(exist_ok=True)
        (settings / 'hud_guidance').write_text('1')
        (settings / 'mm-ipod').write_text('#!/bin/ksh\nexec wrapper\n')
        self.p['MMIPOD'].unlink()
        self.p['MMIPOD'].symlink_to(settings / 'mm-ipod')

    def test_uninstall(self):
        self.install_with_switches()
        installed = {f: (self.p['PLUGIN'] / f).read_bytes() for f in FILES}
        out = self.run_script('uninstall')
        self.assertIn('SUCCESS: uninstall completed', out)
        self.assertFalse(self.p['PLUGIN'].exists())
        self.assertFalse(self.p['SETTINGS'].exists())
        self.assertFalse(self.p['MMIPOD'].is_symlink())
        self.assertEqual(self.p['START_SCREEN'].read_bytes(), START_SCREEN)
        self.assertIn('identical to the kept original', out)
        (b,) = self.backups('uninstall')
        for f in FILES:
            self.assertEqual((b / 'plugin' / f).read_bytes(), installed[f])
        self.assertEqual((b / 'settings/hud_guidance').read_text(), '1')
        self.assertEqual((b / 'start_screen.sh').read_bytes().count(MARK), 1)
        self.assertEqual(self.calls().count('boot new'), 1)                         # only the install's relink
        self.assertIn('Already uninstalled', self.run_script('uninstall'))

    def link_both_layouts(self):
        # boot.sh links both spellings of the layout; in the car /opt/hmi/data is a link to /opt/hmi/ID5/data, so each link alone
        # shadows the same file (HMI 1703, 2026-11-13: uninstall stopped with "still a link after removing it")
        settings = self.p['SETTINGS']
        settings.mkdir(exist_ok=True)
        (settings / 'fullscreen').write_text('1')
        (settings / 'Spec_State_Merged.pbw').write_bytes(b'PBW wide layout')
        for key in ('LAYOUT', 'LAYOUT_ID5'):
            self.p[key].unlink(missing_ok=True)
            self.p[key].symlink_to(settings / 'Spec_State_Merged.pbw')

    def test_uninstall_removes_both_layout_links(self):
        self.install_with_switches()
        self.link_both_layouts()
        out = self.run_script('uninstall')
        self.assertIn('SUCCESS: uninstall completed', out)
        self.assertFalse(self.p['LAYOUT'].is_symlink())
        self.assertFalse(self.p['LAYOUT_ID5'].is_symlink())

    def test_uninstall_removes_both_common_layout_links(self):
        # a BMW: the plugin's copy of the HMI's common layout, linked under both spellings by boot.sh (a symlink here replaces the
        # file; a path-manager link in the car only shadows it)
        self.install_with_switches()
        settings = self.p['SETTINGS']
        (settings / 'fullscreen').write_text('1')
        (settings / 'Spec_State_Merged-common.pbw').write_bytes(b'PBW wide common layout')
        for key in ('LAYOUT_COMMON', 'LAYOUT_COMMON_ID5'):
            self.p[key].unlink(missing_ok=True)
            self.p[key].symlink_to(settings / 'Spec_State_Merged-common.pbw')
        self.assertIn('shadowed by a link', self.run_script('status'))
        out = self.run_script('uninstall')
        self.assertIn('SUCCESS: uninstall completed', out)
        self.assertNotIn('still a link', out)
        self.assertFalse(self.p['LAYOUT_COMMON'].is_symlink())
        self.assertFalse(self.p['LAYOUT_COMMON_ID5'].is_symlink())

    def test_uninstall_both_layout_links_without_kept_original(self):
        self.install_with_switches()
        orig = self.p['BACKUPS'] / 'originals'
        for f in orig.glob('Spec_State_Merged.pbw*'):
            f.unlink()
        self.link_both_layouts()
        out = self.run_script('uninstall')
        self.assertIn('SUCCESS: uninstall completed', out)
        self.assertNotIn('still a link', out)
        self.assertFalse(self.p['LAYOUT'].is_symlink())
        self.assertFalse(self.p['LAYOUT_ID5'].is_symlink())

    def test_uninstall_keep_config(self):
        self.install_with_switches()
        self.run_script('uninstall', '--keep-config')
        self.assertFalse(self.p['PLUGIN'].exists())
        self.assertEqual((self.p['SETTINGS'] / 'hud_guidance').read_text(), '1')
        self.assertEqual(self.hooked(), 0)

    def test_uninstall_dry_run(self):
        self.install_with_switches()
        before = sorted(str(p) for p in self.root.rglob('*'))
        out = self.run_script('uninstall', '--dry-run')
        self.assertIn('remove the boot-hook line', out)
        self.assertEqual(sorted(str(p) for p in self.root.rglob('*')), before)
        self.assertEqual(self.hooked(), 1)

    def test_uninstall_failure_rolls_back_and_relinks(self):
        self.install_with_switches()
        out = self.run_script('uninstall', rc=1, TEST_SYNC_RC=1)
        self.assertIn('Previous files restored', out)
        self.assertTrue(self.p['PLUGIN'].exists())
        self.assertTrue((self.p['SETTINGS'] / 'hud_guidance').exists())
        self.assertEqual(self.hooked(), 1)
        self.assertTrue(self.p['MMIPOD'].is_symlink())                                # made again by the restored boot.sh

    def test_keep_config_needs_uninstall(self):
        self.assertIn('requires uninstall', self.run_script('install', '--keep-config', rc=1))

    def test_status(self):
        self.install_with_switches()
        (self.root / 'processes').write_text('1234 /opt/hmi/bin/HmiMain3D -c=DSI\n77 mm-ipod -x\n')
        out = self.run_script('status')
        self.assertIn('HMI: NBTevo_ID5_1803_Release', out)
        self.assertIn('Plugin: installed', out)
        self.assertIn('Boot hook: installed', out)
        self.assertIn('hud_guidance', out)
        self.assertIn('%s: shadowed by a link' % self.p['MMIPOD'], out)
        self.assertIn('HmiMain3D PID(s): 1234', out)
        self.assertIn('mm-ipod PID(s): 77', out)
        self.assertIn('Connectivity PID(s): none', out)


class ClusterTest(Base):
    """Where CarPlay directions go (libcpprobe.so's answer, or --cluster most|kombi|both): librghook-kombi.so as librghook.so for
    kombi and both, librghook.so for most; recorded in carplaymenu/cluster (hud.h reads it: kombi = nothing drawn on MOST)."""
    def cluster(self):
        f = self.p['SETTINGS'] / 'cluster'
        return f.read_text().strip() if f.exists() else None

    def rghook(self):
        got = (self.p['PLUGIN'] / 'librghook.so').read_bytes()
        for name in ('librghook.so', 'librghook-kombi.so', 'librghook-most.so', 'librghook-both.so'):
            if got == (self.pl / name).read_bytes():
                return name
        return None

    def test_ethernet_kombi(self):
        out = self.run_script('install', TEST_PROBE='kombi=1')
        self.assertIn('Ethernet KOMBI found', out)
        self.assertIn('kombi: CarPlay directions to the KOMBI over SOME/IP from mm-ipod (librghook-kombi.so', out)
        self.assertEqual(self.rghook(), 'librghook-kombi.so')
        self.assertEqual(self.cluster(), 'kombi')
        self.assertIn('CarPlay directions (recorded at install): kombi', self.run_script('status', TEST_PROBE='kombi=1'))

    def test_most(self):
        out = self.run_script('install', TEST_PROBE='kombi=0 refused or unreachable')
        self.assertIn('no Ethernet KOMBI (refused or unreachable)', out)
        self.assertEqual(self.rghook(), 'librghook.so')
        self.assertEqual(self.cluster(), 'most')

    def test_no_answer_installs_most(self):
        out = self.run_script('install')
        self.assertIn('Cluster: not detected', out)
        self.assertIn('--cluster kombi', out)
        self.assertEqual(self.rghook(), 'librghook.so')
        self.assertEqual(self.cluster(), 'most')

    def test_forced(self):
        out = self.run_script('install', '--cluster', 'kombi', TEST_PROBE='kombi=0 refused or unreachable')
        self.assertIn('Cluster: kombi (--cluster)', out)
        self.assertNotIn('no Ethernet KOMBI', out)                    # the probe is not run
        self.assertEqual(self.rghook(), 'librghook-kombi.so')
        self.run_script('install', '--cluster', 'most', TEST_PROBE='kombi=1')
        self.assertEqual(self.rghook(), 'librghook.so')
        self.assertEqual(self.cluster(), 'most')
        out = self.run_script('install', '--cluster', 'both', TEST_PROBE='kombi=1')
        self.assertIn('both: the KOMBI over SOME/IP and the MOST HUDTerminal (librghook-kombi.so)', out)
        self.assertEqual(self.rghook(), 'librghook-kombi.so')
        self.assertEqual(self.cluster(), 'both')
        self.assertIn('--cluster needs most, kombi or both', self.run_script('install', '--cluster', 'x', rc=1))

    def test_hud_tx_override_is_saved_and_reported(self):
        out = self.run_script('install', '--hud-tx', '4')
        self.assertIn('HUDTerminal transmissionType: 4', out)
        self.assertEqual((self.p['SETTINGS'] / 'hud_tx').read_text().strip(), '4')
        out = self.run_script('hud-probe', rc=1)  # no MOST log in this fixture; switch is printed before that check
        self.assertIn('switch hud_tx: on (4)', out)

    def test_hud_tx_dry_run_and_argument_validation(self):
        out = self.run_script('install', '--hud-tx', '4', '--dry-run')
        self.assertIn('HUDTerminal transmissionType: 4', out)
        self.assertFalse((self.p['SETTINGS'] / 'hud_tx').exists())
        self.assertIn('--hud-tx needs 0 or 4', self.run_script('install', '--hud-tx', '2', rc=1))
        self.assertIn('--hud-tx requires install', self.run_script('status', '--hud-tx', '4', rc=1))

    def hud_only(self, probe, *extra):
        return self.run_script('install', '--kind', 'id6', '--mode', 'hud', *extra, TEST_PROBE=probe)

    # without the menu plugin librghook itself draws: -most on MOST, -kombi on the KOMBI, -both for the two (fresh units: a second
    # HUD-only install on top of one stops at the mm-ipod link, as before)
    def test_hud_only_most(self):
        out = self.hud_only('kombi=0 refused or unreachable')
        self.assertIn('most: CarPlay directions on the MOST HUDTerminal (librghook-most.so)', out)
        self.assertIn('Drawn on MOST from mm-ipod (without the full plugin)', out)
        self.assertEqual(self.rghook(), 'librghook-most.so')
        self.assertTrue((self.p['PLUGIN'] / 'libcpprobe.so').exists())

    def test_hud_only_kombi(self):
        out = self.hud_only('kombi=1')
        self.assertNotIn('Drawn on MOST', out)
        self.assertEqual(self.rghook(), 'librghook-kombi.so')
        self.assertEqual(self.cluster(), 'kombi')

    def test_hud_only_both(self):
        self.hud_only('kombi=1', '--cluster', 'both')
        self.assertEqual(self.rghook(), 'librghook-both.so')
        self.assertEqual(self.cluster(), 'both')

    def test_dry_run_writes_nothing(self):
        out = self.run_script('install', '--dry-run', TEST_PROBE='kombi=1')
        self.assertIn('Ethernet KOMBI found', out)
        self.assertIsNone(self.cluster())
        self.assertFalse(self.p['PLUGIN'].exists())


def hmi_patterns(script=SOURCE):
    s = Path(script).read_text()
    head = "hmi_patterns() {\n    cat <<'EOF'\n"
    start = s.index(head) + len(head)
    return s[start:s.index('EOF\n}\n', start)].splitlines()


def scanner(script=SOURCE):
    """The installer's hmi_patterns and hmi_scan functions, to source on their own."""
    lines, out, on, sc = Path(script).read_text().splitlines(), [], False, False
    for l in lines:
        on = on or l.startswith('hmi_patterns() {')
        if on:
            out.append(l)
        sc = sc or l.startswith('hmi_scan() {')
        if sc and l == '}':
            break
    return '\n'.join(out) + '\n'


def b_word(at, to, op='ea'):
    return '%s%06x' % (op, ((to - at - 8) // 4) & 0xffffff)


def synth_hmi(omit=(), twice=(), base=0x10000):
    """A made-up HmiMain3D: every "find" window of the installer's patterns laid out once (no firmware), the masked words filled
    in so that the values are known. Returns the ELF bytes and the build.tab lines (without hmi) the scanner must print."""
    finds, patches = {}, []
    for l in hmi_patterns():
        f = l.split()
        if f and f[0] == 'find':
            to = [t for t in f[4:] if t.startswith('to:')]
            finds[f[1]] = (int(f[2]), [t for t in f[4:] if not t.startswith('to:')], to[0].split(':')[1:] if to else None)
        elif f and f[0] == 'patch':
            patches.append(f[1:])
    # windows that are the same code in the real builds (ctl lies inside tB) are overlaid where all their words agree
    cells, anchor, filled = {}, {}, {}
    fields = {'touch': (10, 0x24), 'tdfirst': (0, 0x10), 'tdend': (0, 0x14)}

    def fits(a, b):
        return all(x == '.' or y == '.' or x == y for x, y in zip(a, b))

    def merge(a, b):
        return ''.join(y if x == '.' else x for x, y in zip(a, b))

    def lay(name, decoy=False):
        idx, toks, _ = finds[name]
        top = max(cells) + 1 if cells else 0
        best, start = 0, top + 4                                  # appended after a gap no pattern matches
        if not decoy:
            for p in range(0, top):
                if all(cells.get(p + k) is None or fits(cells[p + k], t) for k, t in enumerate(toks)):
                    shared = sum(1 for k, t in enumerate(toks) if p + k in cells and '.' not in t and '.' not in cells[p + k])
                    if shared > best and shared >= 3:
                        best, start = shared, p
        for k in range(top, start):
            cells[k] = 'ffffffff'
        for k, t in enumerate(toks):
            cells[start + k] = merge(cells[start + k], t) if start + k in cells else t
        if not decoy:
            anchor[name] = base + 4 * (start + idx)
            filled[name] = (start, idx)

    for name in sorted(finds, key=lambda n: -len(finds[n][1])):  # the longest first: shorter ones overlay them
        if name not in omit:
            lay(name)
        if name in twice:
            lay(name, decoy=True)
    words = [int(cells.get(k, 'ffffffff').replace('.', '0'), 16) for k in range(max(cells) + 1)]
    for name, (k, v) in fields.items():
        if name in filled:
            s0, idx = filled[name]
            words[s0 + idx + k] = (words[s0 + idx + k] & 0xfffff000) | v
    calls = {}
    for name in ('ctl', 'play'):                                 # the calls: a BL to a place of our choice
        if name in anchor:
            calls[name] = anchor[name] + 0x40000
            s, idx = filled[name]
            words[s + idx] = int(b_word(anchor[name], calls[name], 'eb'), 16)
    for name, (idx, toks, to) in finds.items():                  # a branch that must go to another anchor
        if to and name in anchor and to[1] in anchor:
            s, i = filled[name]
            k = int(to[0])
            words[s + k] = int(b_word(base + 4 * (s + k), anchor[to[1]]), 16)
    text = struct.pack('<%dI' % len(words), *words)
    hdr = bytearray(52)
    hdr[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HHIIIIIHHHHHH', hdr, 16, 2, 40, 1, base, 52, 0, 0, 52, 32, 1, 0, 0, 0)
    ph = struct.pack('<8I', 1, 0x1000, base, base, len(text), len(text), 5, 0x1000)
    elf = bytes(hdr) + ph + bytes(0x1000 - 52 - 32) + text
    word_at = lambda a: words[(a - base) // 4]
    if any(n not in anchor for n in ('touch', 'tdfirst', 'tdend', 'ctl', 'play')):
        return elf, None
    fs = all(p[1] in anchor for p in patches if p[0] == 'fs')
    tilt = all(p[1] in anchor for p in patches if p[0] == 'tilt')
    out = ['touchFn %x' % anchor['touch'], 'ctlSetFn %x' % calls['ctl'], 'ctlProxy 4e60', 'playFn %x' % calls['play'], 'playObj 52b0',
           'tdFirst 10', 'tdEnd 14', 'tdTime 20', 'tdOrigin 24', 'pbw %d' % (1 if fs else 2), 'pbwBmw %d' % (1 if fs else 2), 'ini 1']
    for g, an, off, new, mode in patches:
        if (g == 'fs' and not fs) or (g == 'tilt' and not tilt):
            continue
        a = anchor[an] + int(off, 16)
        o = '%08x' % word_at(a)
        if mode == 'imm24':
            new = new[:2] + o[2:]
        elif mode.startswith('b:'):
            other, d = mode[2:].split('+')
            new = b_word(a, anchor[other] + int(d, 16), new[:2])
        out.append('%s %x %s %s' % (g, a, o, new))
    if not tilt:
        out.append('# tilt: not found (knob tilts off)')
    if not fs:
        out.append('# fs: no CARPLAY_FULLSCREEN flag code (full screen by the layout only)')
    return elf, out


class HmiScanTest(unittest.TestCase):
    """hmi_scan (od + awk) on made-up HmiMain3D files built from its own patterns, and on the real builds when they are given."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cpa-scan-')
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / 'scan.sh').write_text(scanner())

    def scan(self, elf_bytes=None, path=None, rc=0):
        if path is None:
            path = self.dir / 'HmiMain3D'
            path.write_bytes(elf_bytes)
        res = subprocess.run(['/bin/sh', '-c', '. "$1"; hmi_scan "$2" "HMI test build"', 'sh', str(self.dir / 'scan.sh'), str(path)],
                             capture_output=True, timeout=600)
        self.assertEqual(res.returncode, rc, res.stderr.decode())
        return res.stdout.decode().splitlines(), res.stderr.decode()

    def test_all_found(self):
        elf, want = synth_hmi()
        out, _ = self.scan(elf)
        self.assertEqual(out[0], 'hmi HMI test build')
        self.assertEqual(out[1:], want)
        self.assertTrue(any(l.startswith('fs ') for l in out) and any(l.startswith('tilt ') for l in out))

    def test_branch_constraint_picks_the_right_copy(self):
        elf, want = synth_hmi(twice=('tC',))                     # a second tC window whose branch goes elsewhere
        self.assertEqual(self.scan(elf)[0][1:], want)

    def test_without_fullscreen_code_and_tilts(self):
        elf, want = synth_hmi(omit=('f3', 'tC'))
        out, _ = self.scan(elf)
        self.assertEqual(out[1:], want)
        self.assertIn('pbw 2', out)
        self.assertFalse([l for l in out if l.startswith(('fs ', 'tilt '))])

    def test_missing_or_twice_is_not_found(self):
        elf, _ = synth_hmi(omit=('play',))                      # (ctl is inside tB's window, as in the real builds)
        self.assertIn('not found: play', self.scan(elf, rc=1)[1])
        elf, _ = synth_hmi(twice=('touch',))
        self.assertIn('not found: touch', self.scan(elf, rc=1)[1])

    def test_not_an_elf(self):
        self.assertIn('not a little-endian ELF32', self.scan(b'HmiMain3D 006', rc=1)[1])

    @unittest.skipUnless(os.environ.get('CPA_HMI_006') and os.environ.get('CPA_HMI_1703'),
                         'CPA_HMI_006 / CPA_HMI_1703: the plain HmiMain3D of 006_017_006 and 1703 Build 139')
    def test_known_builds(self):
        table = {}
        s = SOURCE.read_text()
        for l in s[s.index('supported_table() {'):].splitlines()[2:]:
            if l == 'EOF':
                break
            f = l.split()
            if len(f) == 3 and f[1] == 'scan':
                table[f[0]] = f[2]
        for env, build, name in (('CPA_HMI_006', '006_017_006', 'ID5_1803-510-1749MA_Build_71'),
                                 ('CPA_HMI_1703', '1703 Build 139', 'ID5_1703-490-1650ZD_Build_139')):
            out, _ = self.scan(path=os.environ[env])
            want = subprocess.run(['python3', str(HERE / 'tools/hmipatterns.py'), '--expect', build], capture_output=True,
                                  check=True).stdout.decode().splitlines()
            body = [l for l in out[1:] if not l.startswith('#')]
            self.assertEqual(body, want, build)
            self.assertEqual(sha(('\n'.join(body) + '\n').encode()), table[name], build)


def per_shell(cls):
    """One test class per shell (/bin/sh and ksh)."""
    out = {}
    for sh in SHELLS:
        name = '%s_%s' % (cls.__name__, os.path.basename(sh))
        out[name] = type(name, (cls, unittest.TestCase), {'SHELL': sh})
    return out


globals().update(per_shell(InstallTest))
globals().update(per_shell(UninstallStatusTest))
globals().update(per_shell(FromComputerTest))
globals().update(per_shell(ClusterTest))
del InstallTest, UninstallStatusTest, FromComputerTest, ClusterTest

if __name__ == '__main__':
    unittest.main()
