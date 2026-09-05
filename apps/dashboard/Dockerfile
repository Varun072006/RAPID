# Multi-stage Dockerfile for Next.js Dashboard
FROM node:20-alpine AS base

# Step 1: Install dependencies
FROM base AS deps
WORKDIR /app
COPY package.json ./
COPY apps/dashboard/package.json apps/dashboard/package-lock.json ./apps/dashboard/
WORKDIR /app/apps/dashboard
RUN npm ci

# Step 2: Build application
FROM base AS builder
WORKDIR /app/apps/dashboard
COPY --from=deps /app/apps/dashboard/node_modules ./node_modules
COPY apps/dashboard ./
ENV NEXT_TELEMETRY_DISABLED 1
RUN npm run build

# Step 3: Production runner
FROM base AS runner
WORKDIR /app/apps/dashboard
ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/apps/dashboard/.next ./.next
COPY --from=builder /app/apps/dashboard/node_modules ./node_modules
COPY --from=builder /app/apps/dashboard/package.json ./package.json

USER nextjs

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["npm", "start"]
