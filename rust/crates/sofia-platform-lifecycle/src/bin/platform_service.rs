//! Rust process owner for the installed, Core-free Platform state adapter.
//! Trusted OS service configuration only; no public management/enrollment IPC.
use serde::Deserialize;
use serde_json::json;
use std::io::{BufRead, BufReader, Read, Write};
use std::path::PathBuf;
#[cfg(not(windows))]
use std::process::Command;
use std::process::{Child, ChildStdin, Stdio};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    mpsc, Arc,
};
use std::time::{Duration, Instant};

const SCHEMA: &str = "aegis.platform.service-control.v1";
// Match reviewed #224 cold-start protection; health IPC stays at five seconds.
const INITIAL_REPLY_TIMEOUT: Duration = Duration::from_secs(12);
const HEALTH_REPLY_TIMEOUT: Duration = Duration::from_secs(5);
// The Python Platform session may drain one Hub handshake (<=33s),
// management IPC (<=3s), and an active recipient (<=30s) before releasing
// its RUN lease. Never kill it after the old five-second stop deadline.
const SHUTDOWN_DRAIN_TIMEOUT: Duration = Duration::from_secs(75);
type Failure = Box<dyn std::error::Error + Send + Sync>;
// Reject arbitrary 36-character labels before starting a privileged service.
// Keep the lexical check dependency-free and accept UUID versions supported by
// the durable identity store (not just random v4 UUIDs).
fn valid_platform_uuid(value: &str) -> bool {
    let bytes = value.as_bytes();
    bytes.len() == 36
        && bytes.iter().enumerate().all(|(i, byte)| {
            if matches!(i, 8 | 13 | 18 | 23) {
                *byte == b'-'
            } else {
                byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase()
            }
        })
}


