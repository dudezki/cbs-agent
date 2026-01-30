FROM node:18-alpine as build-stage
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# Set the API URL environment variable for the build
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# production stage
FROM nginx:stable-alpine as production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html
# Copy custom nginx config template
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
# Cloud Run sets PORT environment variable, Nginx needs to listen on it
# The default nginx docker image supports envsubst on templates in /etc/nginx/templates/
# We use that to replace $PORT in the config.

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
