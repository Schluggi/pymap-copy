#!/usr/bin/python3
"""
    Copy and transfer IMAP mailboxes
"""
__version__ = '1.0.1'
__author__ = 'Lukas Schulte-Tickmann'
__url__ = 'https://github.com/Schluggi/pymap-copy'

from argparse import ArgumentParser, ArgumentTypeError
from time import time

from imapclient import IMAPClient, exceptions

from imapidle import IMAPIdle
from utils import decode_mime, beautysized, imaperror_decode


def check_encryption(value):
    """
        check for the --???-encryption argument
        raise an exception if the given encryption is invalid
    """
    value = value.lower()
    if value not in ['ssl', 'tls', 'starttls', 'none']:
        raise ArgumentTypeError(f'{value} is an unknown encryption. Use can use ssl, tls, starttls or none instead.')
    return value


def default_port(encryption):
    """
        returns a port based on the encryption
    """
    if encryption in ['starttls', 'none']:
        return 143
    return 993


def colorize(s, color=None, bold=False, clear=False):
    """
        turn the string into a colored and/or bold one
    """
    colors = {'red': '\x1b[31m',
              'green': '\x1b[32m',
              'cyan': '\x1b[36m',
              'yellow': '\x1b[33m'}
    if args.no_colors:
        return s

    if clear:
        s = f'\r\x1b[2K{s}'
    if bold:
        s = f'\x1b[1m{s}'
    if color:
        s = f'{colors[color]}{s}'
    return f'{s}\x1b[0m'


def connect(server, port, encryption):
    """
        connect to the server with the right ssl_context in case of encryption
        returns a client handle if connected and None if not
    """
    use_ssl = False
    ssl_context = None  # IMAPClient will use a context by default if ssl_context is None

    if encryption in ['tls', 'ssl']:
        use_ssl = True

    if args.ssl_no_verify:
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    try:
        client = IMAPClient(host=server, port=port, ssl=use_ssl, ssl_context=ssl_context)
        if encryption == 'starttls':
            client.starttls(ssl_context=ssl_context)
            client_status = f'{colorize("OK", color="green")} ({colorize("STARTTLS", color="green")})'

        elif encryption in ['ssl', 'tls']:
            client_status = f'{colorize("OK", color="green")} ({colorize("SSL/TLS", color="green")})'

        else:
            client_status = f'{colorize("OK", color="green")} ({colorize("NOT ENCRYPTED", color="yellow")})'

        return client, client_status

    except Exception as e:
        client_status = f'{colorize("Error:", color="red", bold=True)} {imaperror_decode(e)}'
        return None, client_status


def login(client, user, password):
    """
        login the client with the given username and password
    """
    if client:
        try:
            client.login(user, password)
            return True, colorize('OK', color='green')
        except Exception as e:
            return False, f'{colorize("Error:", color="red", bold=True)} {imaperror_decode(e)}'
    else:
        return False, f'{colorize("Error:", color="red", bold=True)} No active connection'


def get_quota(client):
    """
        returns the quota of the mailbox
    """
    if client.has_capability('QUOTA') and args.ignore_quota is False:
        quota = client.get_quota()[0]
        quota_usage = beautysized(quota.usage * 1000)
        quota_limit = beautysized(quota.limit * 1000)
        quota_filled = f'{quota.usage / quota.limit * 100:.0f}'
        return quota, quota_usage, quota_limit, quota_filled
    logging.info(f'Server does not support quota')
    return None, None, None, None


parser = ArgumentParser(description='Copy and transfer IMAP mailboxes',
                        epilog=f'pymap-copy by {__author__} ({__url__})')
parser.add_argument('-v', '--version', help='show version and exit.', action="version",
                    version=f'pymap-copy {__version__} by {__author__} ({__url__})')

