//! `CPython` Windows venv launchers create another process. Launch the trusted
//! base interpreter directly with `CPython`'s own venv selector, keeping the
//! actual child/parent PID contract intact. No arbitrary command is accepted.
use super::Failure;
use std::fs::File;
use std::io::Read;
use std::os::windows::fs::MetadataExt;
use std::path::{Component, Path, PathBuf, Prefix};
use std::process::Command;

fn unredirected(path: &Path) -> Result<(), Failure> {
    if !path.is_absolute()
        || !matches!(path.components().next(), Some(Component::Prefix(prefix))
        if matches!(prefix.kind(), Prefix::Disk(_) | Prefix::VerbatimDisk(_)))
        || path.components().any(|part| part == Component::ParentDir)
    {
        return Err("a local absolute interpreter path is required".into());
    }
    for entry in path.ancestors() {
        let metadata = std::fs::symlink_metadata(entry)?;
        if metadata.file_type().is_symlink() || metadata.file_attributes() & 0x400 != 0 {
            return Err("interpreter configuration is redirected".into());
        }
    }
    Ok(())
}

fn home(contents: &str) -> Result<PathBuf, Failure> {
    let mut found = None;
    for line in contents.lines() {
        if let Some((key, value)) = line.split_once('=') {
            if key.trim() == "home" {
                if found.is_some() || value.trim().is_empty() {
                    return Err("ambiguous venv home".into());
                }
                found = Some(PathBuf::from(value.trim()));
            }
        }
    }
    found.ok_or_else(|| "venv home unavailable".into())
}

pub(super) fn command(python: &Path) -> Result<Command, Failure> {
    unredirected(python)?;
    let parent = python.parent().ok_or("interpreter directory unavailable")?;
    for directory in [Some(parent), parent.parent()].into_iter().flatten() {
        let config = directory.join("pyvenv.cfg");
        if !config.try_exists()? {
            continue;
        }
        unredirected(&config)?;
        let mut text = String::new();
        File::open(config)?.take(8193).read_to_string(&mut text)?;
        if text.len() > 8192 {
            return Err("venv configuration oversized".into());
        }
        let executable = home(&text)?.join("python.exe");
        unredirected(&executable)?;
        if !executable.is_file() {
            return Err("base interpreter unavailable".into());
        }
        let mut command = Command::new(executable);
        command.env("__PYVENV_LAUNCHER__", python);
        return Ok(command);
    }
    let mut command = Command::new(python);
    command.env_remove("__PYVENV_LAUNCHER__");
    Ok(command)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn venv_home_is_exact_and_not_a_shell_command() {
        assert_eq!(
            home("home = C:\\Python312\nversion = 3.12\n").unwrap(),
            PathBuf::from("C:\\Python312")
        );
        assert!(home("home = C:\\a\nhome = C:\\b\n").is_err());
        assert!(home("home = \n").is_err());
        assert!(home("executable = C:\\ignored.exe\n").is_err());
    }
}
