#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends qemu-system-x86 e2fsprogs gcc libc6-dev
apt-get clean
rm -rf /var/lib/apt/lists/*
mkdir -p /vm/rootfs /vm/dependencies
export PATH="/toolchain/bin:$PATH"
export CARGO_HOME=/vm/cargo
export CARGO_TARGET_DIR=/vm/target
export CARGO_HTTP_CAINFO=/run/proxy-ca.crt
rustc --version | grep -F 'rustc 1.88.0 '
cargo build --locked --release --manifest-path /input/Cargo.toml -p sofia-platform-lifecycle --bin aegis-platform-service
python -m pip download --disable-pip-version-check --only-binary=:all: --dest /vm/dependencies /input/wheels/*.whl --cert /run/proxy-ca.crt
rm -rf /root/.cache/pip
tar -xpf /vm/debian-python-rootfs.tar -C /vm/rootfs
cp /etc/resolv.conf /vm/rootfs/etc/resolv.conf
rm -f /vm/rootfs/.dockerenv
mkdir -p /vm/rootfs/dev /vm/rootfs/proc /vm/rootfs/sys /vm/rootfs/tmp
for item in 'null 1 3' 'zero 1 5' 'random 1 8' 'urandom 1 9'; do
  read -r name major minor <<< "$item"
  if [ ! -e "/vm/rootfs/dev/$name" ]; then mknod -m 666 "/vm/rootfs/dev/$name" c "$major" "$minor"; fi
done
printf '#!/bin/sh\nexit 101\n' > /vm/rootfs/usr/sbin/policy-rc.d
chmod 755 /vm/rootfs/usr/sbin/policy-rc.d
chroot /vm/rootfs apt-get update
chroot /vm/rootfs apt-get install -y --no-install-recommends systemd-sysv linux-image-amd64 initramfs-tools passwd util-linux e2fsprogs
chroot /vm/rootfs apt-get clean
rm -rf /vm/rootfs/var/lib/apt/lists/*
# Exercise the production signed-release/staging APIs with a separately
# generated in-memory disposable signer; no production trust or owner grant.
python -m pip install --no-index --find-links=/vm/dependencies sofia-sdk sofia-platform
python /input/prepare_release.py --disposable-vm
# Only verified public code is exposed to the guest service account.
chmod 755 /vm/rootfs/opt/aegis
chmod -R a+rX /vm/rootfs/opt/aegis/staged-release
chroot /vm/rootfs /usr/bin/env LD_LIBRARY_PATH=/opt/aegis/staged-release/runtime/python/lib PYTHONDONTWRITEBYTECODE=1 /opt/aegis/staged-release/runtime/python/bin/python3.12 -B -m venv /opt/aegis/venv
chroot /vm/rootfs /usr/bin/env LD_LIBRARY_PATH=/opt/aegis/staged-release/runtime/python/lib PYTHONDONTWRITEBYTECODE=1 /opt/aegis/venv/bin/python -B -m pip install --no-compile --no-index --find-links=/opt/aegis/staged-release/assets sofia-sdk sofia-platform
chroot /vm/rootfs /usr/bin/env LD_LIBRARY_PATH=/opt/aegis/staged-release/runtime/python/lib /opt/aegis/venv/bin/python -B -m pip check
chroot /vm/rootfs useradd --system --user-group --no-create-home --home-dir /var/lib/aegis --shell /usr/sbin/nologin aegis
install -d -m 755 /vm/rootfs/opt/aegis/bin
install -d -m 700 /vm/rootfs/var/lib/aegis /vm/rootfs/etc/aegis
chroot /vm/rootfs chown aegis:aegis /var/lib/aegis
install -m 755 /vm/rootfs/opt/aegis/staged-release/assets/aegis-platform-service /vm/rootfs/opt/aegis/bin/
install -m 644 /input/inputs.json /vm/rootfs/opt/aegis/test-inputs.json
install -m 644 /input/probe.py /vm/rootfs/opt/aegis/vm_probe.py
install -m 644 /input/aegis-platform.service /vm/rootfs/etc/systemd/system/aegis-platform.service
chroot /vm/rootfs runuser -u aegis -- /usr/bin/env LD_LIBRARY_PATH=/opt/aegis/staged-release/runtime/python/lib /opt/aegis/venv/bin/python -B -I -c '
import json
from pathlib import Path
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.state.local_store import PlatformLocalStore
from sofia.platform.config.roles import PlatformRole,PlatformRoleConfiguration
identity=InstallationIdentityStore(Path("/var/lib/aegis/identity")).initialize()
PlatformLocalStore(Path("/var/lib/aegis/platform.db"),roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),host_identity=identity.identity.canonical_uuid)
print(json.dumps(identity.to_payload()))
' > /vm/rootfs/opt/aegis/identity-reference.json
python - <<'PY'
import json
from pathlib import Path
root=Path('/vm/rootfs')
public=json.loads((root/'opt/aegis/identity-reference.json').read_text())
(root/'etc/aegis/platform-service.env').write_text('\n'.join((
'AEGIS_PYTHON=/opt/aegis/venv/bin/python','LD_LIBRARY_PATH=/opt/aegis/staged-release/runtime/python/lib','AEGIS_IDENTITY_HOME=/var/lib/aegis/identity',
'AEGIS_LOCAL_STATE=/var/lib/aegis/platform.db','AEGIS_PLATFORM_ID='+public['identity']['uuid'],
'AEGIS_PUBLIC_KEY_SHA256='+public['public_key_sha256'],'')))
(root/'etc/aegis/platform-service.env').chmod(0o600)
PY
printf 'aegis-lab-debian12\n' > /vm/rootfs/etc/hostname
printf '/dev/vda / ext4 defaults 0 1\n' > /vm/rootfs/etc/fstab
cat > /vm/rootfs/etc/systemd/system/aegis-vm-selftest.service <<'EOF'
[Unit]
Description=Explicit disposable Aegis VM self-test, never a release installer
After=aegis-platform.service
Wants=aegis-platform.service
[Service]
Type=oneshot
Environment=LD_LIBRARY_PATH=/opt/aegis/staged-release/runtime/python/lib
ExecStart=/opt/aegis/venv/bin/python -B -I /opt/aegis/vm_probe.py
StandardOutput=journal+console
StandardError=journal+console
TimeoutStartSec=150
[Install]
WantedBy=multi-user.target
EOF
mkdir -p /vm/rootfs/etc/systemd/system/multi-user.target.wants
ln -s ../aegis-platform.service /vm/rootfs/etc/systemd/system/multi-user.target.wants/aegis-platform.service
ln -s ../aegis-vm-selftest.service /vm/rootfs/etc/systemd/system/multi-user.target.wants/aegis-vm-selftest.service
ln -sfn /lib/systemd/system/multi-user.target /vm/rootfs/etc/systemd/system/default.target
cp /vm/rootfs/boot/vmlinuz-* /vm/vmlinuz
cp /vm/rootfs/boot/initrd.img-* /vm/initrd.img
truncate -s 1800M /vm/platform.ext4
mkfs.ext4 -F -L aegis-test -d /vm/rootfs /vm/platform.ext4
chmod 600 /vm/platform.ext4
chown "$AEGIS_OUTPUT_UID:$AEGIS_OUTPUT_GID" /vm/platform.ext4 /vm/vmlinuz /vm/initrd.img
python - <<'PYARTIFACT'
from pathlib import Path
from hashlib import sha256
import json
files=[Path('/vm/python-runtime.zip'),Path('/vm/target/release/aegis-platform-service'),*Path('/vm/dependencies').glob('*.whl')]
Path('/vm/built-artifacts.json').write_text(json.dumps({p.name:sha256(p.read_bytes()).hexdigest() for p in files},sort_keys=True)+'\n')
PYARTIFACT
chown "$AEGIS_OUTPUT_UID:$AEGIS_OUTPUT_GID" /vm/built-artifacts.json /vm/runtime-reference.json /vm/test-release-envelope.json /vm/test-release-stage.json /vm/python-runtime.zip /vm/target/release/aegis-platform-service /vm/dependencies/*.whl
printf 'AEGIS_VM_IMAGE_BUILT\n'

for boot in 1 2; do
  timeout 240 qemu-system-x86_64 -accel tcg -m 768 -smp 2 -nographic -no-reboot -nic none \
    -drive file=/vm/platform.ext4,format=raw,if=virtio,cache=writeback \
    -kernel /vm/vmlinuz -initrd /vm/initrd.img \
    -append 'root=/dev/vda rw console=ttyS0 systemd.show_status=no loglevel=3 aegis.disposable_vm=1' \
    > "/vm/boot-$boot.log" 2>&1
  python - "$boot" <<'PYVM'
import json, sys
from pathlib import Path
boot=sys.argv[1]
rows=[]
for line in Path('/vm/boot-'+boot+'.log').read_text(errors='replace').splitlines():
    prefix='AEGIS_VM_RESULT '
    if prefix in line:
        rows.append(json.loads(line.split(prefix,1)[1]))
assert len(rows)==1 and rows[0]['result']=='PASS',rows
Path('/vm/receipt-'+boot+'.json').write_text(json.dumps(rows[0],sort_keys=True)+'\n')
print(json.dumps(rows[0],sort_keys=True),flush=True)
PYVM
done
python - <<'PYVM'
import json
from pathlib import Path
first,second=[json.loads(Path('/vm/receipt-'+str(n)+'.json').read_text()) for n in (1,2)]
assert first['boot_id']!=second['boot_id']
assert first['platform_id']==second['platform_id']
assert first['public_key_sha256']==second['public_key_sha256']
assert min(second['generations'])>max(first['generations'])
print('AEGIS_VM_TWO_BOOTS_VERIFIED',flush=True)
PYVM
chown "$AEGIS_OUTPUT_UID:$AEGIS_OUTPUT_GID" /vm/boot-*.log /vm/receipt-*.json