#[derive(Clone)]
struct Configuration {
    python: PathBuf,
    identity: PathBuf,
    state: PathBuf,
    platform_id: String,
    public_key: String,
}
impl Configuration {
    fn parse(args: &[String]) -> Result<Self, Failure> {
        if args.len() != 10 {
            return Err("five exact service configuration options required".into());
        }
        let names = [
            "--python",
            "--identity-home",
            "--state",
            "--platform-id",
            "--public-key-sha256",
        ];
        if args
            .chunks_exact(2)
            .zip(names)
            .any(|(pair, name)| pair[0] != name)
        {
            return Err("invalid service configuration".into());
        }
        let config = Self {
            python: args[1].clone().into(),
            identity: args[3].clone().into(),
            state: args[5].clone().into(),
            platform_id: args[7].clone(),
            public_key: args[9].clone(),
        };
        if !config.python.is_absolute()
            || !config.python.is_file()
            || !config.identity.is_absolute()
            || !config.state.is_absolute()
            || !valid_platform_uuid(&config.platform_id)
            || config.public_key.len() != 64
            || !config
                .public_key
                .bytes()
                .all(|v| v.is_ascii_digit() || (b'a'..=b'f').contains(&v))
        {
            return Err("absolute installed paths and pinned Platform identity required".into());
        }
        Ok(config)
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Reply {
    schema: String,
    phase: String,
    platform_id: String,
    public_key_sha256: String,
    serial: String,
    generation: u64,
    core_started: bool,
    operator_stop: bool,
    sequence: Option<u64>,
    pid: Option<u32>,
    supervisor_pid: Option<u32>,
    #[serde(default)]
    management_listening: bool,
    #[serde(default)]
    management_endpoint: Option<String>,
}

// The child is not an independent authority: every response must remain
// pinned to the installed Platform, its generation and its first READY serial.
// Identity serial v1 encodes exactly the UUID bits as four uppercase
// eight-digit hex groups. Never accept a plausible-looking substitute.
fn canonical_platform_serial(uuid: &str) -> String {
    let hex = uuid.replace('-', "").to_ascii_uppercase();
    format!(
        "AEG-P-{}-{}-{}-{}",
        &hex[0..8], &hex[8..16], &hex[16..24], &hex[24..32],
    )
}

fn reply_matches_identity(reply: &Reply, config: &Configuration, serial: Option<&str>) -> bool {
    reply.schema == SCHEMA
        && reply.platform_id == config.platform_id
        && reply.public_key_sha256 == config.public_key
        && !reply.core_started
        && reply.generation != 0
        && valid_platform_uuid(&config.platform_id)
        && reply.serial == canonical_platform_serial(&config.platform_id)
        && serial.map_or(true, |pinned| reply.serial == pinned)
}

#[cfg(not(windows))]
fn valid_installed_unix_endpoint(endpoint: &str, generation: u64, runtime: &str) -> bool {
    // The installed systemd profile supplies one of these exact runtime
    // roots; no arbitrary environment path may become an IPC authority.
    matches!(runtime, "/run/aegis" | "/run/aegis-platform")
        && endpoint == format!("{runtime}/mgmt-{generation}.sock")
}

#[cfg(not(windows))]
fn valid_unix_endpoint_with_context(
    endpoint: &str, generation: u64, runtime: Option<&str>, systemd: bool,
) -> bool {
    if let Some(runtime) = runtime {
        return valid_installed_unix_endpoint(endpoint, generation, runtime);
    }
    // Missing RuntimeDirectory in a systemd invocation is a hard failure.
    if systemd {
        return false;
    }
    // Explicit developer foreground sessions have a private temp socket,
    // never an installed service's runtime generation endpoint.
    let path = std::path::Path::new(endpoint);
    path.is_absolute()
        && !path.components().any(|part| matches!(part, std::path::Component::ParentDir))
        && path.file_name() == Some(std::ffi::OsStr::new("management.sock"))
}

// Never declare the native management interface ready just because the
// child returned a non-empty string. Require this RUN generation's endpoint.
fn valid_management_endpoint(endpoint: &str, platform_id: &str, generation: u64) -> bool {
    if endpoint.is_empty()
        || endpoint.len() > 256
        || generation == 0
        || endpoint.chars().any(char::is_control)
    {
        return false;
    }
    #[cfg(windows)]
    {
        let expected = format!(
            r"\\.\pipe\AegisPlatform-{}-{}",
            platform_id.replace('-', ""), generation,
        );
        endpoint == expected
    }
    #[cfg(not(windows))]
    {
        let _ = platform_id;
        // Never let a systemd invocation adopt a developer fallback.
        let runtime = std::env::var_os("RUNTIME_DIRECTORY");
        let runtime = match runtime.as_ref() {
            Some(value) => match value.to_str() {
                Some(value) => Some(value),
                None => return false,
            },
            None => None,
        };
        valid_unix_endpoint_with_context(
            endpoint, generation, runtime,
            std::env::var_os("INVOCATION_ID").is_some(),
        )
    }
}

struct Worker {
    child: Child,
    input: Option<ChildStdin>,
    replies: mpsc::Receiver<Result<Reply, String>>,
    generation: u64,
    sequence: u64,
    operator_stop: bool,
    serial: String,
    management_endpoint: String,
    config: Configuration,
}
impl Worker {
    fn start(config: &Configuration) -> Result<Self, Failure> {
        #[cfg(windows)]
        let mut command = interpreter::command(&config.python)?;
        #[cfg(not(windows))]
        let mut command = Command::new(&config.python);
        command
            .args([
                "-I",
                "-m",
                "sofia.platform.run.platform_service",
                "--identity-home",
            ])
            .arg(&config.identity)
            .arg("--state")
            .arg(&config.state)
            .arg("--platform-id")
            .arg(&config.platform_id)
            .arg("--public-key-sha256")
            .arg(&config.public_key)
            .arg("--supervisor-pid")
            .arg(std::process::id().to_string())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
        }
        let mut child = command.spawn()?;
        let input = child.stdin.take();
        let output = child.stdout.take().ok_or("service pipe unavailable")?;
        let (sender, replies) = mpsc::sync_channel(1);
        std::thread::spawn(move || {
            let mut output = BufReader::new(output);
            loop {
                let mut bytes = Vec::new();
                let result = output.by_ref().take(16385).read_until(b'\n', &mut bytes);
                let value = match result {
                    Ok(_) if bytes.len() <= 16384 && bytes.last() == Some(&b'\n') => {
                        serde_json::from_slice(&bytes)
                            .map_err(|_| "invalid service response".to_owned())
                    }
                    _ => Err("service response unavailable or oversized".to_owned()),
                };
                let failed = value.is_err();
                if sender.send(value).is_err() || failed {
                    break;
                }
            }
        });
        let mut worker = Self {
            child,
            input,
            replies,
            generation: 0,
            sequence: 0,
            operator_stop: false,
            serial: String::new(),
            management_endpoint: String::new(),
            config: config.clone(),
        };
        let ready = worker.receive(INITIAL_REPLY_TIMEOUT)?;
        worker.generation = ready.generation;
        worker.operator_stop = ready.operator_stop;
        worker.serial = ready.serial.clone();
        worker.management_endpoint = ready.management_endpoint.clone().unwrap_or_default();
        if !ready.management_listening
            || !valid_management_endpoint(
                &worker.management_endpoint,
                &config.platform_id,
                worker.generation,
            )
        {
            return Err("authenticated management listener not ready".into());
        }
        if ready.phase != "ready"
            || ready.sequence.is_some()
            || ready.pid.map(u64::from) != Some(u64::from(worker.child.id()))
            || ready.supervisor_pid.map(u64::from) != Some(u64::from(std::process::id()))
        {
            return Err("service lifetime binding differs".into());
        }
        Ok(worker)
    }
    fn receive(&self, timeout: Duration) -> Result<Reply, Failure> {
        let value = self
            .replies
            .recv_timeout(timeout)?
            .map_err(|_| "canonical Platform service unavailable")?;
        if !reply_matches_identity(
            &value,
            &self.config,
            if self.serial.is_empty() { None } else { Some(&self.serial) },
        ) {
            return Err("service identity response differs".into());
        }
        Ok(value)
    }
    fn request(&mut self, operation: &str) -> Result<(), Failure> {
        self.sequence = self
            .sequence
            .checked_add(1)
            .ok_or("service sequence exhausted")?;
        let request = json!({"schema": SCHEMA, "sequence": self.sequence,
            "generation": self.generation, "operation": operation});
        let input = self.input.as_mut().ok_or("service input closed")?;
        writeln!(input, "{request}")?;
        input.flush()?;
        let value = self.receive(HEALTH_REPLY_TIMEOUT)?;
        if value.sequence != Some(self.sequence)
            || value.serial != self.serial
            || value.pid.is_some()
            || value.supervisor_pid.is_some()
            || value.generation != self.generation
            || !value.management_listening
            || value.management_endpoint.as_deref() != Some(self.management_endpoint.as_str())
            || value.phase
                != if operation == "shutdown" {
                    "stopped"
                } else {
                    "healthy"
                }
        {
            return Err("stale service response".into());
        }
        self.operator_stop = value.operator_stop;
        Ok(())
    }
    fn stop(&mut self) -> Result<(), Failure> {
        self.request("shutdown")?;
        self.input.take();
        let deadline = Instant::now() + SHUTDOWN_DRAIN_TIMEOUT;
        while Instant::now() < deadline {
            if let Some(status) = self.child.try_wait()? {
                return if status.success() {
                    Ok(())
                } else {
                    Err("service shutdown failed".into())
                };
            }
            std::thread::sleep(Duration::from_millis(20));
        }
        Err("service drain deadline exceeded".into())
    }
}
impl Drop for Worker {
    fn drop(&mut self) {
        self.input.take();
        if !matches!(self.child.try_wait(), Ok(Some(_))) {
            let _ = self.child.kill();
        }
        let _ = self.child.wait();
    }
}

fn run(
    config: &Configuration,
    stopped: &AtomicBool,
    ready: impl FnOnce(&Worker) -> Result<(), Failure>,
    draining: impl FnOnce() -> Result<(), Failure>,
) -> Result<(), Failure> {
    let mut worker = Worker::start(config)?;
    ready(&worker)?;
    while !stopped.load(Ordering::SeqCst) {
        worker.request("status")?;
        for _ in 0..10 {
            if stopped.load(Ordering::SeqCst) {
                break;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    }
    draining()?;
    worker.stop()
}

#[cfg(unix)]
fn notify(message: &str) -> Result<(), Failure> {
    use std::os::unix::net::UnixDatagram;
    if let Some(path) = std::env::var_os("NOTIFY_SOCKET") {
        // Filesystem systemd sockets are supported. Abstract addresses require
        // a separately verified adapter; fail closed instead of claiming readiness.
        if path.as_encoded_bytes().first() == Some(&b'@') {
            return Err("abstract notify socket unsupported".into());
        }
        let socket = UnixDatagram::unbound()?;
        socket.set_write_timeout(Some(Duration::from_secs(1)))?;
        socket.send_to(message.as_bytes(), path)?;
    }
    Ok(())
}

fn console(config: &Configuration) -> Result<(), Failure> {
    let stopped = Arc::new(AtomicBool::new(false));
    let signal = stopped.clone();
    ctrlc::set_handler(move || signal.store(true, Ordering::SeqCst))
        .map_err(|error| format!("console control handler unavailable: {error}"))?;
    let result = run(
        config,
        &stopped,
        |worker| {
            #[cfg(unix)]
            notify("READY=1\nSTATUS=Core-free Platform authority active")?;
            println!(
                "{}",
                json!({"schema": SCHEMA, "phase":"ready", "supervisor_pid": std::process::id(), "platform_id":config.platform_id, "worker_pid":worker.child.id(), "generation":worker.generation, "operator_stop":worker.operator_stop, "management_listening": true})
            );
            Ok(())
        },
        || {
            #[cfg(unix)]
            notify("STOPPING=1")?;
            Ok(())
        },
    );
    #[cfg(unix)]
    {
        let _ = notify("STOPPING=1");
    }
    result
}

#[cfg(windows)]
#[path = "../service_interpreter.rs"]
mod interpreter;

#[cfg(windows)]
#[path = "../service_windows.rs"]
mod scm;

fn main() {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    #[cfg(windows)]
    if args.first().is_some_and(|v| v == "--scm") {
        args.remove(0);
        if Configuration::parse(&args).is_err() {
            std::process::exit(2);
        }
        if scm::dispatch().is_err() {
            std::process::exit(2);
        }
        return;
    }
    #[cfg(not(windows))]
    let _ = &mut args;
    let result = Configuration::parse(&args).and_then(|config| console(&config));
    if let Err(error) = result {
        let detail: String = error
            .to_string()
            .chars()
            .take(160)
            .map(|c| if c.is_control() { '?' } else { c })
            .collect();
        eprintln!("Platform service failed closed: {detail}");
        std::process::exit(2);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn shutdown_waits_for_bounded_hub_and_recipient_drain() {
        assert!(SHUTDOWN_DRAIN_TIMEOUT >= Duration::from_secs(66));
        assert!(SHUTDOWN_DRAIN_TIMEOUT < Duration::from_secs(90));
        assert_eq!(HEALTH_REPLY_TIMEOUT, Duration::from_secs(5));
    }
    #[test]
    fn cold_boot_timeout_is_bounded_without_relaxing_health_ipc() {
        assert!(INITIAL_REPLY_TIMEOUT > HEALTH_REPLY_TIMEOUT);
        assert!(INITIAL_REPLY_TIMEOUT < Duration::from_secs(15));
        assert_eq!(HEALTH_REPLY_TIMEOUT, Duration::from_secs(5));
    }
    #[test]
    fn reply_rejects_duplicate_and_unknown_fields() {
        let value = json!({"schema":SCHEMA,"phase":"healthy","platform_id":"p",
            "public_key_sha256":"f","serial":"s","generation":1,"core_started":false,
            "operator_stop":true,"sequence":1});
        let mut raw = value.to_string();
        assert!(serde_json::from_str::<Reply>(&raw).is_ok());
        raw.insert_str(1, "\"generation\":2,");
        assert!(serde_json::from_str::<Reply>(&raw).is_err());
        let mut extra = value;
        extra["owner_authorized"] = json!(true);
        assert!(serde_json::from_value::<Reply>(extra).is_err());
    }
    #[test]
    fn platform_id_requires_canonical_lowercase_uuid() {
        assert!(valid_platform_uuid("12345678-1234-4abc-8abc-1234567890ab"));
        assert!(valid_platform_uuid("00000000-0000-0000-0000-000000000000"));
        assert!(!valid_platform_uuid("x".repeat(36).as_str()));
        assert!(!valid_platform_uuid("1234567812344abc8abc1234567890ab"));
        assert!(!valid_platform_uuid("12345678_1234_4abc_8abc_1234567890ab"));
        assert!(!valid_platform_uuid("12345678-1234-4ABC-8abc-1234567890ab"));
        assert!(!valid_platform_uuid("12345678-1234-4abc-8abc-1234567890ab "));
    }
    #[test]
    fn platform_serial_matches_identity_contract() {
        assert_eq!(
            canonical_platform_serial("01234567-89ab-cdef-fedc-ba9876543210"),
            "AEG-P-01234567-89ABCDEF-FEDCBA98-76543210",
        );
    }
    #[test]
    fn reply_serial_cannot_change_after_ready() {
        let config = Configuration {
            python: PathBuf::from("/unused/python"),
            identity: PathBuf::from("/unused/identity"),
            state: PathBuf::from("/unused/state"),
            platform_id: "12345678-1234-4abc-8abc-1234567890ab".to_owned(),
            public_key: "a".repeat(64),
        };
        let mut reply: Reply = serde_json::from_value(json!({
            "schema": SCHEMA, "phase":"ready",
            "platform_id":config.platform_id,
            "public_key_sha256":config.public_key,
            "serial":"AEG-P-12345678-12344ABC-8ABC1234-567890AB", "generation":1,
            "core_started":false, "operator_stop":false,
            "sequence":null, "pid":1, "supervisor_pid":2,
        })).expect("valid reply");
        assert!(reply_matches_identity(&reply, &config, None));
        assert!(reply_matches_identity(&reply, &config, Some("AEG-P-12345678-12344ABC-8ABC1234-567890AB")));
        assert!(!reply_matches_identity(&reply, &config, Some("AEG-P-00000000-00000000-00000000-00000000")));
        reply.serial = "AEG-P-00000000-00000000-00000000-00000000".to_owned();
        assert!(!reply_matches_identity(&reply, &config, Some("AEG-P-12345678-12344ABC-8ABC1234-567890AB")));
        reply.serial = "AEG-P-12345678-12344ABC-8ABC1234-567890AB\\nforged".to_owned();
        assert!(!reply_matches_identity(&reply, &config, None));
        reply.serial = "AEG-P-12345678-12344ABC-8ABC1234-567890AB".to_owned();
        reply.core_started = true;
        assert!(!reply_matches_identity(&reply, &config, None));
    }
    #[test]
    fn native_management_endpoint_is_generation_bound() {
        let id = "12345678-1234-4abc-8abc-1234567890ab";
        #[cfg(windows)]
        {
            let good = format!(r"\\.\pipe\AegisPlatform-{}-7", id.replace('-', ""));
            assert!(valid_management_endpoint(&good, id, 7));
            assert!(!valid_management_endpoint(&good, id, 8));
            assert!(!valid_management_endpoint(r"\\.\pipe\SomeOtherService", id, 7));
        }
        #[cfg(not(windows))]
        {
            assert!(valid_installed_unix_endpoint("/run/aegis/mgmt-7.sock", 7, "/run/aegis"));
            assert!(valid_unix_endpoint_with_context(
                "/tmp/aegis-mgmt-test/management.sock", 7, None, false,
            ));
            assert!(!valid_unix_endpoint_with_context(
                "/run/aegis/mgmt-7.sock", 8, Some("/run/aegis"), true,
            ));
            assert!(!valid_unix_endpoint_with_context(
                "mgmt-7.sock", 7, None, false,
            ));
            assert!(!valid_unix_endpoint_with_context(
                "/run/../tmp/mgmt-7.sock", 7, Some("/run/aegis"), true,
            ));
        }
        assert!(!valid_management_endpoint("socket\nforged", id, 7));
        assert!(!valid_management_endpoint("", id, 7));
        assert!(!valid_management_endpoint("ignored", id, 0));
    }
    #[cfg(not(windows))]
    #[test]
    fn unix_management_endpoint_requires_installed_runtime_or_explicit_dev() {
        let endpoint = "/run/aegis-platform/mgmt-9.sock";
        assert!(valid_unix_endpoint_with_context(
            endpoint, 9, Some("/run/aegis-platform"), true,
        ));
        assert!(!valid_unix_endpoint_with_context(
            endpoint, 9, None, true,
        ));
        assert!(!valid_unix_endpoint_with_context(
            "/tmp/private/management.sock", 9, None, true,
        ));
        assert!(valid_unix_endpoint_with_context(
            "/tmp/private/management.sock", 9, None, false,
        ));
        assert!(!valid_unix_endpoint_with_context(
            "/tmp/private/management.sock", 9, Some("/run/aegis-platform"), true,
        ));
        assert!(!valid_unix_endpoint_with_context(
            "/tmp/../private/management.sock", 9, None, false,
        ));
    }

    #[cfg(not(windows))]
    #[test]
    fn installed_systemd_listener_never_adopts_unreviewed_runtime() {
        assert!(valid_installed_unix_endpoint(
            "/run/aegis-platform/mgmt-7.sock", 7, "/run/aegis-platform"
        ));
        assert!(valid_installed_unix_endpoint(
            "/run/aegis/mgmt-7.sock", 7, "/run/aegis"
        ));
        assert!(!valid_installed_unix_endpoint(
            "/tmp/mgmt-7.sock", 7, "/tmp"
        ));
        assert!(!valid_installed_unix_endpoint(
            "/run/aegis-platform/mgmt-6.sock", 7, "/run/aegis-platform"
        ));
        assert!(!valid_installed_unix_endpoint(
            "/run/aegis-platform/management.sock", 7, "/run/aegis-platform"
        ));
        assert!(!valid_installed_unix_endpoint(
            "/run/aegis-platform/mgmt-7.sock", 7, "/run/../run/aegis-platform"
        ));
    }
    #[test]
    fn no_arbitrary_program_or_incomplete_configuration() {
        assert!(Configuration::parse(&[]).is_err());
        let values: Vec<String> = [
            "--python",
            "relative-python",
            "--identity-home",
            "/identity",
            "--state",
            "/state",
            "--platform-id",
            "bad",
            "--public-key-sha256",
            "bad",
        ]
        .iter()
        .map(|value| (*value).into())
        .collect();
        assert!(Configuration::parse(&values).is_err());
    }
}
