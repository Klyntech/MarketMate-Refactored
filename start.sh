#!/bin/bash
# Start script for MarketMate Website on Render
# Ensures database directory exists and schema is up to date before starting

# Create data directory if it doesn't exist (for SQLite persistence)
mkdir -p ./data

# Push Prisma schema to database (creates/migrates tables)
npx prisma db push --skip-generate 2>/dev/null

# Start the Next.js server
exec npm run start -- -H 0.0.0.0 -p $PORT
