#!/bin/bash
cp ~/.openclaw/openclaw.json ~/homelab-configs/oracle-cloud/openclaw/
cp ~/.openclaw/cron/jobs.json ~/homelab-configs/oracle-cloud/openclaw/cron-jobs.json
cp ~/.openclaw/workspace/scripts/*.py ~/homelab-configs/oracle-cloud/scripts/
cd ~/homelab-configs
git add .
git commit -m "manual sync: $(date '+%Y-%m-%d')"
git push
