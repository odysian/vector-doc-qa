# GCP Backend Deploy SSH Reset Guide

## What Is Broken Right Now

GitHub Actions deploy fails at SSH with:

`Permission denied (publickey)`

This means only one thing: the private key in GitHub Actions secrets does **not** match a public key that the target VM user accepts.

The backend/container/GCS changes are not the cause of this specific failure.

---

## Why This Happened (Current Incident)

We did several valid steps in sequence, but they mixed identities:

1. Deploy previously worked with one SSH user/key combo.
2. We then did storage setup and VM scope updates (unrelated to SSH auth).
3. During recovery, `gcloud compute ssh` created/used a different keypair (`google_compute_engine`) and logged in as user `odys`.
4. We also added/check keys at different times, but not always for the same user/keypair used by GitHub Actions.

Result: GitHub Actions presented a private key that the VM user did not trust.

---

## Root Cause (Plain English)

There is a mismatch across these 3 values:

- GitHub secret `GCP_VM_SSH_KEY` (private key)
- VM `~/.ssh/authorized_keys` entry (public key)
- GitHub secret `GCP_VM_USER` (Linux user)

All three must refer to the same identity.

---

## Clean Reset (Recommended, 10 minutes)

Use a **dedicated deploy key** just for GitHub Actions so personal/gcloud keys do not interfere.

### 1) Local terminal: create dedicated keypair

```bash
ssh-keygen -t ed25519 -f ~/.ssh/gha_quaero -C gha-deploy -N ""
```

### 2) Local terminal: copy public key

```bash
command cat ~/.ssh/gha_quaero.pub
```

Copy the full single-line output.

### 3) Local terminal: open VM shell as current admin user

```bash
gcloud compute ssh quaero-backend --zone us-east1-b --project portfolio-488721
```

### 4) VM shell: add that public key to deploy user (`odys`)

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
cat >> ~/.ssh/authorized_keys <<'EOF'
<PASTE gha_quaero.pub LINE HERE>
EOF
chmod 600 ~/.ssh/authorized_keys
chown -R "$USER:$USER" ~/.ssh
```

### 5) Exit VM, then local terminal: verify SSH with dedicated key

```bash
ssh -i ~/.ssh/gha_quaero -o IdentitiesOnly=yes -o StrictHostKeyChecking=no odys@34.26.82.138 "echo ok"
```

Expected output: `ok`

### 6) GitHub repo secrets: set exact values

- `GCP_VM_USER` = `odys`
- `GCP_VM_HOST` = `34.26.82.138`
- `GCP_VM_SSH_KEY` = contents of `~/.ssh/gha_quaero` (private key, full block)

Get private key safely:

```bash
command cat ~/.ssh/gha_quaero
```

### 7) Re-run backend deploy workflow

If step 5 worked, Actions SSH should work too.

---

## Important Clarification

`gcloud compute ssh` key files (`~/.ssh/google_compute_engine*`) are separate from GitHub Actions deploy key files.  
They can coexist. One does not automatically configure the other.

---

## If It Still Fails

Check these in order:

1. `GCP_VM_USER` exactly matches the Linux account where key was added.
2. `GCP_VM_SSH_KEY` is the private key paired with the exact public key in `authorized_keys`.
3. Local verification command (Step 5) succeeds before rerunning Actions.

If local Step 5 fails, fix that first; Actions will fail the same way.

---

## After SSH Is Fixed (Storage Migration Continuation)

Then continue with:

1. Update `/opt/quaero/env/backend.env`:
   - `STORAGE_BACKEND=gcs`
   - `GCS_BUCKET_NAME=quaero-pdf-storage`
   - `GCP_PROJECT_ID=portfolio-488721`
2. Deploy backend from GitHub Actions.
3. Validate object writes:

```bash
gcloud storage ls gs://quaero-pdf-storage/uploads/
```

