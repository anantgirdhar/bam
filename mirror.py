#!/bin/python
from collections import OrderedDict
import datetime
import fnmatch
from glob import glob
from pprint import pprint
import re
import subprocess
import sys
import os


# Mirror

# This script creates a mirror based on the configuration

# WARNING: If a source file is deleted, it will also be deleted from the
# destination.

CFG = 'bamrc'

BASE_RSYNC_CMD = (
        'rsync'
        # + ' --dry-run'
        + ' --archive'
        + ' --partial'
        + ' --compress'
        # + ' --verbose'
        + ' --stats'
        + ' --itemize-changes'
        # + ' --progress'
        + ' --human-readable'
        + ' --delete'
        + ' --delete-delay'
        )

def load_config():
    # Parse config
    SOURCES = OrderedDict()
    PROFILES = OrderedDict()
    #TODO: Implement some kind of error handling at some point
    with open(CFG, 'r') as f:
        for line in f.readlines():
            if line.startswith('#') or line == '':
                continue
            tokens = line.strip().split(' ')
            if 'source' == tokens[0]:
                SOURCES[tokens[1]] = {
                        'path': tokens[2],
                        'exclude': [],
                        'collapse': [],
                        }
            elif 'i' == tokens[0]:
                last_source = list(SOURCES.keys())[-1]
                SOURCES[last_source]['exclude'].append(tokens[1])
            elif 'c' == tokens[0]:
                last_source = list(SOURCES.keys())[-1]
                SOURCES[last_source]['collapse'].append(tokens[1])
            elif tokens[0].startswith('[') and tokens[0].endswith(']'):
                destination = tokens[0][1:-1]
                PROFILES[destination] = {}
            elif '+' == tokens[0]:
                last_dest = list(PROFILES.keys())[-1]
                PROFILES[last_dest][tokens[1]] = last_dest + '/' + tokens[3]
    return SOURCES, PROFILES

def get_collapse_pattern_prefix(pattern, line):
    # Change the pattern to a python regex
    # This will help with prepending the prefix appropriately in the output
    reobj = re.compile(fnmatch.translate(pattern))
    try:
        prefix = reobj.match(line).groups()[0]
        prefix = prefix + r'*'
    except IndexError:
        prefix = pattern
    return prefix

def collapse_output(raw, collapse_patterns):
    processed = []
    previous_collapse_pattern = None
    collapse_pattern_prefix = None
    collapse_pattern_count = 0
    for line in raw:
        for collapse_candidate in collapse_patterns:
            if fnmatch.fnmatchcase(line, collapse_candidate):
                if previous_collapse_pattern is None:
                    previous_collapse_pattern = collapse_candidate
                    collapse_pattern_prefix = get_collapse_pattern_prefix(
                            collapse_candidate,
                            line,
                            )
                    collapse_pattern_count = 1
                elif previous_collapse_pattern == collapse_candidate:
                    collapse_pattern_count += 1
                else:
                    processed.append(f'{collapse_pattern_prefix} ... {collapse_pattern_count} lines collapsed')
                    previous_collapse_pattern = collapse_candidate
                    collapse_pattern_prefix = get_collapse_pattern_prefix(
                            collapse_candidate,
                            line,
                            )
                    collapsed_line_count = 1
                break
        else:
            if previous_collapse_pattern is None:
                processed.append(line)
            else:
                processed.append(f'{collapse_pattern_prefix} ... {collapse_pattern_count} lines collapsed')
                previous_collapse_pattern = None
                collapse_pattern_prefix = None
                collapse_pattern_count = 0
                processed.append(line)
    if previous_collapse_pattern is not None:
        processed.append(f'{collapse_pattern_prefix} ... {collapse_pattern_count} lines collapsed')
        previous_collapse_pattern = None
        collapse_pattern_count = 0
    return processed

