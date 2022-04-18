# Backup and Mirror (bam)

This utility can be used to create backups and mirrors of files. It uses rsync
to transfer files. The main purpose of this is to allow the user to create
profiles mapping source directories to destination directories, thus allowing
the user to be able to just run a very short command.

Note: The backup part of bam hasn't been built yet.

## Dependencies

This tool needs python and rsync. In addition it also needs the following
python libraries:

- collections
- datetime
- fnmatch
- glob
- pprint
- re
- subprocess
- sys
- os

## Usage

1. Setup the config file. It should be called bamrc. A sample file
    (bamrc_sample) has been provided.
2. Run the script (mirror.py)!
3. The script will use rsync to figure out which files have changed and present
   you with the results of the transfer (without making any changes).
4. The changes will open up in an editor (you can set the $EDITOR environment
   variable). Review the changes and provide confirmation to proceed.
5. Sit back and relax and bam, your files will be mirrored!
