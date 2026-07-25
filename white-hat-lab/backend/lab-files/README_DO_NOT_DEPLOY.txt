SIMULATED OPERATOR NOTE — White Hat Lab training environment
============================================================

This file exists to make a teaching point.

In real breaches, attackers routinely find directories exactly like this one:
left behind after a migration, "hidden" behind an unlinked URL, and protected by
nothing but the hope that nobody guesses the path.

Content discovery tools (gobuster, ffuf, dirsearch) try thousands of common
directory names per minute. "Nobody knows the URL" is not a security control.

Lessons:
  1. Obscurity is not security.
  2. Backups and secrets never belong under the web root.
  3. Every administrative surface needs authentication AND authorization.
  4. Monitor for content-discovery scanning; it is a strong early-warning signal.
