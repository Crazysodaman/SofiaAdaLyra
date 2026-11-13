//! Read-only local named-pipe transport. OS identity is a pin, not owner enrollment.
use crate::control_center::{InstallationState, PermissionState, SafeState};
use crate::control_center_session::{
    from_verified_denial, DisplayReadSource, DisplaySnapshot, ReadFailure,
};
use chrono::{Duration as ChronoDuration, SecondsFormat, Utc};
use interprocess::os::windows::named_pipe::{pipe_mode, DuplexPipeStream};
use sofia_contracts::management::{
    UntrustedManagementRead, UntrustedManagementResponse, MANAGEMENT_READ_PROTOCOL,
    MANAGEMENT_READ_SCHEMA, MAX_MANAGEMENT_RESPONSE_BYTES,
};
use std::fmt::Write as _;
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::os::windows::fs::OpenOptionsExt;
use std::os::windows::io::{AsHandle, OwnedHandle};
use std::time::{Duration, Instant};
use winsafe::{self as w, co};

const IO_TIMEOUT: Duration = Duration::from_secs(2);
const MAX_GENERATION: u64 = 9_007_199_254_740_991;
type Connection = DuplexPipeStream<pipe_mode::Bytes>;

/// Exact, externally verified installed service instance. This constructor
/// validates syntax only; raw JSON, arguments and environment are not trust.
#[derive(Debug, Clone)]
pub struct InstalledNativeServicePins {
    pipe_path: String,
    platform_id: String,
    generation: u64,
    service_pid: u32,
    service_sid: String,
    service_creation_time: u64,
}

impl InstalledNativeServicePins {
    /// Use only current publisher-verified installation and owner enrollment evidence.
    /// `pipe_name` is a local leaf name, never a UNC destination.
    /// `service_creation_time` is the installed process creation FILETIME.
    ///
    /// # Errors
    /// Rejects ambiguous endpoints, invalid identities and missing process pins.
    #[allow(clippy::similar_names)] // PID and SID are separate exact OS identity pins.
    pub fn from_externally_verified_installation(
        pipe_name: &str,
        platform_id: String,
        generation: u64,
        service_pid: u32,
        service_sid: String,
        service_creation_time: u64,
    ) -> Result<Self, ReadFailure> {
        let id = platform_id.as_bytes();
        if pipe_name.is_empty()
            || pipe_name.len() > 120
            || !pipe_name
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'.' | b'-'))
            || id.is_empty()
            || id.len() > 160
            || !id[0].is_ascii_alphanumeric()
            || !id.iter().all(|b| {
                b.is_ascii_alphanumeric() || matches!(b, b'_' | b'.' | b'-' | b':' | b'@' | b'/')
            })
            || generation == 0
            || generation > MAX_GENERATION
            || service_pid == 0
            || service_creation_time == 0
            || !valid_sid(&service_sid)
        {
            return Err(ReadFailure::Unverified);
        }
        Ok(Self {
            pipe_path: format!(r"\\.\pipe\{pipe_name}"),
            platform_id,
            generation,
            service_pid,
            service_sid,
            service_creation_time,
        })
    }
}

fn valid_sid(sid: &str) -> bool {
    sid.len() <= 184
        && sid.starts_with("S-1-")
        && sid[4..].split('-').all(|part| {
            !part.is_empty()
                && (part == "0" || !part.starts_with('0'))
                && part.bytes().all(|b| b.is_ascii_digit())
                && part.parse::<u64>().is_ok()
        })
}

/// Fresh, correlated observation only. No enrollment, effects or automatic
/// adoption of another process after restart. New installed pins are required.
pub struct NativeWindowsManagementReader {
    pins: InstalledNativeServicePins,
    local_sequence: u64,
}
impl NativeWindowsManagementReader {
    #[must_use]
    pub fn new(pins: InstalledNativeServicePins) -> Self {
        Self {
            pins,
            local_sequence: 0,
        }
    }

