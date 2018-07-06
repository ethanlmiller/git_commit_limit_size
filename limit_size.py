#!/usr/bin/python3
#
# This script is designed to limit the size and number of files of git repositories.
#
# There's a config file (in the same directory, by default, but it can be relocated)
# that determines the limits based on regular expression matching.
#
##################################################################################
#
# (c) Copyright 2018 Ethan L. Miller (elm@ucsc.edu)
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the University of California.
#
##################################################################################

# Need to import this here because log_level depends on it
import logging

# Default values for git location and for limits.  Overridden by config file
git_cmd = '/usr/bin/git'
config_file_name = '/home/gitlab/hooks/pre-receive.d/limit_size.conf'
max_file_size = 5 * 1024 * 1024
max_repo_size = 20 * 1024 * 1024
max_num_files = 400
# Message to print if an error occurs.  This will be printed along with the limits
# that applied to the repository being committed.
contact_info='''==================================================================
If you believe your repo doesn't exceed the limits listed above,
please contact gitlab-admin@ucsc.edu.  If you need help getting
your repo below the limits, please read the documentation
at https://gitlab.soe.ucsc.edu/.  If you're still having difficulty,
please contact your course staff.
=================================================================='''
# Location of log file and default logging level.  INFO is recommended, but
# WARNING would be OK instead.  Only use DEBUG for actual debugging, since
# it logs environment variables, among other things.
log_file = '/var/log/gitlab/gitlab-shell/gitlab-shell.log'
log_level = logging.INFO

#================================================================================
#
# Shouldn't need to customize below this line
#
#================================================================================
import sys, os, re, subprocess
from os.path import basename

logger = logging.getLogger (__name__)

