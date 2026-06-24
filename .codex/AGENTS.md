# Codex Draft: /mnt/5.42-opt/kus

Status: `LIVE`.

Role: production KUS dog diet service on Moscow. Amsterdam `/root/kus` is the safer local clone/orchestrator.

Important paths:

- Production path through sshfs: `/mnt/5.42-opt/kus`
- Amsterdam local clone: `/root/kus`
- Secrets: `/mnt/5.42-opt/kus/.env`
- DBs: `bot.db`, `kus.db`, `orders.db`
- Service file noted in audit: `kus/kus-support.service`

Safety rules:

- Prefer changing and testing `/root/kus` first.
- Do not edit production files through sshfs unless explicitly asked.
- Do not restart production services without confirmation.
- Do not touch orders DBs or payment state without confirmation.
- Do not send real client messages.
- Client-facing copy should not sell the product as AI/neural network; use "personal analysis" and "checked by a specialist".
- No diet/report consistency bug fix without a test/invariant that catches it.
- `systemctl` on Amsterdam is not Moscow; verify Moscow service state only with an explicit Moscow command.

Safe checks:

```bash
git -C /mnt/5.42-opt/kus status --short --branch
find /mnt/5.42-opt/kus -maxdepth 2 -type f \( -name '.env' -o -name '*.db' -o -name '*.service' \) -printf '%m %u:%g %p\n'
```
