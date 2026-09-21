"""Owning the machine: taking a copy, proving it, putting it back, and checking.

Not a product surface. No route, no screen, nothing a user of the product sees —
these are the four verbs an operator needs on the day the disk fails, and the
one they should run after every deploy.
"""

from .backup import Manifest, Member, create_backup
from .doctor import Check, run_checks
from .restore import restore_backup, verify_backup

__all__ = [
    "Check",
    "Manifest",
    "Member",
    "create_backup",
    "restore_backup",
    "run_checks",
    "verify_backup",
]
