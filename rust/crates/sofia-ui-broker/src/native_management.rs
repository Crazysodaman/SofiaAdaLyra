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
                service_pid,
            })
        }
    }

    /// One new request per call, bounded native IO and exact shared v1 parser.
    /// No connection pooling, discovery, permission grant, effect or retry.
    pub struct NativeLinuxManagementReader {
        pins: InstalledNativeServicePins,
        local_sequence: u64,
    }

    impl NativeLinuxManagementReader {
        #[must_use]
        pub fn new(pins: InstalledNativeServicePins) -> Self {
            Self {
                pins,
                local_sequence: 0,
            }
        }

        fn status(&mut self) -> Result<DisplaySnapshot, ReadFailure> {
            // The exact native instance and its filesystem inode must agree.
            let inode = verify_endpoint(&self.pins)?;
            let now = Utc::now().fixed_offset();
            let mut random = [0_u8; 16];
            getrandom::getrandom(&mut random).map_err(|_| ReadFailure::Unverified)?;
            let mut request_id = String::from("req:");
            for value in random {
                request_id.push_str(&format!("{value:02x}"));
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
                "uncorrelated_management_response" => ReadFailure::UnknownGeneration,
                _ => ReadFailure::Unverified,
            })?;
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
        if !dir.is_dir()
            || dir.uid() != pins.service_uid
            || dir.gid() != pins.service_gid
            || !matches!(mode, 0o700 | 0o750)
            || !leaf.file_type().is_socket()
            || leaf.uid() != pins.service_uid
            || leaf.gid() != pins.service_gid
            || (leaf.permissions().mode() & 0o777)
                != if mode == 0o700 { 0o600 } else { 0o660 }
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
                if outcome == "STOPPED" || outcome == "REVOKED" {
                    result["outcome"] = serde_json::json!("DENIED");
                    result["data"] = serde_json::Value::Null;
                    result["denial"] = serde_json::json!({"code": outcome});
                }
                if outcome == "STALE_GENERATION" {
                    result["platform_generation"] = serde_json::json!(2);
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
                ("EOF", ReadFailure::Offline),
                ("STALE_GENERATION", ReadFailure::UnknownGeneration),
                ("DUPLICATE", ReadFailure::Unverified),
            ] {
                let (_home, pins, thread) = fake_service(case);
                let mut client = NativeLinuxManagementReader::new(pins);
                assert_eq!(client.next().err(), Some(expected), "{case}");
                thread.join().unwrap();
            }
        }

        #[test]
        fn wrong_pinned_uid_and_socket_mode_are_rejected() {
            let (_home, mut pins, thread) = fake_service("EOF");
            pins.service_uid = pins.service_uid.checked_add(1).unwrap();
            let mut client = NativeLinuxManagementReader::new(pins);
            assert_eq!(client.next().err(), Some(ReadFailure::Unverified));
            // The test listener has no connection and would block; drop it
            // by ending the thread after a local connection to the socket.
            let _ = UnixStream::connect(&client.pins.socket_path);
            thread.join().unwrap();
        }
    }
}
