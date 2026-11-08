//! Read-only client of Team A's single native management broker.
//!
//! This transport adds NO owner enrollment, signer authority or service.
//! It requires B-verified, immutable installed-service pins supplied by an
//! external reviewer; OS credentials alone never establish publisher trust.
//! Until such an installer-backed source is wired, CLI uses OfflineReader.

#[cfg(target_os = "linux")]
pub mod linux {
    use crate::control_center::{InstallationState, PermissionState, SafeState};
    use crate::control_center_session::{
        from_verified_denial, DisplayReadSource, DisplaySnapshot, ReadFailure,
    };
    use chrono::{Duration as ChronoDuration, SecondsFormat, Utc};
    use sofia_contracts::management::{
        UntrustedManagementRead, UntrustedManagementResponse, MANAGEMENT_READ_PROTOCOL,
        MANAGEMENT_READ_SCHEMA, MAX_MANAGEMENT_RESPONSE_BYTES,
    };
    use nix::sys::socket::{getsockopt, sockopt::PeerCredentials};
    use std::fmt::Write as _;
    use std::fs;
    use std::io::{Read, Write};
    use std::os::unix::ffi::OsStrExt;
    use std::os::unix::fs::{FileTypeExt, MetadataExt, PermissionsExt};
    use std::os::unix::net::UnixStream;
    use std::path::{Path, PathBuf};
    use std::time::{Duration, Instant};

    const MAX_SOCK_PATH: usize = 100;
    const MAX_REQUEST: usize = 64 * 1024;
    const IO_TIMEOUT: Duration = Duration::from_secs(2);
    const MAX_GENERATION: u64 = 9_007_199_254_740_991;

    /// Caller must derive these from an independently publisher-verified,
    /// currently enrolled B1 installed-service profile. Merely constructing
    /// this value NEVER authenticates an installation or enrolls an operator.
    /// The UI and CLI must not create these from flags, environment or Hub.
    #[derive(Debug, Clone)]
    pub struct InstalledNativeServicePins {
        socket_path: PathBuf,
        platform_id: String,
        generation: u64,
        service_uid: u32,
        service_gid: u32,
        socket_group_gid: Option<u32>,
        service_pid: Option<i32>,
    }

    impl InstalledNativeServicePins {
        /// Validate installed metadata syntax only, NOT signing/enrollment.
        /// An independently trusted B1 profile is a separate prerequisite.
        ///
        /// # Errors
        /// Invalid source path, identity or generation fails closed.
        pub fn from_externally_verified_installation(
            socket_path: PathBuf,
            platform_id: String,
            generation: u64,
            service_uid: u32,
            service_gid: u32,
            socket_group_gid: Option<u32>,
            service_pid: Option<i32>,
        ) -> Result<Self, ReadFailure> {
            let bytes = platform_id.as_bytes();
            if !socket_path.is_absolute()
                || socket_path.as_os_str().as_bytes().len() > MAX_SOCK_PATH
                || socket_path.as_os_str().as_bytes().contains(&0)
                || bytes.is_empty()
                || bytes.len() > 160
                || !bytes[0].is_ascii_alphanumeric()
                || !bytes
                    .iter()
                    .copied()
                    .all(|byte| byte.is_ascii_alphanumeric()
                        || matches!(byte, b'.' | b'_' | b'-' | b':' | b'@' | b'/'))
                || generation == 0
                || generation > MAX_GENERATION
                || service_pid.is_some_and(|pid| pid <= 0)
            {
                return Err(ReadFailure::Unverified);
            }
            Ok(Self {
                socket_path,
                platform_id,
                generation,
                service_uid,
                service_gid,
                socket_group_gid,
                service_pid,
            })
        }
    }

    /// One new request per call, bounded native IO and exact shared v1 parser.
    /// No connection pooling, discovery, permission grant, effect or retry.
    pub struct NativeLinuxManagementReader {
        pins: InstalledNativeServicePins,
        local_sequence: u64,
        // Bind each current installed epoch to the same actual socket inode.
        // A replaced endpoint requires a NEW B-verified profile, not silent
        // rediscovery from an old signed installation identity.
        verified_endpoint: Option<(u64, u64)>,
    }

    impl NativeLinuxManagementReader {
        #[must_use]
        pub fn new(pins: InstalledNativeServicePins) -> Self {
            Self {
                pins,
                local_sequence: 0,
                verified_endpoint: None,
            }
        }