#: run mode arguments
parser.add_argument('-d', '--dry-run', help='copy & creating nothing, just feign', action="store_true")
parser.add_argument('-l', '--list', help='copy & creating nothing, just list folders', action="store_true")
parser.add_argument('-i', '--incremental', help='copy & creating only new folders/mails', action="store_true")

#: special and optimization arguments
parser.add_argument('--abort-on-error', help='the process will interrupt at the first mail transfer error',
                    action="store_true")
parser.add_argument('-b', '--buffer-size', help='the number of mails loaded with a single query (default: 50)',
                    nargs='?', type=int, default=50)
parser.add_argument('--denied-flags', help='mails with this flags will be skipped', type=str)
parser.add_argument('-r', '--redirect', help='redirect a folder (source:destination --denied-flags seen,recent -d)',
                    action='append')
parser.add_argument('--idle-interval', help='defines the interval (in seconds) after that the idle process is '
                                            'restarted (default: 1680)', type=int, default=1680)
parser.add_argument('--ignore-quota', help='ignores insufficient quota', action='store_true')
parser.add_argument('--ignore-folder-flags', help='do not link default IMAP folders automatically (like Drafts, '
                                                  'Trash, etc.)', action='store_true')
parser.add_argument('--max-line-length', help='use this option when the program crashes by some mails', type=int)
parser.add_argument('--max-mail-size', help='skip all mails larger than the given size in byte', type=int)
parser.add_argument('--no-colors', help='disable ANSI Escape Code (for terminals like powershell or cmd)',
                    action="store_true")
parser.add_argument('--skip-empty-folders', help='skip empty folders', action='store_true')
parser.add_argument('--ssl-no-verify', help='do not verify any ssl certificate', action='store_true')

#: source arguments
parser.add_argument('-u', '--source-user', help='source mailbox username', nargs='?', required=True)
parser.add_argument('-p', '--source-pass', help='source mailbox password', nargs='?', required=True)
parser.add_argument('-s', '--source-server', help='hostname or  of the source IMAP-server', nargs='?', required=True,
                    default=False)
parser.add_argument('-e', '--source-encryption', help='select the source encryption (ssl/tls/starttls/none) '
                                                      '(default: ssl)', default='ssl', type=check_encryption)
parser.add_argument('--source-port', help='the IMAP port of the source server (default: 993)', nargs='?', type=int)
parser.add_argument('-f', '--source-folder', help='', action='append', nargs='?', default=[], type=str)

#: destination arguments
parser.add_argument('-U', '--destination-user', help='destination mailbox username', nargs='?', required=True)
parser.add_argument('-P', '--destination-pass', help='destination mailbox password', nargs='?', required=True)
parser.add_argument('-S', '--destination-server', help='hostname or IP of the destination server', nargs='?',
                    required=True)
parser.add_argument('-E', '--destination-encryption', help='select the destination encryption (ssl/tls/starttls/none) '
                                                           '(default: ssl)', default='ssl', type=check_encryption)
parser.add_argument('--destination-port', help='the IMAP port of the destination server', nargs='?', type=int)
parser.add_argument('--destination-root', help='defines the destination root (case sensitive)', nargs='?', default='',
                    type=str)
parser.add_argument('--destination-root-merge', help='ignores the destination root if the folder is already part of it',
                    action='store_true')
parser.add_argument('--destination-no-subscribe', help='all copied folders will be not are not subscribed',
                    action="store_true", default=False)

args = parser.parse_args()

if args.source_port:
    source_port = args.source_port
else:
    source_port = default_port(args.source_encryption)

if args.destination_port:
    destination_port = args.destination_port
else:
    destination_port = default_port(args.destination_encryption)