def get_files_info (commit_id):
    '''
    Parameter: commit_id
        The commit ID for which file information is to be retrieved

    Return info about all of the files in a particular commit in the current
    working directory.  Information is returned as as list of
    (filename, size_in_bytes) tuples.

    NOTES:
    With a single git command, we can retrieve info about every single file.
    We could, instead, get a list of changed files and use git cat-file on
    each one, but git cat-file is likely to be faster for multiple modified
    files, and acceptable speed if only a few have changed.
    '''
    size_list = []
    try:
        cmd = subprocess.run ([git_cmd, 'ls-tree', '--long', '-r', commit_id],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cmd.check_returncode ()
        result = cmd.stdout.decode ('utf-8').split('\n')
    except:
        return []
    for l in result:
        try:
            (perms, git_type, blob_id, size, filename) = l.strip().split()
        except:
            continue
        if git_type == 'blob':
            size_list.append ((filename, int(size)))
    return size_list

def get_refs (fh):
    updated_refs = set()
    for line in fh:
        logger.debug (line.strip())
        try:
            (old_ref, new_ref, refname) = line.strip().split()
            if new_ref == '0000000000000000000000000000000000000000':
                # If the new ref is NULL, don't bother checking it
                continue
            elif old_ref == '0000000000000000000000000000000000000000':
                # Check all the way back if the old ref is NULL.
                # This is somewhat slower, but only necessary on the first check
                # (in which case there's not much to check) or if a tag or new
                # branch is created (which is infrequent).
                rev_str = new_ref
            else:
                rev_str = old_ref + '..' + new_ref
            git_rev_list_cmd = [git_cmd, 'rev-list', rev_str]
            cmd = subprocess.run (git_rev_list_cmd,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            cmd.check_returncode ()
            for r in cmd.stdout.decode ('utf8').split():
                updated_refs.add (r)
        except:
            logger.warning (' '.join (git_rev_list_cmd) + ' failed!')
    return updated_refs

def get_int (s):
    '''
    Return an integer value, multiplied by a suffix of Ki, Mi, Gi, K, M, or G.  If there's
    an error in conversion, return 1.  Don't return 0, since that means no limit.
    '''
    # If any substring stuff fails, it's because we might not have enough characters.
    # In that case, we must have a plain integer.
    try:
        if s[-1] == 'B':
            s = s[:-1]
        if len(s) > 2:
            suffix = s[-2:].upper ()
            num = int (s[:-2])
            if   suffix == 'KI':
                return num * 1024
            elif suffix == 'MI':
                return num * 1024 * 1024
            elif suffix == 'GI':
                return num * 1024 * 1024 * 1024
        if len(s) > 1:
            suffix = s[-1:].upper ()
            num = int (s[:-1])        
            if suffix == 'K':
                return num * 1000
            elif suffix == 'M':
                return num * 1000 * 1000
            elif suffix == 'G':
                return num * 1000 * 1000 * 1000
        return int(s)
    except:
        logger.error ("Bad value in config file: {0}".format (s))
        return 1

def read_config (config_file_name, repo_name):
    limits = (max_file_size, max_repo_size, max_num_files)
    try:
        with open (config_file_name) as fh:
            for l in fh.readlines ():
                l = l.strip ()
                # Ignore comments
                if l == '' or l[0] == '#':
                    continue
                # See if the repo matches the regex on the line.  We stop at the first hit we get
                fields = l.split()
                if re.search (fields[0], repo_name):
                    limits = list((get_int(f) for f in fields[1:4]))
                    # print ('Matched line:', l.strip())
                    # print ('Limits:', limits)
                    break
    except:
        pass
    return limits


# From https://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
def sizeof_fmt(num, suffix='B'):
    '''
    '''
    for unit in ('','Ki','Mi','Gi','Ti','Pi','Ei','Zi'):
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

if __name__ == '__main__':
    handler = logging.FileHandler (log_file)
    logger.addHandler (handler)
    handler.setFormatter (logging.Formatter (fmt='{levelname:s}:%s: {message:s}' % (basename (sys.argv[0])), style='{'))
    logger.setLevel (log_level)
    logger.debug ('\n'.join (['{0}={1}'.format (k, os.environ[k]) for k in os.environ.keys()]))
    try:
        raw_repo_path = os.environ['GIT_OBJECT_DIRECTORY']
    except:
        raw_repo_path = os.environ['PWD']

    m = re.search (r'^(.*\.git)', raw_repo_path)
    if m:
        repo_name = m.group(1)
    else:
        print ('SYSTEM ERROR: unable to get repo directory!')
        print ('SYSTEM ERROR: push not successful.  Please retry.')
        logger.error ("Unable to get repo directory!")
        for k in os.environ.keys():
            logger.error ("{0}={1}".format (k, os.environ[k]))
        sys.exit (1)

    logger.info ('Checking {0}'.format (repo_name))
    (max_file_size, max_repo_size, max_num_files) = read_config (config_file_name, repo_name)
    updated_refs = get_refs (sys.stdin)
    # print (updated_refs)
    error_list = []
    file_size_error = False
    repo_size_error = False
    num_files_error = False
    for ref in updated_refs:
        file_sizes = get_files_info (ref)
        total_size = 0
        num_files = 0
        for f, sz in file_sizes:
            if sz > max_file_size > 0:
                file_size_error = True
                error_list.append ('commit {0}: file {1} too large (size={2})'.format (ref[:7], f, sz))
            total_size += sz
            num_files += 1
        if total_size > max_repo_size > 0:
            repo_size_error = True
            error_list.append ('commit {0}: total repo size ({1}) is too large (max size is {2})'.format (ref[:7], total_size, max_repo_size))
        if num_files > max_num_files > 0:
            error_list.append ('commit {0}: too many files ({1}) in repo ((max files is {2})'.format (ref[:7], num_files, max_num_files))
    exit_code = 0
    if len(error_list) > 0:
        exit_code = 1
        print ('\n'.join (['ERROR: ' + msg for msg in error_list]))
        print ('ERROR:')
        print ('ERROR:')
        print ('ERROR: ====> NONE OF YOUR COMMITS WERE PUSHED: your repo exceeds these limits')
        print ('ERROR: Maximum file size: {0}'.format (sizeof_fmt (max_file_size)))
        print ('ERROR: Maximum repository size: {0}'.format (sizeof_fmt (max_repo_size)))
        print ('ERROR: Maximum number of files in repository: {0}'.format (max_num_files))
        print ('ERROR: ====> Please fix these problems and try your push again')
        print ('ERROR:')
        print ('\n'.join (['ERROR: ' + msg for msg in contact_info.split('\n')]))
        for msg in error_list:
            logger.warning (repo_name + ": " + msg)
    sys.exit (exit_code)

