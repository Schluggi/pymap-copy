# pymap-copy
In our company we often have to copy mailboxes from one to another server. For this we used 
[IMAPCopy](http://www.ardiehl.de/imapcopy/) as so far. Due to compatibility issues, first of all the missing 
SSL/TLS support i wrote my own python-based version. I hope you enjoy it!

## Features
- Copies folders and subfolders
- Copies mails even with flags (seen, answered, ...)
- Connecting via SSL/TLS (by default)
- Supports incremental copy (copies only new mails/folders)
- Auto subscribe new folders (by default)  
- Uses buffer for max performance
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

### Performance optimization
You could change the buffer size with `-b`/`--buffer-size` to increase the download speed from the source. 
If you know the source mailbox has a lot of small mails use a higher size. In the case of lager mails use a lower size 
to counter timeouts. For bad internet connections you also should use a lower sized buffer.

## TODO
- [ ] Quota warning if source is bigger than the destination

## Credits 
Created and maintained by Schluggi