#: pre-defined variables
SPECIAL_FOLDER_FLAGS = [b'\\Archive', b'\\Junk', b'\\Drafts', b'\\Trash', b'\\Sent']
denied_flags = [b'\\recent']
progress = 0
destination_separator, source_separator = None, None
db = {
    'source': {
        'folders': {}
    },
    'destination': {
        'folders': {}
    }
}
stats = {
    'start_time': time(),
    'source_mails': 0,
    'destination_mails': 0,
    'processed': 0,
    'errors': [],
    'skipped_folders': {
        'already_exists': 0,
        'empty': 0,
        'dry-run': 0,
        'no_parent': 0
    },
    'skipped_mails': {
        'already_exists': 0,
        'zero_size': 0,
        'max_size': 0,
        'max_line_length': 0,
        'no_envelope': 0
    },
    'copied_mails': 0,
    'copied_folders': 0
}

if args.denied_flags:
    denied_flags.extend([f'\\{flag}'.encode() for flag in args.denied_flags.lower().split(',')])

print()

#: connecting source
print(f'Connecting source           : {args.source_server}:{source_port}, ', end='', flush=True)
source, status = connect(args.source_server, source_port, args.source_encryption)
print(status)

#: connecting destination
print(f'Connecting destination      : {args.destination_server}:{destination_port}, ', end='', flush=True)
destination, status = connect(args.destination_server, destination_port, args.destination_encryption)
print(status)

print()


#: login source
print(f'Login source                : {args.source_user}, ', end='', flush=True)
source_login_ok, status = login(source, args.source_user, args.source_pass)
print(status)

#: login destination
print(f'Login destination           : {args.destination_user}, ', end='', flush=True)
destination_login_ok, status = login(destination, args.destination_user, args.destination_pass)
print(status)

if all((source_login_ok, destination_login_ok)) is False:
    print('\nAbort! Please fix the errors above.')
    exit()

print()

#: starting idle threads
print('Starting idle threads       : ', end='', flush=True)
source_idle = IMAPIdle(source, interval=args.idle_interval)
destination_idle = IMAPIdle(destination, interval=args.idle_interval)
source_idle.start()
destination_idle.start()
print(f'{colorize("OK", color="green")} (restarts every {args.idle_interval} seconds)')

print()

#: get quota from source
print('Getting source quota        : ', end='', flush=True)
logging.info(f'Getting source quota...')
source_quota, source_quota_usage, source_quota_limit, source_quota_filled = get_quota(source)
if source_quota:
    print(f'{source_quota_usage}/{source_quota_limit} ({source_quota_filled}%)')
else:
    print('server does not support quota')

#: get quota from destination
print('Getting destination quota   : ', end='', flush=True)
logging.info(f'Getting destination quota...')
destination_quota, destination_quota_usage, destination_quota_limit, destination_quota_filled = get_quota(destination)
if destination_quota:
    print(f'{source_quota_usage}/{source_quota_limit} ({source_quota_filled}%)')
else:
    destination_quota = None
    print('server does not support quota')

#: checking quota
print('Checking quota              : ', end='', flush=True)
if source_quota and destination_quota:
    destination_quota_free = destination_quota.limit - destination_quota.usage
    if destination_quota_free < source_quota.usage:
        print(f'{colorize("Error:", bold=True, color="cyan")} Insufficient quota: The source usage is '
              f'{source_quota.usage} KB but there only {destination_quota_free} KB free on the destination server',
              end='', flush=True)
        if args.ignore_quota:
            print(' (ignoring)')
        else:
            print('\n\nAbort!')
            exit()
    else:
        print(colorize('OK', color='green'))
else:
    print('could not check quota')

print()

destination_idle.start_idle()
wildcards = tuple([f[:-1] for f in args.source_folder if f.endswith('*')])

