# CA-6807: host-local relocation preflight must reject remote or ambiguous media

The existing relocation preflight already refused top-level symbolic links,
obvious UNC paths, same-home destinations, nonempty directories and low free
space. It did not resolve a mapped Windows network drive's actual media type
or distinguish a Linux SMB/NFS mount under an otherwise ordinary absolute
path. Consequently a destination such as a mounted NAS could pass the UI
review check even though live SQLite WAL on remote share is prohibited.

The preflight now uses host OS facts, not path names alone:
- Windows `GetDriveTypeW` distinguishes local fixed media from mapped remote,
  removable, optical and unknown drives. A Windows junction/reparse point is
  rejected alongside symlink ancestors where supported by the runtime.
- Linux `/proc/self/mountinfo` resolves the deepest applicable mount entry,
  classifying known SMB/CIFS/NFS/SSHFS/9p/Ceph/Gluster network filesystems as
  remote. Unknown/unreadable mount evidence fails closed.
- Both source and proposed destination must be proven local. Ambiguous
  `..` path components fail before normalized comparisons.

Only eligibility for **operator review** is affected.
`ready_for_automatic_cutover` remains permanently false because an
independently privileged writer fence, epoch broker and owner-approved
cutover are not implemented. No host selection, state move, pointer write,
backups, tests or deployment occurred. New regression cases were authored
but not run. CA-6807 remains partial pending Windows mapped-drive and
Linux mount proofs on approved real hosts.