        fn status(&mut self) -> Result<DisplaySnapshot, ReadFailure> {
            // The exact native instance and its filesystem inode must agree.
            let inode = verify_endpoint(&self.pins)?;
            if self.verified_endpoint.is_some_and(|old| old != inode) {
                return Err(ReadFailure::Unverified);
            }
            let now = Utc::now().fixed_offset();
            let mut random = [0_u8; 16];
            getrandom::getrandom(&mut random).map_err(|_| ReadFailure::Unverified)?;
            let mut request_id = String::from("req:");
            for value in random {
                write!(&mut request_id, "{value:02x}")
                    .map_err(|_| ReadFailure::Unverified)?;
            }
            let created_at = now.to_rfc3339_opts(SecondsFormat::Micros, true);
            let deadline = (now + ChronoDuration::seconds(5))
                .to_rfc3339_opts(SecondsFormat::Micros, true);
            let raw = serde_json::to_vec(&serde_json::json!({
                "schema": MANAGEMENT_READ_SCHEMA,
                "protocol": MANAGEMENT_READ_PROTOCOL,
                "request_id": request_id,
                "target_platform_id": self.pins.platform_id.clone(),
                "expected_generation": self.pins.generation,
                "operation": "platform.status",
                "created_at": created_at,
                "deadline": deadline,
            }))
            .map_err(|_| ReadFailure::Unverified)?;
            if raw.len() > MAX_REQUEST {
                return Err(ReadFailure::Unverified);
            }
            let expected = UntrustedManagementRead::parse(&raw, now)
                .map_err(|_| ReadFailure::Unverified)?;
            let mut connection = UnixStream::connect(&self.pins.socket_path)
                .map_err(|_| ReadFailure::Offline)?;
            connection
                .set_write_timeout(Some(IO_TIMEOUT))
                .map_err(|_| ReadFailure::Unverified)?;
            verify_os_peer(&connection, &self.pins)?;
            if verify_endpoint(&self.pins)? != inode {
                return Err(ReadFailure::Unverified);
            }
            connection
                .write_all(&raw)
                .and_then(|()| connection.write_all(b"\n"))
                .map_err(|_| ReadFailure::Offline)?;
            let body = read_one(&mut connection)?;
            if verify_endpoint(&self.pins)? != inode {
                return Err(ReadFailure::Unverified);
            }
            let response = UntrustedManagementResponse::parse(
                &body,
                &expected,
                Utc::now().fixed_offset(),
            )
            .map_err(|error| match error.code {
                "stale_management_response" => ReadFailure::Stale,
                // A wrong request ID, operation, target or generation has
                // no verified explanation. Only a correlated typed
                // STALE_GENERATION denial gets an explicit generation label.
                "uncorrelated_management_response" => ReadFailure::Unverified,
                _ => ReadFailure::Unverified,
            })?;
            // A's canonical parser only returns OK or a CORRELATED typed
            // DENIED observation. Both originate at the verified native peer.
            // Fence this socket across subsequent requests even if STOP or
            // revocation was the first authenticated result. Otherwise a
            // replaced endpoint could be silently adopted after a denial.
            self.verified_endpoint = Some(inode);
            if response.outcome == "DENIED" {
                return Err(
                    response.denial.as_ref()
                        .and_then(|denial| from_verified_denial(&denial.code))
                        .unwrap_or(ReadFailure::Unverified),
                );
            }
            if response.outcome != "OK" {
                return Err(ReadFailure::Unverified);
            }
            // A's canonical parser just required exact status fields,
            // operator_stop=false, core_started=false and correlation.
            // This sequence counts locally validated unique random requests,
            // NOT a service-issued status sequence or installation receipt.
            self.local_sequence = self
                .local_sequence
                .checked_add(1)
                .ok_or(ReadFailure::UnknownGeneration)?;
            Ok(DisplaySnapshot {
                platform_id: response.platform_id,
                generation: response.platform_generation,
                sequence: self.local_sequence,
                safe: SafeState::Clear,
                permission: PermissionState::Unknown,
                installation: InstallationState::Unknown,
                saved_revision: None,
                applied_revision: None,
                removal_receipt_verified: false,
            })
        }
    }

    impl DisplayReadSource for NativeLinuxManagementReader {
        fn next(&mut self) -> Result<DisplaySnapshot, ReadFailure> {
            self.status()
        }
    }