#: get source folders
print(colorize('Getting source folders      : loading (this can take a while)', clear=True), flush=True, end='')
logging.info('Getting source folders (this can take a while)')
for flags, separator, name in source.list_folders():
    if not source_separator:
        source_separator = separator.decode()

    if args.source_folder:
        if name not in args.source_folder and name.startswith(wildcards) is False:
            print(colorize(f'Getting source folders      : Progressing ({stats["source_mails"]} mails) (skipping): '
                           f'{name}', clear=True), flush=True, end='')
            continue

    try:
        source.select_folder(name, readonly=True)
    except Exception as e:
        error_information = {'size': 'unknown',
                             'subject': 'unknown',
                             'exception': str(e),
                             'folder': name,
                             'date': 'unknown',
                             'id': 'unknown'}
        stats['skipped_folders']['no_parent'] += 1
        stats['errors'].append(error_information)
        continue

    mails = source.search()

    if not mails and args.skip_empty_folders:
        continue

    db['source']['folders'][name] = {'flags': flags,
                                     'mails': {},
                                     'size': 0,
                                     'buffer': []}

    #: generating mail buffer
    while mails:
        db['source']['folders'][name]['buffer'].append(mails[:args.buffer_size])

        for mail_id, data in source.fetch(mails[:args.buffer_size], ['RFC822.SIZE', 'ENVELOPE']).items():
            if b'ENVELOPE' not in data:  # Encountered message with no ENVELOPE? Skipping it
                stats['skipped_mails']['no_envelope'] += 1
                continue
            elif data[b'ENVELOPE'].subject:
                subject = decode_mime(data[b'ENVELOPE'].subject)
            else:
                subject = '(no subject)'

            db['source']['folders'][name]['mails'][mail_id] = {'size': data[b'RFC822.SIZE'],
                                                               'subject': subject,
                                                               'msg_id': data[b'ENVELOPE'].message_id}
            db['source']['folders'][name]['size'] += data[b'RFC822.SIZE']
            stats['source_mails'] += 1

            print(colorize('Getting source folders      : Progressing ({} mails): {}'.
                           format(stats['source_mails'], name), clear=True), flush=True, end='')

        del mails[:args.buffer_size]

print(colorize(f'Getting source folders      : {stats["source_mails"]} mails in {len(db["source"]["folders"])} folders '
               f'({beautysized(sum([f["size"] for f in db["source"]["folders"].values()]))}) ', clear=True), end='')
if any((args.source_folder, args.destination_root)):
    print(f'({colorize("filtered by arguments", color="yellow")})', end='')
print()

destination_idle.stop_idle()
source_idle.start_idle()


#: get destination folders
print(colorize('Getting destination folders : loading (this can take a while)', clear=True), flush=True, end='')
logging.info('Getting destination folders (this can take a while)')
for flags, separator, name in destination.list_folders(args.destination_root):

    if not destination_separator:
        destination_separator = separator.decode()

    #: no need to process the source destination mailbox if we skipped the source for it
    if args.source_folder:
        if name not in args.source_folder and name.startswith(wildcards) is False:
            print(colorize('Getting source folders      : Progressing ({} mails) (skipping): {}'.
                           format(stats['source_mails'], name), clear=True), flush=True, end='')
            continue

    db['destination']['folders'][name] = {'flags': flags, 'mails': {}, 'size': 0}

    destination.select_folder(name, readonly=True)
    mails = destination.search()

    fetch_data = ['RFC822.SIZE']
    if args.incremental:
        fetch_data.append('ENVELOPE')

    while mails:
        for mail_id, data in destination.fetch(mails[:args.buffer_size], fetch_data).items():
            db['destination']['folders'][name]['mails'][mail_id] = {'size': data[b'RFC822.SIZE']}
            db['destination']['folders'][name]['size'] += data[b'RFC822.SIZE']

            if args.incremental:
                db['destination']['folders'][name]['mails'][mail_id]['msg_id'] = data[b'ENVELOPE'].message_id

            stats['destination_mails'] += 1
            print(colorize('Getting destination folders : Progressing ({} mails): {}'.
                           format(stats['destination_mails'], name), clear=True), flush=True, end='')
        del mails[:args.buffer_size]


