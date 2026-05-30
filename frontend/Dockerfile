#Dockerfile for frontend
# Use a lightweight angular image to build the Angular app
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build

# Use a lightweight Nginx image to serve the built Angular app
FROM nginx:alpine
COPY --from=build /app/dist/wemakecalls-frontend/browser /usr/share/nginx/html
RUN if [ -f /usr/share/nginx/html/index.csr.html ]; then cp /usr/share/nginx/html/index.csr.html /usr/share/nginx/html/index.html; fi
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

