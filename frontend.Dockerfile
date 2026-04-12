FROM nginx:alpine
# Copy your specific nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Copy your frontend files
COPY index.html /usr/share/nginx/html/index.html