//! Native SCM control adapter. SCM authorizes OS service controls; it does not
//! grant Aegis owner permissions, enroll peers or activate a Core.
use super::{run, Configuration, Failure};
use std::ffi::OsString;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::time::Duration;
use windows_service::{
    define_windows_service,
    service::{
        ServiceControl, ServiceControlAccept, ServiceExitCode, ServiceState, ServiceStatus,
        ServiceType,
    },
    service_control_handler::{self, ServiceControlHandlerResult},
    service_dispatcher,
};

const NAME: &str = "AegisPlatform";
define_windows_service!(ffi_service_main, service_main);

pub(super) fn dispatch() -> windows_service::Result<()> {
    service_dispatcher::start(NAME, ffi_service_main)
}

fn status(state: ServiceState, code: u32) -> ServiceStatus {
    ServiceStatus {
        service_type: ServiceType::OWN_PROCESS,
        current_state: state,
        controls_accepted: if state == ServiceState::Running {
            ServiceControlAccept::STOP | ServiceControlAccept::SHUTDOWN
        } else {
            ServiceControlAccept::empty()
        },
        exit_code: ServiceExitCode::Win32(code),
        checkpoint: 0,
        // Stopping may include bounded Hub and recipient drains. SCM must
        // not use the normal startup hint to judge this shutdown.
        wait_hint: if state == ServiceState::StopPending {
            Duration::from_secs(90)
        } else {
            Duration::from_secs(10)
        },
        process_id: None,
    }
}

fn service_main(_arguments: Vec<OsString>) {
    let _ = execute();
}

fn execute() -> Result<(), Failure> {
    let config = Configuration::parse(&std::env::args().skip(2).collect::<Vec<_>>())?;
    let stopped = Arc::new(AtomicBool::new(false));
    let signal = stopped.clone();
    let handle = service_control_handler::register(NAME, move |control| match control {
        ServiceControl::Stop | ServiceControl::Shutdown => {
            signal.store(true, Ordering::SeqCst);
            ServiceControlHandlerResult::NoError
        }
        ServiceControl::Interrogate => ServiceControlHandlerResult::NoError,
        _ => ServiceControlHandlerResult::NotImplemented,
    })?;
    handle.set_service_status(status(ServiceState::StartPending, 0))?;
    let result = run(
        &config,
        &stopped,
        |_| {
            handle.set_service_status(status(ServiceState::Running, 0))?;
            Ok(())
        },
        || {
            handle.set_service_status(status(ServiceState::StopPending, 0))?;
            Ok(())
        },
    );
    handle.set_service_status(status(ServiceState::Stopped, u32::from(result.is_err())))?;
    result
}