    fn status(&mut self) -> Result<DisplaySnapshot, ReadFailure> {
        // CreateFile does not wait for a busy instance. Do not use the dependency's
        // connect_by_path, whose retry loop waits without an overall deadline.
        // Identification SQOS permits server-side identity inspection without
        // permitting the server to impersonate the client for other effects.
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .security_qos_flags(0x0011_0000)
            .open(&self.pins.pipe_path)
            .map_err(|_| ReadFailure::Offline)?;
        let mut pipe =
            Connection::try_from(OwnedHandle::from(file)).map_err(|_| ReadFailure::Unverified)?;
        // Always reclaim the handle explicitly, even on failure: PipeStream's
        // default drop can enqueue a blocking flush. No flush is needed for a
        // bounded request whose correlated response was consumed.
        let result = self.exchange(&mut pipe);
        let handle = OwnedHandle::try_from(pipe).map_err(|_| ReadFailure::Unverified)?;
        drop(handle);
        result
    }

    fn exchange(&mut self, pipe: &mut Connection) -> Result<DisplaySnapshot, ReadFailure> {
        pipe.set_nonblocking(true)
            .map_err(|_| ReadFailure::Unverified)?;
        verify_peer(pipe, &self.pins)?;
        let now = Utc::now().fixed_offset();
        let mut random = [0_u8; 16];
        getrandom::getrandom(&mut random).map_err(|_| ReadFailure::Unverified)?;
        let mut request_id = String::from("req:");
        for byte in random {
            write!(&mut request_id, "{byte:02x}").map_err(|_| ReadFailure::Unverified)?;
        }
        let mut raw = serde_json::to_vec(&serde_json::json!({
            "schema": MANAGEMENT_READ_SCHEMA, "protocol": MANAGEMENT_READ_PROTOCOL,
            "request_id": request_id, "target_platform_id": self.pins.platform_id,
            "expected_generation": self.pins.generation, "operation": "platform.status",
            "created_at": now.to_rfc3339_opts(SecondsFormat::Micros,true),
            "deadline": (now + ChronoDuration::seconds(5)).to_rfc3339_opts(SecondsFormat::Micros,true),
        })).map_err(|_| ReadFailure::Unverified)?;
        let expected =
            UntrustedManagementRead::parse(&raw, now).map_err(|_| ReadFailure::Unverified)?;
        raw.push(b'\n');
        let deadline = Instant::now() + IO_TIMEOUT;
        // interprocess's Read adapter downgrades ERROR_NO_DATA (232) to EOF.
        // PIPE_NOWAIT reports 232 for a live empty pipe, so use File I/O to
        // retain the native error and distinguish it from actual EOF.
        let mut io = File::from(
            pipe.as_handle()
                .try_clone_to_owned()
                .map_err(|_| ReadFailure::Unverified)?,
        );
        write_bounded(&mut io, &raw, deadline)?;
        let body = read_bounded(&mut io, deadline)?;
        verify_peer(pipe, &self.pins)?;
        let response =
            UntrustedManagementResponse::parse(&body, &expected, Utc::now().fixed_offset())
                .map_err(|error| {
                    if error.code == "stale_management_response" {
                        ReadFailure::Stale
                    } else {
                        ReadFailure::Unverified
                    }
                })?;
        if response.outcome == "DENIED" {
            return Err(response
                .denial
                .as_ref()
                .and_then(|d| from_verified_denial(&d.code))
                .unwrap_or(ReadFailure::Unverified));
        }
        if response.outcome != "OK" {
            return Err(ReadFailure::Unverified);
        }
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
impl DisplayReadSource for NativeWindowsManagementReader {
    fn next(&mut self) -> Result<DisplaySnapshot, ReadFailure> {
        self.status()
    }
}

fn verify_peer(pipe: &Connection, pins: &InstalledNativeServicePins) -> Result<(), ReadFailure> {
    if !pipe.is_client()
        || pipe
            .server_process_id()
            .map_err(|_| ReadFailure::Unverified)?
            != pins.service_pid
    {
        return Err(ReadFailure::Unverified);
    }
    let process = w::HPROCESS::OpenProcess(
        co::PROCESS::QUERY_LIMITED_INFORMATION,
        false,
        pins.service_pid,
    )
    .map_err(|_| ReadFailure::Unverified)?;
    let (created, exited, _, _) = process
        .GetProcessTimes()
        .map_err(|_| ReadFailure::Unverified)?;
    if u64::from(created) != pins.service_creation_time || u64::from(exited) != 0 {
        return Err(ReadFailure::Unverified);
    }
    let token = process
        .OpenProcessToken(co::TOKEN::QUERY)
        .map_err(|_| ReadFailure::Unverified)?;
    let w::TokenInfo::User(user) = token
        .GetTokenInformation(co::TOKEN_INFORMATION_CLASS::User)
        .map_err(|_| ReadFailure::Unverified)?
    else {
        return Err(ReadFailure::Unverified);
    };
    let actual_sid = w::ConvertSidToStringSid(user.User.Sid().ok_or(ReadFailure::Unverified)?)
        .map_err(|_| ReadFailure::Unverified)?;
    if actual_sid != pins.service_sid {
        return Err(ReadFailure::Unverified);
    }
    Ok(())
}

fn temporarily_empty(error: &std::io::Error) -> bool {
    error.kind() == std::io::ErrorKind::WouldBlock || error.raw_os_error() == Some(232)
}

fn pause(deadline: Instant) -> Result<(), ReadFailure> {
    let remaining = deadline
        .checked_duration_since(Instant::now())
        .filter(|d| !d.is_zero())
        .ok_or(ReadFailure::Offline)?;
    std::thread::sleep(remaining.min(Duration::from_millis(2)));
    Ok(())
}
fn write_bounded(
    pipe: &mut impl Write,
    mut bytes: &[u8],
    deadline: Instant,
) -> Result<(), ReadFailure> {
    while !bytes.is_empty() {
        if Instant::now() >= deadline {
            return Err(ReadFailure::Offline);
        }
        match pipe.write(bytes) {
            Ok(0) => return Err(ReadFailure::Offline),
            Ok(count) => bytes = &bytes[count..],
            Err(error) if temporarily_empty(&error) => pause(deadline)?,
            Err(_) => return Err(ReadFailure::Offline),
        }
    }
    Ok(())
}
fn read_bounded(pipe: &mut impl Read, deadline: Instant) -> Result<Vec<u8>, ReadFailure> {
    let mut bytes = Vec::new();
    loop {
        if Instant::now() >= deadline {
            return Err(ReadFailure::Offline);
        }
        let mut chunk = [0_u8; 4096];
        match pipe.read(&mut chunk) {
            Ok(0) => return Err(ReadFailure::Offline),
            Ok(count) => bytes.extend_from_slice(&chunk[..count]),
            Err(error) if temporarily_empty(&error) => {
                pause(deadline)?;
                continue;
            }
            Err(_) => return Err(ReadFailure::Offline),
        }
        if bytes.len() > MAX_MANAGEMENT_RESPONSE_BYTES + 1 {
            return Err(ReadFailure::Unverified);
        }
        if bytes.contains(&b'\n') {
            if bytes.last() != Some(&b'\n') || bytes[..bytes.len() - 1].contains(&b'\n') {
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

    fn read_fixture_request(pipe: &mut impl Read, deadline: Instant) -> Option<Vec<u8>> {
        let mut bytes = Vec::new();
        while Instant::now() < deadline {
            let mut chunk = [0_u8; 4096];
            match pipe.read(&mut chunk) {
                Ok(0) => {
                    // A just-connected PIPE_NOWAIT server can transiently report
                    // zero bytes before the client has dispatched its request.
                    let _ = pause(deadline);
                }
                Ok(count) => {
                    bytes.extend_from_slice(&chunk[..count]);
                    if bytes.len() > MAX_MANAGEMENT_RESPONSE_BYTES + 1 {
                        return None;
                    }
                    if bytes.contains(&b'\n') {
                        if bytes.last() != Some(&b'\n') || bytes[..bytes.len() - 1].contains(&b'\n')
                        {
                            return None;
                        }
                        bytes.pop();
                        return Some(bytes);
                    }
                }
                Err(error) if temporarily_empty(&error) => {
                    let _ = pause(deadline);
                }
                Err(_) => return None,
            }
        }
        None
    }

    fn native_fixture(
        outcome: &'static str,
    ) -> (InstalledNativeServicePins, std::thread::JoinHandle<()>) {
        use interprocess::os::windows::named_pipe::PipeListenerOptions;
        let mut random = [0_u8; 8];
        getrandom::getrandom(&mut random).unwrap();
        let name = format!(
            "aegis-test-{}-{:x}",
            std::process::id(),
            u64::from_le_bytes(random)
        );
        let path = format!(r"\\.\pipe\{name}");
        let listener = PipeListenerOptions::new()
            .path(path)
            .create_duplex::<pipe_mode::Bytes>()
            .unwrap();
        let process = w::HPROCESS::GetCurrentProcess();
        let (created, _, _, _) = process.GetProcessTimes().unwrap();
        let token = w::HACCESSTOKEN::GetCurrentProcessToken();
        let w::TokenInfo::User(user) = token
            .GetTokenInformation(co::TOKEN_INFORMATION_CLASS::User)
            .unwrap()
        else {
            panic!("user token required");
        };
        let sid = w::ConvertSidToStringSid(user.User.Sid().unwrap()).unwrap();
        let pins = InstalledNativeServicePins::from_externally_verified_installation(
            &name,
            "platform:synthetic".into(),
            3,
            std::process::id(),
            sid,
            u64::from(created),
        )
        .unwrap();
        let thread = std::thread::spawn(move || {
            let pipe = match listener.accept() {
                Ok(pipe) => pipe,
                // A client that rejects the pinned process before dispatch may
                // close while ConnectNamedPipe is still completing. That is the
                // expected result of the negative identity cases.
                Err(error) if error.raw_os_error() == Some(232) => return,
                Err(error) => panic!("fixture pipe accept failed: {error}"),
            };
            pipe.set_nonblocking(true).unwrap();
            let deadline = Instant::now() + IO_TIMEOUT;
            let mut io = File::from(pipe.as_handle().try_clone_to_owned().unwrap());
            if let Some(body) = read_fixture_request(&mut io, deadline) {
                let request: serde_json::Value = serde_json::from_slice(&body).unwrap();
                let mut response = serde_json::json!({
                    "schema": "aegis.platform.management.read-response.v1", "protocol": "1.0",
                    "request_id": request["request_id"], "platform_id": request["target_platform_id"],
                    "platform_generation": request["expected_generation"], "operation": "platform.status",
                    "source": "PLATFORM_SESSION", "observed_at": Utc::now().to_rfc3339_opts(SecondsFormat::Micros,true),
                    "outcome": "OK", "data": {"platform_id": request["target_platform_id"],"generation": request["expected_generation"],"operator_stop": false,"core_started": false}, "denial": null
                });
                match outcome {
                    "REVOKED" | "STOPPED" | "STALE_GENERATION" => {
                        response["outcome"] = serde_json::json!("DENIED");
                        response["data"] = serde_json::Value::Null;
                        response["denial"] = serde_json::json!({"code":outcome});
                    }
                    "REPLAY" => response["request_id"] = serde_json::json!("req:previous"),
                    "GENERATION" => response["platform_generation"] = serde_json::json!(2),
                    _ => {}
                }
                let mut bytes = serde_json::to_vec(&response).unwrap();
                bytes.push(b'\n');
                let _ = write_bounded(&mut io, &bytes, deadline);
                // Keep server alive until client closes so response-release
                // process checks run against a live peer, without blocking flush.
                let mut probe = [0_u8; 1];
                while Instant::now() < deadline {
                    match io.read(&mut probe) {
                        Err(error) if temporarily_empty(&error) => {
                            let _ = pause(deadline);
                        }
                        Err(_) | Ok(0) => break,
                        Ok(_) => {}
                    }
                }
            }
            drop(OwnedHandle::try_from(pipe).unwrap());
        });
        (pins, thread)
    }

    #[test]
    fn native_pipe_correlates_status_and_typed_security_denials() {
        for (outcome, expected) in [
            ("OK", None),
            ("REVOKED", Some(ReadFailure::Revoked)),
            ("STOPPED", Some(ReadFailure::Stopped)),
            ("STALE_GENERATION", Some(ReadFailure::UnknownGeneration)),
            ("REPLAY", Some(ReadFailure::Unverified)),
            ("GENERATION", Some(ReadFailure::Unverified)),
        ] {
            let (pins, thread) = native_fixture(outcome);
            let result = NativeWindowsManagementReader::new(pins).next();
            if let Some(error) = expected {
                assert!(matches!(result,Err(actual) if actual==error), "{outcome}");
            } else {
                let status = result.unwrap();
                assert_eq!(status.platform_id, "platform:synthetic");
                assert_eq!(status.generation, 3);
                assert_eq!(status.installation, InstallationState::Unknown);
            }
            thread.join().unwrap();
        }
    }

    #[test]
    fn native_pipe_rejects_wrong_pid_sid_and_reused_pid_creation_time() {
        for wrong in ["PID", "SID", "CREATION"] {
            let (mut pins, thread) = native_fixture("OK");
            match wrong {
                "PID" => pins.service_pid = pins.service_pid.saturating_add(1),
                "SID" => pins.service_sid = "S-1-5-18".into(),
                _ => pins.service_creation_time += 1,
            }
            // Windows hosted CI can itself run as SYSTEM; use a definitely distinct SID.
            if wrong == "SID" {
                pins.service_sid = "S-1-5-21-1-2-3-4".into();
            }
            assert!(matches!(
                NativeWindowsManagementReader::new(pins).next(),
                Err(ReadFailure::Unverified)
            ));
            thread.join().unwrap();
        }
    }

    #[test]
    fn remote_pipe_and_missing_process_pins_are_rejected() {
        for name in [r"\\server\pipe\aegis", r"aegis\child", "", "pipe:alias"] {
            assert!(
                InstalledNativeServicePins::from_externally_verified_installation(
                    name,
                    "platform:one".into(),
                    1,
                    1,
                    "S-1-5-18".into(),
                    1
                )
                .is_err()
            );
        }
        assert!(
            InstalledNativeServicePins::from_externally_verified_installation(
                "aegis",
                "platform:one".into(),
                1,
                0,
                "S-1-5-18".into(),
                1
            )
            .is_err()
        );
        assert!(
            InstalledNativeServicePins::from_externally_verified_installation(
                "aegis",
                "platform:one".into(),
                1,
                1,
                "S-1-5-18".into(),
                0
            )
            .is_err()
        );
    }
    #[test]
    fn native_no_data_is_temporary_and_does_not_become_false_eof() {
        struct Delayed {
            first: bool,
        }
        impl Read for Delayed {
            fn read(&mut self, target: &mut [u8]) -> std::io::Result<usize> {
                if self.first {
                    self.first = false;
                    return Err(std::io::Error::from_raw_os_error(232));
                }
                target[..3].copy_from_slice(b"{}\n");
                Ok(3)
            }
        }
        assert_eq!(
            read_bounded(&mut Delayed { first: true }, Instant::now() + IO_TIMEOUT).unwrap(),
            b"{}"
        );
    }

    #[test]
    fn bounded_frames_reject_pipelining_and_eof() {
        assert_eq!(
            read_bounded(&mut &b"{}\n{}\n"[..], Instant::now() + IO_TIMEOUT),
            Err(ReadFailure::Unverified)
        );
        assert_eq!(
            read_bounded(&mut &b"{}"[..], Instant::now() + IO_TIMEOUT),
            Err(ReadFailure::Offline)
        );
    }
    #[test]
    fn stalled_peer_and_expired_write_fail_closed() {
        struct Stalled;
        impl Read for Stalled {
            fn read(&mut self, _: &mut [u8]) -> std::io::Result<usize> {
                Err(std::io::ErrorKind::WouldBlock.into())
            }
        }
        assert_eq!(
            read_bounded(&mut Stalled, Instant::now() + Duration::from_millis(5)),
            Err(ReadFailure::Offline)
        );
        assert_eq!(
            write_bounded(&mut Vec::new(), b"request", Instant::now()),
            Err(ReadFailure::Offline)
        );
    }
}
