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
    use nix::sys::socket::{getsockopt, sockopt::PeerCredentials};
    use sofia_contracts::library::{
        UntrustedLibraryRequest, UntrustedLibraryResponse, LIBRARY_PROTOCOL,
        LIBRARY_REQUEST_SCHEMA, MAX_LIBRARY_CONTROL_BYTES,
    };
    use sofia_contracts::management::{
        UntrustedManagementRead, UntrustedManagementResponse, MANAGEMENT_READ_PROTOCOL,
        MANAGEMENT_READ_SCHEMA, MAX_MANAGEMENT_RESPONSE_BYTES,
    };
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
                || !bytes.iter().copied().all(|byte| {
                    byte.is_ascii_alphanumeric()
                        || matches!(byte, b'.' | b'_' | b'-' | b':' | b'@' | b'/')
                })
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
                write!(&mut request_id, "{value:02x}").map_err(|_| ReadFailure::Unverified)?;
            }
            let created_at = now.to_rfc3339_opts(SecondsFormat::Micros, true);
            let deadline =
                (now + ChronoDuration::seconds(5)).to_rfc3339_opts(SecondsFormat::Micros, true);
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
            let expected =
                UntrustedManagementRead::parse(&raw, now).map_err(|_| ReadFailure::Unverified)?;
            let mut connection =
                UnixStream::connect(&self.pins.socket_path).map_err(|_| ReadFailure::Offline)?;
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
            let response =
                UntrustedManagementResponse::parse(&body, &expected, Utc::now().fixed_offset())
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
                return Err(response
                    .denial
                    .as_ref()
                    .and_then(|denial| from_verified_denial(&denial.code))
                    .unwrap_or(ReadFailure::Unverified));
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

    /// This is an OS-verified observation from the already-authenticated
    /// canonical Platform service, NOT raw Hub publisher proof or a B1
    /// installation receipt. No cached/display values imply installed state.
    #[derive(Debug, Clone)]
    pub struct NativeLibraryCatalogSnapshot {
        pub platform_id: String,
        pub platform_generation: u64,
        pub publisher_catalog_generation: u64,
        pub catalog_revision: u64,
        pub source_platform_id: String,
        pub observed_at: String,
        pub catalog: serde_json::Value,
    }

    /// A separate D028 catalog reader over the EXISTING pinned management
    /// socket, never a listener or new authority. The caller MUST source all
    /// pins including the revision floor from an independently B1-publisher-
    /// verified installed profile. A UI may not construct these from flags,
    /// downloaded Hub JSON or stale local inventory.
    pub struct NativeLinuxLibraryCatalogReader {
        pins: InstalledNativeServicePins,
        expected_source_id: String,
        expected_catalog_generation: u64,
        expected_catalog_revision: u64,
        verified_endpoint: Option<(u64, u64)>,
    }

    impl NativeLinuxLibraryCatalogReader {
        /// Construct a source-only reader. Syntax validation is not proof
        /// the caller has B1 signer trust or current owner SAFE enrollment.
        pub fn from_verified_installation(
            pins: InstalledNativeServicePins,
            expected_source_id: String,
            expected_catalog_generation: u64,
            expected_catalog_revision: u64,
        ) -> Result<Self, ReadFailure> {
            let bytes = expected_source_id.as_bytes();
            if bytes.is_empty()
                || bytes.len() > 160
                || !bytes[0].is_ascii_alphanumeric()
                || bytes.iter().any(|b| {
                    !b.is_ascii_alphanumeric()
                        && !matches!(b, b'.' | b'_' | b':' | b'@' | b'/' | b'-')
                })
                || expected_catalog_generation == 0
                || expected_catalog_generation > MAX_GENERATION
                || expected_catalog_revision == 0
                || expected_catalog_revision > MAX_GENERATION
            {
                return Err(ReadFailure::Unverified);
            }
            Ok(Self {
                pins,
                expected_source_id,
                expected_catalog_generation,
                expected_catalog_revision,
                verified_endpoint: None,
            })
        }

        /// One new request with random correlation IDs and bounded native IO.
        /// No fallback URL, automatic enrollment, package effect or retry.
        pub fn catalog(&mut self) -> Result<NativeLibraryCatalogSnapshot, ReadFailure> {
            let inode = verify_endpoint(&self.pins)?;
            if self.verified_endpoint.is_some_and(|prior| prior != inode) {
                return Err(ReadFailure::Unverified);
            }
            let now = Utc::now().fixed_offset();
            let mut random = [0_u8; 16];
            getrandom::getrandom(&mut random).map_err(|_| ReadFailure::Unverified)?;
            let mut random_id = String::new();
            for value in random {
                write!(&mut random_id, "{value:02x}").map_err(|_| ReadFailure::Unverified)?;
            }
            let raw = serde_json::to_vec(&serde_json::json!({
                "schema": LIBRARY_REQUEST_SCHEMA,
                "protocol": LIBRARY_PROTOCOL,
                "request_id": format!("request:{random_id}"),
                "correlation_id": format!("correlation:{random_id}"),
                "operation": "library.catalog.snapshot.v1",
                "target_platform_id": self.pins.platform_id.clone(),
                "expected_generation": self.pins.generation,
                "expected_revision": self.expected_catalog_revision,
                "idempotency_key": null,
                "created_at": now.to_rfc3339_opts(SecondsFormat::Micros, true),
                "deadline": (now + ChronoDuration::seconds(5))
                    .to_rfc3339_opts(SecondsFormat::Micros, true),
                "parameters": {
                    "limit": 32,
                    "cursor": null,
                    "kinds": [],
                },
            }))
            .map_err(|_| ReadFailure::Unverified)?;
            if raw.len() > MAX_LIBRARY_CONTROL_BYTES {
                return Err(ReadFailure::Unverified);
            }
            let expected =
                UntrustedLibraryRequest::parse(&raw, now).map_err(|_| ReadFailure::Unverified)?;
            let mut connection =
                UnixStream::connect(&self.pins.socket_path).map_err(|_| ReadFailure::Offline)?;
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
            if body.len() > MAX_LIBRARY_CONTROL_BYTES || verify_endpoint(&self.pins)? != inode {
                return Err(ReadFailure::Unverified);
            }
            let response =
                UntrustedLibraryResponse::parse(&body, &expected, Utc::now().fixed_offset())
                    .map_err(|_| ReadFailure::Unverified)?;
            // Fence this exact socket epoch EVEN on a correlated denial:
            // a substituted pipe cannot be adopted after STOP/revocation.
            self.verified_endpoint = Some(inode);
            if response.outcome == "DENIED" {
                return Err(response
                    .denial_code
                    .as_ref()
                    .and_then(|code| from_verified_denial(code))
                    .unwrap_or(ReadFailure::Unverified));
            }
            if response.outcome != "OK" {
                return Err(ReadFailure::Unverified);
            }
            let catalog = response.data.ok_or(ReadFailure::Unverified)?;
            let catalog_generation = catalog["catalog_generation"]
                .as_u64()
                .ok_or(ReadFailure::Unverified)?;
            let catalog_revision = catalog["catalog_revision"]
                .as_u64()
                .ok_or(ReadFailure::Unverified)?;
            let source_id = catalog["source"]["source_id"]
                .as_str()
                .ok_or(ReadFailure::Unverified)?;
            if catalog_generation != self.expected_catalog_generation
                || catalog_revision != self.expected_catalog_revision
                || source_id != self.expected_source_id
            {
                return Err(ReadFailure::Unverified);
            }
            Ok(NativeLibraryCatalogSnapshot {
                platform_id: response.platform_id,
                platform_generation: response.platform_generation,
                publisher_catalog_generation: catalog_generation,
                catalog_revision,
                source_platform_id: source_id.to_owned(),
                observed_at: response.observed_at,
                catalog,
            })
        }
    }

    /// Current owner-only local Platform source states. These observations
    /// do NOT certify package signatures, cache admission or Core startup.
    #[derive(Debug, Clone)]
    pub struct NativeOwnerSourcesSnapshot {
        pub platform_id: String,
        pub platform_generation: u64,
        pub observed_at: String,
        pub source_platform_id: Option<String>,
        pub publisher_state: String,
        pub catalog_state: String,
        pub hub_state: String,
        pub served_chunks: u64,
        pub served_bytes: u64,
    }

    /// OS-authenticated read-only owner status, usable before a Hub or a
    /// publisher exists. Requires the same externally B1-verified installed
    /// service pins as platform.status and a SEPARATE current SAFE owner
    /// grant for library.sources.snapshot.v1. No UI-supplied credentials.
    pub struct NativeLinuxOwnerSourcesReader {
        pins: InstalledNativeServicePins,
        verified_endpoint: Option<(u64, u64)>,
    }

    impl NativeLinuxOwnerSourcesReader {
        #[must_use]
        pub fn from_verified_installation(pins: InstalledNativeServicePins) -> Self {
            Self {
                pins,
                verified_endpoint: None,
            }
        }

        /// Query the same pinned native Unix socket, not a Hub endpoint.
        ///
        /// # Errors
        /// No owner grant, STOP, stale RUN, unknown/corrupt local socket,
        /// unreviewed source states or impossible counters fail closed.
        pub fn sources(&mut self) -> Result<NativeOwnerSourcesSnapshot, ReadFailure> {
            let inode = verify_endpoint(&self.pins)?;
            if self.verified_endpoint.is_some_and(|prior| prior != inode) {
                return Err(ReadFailure::Unverified);
            }
            let now = Utc::now().fixed_offset();
            let mut random = [0_u8; 16];
            getrandom::getrandom(&mut random).map_err(|_| ReadFailure::Unverified)?;
            let mut random_id = String::new();
            for value in random {
                write!(&mut random_id, "{value:02x}").map_err(|_| ReadFailure::Unverified)?;
            }
            let raw = serde_json::to_vec(&serde_json::json!({
                "schema": LIBRARY_REQUEST_SCHEMA,
                "protocol": LIBRARY_PROTOCOL,
                "request_id": format!("request:{random_id}"),
                "correlation_id": format!("correlation:{random_id}"),
                "operation": "library.sources.snapshot.v1",
                "target_platform_id": self.pins.platform_id.clone(),
                "expected_generation": self.pins.generation,
                "expected_revision": 0,
                "idempotency_key": null,
                "created_at": now.to_rfc3339_opts(SecondsFormat::Micros, true),
                "deadline": (now + ChronoDuration::seconds(5))
                    .to_rfc3339_opts(SecondsFormat::Micros, true),
                "parameters": {},
            }))
            .map_err(|_| ReadFailure::Unverified)?;
            if raw.len() > MAX_LIBRARY_CONTROL_BYTES {
                return Err(ReadFailure::Unverified);
            }
            let expected =
                UntrustedLibraryRequest::parse(&raw, now).map_err(|_| ReadFailure::Unverified)?;
            let mut connection =
                UnixStream::connect(&self.pins.socket_path).map_err(|_| ReadFailure::Offline)?;
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
            let reply = read_one(&mut connection)?;
            if reply.len() > MAX_LIBRARY_CONTROL_BYTES || verify_endpoint(&self.pins)? != inode {
                return Err(ReadFailure::Unverified);
            }
            let response =
                UntrustedLibraryResponse::parse(&reply, &expected, Utc::now().fixed_offset())
                    .map_err(|_| ReadFailure::Unverified)?;
            self.verified_endpoint = Some(inode);
            if response.outcome == "DENIED" {
                return Err(response
                    .denial_code
                    .as_ref()
                    .and_then(|code| from_verified_denial(code))
                    .unwrap_or(ReadFailure::Unverified));
            }
            if response.outcome != "OK" {
                return Err(ReadFailure::Unverified);
            }
            let source = response.data.ok_or(ReadFailure::Unverified)?;
            let source_id = if source["source_platform_id"].is_null() {
                None
            } else {
                Some(
                    source["source_platform_id"]
                        .as_str()
                        .ok_or(ReadFailure::Unverified)?
                        .to_owned(),
                )
            };
            Ok(NativeOwnerSourcesSnapshot {
                platform_id: response.platform_id,
                platform_generation: response.platform_generation,
                observed_at: response.observed_at,
                source_platform_id: source_id,
                publisher_state: source["publisher_state"]
                    .as_str()
                    .ok_or(ReadFailure::Unverified)?
                    .to_owned(),
                catalog_state: source["catalog_state"]
                    .as_str()
                    .ok_or(ReadFailure::Unverified)?
                    .to_owned(),
                hub_state: source["hub_state"]
                    .as_str()
                    .ok_or(ReadFailure::Unverified)?
                    .to_owned(),
                served_chunks: source["served_chunks"]
                    .as_u64()
                    .ok_or(ReadFailure::Unverified)?,
                served_bytes: source["served_bytes"]
                    .as_u64()
                    .ok_or(ReadFailure::Unverified)?,
            })
        }
    }

    fn no_symlinks(path: &Path) -> Result<(), ReadFailure> {
        for component in path.ancestors() {
            let info = fs::symlink_metadata(component).map_err(|_| ReadFailure::Offline)?;
            if info.file_type().is_symlink() {
                return Err(ReadFailure::Unverified);
            }
        }
        Ok(())
    }

    fn verify_endpoint(pins: &InstalledNativeServicePins) -> Result<(u64, u64), ReadFailure> {
        no_symlinks(&pins.socket_path)?;
        let parent = pins.socket_path.parent().ok_or(ReadFailure::Unverified)?;
        let dir = fs::symlink_metadata(parent).map_err(|_| ReadFailure::Offline)?;
        let leaf = fs::symlink_metadata(&pins.socket_path).map_err(|_| ReadFailure::Offline)?;
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
        let actual =
            getsockopt(connection, PeerCredentials).map_err(|_| ReadFailure::Unverified)?;
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
            let remaining = deadline
                .checked_duration_since(Instant::now())
                .filter(|time| !time.is_zero())
                .ok_or(ReadFailure::Offline)?;
            connection
                .set_read_timeout(Some(remaining))
                .map_err(|_| ReadFailure::Unverified)?;
            let mut chunk = [0_u8; 4096];
            let got = connection
                .read(&mut chunk)
                .map_err(|_| ReadFailure::Offline)?;
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
        ) -> (
            tempfile::TempDir,
            InstalledNativeServicePins,
            thread::JoinHandle<()>,
        ) {
            let home = tempfile::tempdir().unwrap();
            let socket_path = home.path().join("mgmt-3.sock");
            let listener = UnixListener::bind(&socket_path).unwrap();
            fs::set_permissions(&socket_path, fs::Permissions::from_mode(0o600)).unwrap();
            let info = fs::metadata(home.path()).unwrap();
            let pins = InstalledNativeServicePins::from_externally_verified_installation(
                socket_path,
                "platform:alpha".into(),
                3,
                info.uid(),
                info.gid(),
                None,
                Some(i32::try_from(std::process::id()).unwrap()),
            )
            .unwrap();
            let handle = thread::spawn(move || {
                let (mut connection, _) = listener.accept().unwrap();
                if outcome == "EOF" {
                    return;
                }
                let mut wire = Vec::new();
                BufReader::new(&connection)
                    .read_until(b'\n', &mut wire)
                    .unwrap();
                let request: serde_json::Value = serde_json::from_slice(&wire).unwrap();
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
                    "STOPPED"
                        | "REVOKED"
                        | "NOT_PERMITTED"
                        | "UNAVAILABLE"
                        | "EXPIRED"
                        | "STALE_GENERATION"
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
                    connection
                        .write_all(b"{\"schema\":1,\"schema\":2}\n")
                        .unwrap();
                    return;
                }
                connection
                    .write_all(serde_json::to_string(&result).unwrap().as_bytes())
                    .unwrap();
                connection.write_all(b"\n").unwrap();
            });
            (home, pins, handle)
        }

        fn fake_library_service(
            outcome: &'static str,
        ) -> (
            tempfile::TempDir,
            InstalledNativeServicePins,
            thread::JoinHandle<()>,
        ) {
            let home = tempfile::tempdir().unwrap();
            let socket_path = home.path().join("mgmt-17.sock");
            let listener = UnixListener::bind(&socket_path).unwrap();
            fs::set_permissions(&socket_path, fs::Permissions::from_mode(0o600)).unwrap();
            let stat = fs::metadata(home.path()).unwrap();
            let pins = InstalledNativeServicePins::from_externally_verified_installation(
                socket_path,
                "platform:recipient".into(),
                17,
                stat.uid(),
                stat.gid(),
                None,
                Some(i32::try_from(std::process::id()).unwrap()),
            )
            .unwrap();
            let handle = thread::spawn(move || {
                let (mut socket, _) = listener.accept().unwrap();
                let mut message = Vec::new();
                BufReader::new(&socket)
                    .read_until(b'\n', &mut message)
                    .unwrap();
                if outcome == "EOF" {
                    return;
                }
                let request: serde_json::Value = serde_json::from_slice(&message).unwrap();
                let moment = Utc::now();
                let observed = moment.to_rfc3339_opts(SecondsFormat::Micros, true);
                let freshness = (moment + ChronoDuration::seconds(40))
                    .to_rfc3339_opts(SecondsFormat::Micros, true);
                let mut response = serde_json::json!({
                    "schema": "aegis.platform.library.response.v1",
                    "protocol": "1.0",
                    "request_id": request["request_id"],
                    "correlation_id": request["correlation_id"],
                    "operation": "library.catalog.snapshot.v1",
                    "platform_id": request["target_platform_id"],
                    "platform_generation": request["expected_generation"],
                    "state_revision": request["expected_revision"],
                    "observed_at": observed,
                    "outcome": "OK",
                    "data": {
                        "catalog_revision": request["expected_revision"],
                        "catalog_generation": 9,
                        "catalog_fresh_until": freshness,
                        "target_platform_id": request["target_platform_id"],
                        "source": {
                            "kind": "OWNER_SELECTED_HUB",
                            "source_id": "primary-library",
                            "last_observed_at": observed,
                            "status": "CURRENT"
                        },
                        "page": {
                            "limit": 32,
                            "next_cursor": null,
                            "cursor_state": "CURRENT"
                        },
                        "items": []
                    },
                    "denial": null
                });
                match outcome {
                    "STOPPED" | "REVOKED" | "NOT_PERMITTED" | "UNAVAILABLE" => {
                        response["outcome"] = serde_json::json!("DENIED");
                        response["data"] = serde_json::Value::Null;
                        response["denial"] = serde_json::json!({"code": outcome});
                    }
                    "WRONG_SOURCE" => {
                        response["data"]["source"]["source_id"] =
                            serde_json::json!("untrusted-source");
                    }
                    "WRONG_CATALOG_EPOCH" => {
                        response["data"]["catalog_generation"] = serde_json::json!(8);
                    }
                    "WRONG_REVISION" => {
                        response["data"]["catalog_revision"] = serde_json::json!(6);
                    }
                    "WRONG_PLATFORM" => {
                        response["platform_id"] = serde_json::json!("other-platform");
                    }
                    _ => {}
                }
                socket
                    .write_all(serde_json::to_string(&response).unwrap().as_bytes())
                    .unwrap();
                socket.write_all(b"\n").unwrap();
            });
            (home, pins, handle)
        }

        #[test]
        fn native_catalog_reader_uses_pinned_socket_and_exact_signed_service_scope() {
            let (_root, pins, handle) = fake_library_service("OK");
            let mut reader = NativeLinuxLibraryCatalogReader::from_verified_installation(
                pins,
                "primary-library".into(),
                9,
                7,
            )
            .unwrap();
            let observed = reader.catalog().unwrap();
            assert_eq!(observed.platform_id, "platform:recipient");
            assert_eq!(observed.platform_generation, 17);
            assert_eq!(observed.publisher_catalog_generation, 9);
            assert_eq!(observed.catalog_revision, 7);
            assert_eq!(observed.source_platform_id, "primary-library");
            assert!(observed.catalog["items"].as_array().unwrap().is_empty());
            assert!(observed.catalog.get("installed").is_none());
            handle.join().unwrap();
        }

        #[test]
        fn native_catalog_reader_fails_closed_on_denial_and_signed_scope_mismatch() {
            for outcome in [
                "STOPPED",
                "REVOKED",
                "UNAVAILABLE",
                "WRONG_SOURCE",
                "WRONG_CATALOG_EPOCH",
                "WRONG_REVISION",
                "WRONG_PLATFORM",
                "EOF",
            ] {
                let (_root, pins, handle) = fake_library_service(outcome);
                let mut reader = NativeLinuxLibraryCatalogReader::from_verified_installation(
                    pins,
                    "primary-library".into(),
                    9,
                    7,
                )
                .unwrap();
                let result = reader.catalog();
                assert!(result.is_err(), "unexpected verified Library: {outcome}");
                handle.join().unwrap();
            }
        }

        #[test]
        fn native_catalog_reader_refuses_unknown_b1_index_source() {
            let root = tempfile::tempdir().unwrap();
            let path = root.path().join("mgmt-17.sock");
            let stat = fs::metadata(root.path()).unwrap();
            let pins = InstalledNativeServicePins::from_externally_verified_installation(
                path,
                "platform:recipient".into(),
                17,
                stat.uid(),
                stat.gid(),
                None,
                None,
            )
            .unwrap();
            assert!(NativeLinuxLibraryCatalogReader::from_verified_installation(
                pins.clone(),
                "bad source".into(),
                9,
                7,
            )
            .is_err());
            assert!(NativeLinuxLibraryCatalogReader::from_verified_installation(
                pins.clone(),
                "primary-library".into(),
                0,
                7,
            )
            .is_err());
            assert!(NativeLinuxLibraryCatalogReader::from_verified_installation(
                pins,
                "primary-library".into(),
                9,
                0,
            )
            .is_err());
        }

        fn fake_owner_sources_service(
            result: &'static str,
        ) -> (
            tempfile::TempDir,
            InstalledNativeServicePins,
            thread::JoinHandle<()>,
        ) {
            let home = tempfile::tempdir().unwrap();
            let path = home.path().join("mgmt-17.sock");
            let listener = UnixListener::bind(&path).unwrap();
            fs::set_permissions(&path, fs::Permissions::from_mode(0o600)).unwrap();
            let stat = fs::metadata(home.path()).unwrap();
            let pins = InstalledNativeServicePins::from_externally_verified_installation(
                path,
                "platform:recipient".into(),
                17,
                stat.uid(),
                stat.gid(),
                None,
                Some(i32::try_from(std::process::id()).unwrap()),
            )
            .unwrap();
            let handle = thread::spawn(move || {
                let (mut socket, _) = listener.accept().unwrap();
                let mut request_bytes = Vec::new();
                BufReader::new(&socket)
                    .read_until(b'\n', &mut request_bytes)
                    .unwrap();
                if result == "EOF" {
                    return;
                }
                let request: serde_json::Value = serde_json::from_slice(&request_bytes).unwrap();
                assert_eq!(request["operation"], "library.sources.snapshot.v1");
                let mut message = serde_json::json!({
                    "schema": "aegis.platform.library.response.v1",
                    "protocol": "1.0",
                    "request_id": request["request_id"],
                    "correlation_id": request["correlation_id"],
                    "operation": request["operation"],
                    "platform_id": request["target_platform_id"],
                    "platform_generation": request["expected_generation"],
                    "state_revision": request["expected_revision"],
                    "observed_at": Utc::now()
                        .to_rfc3339_opts(SecondsFormat::Micros, true),
                    "outcome": "OK",
                    "data": {
                        "schema": "aegis.library.owner-sources.v1",
                        "owner_mode": "SINGLE_OWNER_PRIVATE",
                        "source_platform_id": null,
                        "publisher_state": "UNENROLLED",
                        "catalog_state": "UNAVAILABLE",
                        "hub_state": "CLOSED",
                        "served_chunks": 0,
                        "served_bytes": 0
                    },
                    "denial": null
                });
                match result {
                    "CURRENT" => {
                        message["data"]["publisher_state"] = serde_json::json!("CURRENT");
                        message["data"]["source_platform_id"] = serde_json::json!("platform:hub");
                        message["data"]["catalog_state"] = serde_json::json!("CURRENT");
                        message["data"]["hub_state"] = serde_json::json!("SERVING");
                        message["data"]["served_chunks"] = serde_json::json!(2);
                        message["data"]["served_bytes"] = serde_json::json!(2097152);
                    }
                    "STOPPED" | "REVOKED" | "UNAVAILABLE" => {
                        message["outcome"] = serde_json::json!("DENIED");
                        message["data"] = serde_json::Value::Null;
                        message["denial"] = serde_json::json!({"code":result});
                    }
                    "UNSIGNED_READY" => {
                        message["data"]["catalog_state"] = serde_json::json!("CURRENT");
                    }
                    "BOGUS_READY" => {
                        message["data"]["hub_state"] = serde_json::json!("READY");
                    }
                    "EXTRA_OWNER_SECRET" => {
                        message["data"]["owner_secret"] = serde_json::json!("not-allowed");
                    }
                    "BAD_COUNTER" => {
                        message["data"]["served_bytes"] = serde_json::json!(-1);
                    }
                    "WRONG_PLATFORM" => {
                        message["platform_id"] = serde_json::json!("other-platform");
                    }
                    _ => {}
                }
                socket.write_all(message.to_string().as_bytes()).unwrap();
                socket.write_all(b"\n").unwrap();
            });
            (home, pins, handle)
        }

        #[test]
        fn native_owner_status_works_before_publisher_enrollment() {
            let (_home, pins, worker) = fake_owner_sources_service("UNENROLLED");
            let mut client = NativeLinuxOwnerSourcesReader::from_verified_installation(pins);
            let snapshot = client.sources().expect("local owner status");
            assert_eq!(snapshot.platform_id, "platform:recipient");
            assert_eq!(snapshot.platform_generation, 17);
            assert_eq!(snapshot.publisher_state, "UNENROLLED");
            assert_eq!(snapshot.catalog_state, "UNAVAILABLE");
            assert_eq!(snapshot.hub_state, "CLOSED");
            assert!(snapshot.source_platform_id.is_none());
            assert_eq!(snapshot.served_bytes, 0);
            worker.join().unwrap();
        }

        #[test]
        fn native_owner_status_reports_current_internal_hub_without_install_claim() {
            let (_home, pins, worker) = fake_owner_sources_service("CURRENT");
            let mut client = NativeLinuxOwnerSourcesReader::from_verified_installation(pins);
            let snapshot = client
                .sources()
                .expect("verified native service observation");
            assert_eq!(snapshot.source_platform_id.as_deref(), Some("platform:hub"));
            assert_eq!(snapshot.catalog_state, "CURRENT");
            assert_eq!(snapshot.hub_state, "SERVING");
            assert_eq!(snapshot.served_chunks, 2);
            assert_eq!(snapshot.served_bytes, 2097152);
            worker.join().unwrap();
        }

        #[test]
        fn native_owner_status_denials_and_forgeries_never_claim_hub_readiness() {
            for case in [
                "STOPPED",
                "REVOKED",
                "UNAVAILABLE",
                "EOF",
                "UNSIGNED_READY",
                "BOGUS_READY",
                "EXTRA_OWNER_SECRET",
                "BAD_COUNTER",
                "WRONG_PLATFORM",
            ] {
                let (_home, pins, worker) = fake_owner_sources_service(case);
                let mut client = NativeLinuxOwnerSourcesReader::from_verified_installation(pins);
                assert!(client.sources().is_err(), "{case} must fail closed");
                worker.join().unwrap();
            }
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
            fs::set_permissions(&original, fs::Permissions::from_mode(0o600)).unwrap();
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
            assert_eq!(
                client.verified_endpoint.map(|(_, inode)| inode),
                Some(old_inode)
            );
            fs::rename(&original, home.path().join("old-stop-socket")).unwrap();
            let _new_listener = UnixListener::bind(&original).unwrap();
            fs::set_permissions(&original, fs::Permissions::from_mode(0o600)).unwrap();
            assert_ne!(old_inode, fs::metadata(&original).unwrap().ino());
            assert_eq!(client.next().err(), Some(ReadFailure::Unverified));
            assert_eq!(client.local_sequence, 0);
        }

        #[test]
        fn private_and_enrolled_group_modes_do_not_downgrade() {
            let (home, mut pins, thread) = fake_service("EOF");
            fs::set_permissions(home.path(), fs::Permissions::from_mode(0o750)).unwrap();
            fs::set_permissions(&pins.socket_path, fs::Permissions::from_mode(0o660)).unwrap();
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
            fs::set_permissions(&pins.socket_path, fs::Permissions::from_mode(0o666)).unwrap();
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
