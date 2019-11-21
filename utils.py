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
    units = ['B', 'KB', 'MB', 'GB']
    if factor == 1024:
        units = ['B', 'KiB', 'MiB', 'GiB']
    template = '{:.?f} {}'.replace('?', str(precision))
    rv = 0

    if factor > b >= 0:
        rv = '{} {}'.format(b, units[0])
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

    def fallback(mime):
        charset = detect(mime)['encoding']
        return mime_bytes.decode(charset)

    words = []

    try:
        s = mime_bytes.decode()

    except UnicodeDecodeError:
        words.append(fallback(mime_bytes))

    else:
        for word, encoding in decode_header(s):
            try:
                if type(word) is bytes:
                    words.append(word.decode(encoding or 'utf8'))
                else:
                    words.append(word)

            except (UnicodeDecodeError, LookupError):
                words.append(fallback(word))

    return ''.join(words)