def clean_output(output, collapse_patterns):
    changes = []
    deletions = []
    stats = []
    # Extract the changes (until we get to deletions)
    while not (
            output[0].startswith('*deleting   ') or
            output[0] == '' or
            output[0].startswith('Number of files')
            ):
        line = output.pop(0)
        print(line)
        if line == 'sending incremental file list':
            continue
        line = line[len('*deleting   '):]  # remove the rsync chars up front
        changes.append(line)
    # Extract the deletions (separated from the stats by a blank line)
    while not (
            output[0] == '' or
            output[0].startswith('Number of files')
            ):
        line = output.pop(0)
        line = line[len('*deleting   '):]
        deletions.append(line)
    stats = output[:]
    # Collapse the lists
    changes = collapse_output(changes, collapse_patterns)
    deletions = collapse_output(deletions, collapse_patterns)
    return changes, deletions, stats


def run(SOURCES, PROFILES, dryrun=True):
    # Each profile is indexed by a path
    # If the path is valid (the path exists), then run the profile
    if not dryrun and \
            input('Continuing can be devastating. Proceed? [y|N]: ').lower().strip() not in ['y', 'yes']:
        sys.exit(0)
    for out_drive in PROFILES.keys():
        if not os.path.isdir(out_drive):
            continue
        # Check that all the sources exist
        for source in PROFILES[out_drive].keys():
            if len(glob(SOURCES[source]['path'])) == 0:
                raise ValueError(f'Source {SOURCES[source]["path"]} not available.')
        # Now that everything exists, we can do a dry run to make sure that things are working
        outputs = {'changes': [], 'deletions': [], 'stats': []}
        for source, dest in PROFILES[out_drive].items():
            exclude_string = ' --exclude='.join(SOURCES[source]['exclude'])
            # The first item in the exclude list didn't get the flag added
            # before it. Add it in now.
            if exclude_string:
                exclude_string = f'--exclude={exclude_string}'
            if dryrun:
                rsync_cmd = f'{BASE_RSYNC_CMD} --dry-run {exclude_string} {SOURCES[source]["path"]} {dest}'
            else:
                rsync_cmd = f'{BASE_RSYNC_CMD} {exclude_string} {SOURCES[source]["path"]} {dest}'
            print(rsync_cmd)
            cmd_out = os.popen(rsync_cmd).read()
            # Clean and append the outputs
            print(cmd_out.splitlines())
            print(cmd_out.splitlines()[0])
            changes, deletions, stats = clean_output(cmd_out.splitlines(), SOURCES[source]['collapse'])
            outputs['changes'].extend(changes)
            outputs['deletions'].extend(deletions)
            outputs['stats'].extend(stats)
        return outputs

def write_log(changes, deletions, stats, dryrun):
    now = datetime.datetime.now()
    logfile_name = f'log.bam_{now:%y%m%d_%H%M%S}'
    if dryrun:
        logfile_name = f'/tmp/{logfile_name}_DRYRUN'
        f = open(logfile_name, 'w')
    else:
        logfile_name = f'{logfile_name}_LIVE'
        f = open(logfile_name, 'w')
    # if not dryrun:
    #     logfile_name += '_LIVE'
    # else:
    #     logfile_name += '_DRYRUN'
    # with open(logfile_name, 'w') as f:
    f.write('##### CHANGES #####\n')
    f.write('\n'.join(changes))
    f.write('\n\n')
    f.write('##### DELETIONS #####\n')
    f.write('\n'.join(deletions))
    f.write('\n\n')
    f.write('##### STATS INDIVIDUAL #####\n')
    f.write('\n'.join(stats))
    f.close()
    return logfile_name

def run_and_log(sources, profiles, dryrun):
    outputs = run(sources, profiles, dryrun=dryrun)
    changes = outputs['changes']
    deletions = outputs['deletions']
    stats = outputs['stats']
    logfile_name = write_log(changes, deletions, stats, dryrun=dryrun)
    return logfile_name

def main():
    S, P = load_config()
    # Do a dryrun to make sure the user knows what changes are being done
    logfile_name = run_and_log(S, P, dryrun=True)
    # Show the log to the user and confirm
    editor = os.environ.get('EDITOR', 'vim')
    subprocess.call([editor, logfile_name])
    if not input('Ready to proceed? [y|N]: ').lower().strip() in ['y', 'yes']:
        print("Didn't receive confirmation. Aborting.")
        sys.exit(0)
    logfile_name = run_and_log(S, P, dryrun=False)
    print(f'Finished running. Log: {logfile_name}')

if __name__ == "__main__":
    main()
