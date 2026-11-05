//! R6 supervision and R7 release decision reference contracts.
//! These types do NOT start processes, authorize writers, or approve release.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProcessPhase {
    Stopped,
    Starting,
    Ready,
    Draining,
    Uncertain,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LifecycleError {
    InvalidGeneration,
    StaleObserver,
    InvalidTransition,
    NoIndependentProof,
}

fn valid_host_id(host: &str) -> bool {
    if host.is_empty() || host.len() > 160 {
        return false;
    }
    let mut bytes = host.bytes();
    let Some(first) = bytes.next() else {
        return false;
    };
    first.is_ascii_alphanumeric()
        && bytes.all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-' | b':' | b'@' | b'/')
        })
}

/// Process observations are fenced by host and launch generation. An
/// observation is not permission to start a Core or mint a writer lease.
#[derive(Debug, Clone)]
pub struct Supervision {
    pub host_id: String,
    pub generation: u64,
    pub phase: ProcessPhase,
    last_observation_sequence: u64,
}

impl Supervision {
    /// # Errors
    /// Reject a missing host identity or zero generation.
    pub fn new(host_id: String, generation: u64) -> Result<Self, LifecycleError> {
        if !valid_host_id(&host_id) || generation == 0 {
            return Err(LifecycleError::InvalidGeneration);
        }
        Ok(Self {
            host_id,
            generation,
            phase: ProcessPhase::Stopped,
            last_observation_sequence: 0,
        })
    }

    /// A prepared process is not an observed ready process.
    ///
    /// # Errors
    /// Denies transitions from uncertain, draining, or running states.
    pub fn note_start_prepared(&mut self) -> Result<(), LifecycleError> {
        if self.phase != ProcessPhase::Stopped {
            return Err(LifecycleError::InvalidTransition);
        }
        self.phase = ProcessPhase::Starting;
        Ok(())
    }

    fn observe(
        &mut self,
        host_id: &str,
        generation: u64,
        sequence: u64,
        independently_observed: bool,
    ) -> Result<(), LifecycleError> {
        if !independently_observed {
            return Err(LifecycleError::NoIndependentProof);
        }
        if host_id != self.host_id
            || generation != self.generation
            || sequence <= self.last_observation_sequence
        {
            return Err(LifecycleError::StaleObserver);
        }
        self.last_observation_sequence = sequence;
        Ok(())
    }

    /// # Errors
    /// Requires a matching independent readiness observation.
    pub fn note_ready(
        &mut self,
        host_id: &str,
        generation: u64,
        sequence: u64,
        independently_observed: bool,
    ) -> Result<(), LifecycleError> {
        if self.phase != ProcessPhase::Starting {
            return Err(LifecycleError::InvalidTransition);
        }
        self.observe(host_id, generation, sequence, independently_observed)?;
        self.phase = ProcessPhase::Ready;
        Ok(())
    }

    /// # Errors
    /// A stop request is not itself proof that a process stopped.
    pub fn note_drain_requested(&mut self) -> Result<(), LifecycleError> {
        if self.phase != ProcessPhase::Ready {
            return Err(LifecycleError::InvalidTransition);
        }
        self.phase = ProcessPhase::Draining;
        Ok(())
    }

    /// # Errors
    /// Only an independently observed stopped process may clear the state.
    pub fn note_stopped(
        &mut self,
        host_id: &str,
        generation: u64,
        sequence: u64,
        independently_observed: bool,
    ) -> Result<(), LifecycleError> {
        if !matches!(self.phase, ProcessPhase::Draining | ProcessPhase::Uncertain) {
            return Err(LifecycleError::InvalidTransition);
        }
        self.observe(host_id, generation, sequence, independently_observed)?;
        self.phase = ProcessPhase::Stopped;
        Ok(())
    }

