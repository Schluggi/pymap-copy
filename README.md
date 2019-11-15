# pymap-copy
In our company we often have to copy mailboxes from one to another server. For this we used 
[IMAPCopy](http://www.ardiehl.de/imapcopy/) as so far. Due to compatibility issues, first of all the missing 
SSL/TLS support i wrote my own python-based version. I hope you like it!

## Features
- Copies folders and subfolders
- Copies mails even with flags (seen, answered, ...)
- Connecting via SSL/TLS (by default)
- Supports incremental copy (copies only new mails/folders)
- User specific redirections (with wildcard support)
- Auto subscribe new folders (by default)
- Auto find the special IMAP folders Drafts, Trash, etc. (by default)  
- Quota checking (by default)
- Over all progress bar
- Uses buffer for max performance
- Workaround for Microsoft Exchange Server's IMAP bug 
- Statistics
- Simple usage
    
## Requirements
- Python >= 3.5 (with pip)

## Installation
1. Clone this repo
2. Install the requirements by running `pip3 install -r requirements.txt` 
3. Start the program:`./pymap-copy.py --help` 

## Simple usage
By running the following command the whole structure (folders & mails) from user1 will be copy to the mailbox of user2. 
```
./pymap-copy \
--source-user=user1 \
--source-server=server1.example.org \
--source-pass=2345678 \
--destination-user=user2 \
--destination-server=server2.example.info \
--destination-pass=abcdef
```
If you just want to look what would happen append `-d`/`--dry-run`.

### Redirections
You want to merge `INBOX.Send Items` with the `INBOX.Send` folder? You can do this with `-r/--redirect`.
The syntax of this argument is simple `source:destination`. For this example you can use `-r "INBOX.Send Items:INBOX.Send"`
to put all mails from the source folder `INBOX.Send Items` the to destination folder `INBOX.Send`. 
Please make sure you use quotation marks if one of the folders includes a special character or space like as in this example.
In addition, the folder names must be case-sensitive with the correct delimiter. Do a dry run (`-d/--dry-run`) to check 
that everything will redirect correctly. 

### Performance optimization
You could change the buffer size with `-b`/`--buffer-size` to increase the download speed from the source. 
If you know the source mailbox has a lot of small mails use a higher size. In the case of lager mails use a lower size 
to counter timeouts. For bad internet connections you also should use a lower sized buffer.

## Microsoft Exchange Server IMAP bug 
If your destination is an Exchange Server (EX) you'll properly get an `bad command` exception while coping some mails. 
This happens because the EX analyse (and in some cases modify) new mails. There is a bug in this lookup process (since EX version 5 -.-) . 
To prevent an exception you can use the argument `--max-line-length 4096`. This will skip all mails with lines more than 4096 characters.

## Credits 
Created and maintained by Schluggi.