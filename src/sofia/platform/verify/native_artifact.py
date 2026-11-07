"""Bounded native architecture/ABI declarations; never execution or authority."""
import re
import struct
from sofia.sdk.platform_release import PlatformReleaseTarget

def verify_native_target(data, target):
    """Check architecture/ABI declarations, never execution health or authority."""
    if not isinstance(data, bytes) or not isinstance(target, PlatformReleaseTarget):
        raise TypeError("typed native bytes and target required")
    if target is PlatformReleaseTarget.DEBIAN12_X86_64:
        if (len(data)<64 or data[:6]!=b'\x7fELF\x02\x01'
                or struct.unpack_from('<H',data,18)[0]!=62):
            raise ValueError('service header does not match Debian12 x86_64')
        requirements=[tuple(int(v) for v in raw.split(b'.'))
            for raw in re.findall(rb'GLIBC_([0-9]+(?:\.[0-9]+){1,2})\x00',data)]
        if any(version>(2,36) for version in requirements):
            raise ValueError('service requires a newer glibc than Debian12')
    else:
        if len(data)<64 or data[:2]!=b'MZ':
            raise ValueError('service header does not match Windows')
        offset=struct.unpack_from('<I',data,60)[0]
        if (offset>len(data)-26 or data[offset:offset+4]!=b'PE\0\0'
                or struct.unpack_from('<H',data,offset+4)[0]!=0x8664
                or struct.unpack_from('<H',data,offset+24)[0]!=0x20b):
            raise ValueError('service must declare a Windows x86_64 executable')