    fn no_symlinks(path: &Path) -> Result<(), ReadFailure> {
        for component in path.ancestors() {
            let info = fs::symlink_metadata(component)
                .map_err(|_| ReadFailure::Offline)?;
            if info.file_type().is_symlink() {
                return Err(ReadFailure::Unverified);
            }
        }
        Ok(())
    }

    fn verify_endpoint(
        pins: &InstalledNativeServicePins,
    ) -> Result<(u64, u64), ReadFailure> {
        no_symlinks(&pins.socket_path)?;
        let parent = pins.socket_path.parent().ok_or(ReadFailure::Unverified)?;
        let dir = fs::symlink_metadata(parent).map_err(|_| ReadFailure::Offline)?;
        let leaf = fs::symlink_metadata(&pins.socket_path)
            .map_err(|_| ReadFailure::Offline)?;
        let mode = dir.permissions().mode() & 0o777;
        let (expected_group, expected_dir_mode, expected_sock_mode) =
            if let Some(group) = pins.socket_group_gid {
                (group, 0o750, 0o660)
            } else {
                (pins.service_gid, 0o700, 0o600)
            };
        if !dir.is_dir()
            || dir.uid() != pins.service_uid
            || dir.gid() != expected_group
            || mode != expected_dir_mode
            || !leaf.file_type().is_socket()
            || leaf.uid() != pins.service_uid
            || leaf.gid() != expected_group
            || (leaf.permissions().mode() & 0o777) != expected_sock_mode
        {
            return Err(ReadFailure::Unverified);
        }
        Ok((leaf.dev(), leaf.ino()))
    }

    fn verify_os_peer(
        connection: &UnixStream,
        pins: &InstalledNativeServicePins,
    ) -> Result<(), ReadFailure> {
        let actual = getsockopt(connection, PeerCredentials)
            .map_err(|_| ReadFailure::Unverified)?;
        if actual.pid() <= 0
            || actual.uid() != pins.service_uid
            || actual.gid() != pins.service_gid
            || pins.service_pid.is_some_and(|pid| pid != actual.pid())
        {
            return Err(ReadFailure::Unverified);
        }
        Ok(())
    }