print(colorize('Getting destination folders : {} mails in {} folders ({}) '.
               format(stats['destination_mails'], len(db['destination']['folders']),
                      beautysized(sum([f['size'] for f in db['destination']['folders'].values()]))),
               clear=True), end='')
if any((args.source_folder, args.destination_root)):
    print(f'({colorize("filtered by arguments", color="yellow")})', end='')
print('\n')


#: list mode
if args.list:
    #: list all source folders
    print(colorize('Source:', bold=True))
    for name in db['source']['folders']:
        print(f'{name} ({len(db["source"]["folders"][name]["mails"])} mails, '
              f'{beautysized(db["source"]["folders"][name]["size"])})')

    #: list all destination folders
    print(f'\n{colorize("Destination:", bold=True)}')
    for name in db['destination']['folders']:
        print(f'{name} ({len(db["destination"]["folders"][name]["mails"])} mails, '
              f'{beautysized(db["destination"]["folders"][name]["size"])})')

    print()
    print(colorize('Everything skipped! (list mode)', color='cyan'))

    #: stop idle threads & exit
    source_idle.exit()
    destination_idle.exit()
    exit()


#: redirections
redirections = {}
not_found = []
if args.redirect:
    for redirection in args.redirect:
        try:
            r_source, r_destination = redirection.split(':', 1)

            #: parsing wildcards
            if r_source.endswith('*'):
                wildcard_matches = [f for f in db['source']['folders'] if f.startswith(r_source[:-1])]
                if wildcard_matches:
                    for folder in wildcard_matches:
                        redirections[folder] = r_destination
                else:
                    not_found.append(r_source)
            elif r_source not in db['source']['folders']:
                not_found.append(r_source)

        except ValueError as e:
            print('\n{} Could not parse redirection: "{}"\n'.format(colorize('Error:', color='red', bold=True),
                                                                    imaperror_decode(e), redirection))
            exit()
        else:
            redirections[r_source] = r_destination

source_idle.stop_idle()

if not_found:
    print('\n{} Source folder not found: {}\n'.format(colorize('Error:', color='red', bold=True), ', '.join(not_found)))
    exit()

