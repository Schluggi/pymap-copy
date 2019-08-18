#!/usr/bin/python3
from argparse import ArgumentParser
from time import time
from imapclient import IMAPClient, exceptions
from utils import decode_mime, beautysized

parser = ArgumentParser(description='', epilog='pymap-copy by Schluggi')
parser.add_argument('-b', '--buffer-size', help='the number of mails loaded with a single query (default: 50)',
                    nargs='?', type=int, default=50)
parser.add_argument('-d', '--dry-run', help='copy/creating nothing, just feign', action="store_true")
parser.add_argument('-i', '--incremental', help='copy/creating only new folders/mails', action="store_true")
parser.add_argument('--denied-flags', help='mails with this flags will be skipped', type=str)
parser.add_argument('--skip-empty-folders', help='skip empty folders', action='store_true')

parser.add_argument('--source-user', help='Source mailbox username', nargs='?', required=True)
parser.add_argument('--source-pass', help='Source mailbox password', nargs='?', required=True)
parser.add_argument('--source-server', help='Hostname/IP of the source IMAP-server', nargs='?', required=True,
                    default=False)
parser.add_argument('--source-no-ssl', help='Use this option if the destination server does not support TLS/SSL',
                    action="store_true")
parser.add_argument('--source-port', help='The IMAP port of the source server (default: 993)', nargs='?',
                    default=993, type=int)

parser.add_argument('--destination-user', help='Destination mailbox username', nargs='?', required=True)
parser.add_argument('--destination-pass', help='Destination mailbox password', nargs='?', required=True)
parser.add_argument('--destination-server', help='Hostname/IP of the destination server', nargs='?', required=True)
parser.add_argument('--destination-no-ssl', help='Use this option if the destination server does not support TLS/SSL',
                    action="store_true", default=False)
parser.add_argument('--destination-port', help='The IMAP port of the destination server (default: 993)', nargs='?',
                    default=993, type=int)
parser.add_argument('--destination-no-subscribe', help='do not', action="store_true", default=False)

args = parser.parse_args()

denied_flags = [b'\\recent']
login_error = False
stats = {
    'start_time': time(),
    'counter_mails': 0,
    'errors': 0,
    'skipped_folders': {
        'already_exists': 0,
        'empty': 0,
        'dry-run': 0
    },
    'skipped_mails': {
        'already_exists': 0,
        'zero_size': 0,
        'dry-run': 0
    },
    'copied_mails': 0,
    'copied_folders': 0
}

if args.denied_flags:
    denied_flags.extend(['\\{}'.format(flag).encode() for flag in args.denied_flags.lower().split(',')])

source = IMAPClient(host=args.source_server, port=args.source_port, ssl=not args.source_no_ssl)
destination = IMAPClient(host=args.destination_server, port=args.destination_port, ssl=not args.destination_no_ssl)

try:
    #: Login source
    print('Login source ({})...'.format(args.source_user), end='', flush=False)
    source.login(args.source_user, args.source_pass)
    print('OK')
except exceptions.LoginError as e:
    login_error = True
    print('ERROR: {}'.format(e))

try:
    #: Login destination
    print('Login destination ({})...'.format(args.destination_user), end='', flush=False)
    destination.login(args.destination_user, args.destination_pass)
    print('OK')
except exceptions.LoginError as e:
    login_error = True
    print('ERROR: {}'.format(e))

if login_error:
    print('\nAbort!')
    exit()

print()

#: get quota from source
print('Getting source quota...', end='', flush=False)
if source.has_capability('QUOTA'):
    source_quota = source.get_quota()
    print('OK')
else:
    print('ERROR (server does not support quota)')

#: get quota from destination
print('Getting destination quota...', end='', flush=False)
if destination.has_capability('QUOTA'):
    destination_quota = destination.get_quota()
    print('OK')
else:
    print('ERROR (server does not support quota)')

print()

#: get source folders
print('Getting source folders...', end='', flush=False)
source_folders = source.list_folders()
print('OK ({} folders found)'.format(len(source_folders)))

#: get destination folders
print('Getting destination folders...', end='', flush=False)
destination_folders = destination.list_folders()
print('OK ({} folders found)'.format(len(destination_folders)))

print('\nStarting mail transfer\n')