    fn read_one(connection: &mut UnixStream) -> Result<Vec<u8>, ReadFailure> {
        let deadline = Instant::now() + IO_TIMEOUT;
        let mut bytes = Vec::new();
        loop {
            let remaining = deadline.checked_duration_since(Instant::now())
                .filter(|time| !time.is_zero())
                .ok_or(ReadFailure::Offline)?;
            connection
                .set_read_timeout(Some(remaining))
                .map_err(|_| ReadFailure::Unverified)?;
            let mut chunk = [0_u8; 4096];
            let got = connection.read(&mut chunk).map_err(|_| ReadFailure::Offline)?;
            if got == 0 {
                return Err(ReadFailure::Offline);
            }
            bytes.extend_from_slice(&chunk[..got]);
            if bytes.len() > MAX_MANAGEMENT_RESPONSE_BYTES + 1 {
                return Err(ReadFailure::Unverified);
            }
            if bytes.contains(&b'\n') {
                if bytes.last() != Some(&b'\n')
                    || bytes.iter().filter(|byte| **byte == b'\n').count() != 1
                {
                    return Err(ReadFailure::Unverified);
                }
                bytes.pop();
                return Ok(bytes);
            }
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        use std::io::{BufRead, BufReader, Write};
        use std::os::unix::net::UnixListener;
        use std::thread;

        fn fake_service(
            outcome: &'static str,
        ) -> (tempfile::TempDir, InstalledNativeServicePins, thread::JoinHandle<()>) {
            let home = tempfile::tempdir().unwrap();
            let socket_path = home.path().join("mgmt-3.sock");
            let listener = UnixListener::bind(&socket_path).unwrap();
            fs::set_permissions(&socket_path, fs::Permissions::from_mode(0o600))
                .unwrap();
            let info = fs::metadata(home.path()).unwrap();
            let pins = InstalledNativeServicePins::from_externally_verified_installation(
                socket_path,
                "platform:alpha".into(),
                3,
                info.uid(),
                info.gid(),
                None,
                Some(i32::try_from(std::process::id()).unwrap()),
            ).unwrap();
            let handle = thread::spawn(move || {
                let (mut connection, _) = listener.accept().unwrap();
                if outcome == "EOF" {
                    return;
                }
                let mut wire = Vec::new();
                BufReader::new(&connection).read_until(b'\n', &mut wire).unwrap();
                let request: serde_json::Value =
                    serde_json::from_slice(&wire).unwrap();
                let mut result = serde_json::json!({
                    "schema": "aegis.platform.management.read-response.v1",
                    "protocol": "1.0",
                    "request_id": request["request_id"],
                    "platform_id": request["target_platform_id"],
                    "platform_generation": request["expected_generation"],
                    "operation": "platform.status",
                    "source": "PLATFORM_SESSION",
                    "observed_at": Utc::now()
                        .to_rfc3339_opts(SecondsFormat::Micros, true),
                    "outcome": "OK",
                    "data": {
                        "platform_id": request["target_platform_id"],
                        "generation": request["expected_generation"],
                        "operator_stop": false,
                        "core_started": false
                    },
                    "denial": null
                });
                if matches!(
                    outcome,
                    "STOPPED" | "REVOKED" | "NOT_PERMITTED" | "UNAVAILABLE"
                        | "EXPIRED" | "STALE_GENERATION"
                ) {
                    result["outcome"] = serde_json::json!("DENIED");
                    result["data"] = serde_json::Value::Null;
                    result["denial"] = serde_json::json!({"code": outcome});
                }
                if outcome == "FORGED_GENERATION" {
                    result["platform_generation"] = serde_json::json!(2);
                }
                if outcome == "REPLAY" {
                    result["request_id"] = serde_json::json!("req:old-attempt");
                }
                if outcome == "BAD_STOP_OK" {
                    result["data"]["operator_stop"] = serde_json::json!(true);
                }
                if outcome == "DUPLICATE" {
                    connection.write_all(b"{\"schema\":1,\"schema\":2}\n").unwrap();
                    return;
                }
                connection.write_all(
                    serde_json::to_string(&result).unwrap().as_bytes(),
                ).unwrap();
                connection.write_all(b"\n").unwrap();
            });
            (home, pins, handle)
        }

        #[test]
        fn synthetic_native_peer_returns_only_a_correlated_status() {
            let (_home, pins, thread) = fake_service("OK");
            let mut client = NativeLinuxManagementReader::new(pins);
            let snapshot = client.next().unwrap();
            assert_eq!(snapshot.platform_id, "platform:alpha");
            assert_eq!(snapshot.generation, 3);
            assert_eq!(snapshot.sequence, 1);
            assert_eq!(snapshot.safe, SafeState::Clear);
            assert_eq!(snapshot.permission, PermissionState::Unknown);
            assert_eq!(snapshot.installation, InstallationState::Unknown);
            assert!(!snapshot.removal_receipt_verified);
            thread.join().unwrap();
        }

        #[test]
        fn synthetic_stop_and_revocation_never_produce_observation() {
            for (case, expected) in [
                ("STOPPED", ReadFailure::Stopped),
                ("REVOKED", ReadFailure::Revoked),
                ("NOT_PERMITTED", ReadFailure::Denied),
                ("UNAVAILABLE", ReadFailure::Offline),
                ("EXPIRED", ReadFailure::Stale),
                ("EOF", ReadFailure::Offline),
                ("STALE_GENERATION", ReadFailure::UnknownGeneration),
                ("FORGED_GENERATION", ReadFailure::Unverified),
                ("REPLAY", ReadFailure::Unverified),
                ("BAD_STOP_OK", ReadFailure::Unverified),
                ("DUPLICATE", ReadFailure::Unverified),
            ] {
                let (_home, pins, thread) = fake_service(case);
                let mut client = NativeLinuxManagementReader::new(pins);
                assert_eq!(client.next().err(), Some(expected), "{case}");
                thread.join().unwrap();
            }
        }

        #[test]
        fn replaced_socket_inode_requires_a_new_verified_installation_epoch() {
            let (home, pins, thread) = fake_service("OK");
            let original = pins.socket_path.clone();
            let mut client = NativeLinuxManagementReader::new(pins);
            assert!(client.next().is_ok());
            thread.join().unwrap();
            let old_inode = fs::metadata(&original).unwrap().ino();
            fs::rename(&original, home.path().join("old-socket")).unwrap();
            let _new_listener = UnixListener::bind(&original).unwrap();
            fs::set_permissions(&original, fs::Permissions::from_mode(0o600))
                .unwrap();
            assert_ne!(old_inode, fs::metadata(&original).unwrap().ino());
            assert_eq!(client.next().err(), Some(ReadFailure::Unverified));
            assert_eq!(client.local_sequence, 1);
        }

        #[test]
        fn stop_denial_also_pins_native_endpoint_epoch() {
            let (home, pins, thread) = fake_service("STOPPED");
            let original = pins.socket_path.clone();
            let mut client = NativeLinuxManagementReader::new(pins);
            assert_eq!(client.next().err(), Some(ReadFailure::Stopped));
            thread.join().unwrap();
            let old_inode = fs::metadata(&original).unwrap().ino();
            assert_eq!(client.verified_endpoint.map(|(_, inode)| inode), Some(old_inode));
            fs::rename(&original, home.path().join("old-stop-socket")).unwrap();
            let _new_listener = UnixListener::bind(&original).unwrap();
            fs::set_permissions(&original, fs::Permissions::from_mode(0o600))
                .unwrap();
            assert_ne!(old_inode, fs::metadata(&original).unwrap().ino());
            assert_eq!(client.next().err(), Some(ReadFailure::Unverified));
            assert_eq!(client.local_sequence, 0);
        }

        #[test]
        fn private_and_enrolled_group_modes_do_not_downgrade() {
            let (home, mut pins, thread) = fake_service("EOF");
            fs::set_permissions(
                home.path(),
                fs::Permissions::from_mode(0o750),
            ).unwrap();
            fs::set_permissions(
                &pins.socket_path,
                fs::Permissions::from_mode(0o660),
            ).unwrap();
            // Different service primary and socket group must be pinned
            // separately by B. The synthetic same-user test uses current GID,
            // so this is mode coverage, NOT a distinct-operator acceptance.
            pins.socket_group_gid = Some(pins.service_gid);
            let mut client = NativeLinuxManagementReader::new(pins);
            assert_eq!(client.next().err(), Some(ReadFailure::Offline));
            thread.join().unwrap();

            let (_home, mut pins, thread) = fake_service("EOF");
            pins.socket_group_gid = Some(pins.service_gid);
            let mut client = NativeLinuxManagementReader::new(pins);
            assert_eq!(client.next().err(), Some(ReadFailure::Unverified));
            let _ = UnixStream::connect(&client.pins.socket_path);
            thread.join().unwrap();
        }

        #[test]
        fn wrong_pinned_uid_and_gid_are_rejected_before_request() {
            for uid in [true, false] {
                let (_home, mut pins, thread) = fake_service("EOF");
                if uid {
                    pins.service_uid = pins.service_uid.checked_add(1).unwrap();
                } else {
                    pins.service_gid = pins.service_gid.checked_add(1).unwrap();
                }
                let mut client = NativeLinuxManagementReader::new(pins);
                assert_eq!(client.next().err(), Some(ReadFailure::Unverified));
                // The native listener did not accept any verified request.
                let _ = UnixStream::connect(&client.pins.socket_path);
                thread.join().unwrap();
            }
        }

        #[test]
        fn mismatched_pid_and_world_access_never_yield_live_status() {
            let (_home, mut pins, thread) = fake_service("EOF");
            pins.service_pid = Some(i32::try_from(std::process::id()).unwrap() + 1);
            let mut client = NativeLinuxManagementReader::new(pins);
            assert_eq!(client.next().err(), Some(ReadFailure::Unverified));
            thread.join().unwrap();

            let (_home, pins, thread) = fake_service("EOF");
            fs::set_permissions(
                &pins.socket_path,
                fs::Permissions::from_mode(0o666),
            ).unwrap();
            let mut client = NativeLinuxManagementReader::new(pins);
            assert_eq!(client.next().err(), Some(ReadFailure::Unverified));
            let _ = UnixStream::connect(&client.pins.socket_path);
            thread.join().unwrap();
        }

        #[test]
        fn symlink_and_missing_service_fail_closed() {
            let (_home, mut pins, thread) = fake_service("EOF");
            let original = pins.socket_path.clone();
            pins.socket_path = original.with_file_name("alias.sock");
            std::os::unix::fs::symlink(&original, &pins.socket_path).unwrap();
            let mut client = NativeLinuxManagementReader::new(pins);
            assert_eq!(client.next().err(), Some(ReadFailure::Unverified));
            let _ = UnixStream::connect(&original);
            thread.join().unwrap();

            let (_home, mut pins, thread) = fake_service("EOF");
            let original = pins.socket_path.clone();
            pins.socket_path = original.with_file_name("missing.sock");
            let mut client = NativeLinuxManagementReader::new(pins);
            assert_eq!(client.next().err(), Some(ReadFailure::Offline));
            let _ = UnixStream::connect(&original);
            thread.join().unwrap();
        }
    }
}
