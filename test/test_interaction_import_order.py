"""Regression for interaction/chat <-> application bootstrap circular imports.

Fresh Python processes are required: pytest's shared sys.modules can conceal
an import cycle once another test has initialized the application package.
No runtime, LLM, database, network or configured state is opened.
"""
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('first', [
    'from sofia.interaction.chat import InteractiveConversationService',
    'from sofia.application.bootstrap import SofiaApplication',
    'from sofia.application import ConversationLoop, SofiaApplication',
])
def test_application_and_interaction_can_import_in_either_order(first):
    program = '\n'.join((
        first,
        'from sofia.interaction.chat import InteractiveConversationService',
        'from sofia.application.bootstrap import SofiaApplication, SofiaApplicationError',
        'from sofia.application.conversation import ConversationLoop',
        'from sofia.application.conversation_service import ConversationService',
        'from sofia.application import (',
        '    SofiaApplication as ExportedApplication,',
        '    SofiaApplicationError as ExportedError,',
        '    ConversationLoop as ExportedLoop,',
        '    ConversationService as ExportedService,',
        ')',
        'assert ExportedApplication is SofiaApplication',
        'assert ExportedError is SofiaApplicationError',
        'assert ExportedLoop is ConversationLoop',
        'assert ExportedService is ConversationService',
        'assert issubclass(InteractiveConversationService, ConversationService)',
    ))
    result = subprocess.run(
        [sys.executable, '-c', program], cwd=ROOT,
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
