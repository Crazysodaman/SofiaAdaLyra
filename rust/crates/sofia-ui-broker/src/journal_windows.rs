//! Native storage checks only; OS file ownership is not Aegis owner authority.
use super::JournalError;
use std::fs::{self, File, OpenOptions};
use std::os::windows::fs::{MetadataExt, OpenOptionsExt};
use std::path::{Component, Path, PathBuf, Prefix};
use windows_permissions::constants::{AceFlags, AceType, SeObjectType, SecurityInformation};
use windows_permissions::{wrappers, SecurityDescriptor};
use winsafe::{self as w, co};

const REPARSE_POINT: u32 = 0x400;
const OPEN_REPARSE_POINT: u32 = 0x0020_0000;
const BACKUP_SEMANTICS: u32 = 0x0200_0000;
const SHARE_READ: u32 = 1;
const SHARE_WRITE: u32 = 2;

fn current_sids() -> Result<(String, String), JournalError> {
    let token = w::HACCESSTOKEN::GetCurrentProcessToken();
    let w::TokenInfo::User(user) = token
        .GetTokenInformation(co::TOKEN_INFORMATION_CLASS::User)
        .map_err(|_| JournalError::UnsafeStorage)?
    else {
        return Err(JournalError::UnsafeStorage);
    };
    let w::TokenInfo::Owner(owner) = token
        .GetTokenInformation(co::TOKEN_INFORMATION_CLASS::Owner)
        .map_err(|_| JournalError::UnsafeStorage)?
    else {
        return Err(JournalError::UnsafeStorage);
    };
    let user = w::ConvertSidToStringSid(user.User.Sid().ok_or(JournalError::UnsafeStorage)?)
        .map_err(|_| JournalError::UnsafeStorage)?;
    let owner = w::ConvertSidToStringSid(owner.Owner().ok_or(JournalError::UnsafeStorage)?)
        .map_err(|_| JournalError::UnsafeStorage)?;
    Ok((user, owner))
}

fn verify_descriptor(
    descriptor: &SecurityDescriptor,
    user: &str,
    default_owner: &str,
) -> Result<(), JournalError> {
    let owner = descriptor
        .owner()
        .ok_or(JournalError::UnsafeStorage)?
        .to_string();
    if owner != user && owner != default_owner {
        return Err(JournalError::UnsafeStorage);
    }
    // The descriptor crate panics on a present NULL DACL. Inspect native
    // canonical SDDL first: required data access needs at least one ordinary
    // allow ACE. This also fences unknown ACE types before typed decoding.
    let encoded = wrappers::ConvertSecurityDescriptorToStringSecurityDescriptor(
        descriptor,
        SecurityInformation::Dacl,
    )
    .map_err(|_| JournalError::UnsafeStorage)?
    .into_string()
    .map_err(|_| JournalError::UnsafeStorage)?;
    if !encoded.starts_with("D:")
        || !encoded.contains('(')
        || encoded.contains("NO_ACCESS_CONTROL")
        || encoded
            .match_indices('(')
            .any(|(index, _)| !encoded[index..].starts_with("(A;"))
    {
        return Err(JournalError::UnsafeStorage);
    }
    let dacl = descriptor.dacl().ok_or(JournalError::UnsafeStorage)?;
    let mut read = false;
    let mut write = false;
    for index in 0..dacl.len() {
        let ace = dacl.get_ace(index).ok_or(JournalError::UnsafeStorage)?;
        // A private broker directory needs only ordinary allow ACEs. Denies,
        // conditional/object ACEs and unknown types require a richer effective
        // access evaluation; never infer owner access from them.
        if !matches!(ace.ace_type(), AceType::ACCESS_ALLOWED_ACE_TYPE) {
            return Err(JournalError::UnsafeStorage);
        }
        let sid = ace.sid().ok_or(JournalError::UnsafeStorage)?.to_string();
        let mask = ace.mask().bits();
        if mask != 0 && ![user, "S-1-5-18", "S-1-5-32-544", "S-1-3-4"].contains(&sid.as_str()) {
            return Err(JournalError::UnsafeStorage);
        }
        if (sid == user || sid == "S-1-3-4") && !ace.flags().contains(AceFlags::InheritOnly) {
            read |= mask & (0x8000_0000 | 0x1000_0000 | 1) != 0;
            write |= mask & (0x4000_0000 | 0x1000_0000 | 2) != 0;
        }
    }
    if !read || !write {
        return Err(JournalError::UnsafeStorage);
    }
    Ok(())
}

fn verify_private(file: &File) -> Result<(), JournalError> {
    let descriptor = wrappers::GetSecurityInfo(
        file,
        SeObjectType::SE_FILE_OBJECT,
        SecurityInformation::Owner | SecurityInformation::Dacl,
    )
    .map_err(|_| JournalError::UnsafeStorage)?;
    let (user, owner) = current_sids()?;
    verify_descriptor(&descriptor, &user, &owner)
}

pub(super) fn verify_private_file(file: &File) -> Result<(), JournalError> {
    let info = winapi_util::file::information(file)?;
    if info.file_attributes() & u64::from(REPARSE_POINT) != 0 || info.number_of_links() != 1 {
        return Err(JournalError::UnsafeStorage);
    }
    verify_private(file)
}

pub(super) fn restrict_file_options(options: &mut OpenOptions) {
    // Deny replacement or a second writable handle while validating/writing.
    options
        .share_mode(SHARE_READ)
        .custom_flags(OPEN_REPARSE_POINT);
}

