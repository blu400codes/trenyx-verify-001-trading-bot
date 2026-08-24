# Corrections — found by an outside reviewer after publication (2026-08-24, ~17:00 EDT)

The reviewer ran the checks this README tells a buyer to run. Three failed. All three are
the kind of thing this engagement exists to catch, and they were ours.

1. **The attack plan failed its own hash.** Appendix 1 was appended to the hashed file instead
   of shipped beside it, so `shasum -c` returned FAILED. Fixed: `ATTACK-PLAN.md` is restored
   byte-for-byte to its first-commit content (hash `c5f4bf26…` matches again); the appendix
   lives in `APPENDIX-1.md`. Rule adopted: a hashed document is never edited — additions are
   separate files.
2. **Hand-written times were wrong.** Documents claimed 16:05, 16:45, 17:03 for events whose
   commits are stamped 15:23–15:35 EDT. The in-text times were estimates typed by the
   auditor, not clock reads. They are replaced with commit-anchored times, and the rule
   adopted is: no hand-written timestamps in any artifact — every time is taken from `date`
   or `git log`.
3. **Pre-registration was on the honor system.** All commits sit within 17 minutes on a
   repository the auditor controls, so commit order proves nothing about what was read when.
   Adopted for every future engagement: the attack-plan hash is sent to the client (their
   inbox timestamps it) BEFORE any code is shared; for public samples the hash is anchored
   externally (OpenTimestamps) at the moment of pre-registration. For THIS sample the
   claim rests on the commit order and the auditor's word — stated plainly, not dressed up.

Also: three `.pyc` files were committed (now removed, `.gitignore` added), and **effort**:
this sample's artifacts span 15:18–15:35 EDT of commits plus ~90 minutes of reading and
runs around them — well under a day of agent-assisted work. The priced 3–5-day engagement
covers what a sample skips: scoping with the client, running on their data and environment,
the disclosure → fix → retest cycle, and human review of every finding before it is graded.
