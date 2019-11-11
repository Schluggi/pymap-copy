#!/usr/bin/python3
from argparse import ArgumentParser
from time import time
from imaplib import IMAP4
from imapclient import IMAPClient, exceptions
from utils import decode_mime, beautysized, imaperror_decode

parser = ArgumentParser(description='', epilog='pymap-copy by Schluggi')
parser.add_argument('-b', '--buffer-size', help='the number of mails loaded with a single query (default: 50)',
                    nargs='?', type=int, default=50)
parser.add_argument('-d', '--dry-run', help='copy/creating nothing, just feign', action="store_true")
parser.add_argument('-t', '--testing', help='do nothing apart from login and listing folders', action="store_true")
parser.add_argument('-i', '--incremental', help='copy/creating only new folders/mails', action="store_true")
parser.add_argument('--denied-flags', help='mails with this flags will be skipped', type=str)
parser.add_argument('--ignore-quota', help='ignores insufficient quota', action='store_true')
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
parser.add_argument('--destination-no-subscribe', help='All copied folders will be not are not subscribed',
                    action="store_true", default=False)

args = parser.parse_args()

denied_flags = [b'\\recent']
login_error = False
stats = {
    'start_time': time(),
    'counter_mails': 0,
    'errors': [],
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

print('Connecting source ({})...'.format(args.source_server))
source = IMAPClient(host=args.source_server, port=args.source_port, ssl=not args.source_no_ssl)

print('Connecting destination ({})...'.format(args.destination_server))
destination = IMAPClient(host=args.destination_server, port=args.destination_port, ssl=not args.destination_no_ssl)

print()

try:
    #: Login source
    print('Login source ({})...'.format(args.source_user), end='', flush=True)
    source.login(args.source_user, args.source_pass)
    print('OK')
except (exceptions.LoginError, IMAP4.error) as e:
    login_error = True
    print('ERROR: {}'.format(imaperror_decode(e)))

try:
    #: Login destination
    print('Login destination ({})...'.format(args.destination_user), end='', flush=True)
    destination.login(args.destination_user, args.destination_pass)
    print('OK')
except (exceptions.LoginError, IMAP4.error) as e:
    login_error = True
    print('ERROR: {}'.format(imaperror_decode(e)))

if login_error:
    print('\nAbort!')
    exit()

print()

#: get quota from source
print('Getting source quota...', end='', flush=True)
if source.has_capability('QUOTA'):
    source_quota = source.get_quota()[0]
    print('OK ({}/{})'.format(beautysized(source_quota.usage*1000), beautysized(source_quota.limit*1000)))
else:
    source_quota = None
    print('server does not support quota (ignoring)')

#: get quota from destination
print('Getting destination quota...', end='', flush=True)
if destination.has_capability('QUOTA'):
    destination_quota = destination.get_quota()[0]
    print('OK ({}/{})'.format(beautysized(destination_quota.usage*1000), beautysized(destination_quota.limit*1000)))
else:
    destination_quota = None
    print('server does not support quota (ignoring)')

print('\nChecking quota...', end='', flush=True)

#: checking quota
if source_quota and destination_quota:
    destination_quota_free = destination_quota.limit - destination_quota.usage
    if destination_quota_free < source_quota.usage:
        print('ERROR: Insufficient quota: The source usage is {} KB but there only {} KB free on the destination server'
              .format(source_quota.usage, destination_quota_free), end='', flush=True)
        if args.ignore_quota:
            print(' (ignoring)')
        else:
            print('\n\nAbort!')
            exit()
    else:
        print('OK')
else:
    print('could not check quota (ignoring)')

print()

#: get source folders
print('Getting source folders...', end='', flush=True)
source_folders = source.list_folders()
source_delimiter = source_folders[0][1].decode()
source_folder_list = [name for _, _, name in source_folders]
print('OK ({} folders found)'.format(len(source_folders)))

#: get destination folders
print('Getting destination folders...', end='', flush=True)
destination_folders = destination.list_folders()
destination_delimiter = destination_folders[0][1].decode()
destination_folder_list = [name for _, _, name in destination_folders]
print('OK ({} folders found)'.format(len(destination_folders)))

if args.testing:
    print('\n\x1b[1mSource:\x1b[0m')
    source_sum, destination_sum = 0, 0

    for folder in source_folder_list:
        source.select_folder(folder, readonly=True)
        mail_counter = len(source.search())
        source_sum += mail_counter
        print('{}: {} mails'.format(folder, mail_counter))
    print('-----\n{} mails'.format(source_sum))
    print('\n\x1b[1mDestination:\x1b[0m')

    for folder in destination_folder_list:
        destination.select_folder(folder, readonly=True)
        mail_counter = len(destination.search())
        destination_sum += mail_counter
        print('{}: {} mails'.format(folder, mail_counter))
    print('-----\n{} mails'.format(destination_sum))
    exit()

print('\nStarting mail transfer\n')

try:
    for folder in source_folders:
        _, _, sf_name = folder
        df_name = sf_name.replace(source_delimiter, destination_delimiter)

        #: get list of all mails in the current folder
        source.select_folder(sf_name, readonly=True)
        source_mail_ids = source.search()
        mail_counter = len(source_mail_ids)
        stats['counter_mails'] += mail_counter

        #: generating mail buffer
        mail_buffer = []
        while source_mail_ids:
            mail_buffer.append(source_mail_ids[:args.buffer_size])
            del source_mail_ids[:args.buffer_size]

        print('Current folder: {} -> {} ({} mails)'.format(sf_name, df_name, mail_counter))

        #: creating non-existing folders
        if df_name not in destination_folder_list:
            print('Creating...', end='', flush=True)

            if args.dry_run:
                print('Skipped! (dry-run)')

            elif args.skip_empty_folders and mail_counter is 0:
                stats['skipped_folders']['empty'] += 1
                print('Skipped! (skip-empty-folders mode)\n')
                continue

            else:
                try:
                    destination.create_folder(df_name)
                    if args.destination_no_subscribe is False:
                        destination.subscribe_folder(df_name)
                    stats['copied_folders'] += 1
                    print('OK')
                except exceptions.IMAPClientError as e:
                    if 'ALREADYEXISTS' in str(e):
                        stats['skipped_folders']['already_exists'] += 1
                        print('Skipped! (already exists)\n')
                    else:
                        print('ERROR: {}'.format(imaperror_decode(e)))
                        continue
        else:
            stats['skipped_folders']['already_exists'] += 1

        if args.incremental:
            destination.select_folder(df_name, readonly=True)
            destination_mail_ids = destination.search()
            destination_msg_ids = [data[b'ENVELOPE'].message_id for mail_id, data in destination.fetch(
                destination_mail_ids, ['ENVELOPE']).items()]

        for buffer_counter, buffer in enumerate(mail_buffer):
            print('\r\x1b[2KProgressing... (loading buffer {}/{})'.format(buffer_counter+1, len(mail_buffer)), end='')

            for i, fetch in enumerate(source.fetch(buffer, ['ENVELOPE', 'FLAGS', 'RFC822.SIZE', 'RFC822',
                                                            'INTERNALDATE']).items()):
                mail_id, data = fetch
                if data[b'ENVELOPE'].subject:
                    subject = decode_mime(data[b'ENVELOPE'].subject)
                else:
                    subject = '(no subject)'
                flags = data[b'FLAGS']
                msg = data[b'RFC822']
                msg_id = data[b'ENVELOPE'].message_id
                size = data[b'RFC822.SIZE']
                date = data[b'INTERNALDATE']

                #: copy mail
                print('\r\x1b[2KProgressing... (buffer {}/{}) (mail {}/{}) ({}) ({}): {}'.format(buffer_counter+1,
                                                                                                 len(mail_buffer),
                                                                                                 i+1, len(buffer),
                                                                                                 beautysized(size),
                                                                                                 date, subject), end='')
                if size is 0:
                    stats['skipped_mails']['zero_size'] += 1
                    print('\nSkipped! (zero sized)', end='')

                elif args.incremental and msg_id in destination_msg_ids:
                    stats['skipped_mails']['already_exists'] += 1

                elif args.dry_run:
                    pass

                else:
                    try:
                        status = destination.append(df_name, msg, (flag for flag in flags if flag.lower() not in
                                                                   denied_flags), msg_time=date)
                        if b'append completed' in status.lower():
                            stats['copied_mails'] += 1
                        else:
                            raise exceptions.IMAPClientError(status.decode())
                    except exceptions.IMAPClientError as e:
                        e = imaperror_decode(e)
                        stats['errors'].append({'size': beautysized(size),
                                                'subject': subject,
                                                'exception': e,
                                                'folder': df_name,
                                                'date': date})
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
    print('Logout source...', end='', flush=True)
    source.logout()
    print('OK')
except exceptions.IMAPClientError as e:
    print('ERROR: {}'.format(imaperror_decode(e)))

try:
    print('Logout Destination...', end='', flush=True)
    destination.logout()
    print('OK')
except exceptions.IMAPClientError as e:
    print('ERROR: {}'.format(imaperror_decode(e)))

print('\nCopied \x1b[1m{}/{}\x1b[0m mails and \x1b[1m{}/{}\x1b[0m folders in {:.2f}s\n'.format(
    stats['copied_mails'], stats['counter_mails'], stats['copied_folders'], len(source_folders),
    time()-stats['start_time']))

if args.dry_run:
    print('Everything skipped! (dry-run)')
else:
    print('Errors            : {} (see below)'.format(len(stats['errors'])))
    print('Skipped folders   : {}'.format(stats['skipped_folders']['empty'] + stats['skipped_folders']['already_exists']))
    print('├─ Empty          : {} (skip-empty-folders mode only)'.format(stats['skipped_folders']['empty']))
    print('└─ Already exists : {} '.format(stats['skipped_folders']['already_exists']))
    print('Skipped mails     : {}'.format(stats['skipped_mails']['zero_size'] + stats['skipped_mails']['already_exists']))
    print('├─ Zero sized     : {}'.format(stats['skipped_mails']['zero_size']))
    print('└─ Already exists : {} (incremental mode only)'.format(stats['skipped_mails']['already_exists']))
    print('\nErrors:')

    if stats['errors']:
        for err in stats['errors']:
            print('({}) ({}) ({}) ({}): {}'.format(err['size'], err['date'], err['folder'], err['subject'],
                                                   err['exception']))
    else:
        print('(no errors)')