try:
    for sf_name in sorted(db['source']['folders'], key=lambda x: x.lower()):
        source.select_folder(sf_name, readonly=True)
        df_name = sf_name.replace(source_separator, destination_separator)

        if args.destination_root:
            if args.destination_root_merge is False or \
                    (df_name.startswith(f'{args.destination_root}{destination_separator}') is False
                     and df_name != args.destination_root):
                df_name = f'{args.destination_root}{destination_separator}{df_name}'

        #: link special IMAP folder
        if not args.ignore_folder_flags:
            for sf_flag in db['source']['folders'][sf_name]['flags']:
                if sf_flag in SPECIAL_FOLDER_FLAGS:
                    for name in db['destination']['folders']:
                        if sf_flag in db['destination']['folders'][name]['flags']:
                            df_name = name
                            break

        #: custom links
        if sf_name in redirections:
            df_name = redirections[sf_name]

        if df_name in db['destination']['folders']:
            print('Current folder: {} ({} mails, {}) -> {} ({} mails, {})'.format(
                sf_name, len(db['source']['folders'][sf_name]['mails']),
                beautysized(db['source']['folders'][sf_name]['size']), df_name,
                len(db['destination']['folders'][df_name]['mails']),
                beautysized(db['destination']['folders'][df_name]['size'])))

            stats['skipped_folders']['already_exists'] += 1

        else:
            print('Current folder: {} ({} mails, {}) -> {} (non existing)'.format(
                sf_name, len(db['source']['folders'][sf_name]['mails']),
                beautysized(db['source']['folders'][sf_name]['size']), df_name))

            #: creating non-existing folders
            if not args.dry_run:
                print('Creating...', end='', flush=True)

                if args.skip_empty_folders and not db['source']['folders'][sf_name]['mails']:
                    stats['skipped_folders']['empty'] += 1
                    print('{} \n'.format(colorize('Skipped! (skip-empty-folders mode)', color='cyan')))
                    continue
                else:
                    try:
                        destination.create_folder(df_name)
                        if args.destination_no_subscribe is False:
                            destination.subscribe_folder(df_name)
                        stats['copied_folders'] += 1
                        print(colorize('OK', color='green'))

                    except exceptions.IMAPClientError as e:
                        if 'alreadyexists' in str(e).lower():
                            stats['skipped_folders']['already_exists'] += 1
                            print('{} \n'.format(colorize('Skipped! (already exists)', color='cyan')))
                        else:
                            e = imaperror_decode(e)
                            print('{} {}\n'.format(colorize('Error:', color='red', bold=True), e))
                            if args.abort_on_error:
                                raise KeyboardInterrupt
                            continue
        if args.dry_run:
            continue

        for buffer_counter, buffer in enumerate(db['source']['folders'][sf_name]['buffer']):
            print(colorize('[{:>5.1f}%] Progressing... (loading buffer {}/{})'.format(
                progress, buffer_counter+1, len(db['source']['folders'][sf_name]['buffer'])), clear=True), end='')

            for i, fetch in enumerate(source.fetch(buffer, ['FLAGS', 'RFC822', 'INTERNALDATE']).items()):
                progress = stats['processed'] / stats['source_mails'] * 100
                mail_id, data = fetch

                #: placeholders, so we can still attempt to use them in error reporting
                flags = msg = date = size = subject = "(unknown)"
                msg_id = b"(unknown)"

                try:
                    msg_id = db['source']['folders'][sf_name]['mails'][mail_id]['msg_id']
                    size = db['source']['folders'][sf_name]['mails'][mail_id]['size']
                    subject = db['source']['folders'][sf_name]['mails'][mail_id]['subject']
                    
                    flags = data[b'FLAGS']
                    msg = data[b'RFC822']
                    date = data[b'INTERNALDATE']

                except KeyError as e:
                    try:
                        msg_id_decoded = msg_id.decode()
                    except Exception as sub_exception:
                        msg_id_decoded = f'(decode failure): {sub_exception}'

                    stats['errors'].append({'size': size,
                                            'subject': subject,
                                            'exception': f'{type(e).__name__}: {e}',
                                            'folder': df_name,
                                            'date': date,
                                            'id': msg_id_decoded})
                    print('\n{} {}\n'.format(colorize('Error:', color='red', bold=True), e))
                    continue

                #: copy mail
                print(colorize('[{:>5.1f}%] Progressing... (buffer {}/{}) (mail {}/{}) ({}) ({}): {}'.format(
                    progress, buffer_counter+1, len(db['source']['folders'][sf_name]['buffer']), i+1, len(buffer),
                    beautysized(size), date, subject), clear=True), end='')

                #: skip empty mails / zero sized
                if size == 0:
                    stats['skipped_mails']['zero_size'] += 1
                    stats['processed'] += 1
                    print('\n{} \n'.format(colorize('Skipped! (zero sized)', color='cyan')), end='')

                #: skip too large mails
                elif args.max_mail_size and size > args.max_mail_size:
                    stats['skipped_mails']['max_size'] += 1
                    stats['processed'] += 1
                    print('\n{} \n'.format(colorize('Skipped! (too large)', color='cyan')), end='')

                #: skip mails that already exist
                elif args.incremental and df_name in db['destination']['folders'] and \
                        msg_id in [m['msg_id'] for m in db['destination']['folders'][df_name]['mails'].values()]:
                    stats['skipped_mails']['already_exists'] += 1
                    stats['processed'] += 1

                elif args.dry_run:
                    pass

                else:
                    try:
                        #: workaround for microsoft exchange server
                        if args.max_line_length:
                            if any([len(line) > args.max_line_length for line in msg.split(b'\n')]):
                                stats['skipped_mails']['max_line_length'] += 1
                                print('\n{} \n'.format(colorize('Skipped! (line length)', color='cyan')), end='')
                                continue

                        status = destination.append(df_name, msg, (flag for flag in flags if flag.lower() not in
                                                                   denied_flags), msg_time=date)

                        #: differed IMAP servers have differed return codes
                        success_messages = [b'append completed', b'(success)']
                        if any([msg in status.lower() for msg in success_messages]):
                            stats['copied_mails'] += 1
                        else:
                            raise exceptions.IMAPClientError(f'Unknown success message: {status.decode()}')

                    except exceptions.IMAPClientError as e:
                        e_decoded = imaperror_decode(e)

                        try:
                            msg_id_decoded = msg_id.decode()
                        except Exception as sub_exception:
                            msg_id_decoded = f'(decode failure): {sub_exception}'

                        error_information = {'size': beautysized(size),
                                             'subject': subject,
                                             'exception': f'{type(e).__name__}: {e}',
                                             'folder': df_name,
                                             'date': date,
                                             'id': msg_id_decoded}

                        stats['errors'].append(error_information)
                        print(f'\n{colorize("Error:", color="red", bold=True)} {e}\n')

                        if args.abort_on_error:
                            raise KeyboardInterrupt

                    finally:
                        stats['processed'] += 1

        print(colorize('Folder finished!', clear=True))

        if not args.dry_run:
            print()

