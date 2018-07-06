# git_commit_limit_size

## Overview

This is a Python script for pre-receive hook to limit the commit size for git repositories.  It can set the following
limits:

* Limit the maximum size of any individual file
* Limit the total size of all files being committed
* Limit the number of files being committed

The script is designed as a hook that runs on many repos, for installations such as GitLab.  Limits are set
in a configuration file, using Python 3 regular expressions against which the repository name is matched.
Each line specifies all three limits for a particular regular expression, with 0 for a specific limit meaning
"no limit".  Limits are set by the first line with a matching regular expression.
It is recommended that the last line contain the regular expression `.*`, which matches all repositories.

## Contents

* `limit_size.py`: pre-receive hook to limit the size of files and entire git repostories
* `limit_size.conf`: sample configuration file for `limit_size.py`

## Requirements

There are no requirements for installation beyond Python 3 and git.

## Contributors

* Ethan L. Miller (https://www.soe.ucsc.edu/~elm/)
