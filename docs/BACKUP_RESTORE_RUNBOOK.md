# Backup & Restore Runbook

> Step-by-step instructions for restoring data from a backup. Follow these exactly.

---

## Where Are the Backups?

Your database backups are stored in **Cloudflare R2** (like Amazon S3 but cheaper).

- **What gets backed up:** The entire Neon PostgreSQL database (all projects, pages, keywords, content, clusters, links — everything)
- **How often:** Every 6 hours, automatically
- **How long they're kept:** 30 days, then automatically deleted
- **Backup format:** PostgreSQL dump file (`.sql.gz` compressed)

---

## How to Check That Backups Are Running

1. Go to https://dash.cloudflare.com
2. Sign in to your Cloudflare account
3. Click **R2 Object Storage** in the left sidebar
4. Click the **client-fullfilment-backups** bucket
5. You should see backup files named like `backup-2026-02-14T20-23-52-259Z.sql.gz`
6. Check that the most recent one is less than 6 hours old

If you don't see recent backups, check the Railway backup service logs (see "Troubleshooting" at the bottom).

---

## When Would I Need to Restore?

- Data got accidentally deleted (projects, content, etc.)
- Something corrupted the database
- You need to go back in time to before a mistake happened

---

## Option 1: Use Neon Time Travel (Easiest — last 6 hours only)

If the problem happened **less than 6 hours ago**, Neon can rewind your database automatically.

1. Go to https://console.neon.tech
2. Sign in and click on the project **spring-fog-49733273**
3. Click **Branches** in the left sidebar
4. Click **Create Branch**
5. Name it something like `restore-feb-14`
6. Under **From**, pick a time BEFORE the problem happened
7. Click **Create Branch**
8. This creates a copy of your database from that point in time
9. Check the data on this branch to make sure it looks right
10. If it looks good, update `DATABASE_URL` in Railway to point to this new branch's connection string
11. Redeploy your Railway backend services

---

## Option 2: Restore from R2 Backup (Any time in last 30 days)

If the problem happened **more than 6 hours ago**, or you want to be extra safe, restore from an R2 backup.

### What You Need

- A computer with Terminal (Mac) or Command Prompt (Windows)
- PostgreSQL tools installed (`pg_dump`, `pg_restore`, `psql`)
  - Mac: `brew install libpq` then add to PATH
- Access to Cloudflare R2 dashboard
- Access to Neon dashboard

### Step 1: Download the Backup File

1. Go to https://dash.cloudflare.com
2. Click **R2 Object Storage** in the left sidebar
3. Click the **client-fullfilment-backups** bucket
4. Find the backup from BEFORE the problem happened (look at the dates)
5. Click on the backup file
6. Click **Download**
7. Save it somewhere you can find it (like your Downloads folder)

### Step 2: Create a Fresh Database on Neon

1. Go to https://console.neon.tech
2. Click on your project **spring-fog-49733273**
3. Click **Branches** in the left sidebar
4. Click **Create Branch**
5. Name it `restore-YYYY-MM-DD` (today's date)
6. Under **From**, select **Head (latest)**
7. Click **Create Branch**
8. Click on the new branch and copy its **Connection string**
   - It looks like: `postgresql://neondb_owner:abc123@ep-something.us-east-1.aws.neon.tech/neondb`

### Step 3: Clear the New Branch and Restore

Open Terminal and run these commands one at a time. Replace the parts in `ALL_CAPS` with your actual values.

```bash
# First, set the connection string you copied in Step 2
export RESTORE_URL="postgresql://neondb_owner:YOUR_PASSWORD@ep-YOUR-BRANCH.us-east-1.aws.neon.tech/neondb?sslmode=require"
```

```bash
# Drop all existing tables on the new branch (start fresh)
psql "$RESTORE_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

```bash
# Restore the backup file you downloaded
# Replace the path with wherever you saved the file
pg_restore -v -d "$RESTORE_URL" ~/Downloads/YOUR_BACKUP_FILENAME.sql.gz
```

Wait for it to finish. You might see some warnings — that's normal. Look for errors (lines starting with `pg_restore: error`). A few permission warnings are OK.

### Step 4: Verify the Data

```bash
# Check that tables exist and have data
psql "$RESTORE_URL" -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
```

You should see ~24 tables (projects, crawled_pages, keyword_clusters, etc.).

```bash
# Check project count
psql "$RESTORE_URL" -c "SELECT COUNT(*) FROM projects;"
```

Make sure the number matches what you expect.

### Step 5: Point the App at the Restored Database

1. Go to your Railway dashboard
2. Click on the **backend** service
3. Go to **Variables**
4. Change `DATABASE_URL` to the connection string from Step 2 (the restore branch)
   - **Important:** Remove `?sslmode=require` from the end of the URL
   - The app handles SSL automatically
5. Click **Save**
6. The app will automatically redeploy

### Step 6: Verify Everything Works

1. Go to your app (staging or production URL)
2. Check that projects show up
3. Click into a project — check that pages, keywords, and content are there
4. If everything looks good, you're done!

### Step 7: Update the Backup Service (Important!)

The backup service is still backing up from the OLD database branch. Update it:

1. Go to your Railway backup project
2. Click on the backup service
3. Go to **Variables**
4. Change `BACKUP_DATABASE_URL` to the new branch connection string
5. Save and redeploy

### Step 8: Clean Up the Old Branch

Once you've confirmed everything works (give it a day or two):

1. Go to https://console.neon.tech
2. Click **Branches**
3. Delete the old branch you're no longer using

---

## Quick Reference

| Thing | Where to Find It |
|-------|-------------------|
| **Neon database dashboard** | https://console.neon.tech |
| **Neon project** | `spring-fog-49733273` |
| **Cloudflare R2 backups** | https://dash.cloudflare.com → R2 → `client-fullfilment-backups` |
| **Railway app services** | https://railway.app (your project dashboard) |
| **Railway backup service** | Separate Railway project (postgres-s3-backups template) |
| **Backup schedule** | Every 6 hours |
| **Backup retention** | 30 days |
| **Neon Time Travel window** | 6 hours (free tier) |

---

## Troubleshooting

### "I don't see recent backups in R2"
- Go to Railway, find the backup service, check its **Deployments** → **Logs**
- If it says connection refused: the `BACKUP_DATABASE_URL` might be wrong
- If it says authentication failed: the Neon password may have changed

### "pg_restore gives errors"
- A few warnings about permissions or roles are normal — ignore them
- If it says "connection refused": check that your `RESTORE_URL` is correct
- If it says "authentication failed": check the password in the connection string

### "The app shows an error after restore"
- Check Railway logs for the backend service
- Most likely: `DATABASE_URL` still has `?sslmode=require` at the end — remove it
- Or: the `ENVIRONMENT` variable isn't set to `staging` or `production` (SSL won't activate)

### "I need help"
- Check the Railway backend service logs for error messages
- The Neon dashboard shows connection activity under **Monitoring**
- Database schema migrations: run `alembic upgrade head` if tables are missing columns