except KeyboardInterrupt:
    print('\n\nAbort!\n')
else:
    if args.dry_run:
        print()
    print('Finish!\n')

#: stop idle threads
source_idle.exit()
destination_idle.exit()

#: logout source
try:
    print('Logout source...', end='', flush=True)
    source.logout()
    print(colorize('OK', color='green'))
except exceptions.IMAPClientError as e:
    print(f'ERROR: {imaperror_decode(e)}')

#: logout destination
try:
    print('Logout destination...', end='', flush=True)
    destination.logout()
    print(colorize('OK', color='green'))
except exceptions.IMAPClientError as e:
    print(f'ERROR: {imaperror_decode(e)}')


#: print statistics
print('\n\nCopied {} mails and {} folders in {:.2f}s\n'.format(
    colorize(f'{stats["copied_mails"]}/{stats["source_mails"]}', bold=True),
    colorize(f'{stats["copied_folders"]}/{len(db["source"]["folders"])}', bold=True),
    time()-stats['start_time']))

if args.dry_run:
    print(colorize('Everything skipped! (dry-run)', color='cyan'))
else:
    print(f'Skipped folders     : {sum([stats["skipped_folders"][c] for c in stats["skipped_folders"]])}')
    print(f'├─ Empty            : {stats["skipped_folders"]["empty"]} (skip-empty-folders mode only)')
    print(f'├─ No parent folder : {stats["skipped_folders"]["no_parent"]}')
    print(f'└─ Already exists   : {stats["skipped_folders"]["already_exists"]}')
    print()
    print(f'Skipped mails       : {sum([stats["skipped_mails"][c] for c in stats["skipped_mails"]])}')
    print(f'├─ Zero sized       : {stats["skipped_mails"]["zero_size"]}')
    print(f'├─ To large         : {stats["skipped_mails"]["max_size"]} (max-mail-size mode only)')
    print(f'├─ No envelope      : {stats["skipped_mails"]["no_envelope"]}')
    print(f'├─ Line length      : {stats["skipped_mails"]["max_line_length"]} (max-line-length mode only)')
    print(f'└─ Already exists   : {stats["skipped_mails"]["already_exists"]} (incremental mode only)')

    print(f'\nErrors ({len(stats["errors"])}):')
    if stats['errors']:
        for err in stats['errors']:
            print(f'({err["size"]}) ({err["date"]}) ({err["folder"]}) ({err["id"]}) ({err["subject"]}): '
                  f'{err["exception"]}')
    else:
        print('(no errors)')

