"""Explicit local Fleet naming operations using existing SAFE approval IDs."""
from __future__ import annotations

import argparse
from base64 import b64decode
import json
from pathlib import Path
import sqlite3

from sofia.platform.ops.callsigns import CallsignAuthority, CallsignRevisionConflict, CallsignUnavailable, _OPERATIONS
from sofia.platform.state.installation_identity import InstallationIdentityStore


def _document(value):
    if len(value.encode('utf-8')) > 16_384:
        raise ValueError('review document exceeds its bound')
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result: raise ValueError('duplicate review document field')
            result[key] = item
        return result
    result = json.loads(value, object_pairs_hook=unique)
    if type(result) is not dict:
        raise ValueError('review document must be an object')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--installation-home', type=Path, required=True,
        help='Existing designated authority host installation identity; never auto-created.')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('review-initialize', 'initialize'):
        command = commands.add_parser(name)
        command.add_argument('--authority-id', required=True)
        if name == 'initialize': command.add_argument('--approval-id', required=True)
    show = commands.add_parser('show')
    show.add_argument('--platform-id', required=True)
    for name in ('review', 'apply'):
        command = commands.add_parser(name)
        command.add_argument('--operation', choices=sorted(_OPERATIONS), required=True)
        command.add_argument('--platform-id', required=True)
        command.add_argument('--expected-revision', type=int, required=True)
        command.add_argument('--request-id', required=True)
        command.add_argument('--payload-json', required=True)
        if name == 'apply': command.add_argument('--approval-id', required=True)
    core = commands.add_parser('core-rename')
    core.add_argument('--request-json', required=True)
    core.add_argument('--signature', required=True, help='Base64 one-use Core request signature, not a private key.')
    args = parser.parse_args(argv)
    try:
        installation = InstallationIdentityStore(args.installation_home)
        if args.command == 'review-initialize':
            output = {'capability':'fleet.callsign.authority.initialize', 'parameters':
                CallsignAuthority.initialize_parameters(args.database, installation, args.authority_id)}
        elif args.command == 'initialize':
            authority = CallsignAuthority.initialize(args.database, installation,
                authority_id=args.authority_id, approval_id=args.approval_id)
            output = {'schema':'aegis.fleet.callsigns.v1', 'authority_id':authority.authority_id, 'result':'COMMITTED'}
        else:
            authority = CallsignAuthority(args.database, installation)
            if args.command == 'show':
                output = authority.snapshot(args.platform_id)
            elif args.command == 'core-rename':
                output = authority.core_rename(_document(args.request_json), b64decode(args.signature, validate=True))
            else:
                fields = {'expected_revision':args.expected_revision, 'request_id':args.request_id,
                          'payload':_document(args.payload_json)}
                if args.command == 'review':
                    capability, parameters = authority.approval_parameters(args.operation, args.platform_id, **fields)
                    output = {'capability':capability, 'parameters':parameters}
                else:
                    output = authority.owner_operation(args.operation, args.platform_id,
                        approval_id=args.approval_id, **fields)
        print(json.dumps(output, sort_keys=True))
        return 3 if output.get('result') == 'CONFLICT' else 0
    except PermissionError as exc:
        print(json.dumps({'result':'DENIED','reason':str(exc)}))
        return 2
    except (ValueError, TypeError) as exc:
        print(json.dumps({'result':'INVALID','reason':str(exc)}))
        return 2
    except CallsignRevisionConflict as exc:
        print(json.dumps({'result':'STALE','reason':str(exc)}))
        return 3
    except (CallsignUnavailable, OSError, sqlite3.Error) as exc:
        print(json.dumps({'result':'UNCONFIRMED','reason':str(exc)}))
        return 4


if __name__ == '__main__':
    raise SystemExit(main())
