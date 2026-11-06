//! Rust process owner for the installed, Core-free Platform state adapter.
//! Trusted OS service configuration only; no public management/enrollment IPC.
use serde::Deserialize;
use serde_json::json;
use std::io::{BufRead, BufReader, Read, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    mpsc, Arc,
};
use std::time::{Duration, Instant};

const SCHEMA: &str = "aegis.platform.service-control.v1";
type Failure = Box<dyn std::error::Error + Send + Sync>;

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
            || config.platform_id.len() != 36
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
}

struct Worker {
    child: Child,
    input: Option<ChildStdin>,
    replies: mpsc::Receiver<Result<Reply, String>>,
    generation: u64,
    sequence: u64,
    operator_stop: bool,
    config: Configuration,
}
impl Worker {
    fn start(config: &Configuration) -> Result<Self, Failure> {
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
            config: config.clone(),
        };
        let ready = worker.receive()?;
        worker.generation = ready.generation;
        worker.operator_stop = ready.operator_stop;
        if ready.phase != "ready"
            || ready.sequence.is_some()
            || ready.pid.map(u64::from) != Some(u64::from(worker.child.id()))
            || ready.supervisor_pid.map(u64::from) != Some(u64::from(std::process::id()))
        {
            return Err("service lifetime binding differs".into());
        }
        Ok(worker)
    }
    fn receive(&self) -> Result<Reply, Failure> {
        let value = self
            .replies
            .recv_timeout(Duration::from_secs(5))?
            .map_err(|_| "canonical Platform service unavailable")?;
        if value.schema != SCHEMA
            || value.platform_id != self.config.platform_id
            || value.public_key_sha256 != self.config.public_key
            || value.core_started
            || value.generation == 0
            || !value.serial.starts_with("AEG-P-")
        {
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
        let value = self.receive()?;
        if value.sequence != Some(self.sequence)
            || value.pid.is_some()
            || value.supervisor_pid.is_some()
            || value.generation != self.generation
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
        let deadline = Instant::now() + Duration::from_secs(5);
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
    ctrlc::set_handler(move || signal.store(true, Ordering::SeqCst))?;
    let result = run(
        config,
        &stopped,
        |worker| {
            #[cfg(unix)]
            notify("READY=1\nSTATUS=Core-free Platform authority active")?;
            println!(
                "{}",
                json!({"schema": SCHEMA, "phase":"ready", "supervisor_pid": std::process::id(), "platform_id":config.platform_id, "worker_pid":worker.child.id(), "generation":worker.generation, "operator_stop":worker.operator_stop})
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
    if result.is_err() {
        eprintln!("Platform service failed closed; inspect canonical identity, local state and service configuration");
        std::process::exit(2);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
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