    /// Crash or lost heartbeat after launch requires reconciliation, not a
    /// second automatic Core process or writer.
    pub fn note_uncertain(&mut self) {
        if self.phase != ProcessPhase::Stopped {
            self.phase = ProcessPhase::Uncertain;
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ReleaseBlocker {
    InvalidSourceRevision,
    SeparateInstalledArtifactsUnverified,
    CanonicalWriterOrFenceUnverified,
    SecurityAndRevocationUnverified,
    WindowsReleaseCandidateUnverified,
    DebianReleaseCandidateUnverified,
    RollbackUnverified,
    OwnerApprovalMissing,
    RealHostShakedownUnverified,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EvidenceState {
    Verified,
    Missing,
}

/// Receipts must be populated by independent release and host verifiers.
/// None of these boolean fields is a signed grant or authorization to act.
#[derive(Debug, Clone)]
pub struct HybridReleaseEvidence {
    pub source_sha: String,
    pub separate_installed_artifacts_verified: EvidenceState,
    pub single_writer_and_fencing_verified: EvidenceState,
    pub security_revocation_verified: EvidenceState,
    pub windows_release_candidate_verified: EvidenceState,
    pub debian_release_candidate_verified: EvidenceState,
    pub rollback_verified: EvidenceState,
    pub owner_approved: EvidenceState,
    pub real_host_shakedown_verified: EvidenceState,
}

impl HybridReleaseEvidence {
    /// This is a read-only assessment. It never authorizes cutover or
    /// executes a state migration, regardless of its result.
    #[must_use]
    pub fn assess(&self) -> Vec<ReleaseBlocker> {
        let mut blockers = Vec::new();
        if self.source_sha.len() != 40
            || !self
                .source_sha
                .bytes()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
        {
            blockers.push(ReleaseBlocker::InvalidSourceRevision);
        }
        if self.separate_installed_artifacts_verified != EvidenceState::Verified {
            blockers.push(ReleaseBlocker::SeparateInstalledArtifactsUnverified);
        }
        if self.single_writer_and_fencing_verified != EvidenceState::Verified {
            blockers.push(ReleaseBlocker::CanonicalWriterOrFenceUnverified);
        }
        if self.security_revocation_verified != EvidenceState::Verified {
            blockers.push(ReleaseBlocker::SecurityAndRevocationUnverified);
        }
        if self.windows_release_candidate_verified != EvidenceState::Verified {
            blockers.push(ReleaseBlocker::WindowsReleaseCandidateUnverified);
        }
        if self.debian_release_candidate_verified != EvidenceState::Verified {
            blockers.push(ReleaseBlocker::DebianReleaseCandidateUnverified);
        }
        if self.rollback_verified != EvidenceState::Verified {
            blockers.push(ReleaseBlocker::RollbackUnverified);
        }
        if self.owner_approved != EvidenceState::Verified {
            blockers.push(ReleaseBlocker::OwnerApprovalMissing);
        }
        if self.real_host_shakedown_verified != EvidenceState::Verified {
            blockers.push(ReleaseBlocker::RealHostShakedownUnverified);
        }
        blockers
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn invalid_or_unbounded_host_identity_never_enters_fenced_supervision() {
        for invalid in [
            "",
            " ",
            " host:artemis",
            "host:artemis ",
            "host:artemis\nother",
            "host:artemis\t",
            "host:artemis?",
        ] {
            assert_eq!(
                Supervision::new(invalid.into(), 7).unwrap_err(),
                LifecycleError::InvalidGeneration
            );
        }
        assert_eq!(
            Supervision::new("a".repeat(161), 7).unwrap_err(),
            LifecycleError::InvalidGeneration
        );
        assert!(Supervision::new("host:artemis-vm".into(), 7).is_ok());
        assert!(Supervision::new("VENUS_PC".into(), 7).is_ok());
    }

    #[test]
    fn never_claim_ready_from_stale_or_unverified_process_observation() {
        let mut state = Supervision::new("venus".into(), 7).unwrap();
        state.note_start_prepared().unwrap();
        assert_eq!(
            state.note_ready("venus", 7, 1, false),
            Err(LifecycleError::NoIndependentProof)
        );
        assert_eq!(
            state.note_ready("venus", 6, 1, true),
            Err(LifecycleError::StaleObserver)
        );
        assert_eq!(state.phase, ProcessPhase::Starting);
        state.note_ready("venus", 7, 1, true).unwrap();
        assert_eq!(state.phase, ProcessPhase::Ready);
        assert_eq!(
            state.note_ready("venus", 7, 2, true),
            Err(LifecycleError::InvalidTransition)
        );
    }

    #[test]
    fn uncertain_core_cannot_relaunch_without_stopped_witness() {
        let mut state = Supervision::new("artemis".into(), 12).unwrap();
        state.note_start_prepared().unwrap();
        state.note_uncertain();
        assert_eq!(
            state.note_start_prepared(),
            Err(LifecycleError::InvalidTransition)
        );
        assert_eq!(
            state.note_stopped("artemis", 12, 3, false),
            Err(LifecycleError::NoIndependentProof)
        );
        state.note_stopped("artemis", 12, 3, true).unwrap();
        state.note_start_prepared().unwrap();
    }

    #[test]
    fn draining_is_not_proof_of_stop() {
        let mut state = Supervision::new("venus".into(), 2).unwrap();
        state.note_start_prepared().unwrap();
        state.note_ready("venus", 2, 1, true).unwrap();
        state.note_drain_requested().unwrap();
        assert_eq!(state.phase, ProcessPhase::Draining);
        assert_eq!(
            state.note_stopped("wrong-host", 2, 2, true),
            Err(LifecycleError::StaleObserver)
        );
        assert_eq!(state.phase, ProcessPhase::Draining);
        state.note_stopped("venus", 2, 2, true).unwrap();
        assert_eq!(state.phase, ProcessPhase::Stopped);
    }

    #[test]
    fn incomplete_hybrid_release_is_never_accepted() {
        let evidence = HybridReleaseEvidence {
            source_sha: "a".repeat(40),
            separate_installed_artifacts_verified: EvidenceState::Verified,
            single_writer_and_fencing_verified: EvidenceState::Missing,
            security_revocation_verified: EvidenceState::Missing,
            windows_release_candidate_verified: EvidenceState::Verified,
            debian_release_candidate_verified: EvidenceState::Missing,
            rollback_verified: EvidenceState::Missing,
            owner_approved: EvidenceState::Missing,
            real_host_shakedown_verified: EvidenceState::Missing,
        };
        let blockers = evidence.assess();
        assert!(blockers.contains(&ReleaseBlocker::CanonicalWriterOrFenceUnverified));
        assert!(blockers.contains(&ReleaseBlocker::SecurityAndRevocationUnverified));
        assert!(blockers.contains(&ReleaseBlocker::DebianReleaseCandidateUnverified));
        assert!(blockers.contains(&ReleaseBlocker::RollbackUnverified));
        assert!(blockers.contains(&ReleaseBlocker::OwnerApprovalMissing));
        assert!(blockers.contains(&ReleaseBlocker::RealHostShakedownUnverified));
    }

    #[test]
    fn release_assessment_rejects_unknown_revision_even_with_all_flags() {
        let evidence = HybridReleaseEvidence {
            source_sha: "unverified".into(),
            separate_installed_artifacts_verified: EvidenceState::Verified,
            single_writer_and_fencing_verified: EvidenceState::Verified,
            security_revocation_verified: EvidenceState::Verified,
            windows_release_candidate_verified: EvidenceState::Verified,
            debian_release_candidate_verified: EvidenceState::Verified,
            rollback_verified: EvidenceState::Verified,
            owner_approved: EvidenceState::Verified,
            real_host_shakedown_verified: EvidenceState::Verified,
        };
        assert_eq!(
            evidence.assess(),
            vec![ReleaseBlocker::InvalidSourceRevision]
        );
    }
}
