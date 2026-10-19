FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies based on package-lock.json
COPY package*.json ./
RUN npm install

# Copy source code and build Next.js bundle
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Production runner image
FROM node:20-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/package*.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.ts ./

EXPOSE 3000

CMD ["sh", "-c", "npx next start -p ${PORT:-3000} -H 0.0.0.0"]