fn validate_path(directory: &Path) -> Result<(), JournalError> {
    let mut drive = None;
    for component in directory.components() {
        match component {
            Component::ParentDir => return Err(JournalError::UnsafeStorage),
            Component::Prefix(prefix) => match prefix.kind() {
                Prefix::Disk(letter) | Prefix::VerbatimDisk(letter) => drive = Some(letter),
                _ => return Err(JournalError::UnsafeStorage),
            },
            _ => {}
        }
    }
    if let Some(letter) = drive {
        let root = format!("{}:\\", char::from(letter));
        if w::GetDriveType(Some(&root)) != co::DRIVE::FIXED {
            return Err(JournalError::UnsafeStorage);
        }
    }
    Ok(())
}

pub(super) fn absolute_directory(directory: &Path) -> Result<PathBuf, JournalError> {
    // Reject lexical escapes before Windows absolute-path normalization can
    // erase them. A mapped network drive is not a local durable journal.
    validate_path(directory)?;
    let directory = std::path::absolute(directory)?;
    validate_path(&directory)?;
    Ok(directory)
}

pub(super) fn pin_directory(directory: &Path) -> Result<Vec<File>, JournalError> {
    validate_path(directory)?;
    if !directory.is_absolute() {
        return Err(JournalError::UnsafeStorage);
    }
    let mut handles = Vec::new();
    // Opening each ancestor without FILE_SHARE_DELETE pins the lexical path.
    // OPEN_REPARSE_POINT makes a junction visible to handle metadata checks.
    for ancestor in directory.ancestors().collect::<Vec<_>>().into_iter().rev() {
        let file = OpenOptions::new()
            .read(true)
            .share_mode(SHARE_READ | SHARE_WRITE)
            .custom_flags(BACKUP_SEMANTICS | OPEN_REPARSE_POINT)
            .open(ancestor)?;
        let metadata = file.metadata()?;
        if !metadata.is_dir() || metadata.file_attributes() & REPARSE_POINT != 0 {
            return Err(JournalError::UnsafeStorage);
        }
        handles.push(file);
    }
    verify_private(handles.last().ok_or(JournalError::UnsafeStorage)?)?;
    Ok(handles)
}

fn native_path(path: &Path) -> Result<PathBuf, JournalError> {
    // The already-pinned parent is canonicalized to support local long paths.
    let parent = fs::canonicalize(path.parent().ok_or(JournalError::UnsafeStorage)?)?;
    Ok(parent.join(path.file_name().ok_or(JournalError::UnsafeStorage)?))
}

pub(super) fn replace(staging: &Path, target: &Path) -> Result<(), JournalError> {
    // The safe wrapper uses MoveFileExW(REPLACE_EXISTING | WRITE_THROUGH).
    // No copy/delete fallback or project-local unsafe code is permitted.
    atomicwrites::replace_atomic(&native_path(staging)?, &native_path(target)?)?;
    Ok(())
}

#[cfg(test)]
pub(super) fn protect_test_directory(path: &Path) -> Result<(), JournalError> {
    let (user, _) = current_sids()?;
    let descriptor: windows_permissions::LocalBox<SecurityDescriptor> =
        format!("D:P(A;OICI;FA;;;{user})(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)").parse()?;
    wrappers::SetNamedSecurityInfo(
        path.as_os_str(),
        SeObjectType::SE_FILE_OBJECT,
        SecurityInformation::Dacl | SecurityInformation::ProtectedDacl,
        None,
        None,
        descriptor.dacl(),
        None,
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use windows_permissions::LocalBox;

    #[test]
    fn descriptor_requires_native_owner_and_explicit_data_access() {
        let (user, owner) = current_sids().unwrap();
        let valid: LocalBox<SecurityDescriptor> =
            format!("O:{user}D:P(A;;FA;;;{user})(A;;FA;;;SY)(A;;FA;;;BA)")
                .parse()
                .unwrap();
        assert!(verify_descriptor(&valid, &user, &owner).is_ok());
        let rights: LocalBox<SecurityDescriptor> =
            format!("O:{user}D:P(A;;FA;;;OW)").parse().unwrap();
        assert!(verify_descriptor(&rights, &user, &owner).is_ok());
        for sddl in [
            format!("D:P(A;;FA;;;{user})"),
            format!("O:{user}"),
            format!("O:{user}D:P(OA;;FA;00112233-4455-6677-8899-aabbccddeeff;;{user})"),
            format!("O:S-1-5-32-546D:P(A;;FA;;;{user})"),
            format!("O:{user}D:NO_ACCESS_CONTROL"),
            format!("O:{user}D:P"),
            format!("O:{user}D:P(A;;FR;;;{user})"),
            format!("O:{user}D:P(A;;RC;;;{user})"),
            format!("O:{user}D:P(A;IO;FA;;;{user})"),
            format!("O:{user}D:P(D;;FA;;;{user})(A;;FA;;;{user})"),
            format!("O:{user}D:P(A;;FA;;;{user})(A;;FR;;;WD)"),
        ] {
            let descriptor: LocalBox<SecurityDescriptor> = sddl.parse().unwrap();
            assert!(
                matches!(
                    verify_descriptor(&descriptor, &user, &owner),
                    Err(JournalError::UnsafeStorage)
                ),
                "accepted unsafe descriptor"
            );
        }
    }

    #[test]
    fn remote_device_and_parent_escape_paths_are_rejected_before_io() {
        for path in [
            r"\\server\share\journal",
            r"\\.\C:\journal",
            r"C:\journal\..\other",
        ] {
            assert!(matches!(
                pin_directory(Path::new(path)),
                Err(JournalError::UnsafeStorage)
            ));
        }
    }
}
