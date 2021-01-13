from chardet import detect
from email.header import decode_header
from ast import literal_eval


def imaperror_decode(e):
    s = str(e)

    if s.startswith(('b"', "b'")):
        return literal_eval(s).decode()
    elif type(e) is bytes:
        return e.decode()
    else:
        return s


def beautysized(b, factor=1000, precision=1):
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    if factor == 1024:
        units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
    template = '{:.?f} {}'.replace('?', str(precision))
    rv = 0

    if factor > b >= 0:
        rv = f'{b} {units[0]}'
    elif b < factor**2:
        rv = template.format(b/factor, units[1])
    elif b < factor**3:
        rv = template.format(b/factor**2, units[2])
    elif b < factor**4:
        rv = template.format(b/factor**3, units[3])
    elif b < factor**5:
        rv = template.format(b/factor**4, units[4])
    elif b < factor**6:
        rv = template.format(b/factor**5, units[5])
    return rv


def decode_mime(mime_bytes):
    words = []

    try:
        #: convert to string for decode_header()
        s = mime_bytes.decode()

    except UnicodeDecodeError:
        #: try to detect encoding
        encoding = detect(mime_bytes)['encoding']

        if encoding:
            return mime_bytes.decode(encoding)
        else:
            #: return raw bytes without the b''
            return repr(mime_bytes)[2:-1]

    else:
        for word, encoding in decode_header(s):
            if type(word) is bytes:
                try:
                    if encoding:
                        if encoding.startswith('dos-'):
                            encoding = 'cp{}'.format(encoding.split('dos-', 1)[1])
                    else:
                        encoding = 'utf8'

                    words.append(word.decode(encoding))

                except (UnicodeDecodeError, LookupError):
                    #: return raw bytes without the b''
                    return repr(mime_bytes)[2:-1]
            else:
                words.append(word)

    return ''.join(words)
