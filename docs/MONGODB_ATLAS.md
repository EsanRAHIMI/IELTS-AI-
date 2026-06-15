# MongoDB Atlas setup

The app uses **MongoDB Atlas** for all persistence. A free **M0** cluster is
enough for personal use.

## Steps

1. Create a free account at <https://www.mongodb.com/cloud/atlas> and create a
   new **M0 (free) cluster**.
2. **Database Access** → *Add New Database User* → create a username/password
   (use a strong password, no special URL characters or URL-encode them).
3. **Network Access** → *Add IP Address* → add your current IP, or
   `0.0.0.0/0` for development (less secure; restrict for production).
4. **Connect → Drivers → Python** → copy the connection string, e.g.

   ```
   mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```

5. Paste it into `api/.env` as `MONGODB_URI`, and set `MONGODB_DB=ielts_ai_mastery`.

## Collections (created automatically)

`users`, `sources`, `vocabulary`, `phrases`, `sentence_patterns`,
`learning_cards`, `review_history`, `daily_plans`, `jobs`.

Indexes are ensured on startup (`api/database.py → init_indexes`): unique email,
`(userId, priorityScore)`, `(userId, status)`, `(userId, lemma)`,
`(userId, nextReviewAt)`, job status, etc.

## Verify the connection

```bash
curl http://localhost:8010/health
# {"status":"ok","db":true,"aiProvider":"openai","aiConfigured":false}
```

If `db` is `false`, re-check the URI, the database user, and Network Access.