try:
    for folder in source_folders:
        f_flags, f_delimiter, f_name = folder

        #: get list of all mails in the current folder
        source.select_folder(f_name, readonly=True)
        source_mail_ids = source.search()
        mail_counter = len(source_mail_ids)
        stats['counter_mails'] += mail_counter

        #: generating mail buffer
        mail_buffer = []
        while source_mail_ids:
            mail_buffer.append(source_mail_ids[:args.buffer_size])
            del source_mail_ids[:args.buffer_size]

        print('Current folder: {} ({} mails)'.format(f_name, mail_counter))

        #: creating non-existing folders
        if f_name not in [name for _, _, name in destination_folders]:
            print('Creating...', end='', flush=False)

            if args.dry_run:
                print('Skipped! (dry-run)')

            elif args.skip_empty_folders and mail_counter is 0:
                stats['skipped_folders']['empty'] += 1
                print('Skipped! (skip-empty-folders mode)\n')
                continue

            else:
                try:
                    destination.create_folder(f_name)
                    if args.destination_no_subscribe is False:
                        destination.subscribe_folder(f_name)
                    stats['copied_folders'] += 1
                    print('OK')
                except exceptions.IMAPClientError as e:
                    if 'ALREADYEXISTS' in str(e):
                        stats['skipped_folders']['already_exists'] += 1
                        print('Skipped! (already exists)\n')
                    else:
                        print('ERROR: {}'.format(e))
                        continue
        else:
            stats['skipped_folders']['already_exists'] += 1

        if args.incremental:
            destination.select_folder(f_name, readonly=True)
            destination_mail_ids = destination.search()
            destination_msg_ids = [data[b'ENVELOPE'].message_id for mail_id, data in destination.fetch(
                destination_mail_ids, ['ENVELOPE']).items()]

        for buffer_counter, buffer in enumerate(mail_buffer):
            print('\r\x1b[2KProgressing... (loading buffer {}/{})'.format(buffer_counter+1, len(mail_buffer)), end='')

            for i, fetch in enumerate(source.fetch(buffer, ['ENVELOPE', 'FLAGS', 'RFC822.SIZE', 'RFC822']).items()):
                mail_id, data = fetch
                if data[b'ENVELOPE'].subject:
                    subject = decode_mime(data[b'ENVELOPE'].subject)
                else:
                    subject = '(no subject)'
                flags = data[b'FLAGS']
                msg = data[b'RFC822']
                msg_id = data[b'ENVELOPE'].message_id
                size = data[b'RFC822.SIZE']

                #: copy mail
                print('\r\x1b[2KProgressing... (buffer {}/{}) (mail {}/{}) ({}): {}'.format(buffer_counter+1,
                                                                                            len(mail_buffer),
                                                                                            i+1, len(buffer),
                                                                                            beautysized(size),
                                                                                            subject), end='')
                if size is 0:
                    stats['skipped_mails']['zero_size'] += 1
                    print('\nSkipped! (zero sized)', end='')

                elif args.incremental and msg_id in destination_msg_ids:
                    stats['skipped_mails']['already_exists'] += 1

                elif args.dry_run:
                    pass

                else:
                    try:
                        status = destination.append(f_name, msg, (flag for flag in flags if flag.lower() not in
                                                                  denied_flags))
                        if b'Append completed' in status:
                            stats['copied_mails'] += 1
                        else:
                            raise exceptions.IMAPClientError(status.decode())
                    except exceptions.IMAPClientError as e:
                        stats['errors'] += 1
                        print('\n\x1b[41m\x1b[1mError:\x1b[0m {}\n'.format(e))

        if mail_buffer:
            print('\n')
        else:
            print()


except KeyboardInterrupt:
    print('\n\nAbort!\n')
else:
    print('Finish!\n')

try:
    print('Logout source...', end='', flush=False)
    source.logout()
    print('OK')
except exceptions.IMAPClientError as e:
    print('ERROR: {}'.format(e))

try:
    print('Logout Destination...', end='', flush=False)
    destination.logout()
    print('OK')
except exceptions.IMAPClientError as e:
    print('ERROR: {}'.format(e))

print('\nCopied \x1b[1m{}/{}\x1b[0m mails and \x1b[1m{}/{}\x1b[0m folders in {:.2f}s\n'.format(
    stats['copied_mails'], stats['counter_mails'], stats['copied_folders'], len(source_folders),
    time()-stats['start_time']))

if args.dry_run:
    print('Everything skipped! (dry-run)')
else:
    print('Errors            : {}'.format(stats['errors']))
    print('Skipped folders   : {}'.format(stats['skipped_folders']['empty'] + stats['skipped_folders']['already_exists']))
    print('├─ Empty          : {} (skip-empty-folders mode only)'.format(stats['skipped_folders']['empty']))
    print('└─ Already exists : {} '.format(stats['skipped_folders']['already_exists']))
    print('Skipped mails     : {}'.format(stats['skipped_mails']['zero_size'] + stats['skipped_mails']['already_exists']))
    print('├─ Zero sized     : {}'.format(stats['skipped_mails']['zero_size']))
    print('└─ Already exists : {} (incremental mode only)'.format(stats['skipped_mails']['already_exists']))


