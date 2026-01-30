# Build Stage
FROM node:18-alpine as build-stage
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# Ensure env vars are passed at build time if needed, or allow runtime config.
# For Vite, variables must start with VITE_.
# We'll assume VITE_GOOGLE_CLIENT_ID is passed as build arg or we accept it's hardcoded for now.
RUN npm run build

# Production Stage
FROM nginx:stable-alpine as production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html
# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
